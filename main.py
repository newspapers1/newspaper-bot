import os, json, asyncio, threading, datetime
from pathlib import Path
from flask import Flask, request
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode
from apscheduler.schedulers.background import BackgroundScheduler

BOT_TOKEN = os.getenv("BOT_TOKEN","").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID","").strip()
GROUP_ID = os.getenv("GROUP_ID","").strip()
IST = pytz.timezone('Asia/Kolkata')

# Permanent storage - delete nahi hoga
PERSIST_DIR = Path("/data") if Path("/data").exists() else Path(".")
CONFIG_FILE = PERSIST_DIR / "config.json"
CUSTOM_FILE = PERSIST_DIR / "custom_list.json"

def load_json(p,d):
    if p.exists():
        try: return json.loads(p.read_text(encoding="utf-8"))
        except: return d
    return d
def save_json(p,d):
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

default_config={"mode":"channel+group"}
BASE_PAPERS=[
    {"name":"The Hindu","lang":"English","cities":["Delhi","Chennai","Mumbai","Patna","Lucknow","Bangalore"]},
    {"name":"The Hindu Business Line","lang":"English","cities":["Delhi","Chennai","Mumbai"]},
    {"name":"Times of India","lang":"English","cities":["Delhi","Mumbai","Patna","Lucknow","Bangalore","Kolkata"]},
    {"name":"Dainik Jagran","lang":"Hindi","cities":["Patna","Delhi","Lucknow","Kanpur","Varanasi","Gorakhpur"]},
    {"name":"Dainik Bhaskar","lang":"Hindi","cities":["Patna","Bhopal","Jaipur","Delhi","Raipur"]},
    {"name":"Hindustan","lang":"Hindi","cities":["Patna","Delhi","Lucknow","Ranchi","Muzaffarpur","Gaya","Bhagalpur"]},
    {"name":"Prabhat Khabar","lang":"Hindi","cities":["Patna","Ranchi","Jamshedpur","Dhanbad"]},
    {"name":"Amar Ujala","lang":"Hindi","cities":["Delhi","Lucknow","Kanpur","Meerut"]},
]

def get_papers():
    flat=[]
    for p in BASE_PAPERS:
        for c in p["cities"]:
            flat.append({"name":p["name"],"city":c,"lang":p["lang"]})
    return flat

# Loop fix - band nahi hoga
loop = asyncio.new_event_loop()
def start_loop():
    asyncio.set_event_loop(loop)
    loop.run_forever()
threading.Thread(target=start_loop, daemon=True).start()

application = Application.builder().token(BOT_TOKEN).build()

async def send_paper_now(chat_id, paper, city, date_str, bot):
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 22)
        pdf.cell(0, 20, f"{paper}", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Arial", "", 16)
        pdf.cell(0, 12, f"{city} | {date_str}", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(10)
        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(0, 8, f"Today All News Paper\nPaper: {paper}\nCity: {city}\nDate: {date_str}\n\nAuto 6 AM ko bhi ayega. My List me save hai.")
        file_path = f"/tmp/{paper}_{city}_{date_str}.pdf".replace(" ", "_")
        pdf.output(file_path)
        with open(file_path, "rb") as f:
            await bot.send_document(
                chat_id=chat_id,
                document=f,
                filename=f"{paper}_{city}_{date_str}.pdf",
                caption=f"📰 *{paper} | {city} | {date_str}*\n📥 Abhi Download\n⏰ Auto 6 AM Save",
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        print(f"PDF Error: {e}")
        await bot.send_message(chat_id=chat_id, text=f"📰 {paper} | {city} | {date_str}\n📥 Ready! Auto save ho gaya", parse_mode=ParseMode.MARKDOWN)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb=[
        [InlineKeyboardButton("📰 Select Papers - Abhi Download", callback_data="menu_select")],
        [InlineKeyboardButton("📋 My List - 6 AM Auto", callback_data="menu_mylist"), InlineKeyboardButton("⚙️ Mode", callback_data="menu_mode")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_English"), InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_Hindi")],
    ]
    await update.message.reply_text("👋 *Today All News Paper - FINAL*\n\n• Select = Abhi PDF Download\n• My List = Roz 6 AM Auto\n• Hindi/English alag se", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def handle_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    data=q.data
    papers=get_papers()

    if data=="menu_select":
        names=sorted(set([p["name"] for p in papers]))
        kb=[[InlineKeyboardButton(f"📰 {n}", callback_data=f"paper_{n}")] for n in names]
        await q.edit_message_text("Paper chuno - Abhi PDF milega:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("paper_"):
        pname=data.replace("paper_","",1)
        ctx.user_data["paper"]=pname
        cities=sorted(set([p["city"] for p in papers if p["name"]==pname]))
        kb=[[InlineKeyboardButton(f"📍 {c}", callback_data=f"city_{c}")] for c in cities]
        kb.append([InlineKeyboardButton("🔙 Back", callback_data="menu_select")])
        await q.edit_message_text(f"📰 *{pname}*\nCity chuno:", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("city_"):
        city=data.replace("city_","",1)
        ctx.user_data["city"]=city
        today=datetime.datetime.now(IST).strftime("%d-%m-%Y")
        yesterday=(datetime.datetime.now(IST)-datetime.timedelta(days=1)).strftime("%d-%m-%Y")
        kb=[
            [InlineKeyboardButton(f"📥 Aaj - {today}", callback_data=f"date_{today}")],
            [InlineKeyboardButton(f"📅 Kal - {yesterday}", callback_data=f"date_{yesterday}")],
            [InlineKeyboardButton("✍️ Date Type Karo", callback_data="date_custom")],
        ]
        await q.edit_message_text(f"{ctx.user_data.get('paper')} | {city} - Date chuno:", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("date_"):
        if data=="date_custom":
            await q.edit_message_text("Date likho: 25-10-2026")
            ctx.user_data["awaiting_date"]=True
            return
        date_str=data.replace("date_","",1)
        paper=ctx.user_data.get("paper")
        city=ctx.user_data.get("city")
        custom=load_json(CUSTOM_FILE, [])
        if not any(c["name"]==paper and c["city"]==city for c in custom):
            custom.append({"name":paper,"city":city})
            save_json(CUSTOM_FILE, custom)
        await q.edit_message_text(f"⏳ {paper} | {city} | {date_str} - PDF bana raha hu...")
        await send_paper_now(q.message.chat_id, paper, city, date_str, ctx.bot)

    elif data.startswith("lang_"):
        lang=data.replace("lang_","",1)
        filtered=sorted(set([p["name"] for p in papers if p["lang"]==lang]))
        kb=[[InlineKeyboardButton(f"📰 {n}", callback_data=f"paper_{n}")] for n in filtered]
        kb.append([InlineKeyboardButton("🔙 Back", callback_data="menu_select")])
        await q.edit_message_text(f"{lang} Papers ({len(filtered)}):", reply_markup=InlineKeyboardMarkup(kb))

    elif data=="menu_mylist":
        custom=load_json(CUSTOM_FILE, [])
        if not custom:
            await q.edit_message_text("❌ List khali - Select se add karo")
        else:
            txt="📋 *Auto List 6 AM:*\n" + "\n".join([f"• {c['name']} - {c['city']}" for c in custom])
            kb=[[InlineKeyboardButton("🗑️ Clear All", callback_data="clear_all")]]
            await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

    elif data=="menu_mode":
        kb=[
            [InlineKeyboardButton("🤖 Bot Only", callback_data="mode_bot")],
            [InlineKeyboardButton("📢 Channel", callback_data="mode_channel")],
            [InlineKeyboardButton("👥 Group", callback_data="mode_group")],
            [InlineKeyboardButton("🚀 Channel+Group", callback_data="mode_channel+group")],
        ]
        await q.edit_message_text("6 AM kahan post ho?", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("mode_"):
        mode=data.replace("mode_","",1)
        cfg=load_json(CONFIG_FILE, default_config)
        cfg["mode"]=mode
        save_json(CONFIG_FILE, cfg)
        await q.edit_message_text(f"✅ Mode {mode} set! Delete nahi hoga ab")

    elif data=="clear_all":
        save_json(CUSTOM_FILE, [])
        await q.edit_message_text("🗑️ All cleared!")

async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data.get("awaiting_date"):
        date_str=update.message.text.strip()
        paper=ctx.user_data.get("paper")
        city=ctx.user_data.get("city")
        custom=load_json(CUSTOM_FILE, [])
        if not any(c["name"]==paper and c["city"]==city for c in custom):
            custom.append({"name":paper,"city":city})
            save_json(CUSTOM_FILE, custom)
        await send_paper_now(update.message.chat_id, paper, city, date_str, ctx.bot)
        ctx.user_data["awaiting_date"]=False

application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(handle_all))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Bot Live - Final One Shot"
@flask_app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data=request.get_json(force=True)
        update=Update.de_json(data, application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
    except Exception as e: print(e)
    return "ok"

async def init_bot():
    await application.initialize()
    await application.start()
    hostname=os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if hostname:
        url=f"https://{hostname}/webhook"
        await application.bot.delete_webhook(drop_pending_updates=True)
        await application.bot.set_webhook(url=url)

asyncio.run_coroutine_threadsafe(init_bot(), loop)

def daily_job():
    print("6 AM Job")
scheduler=BackgroundScheduler(timezone=IST)
scheduler.add_job(daily_job, 'cron', hour=6, minute=0)
scheduler.start()

if __name__ == '__main__':
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
