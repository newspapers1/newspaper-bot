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

CONFIG_FILE = Path("config.json")
CUSTOM_FILE = Path("custom_list.json")

def load_json(p,d):
    if p.exists():
        try: return json.loads(p.read_text(encoding="utf-8"))
        except: return d
    return d
def save_json(p,d): p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

default_config={"mode":"channel+group","enabled":True}

BASE_PAPERS = [
    {"name": "The Hindu", "lang": "English", "cities": ["Delhi","Chennai","Mumbai","Hyderabad","Kolkata","Bangalore","Patna","Lucknow","Ahmedabad"]},
    {"name": "The Hindu Business Line", "lang": "English", "cities": ["Delhi","Chennai","Mumbai","Hyderabad","Kolkata","Bangalore"]},
    {"name": "Business Line", "lang": "English", "cities": ["Delhi","Chennai","Mumbai"]},
    {"name": "The Indian Express", "lang": "English", "cities": ["Delhi","Mumbai","Pune","Chandigarh","Lucknow"]},
    {"name": "Hindustan Times", "lang": "English", "cities": ["Delhi","Mumbai","Patna","Lucknow","Chandigarh"]},
    {"name": "Times of India", "lang": "English", "cities": ["Delhi","Mumbai","Kolkata","Chennai","Patna","Lucknow","Bangalore","Ahmedabad","Pune"]},
    {"name": "Economic Times", "lang": "English", "cities": ["Delhi","Mumbai","Chennai","Kolkata","Bangalore"]},
    {"name": "Dainik Jagran", "lang": "Hindi", "cities": ["Patna","Delhi","Lucknow","Kanpur","Varanasi","Gorakhpur","Meerut","Agra","Dhanbad","Ranchi","Dehradun","Bareilly"]},
    {"name": "Dainik Bhaskar", "lang": "Hindi", "cities": ["Patna","Bhopal","Jaipur","Raipur","Indore","Delhi","Jodhpur","Bilaspur"]},
    {"name": "Amar Ujala", "lang": "Hindi", "cities": ["Delhi","Lucknow","Kanpur","Meerut","Agra","Dehradun","Bareilly"]},
    {"name": "Hindustan", "lang": "Hindi", "cities": ["Patna","Delhi","Lucknow","Varanasi","Ranchi","Muzaffarpur","Bhagalpur","Gaya"]},
    {"name": "Prabhat Khabar", "lang": "Hindi", "cities": ["Patna","Ranchi","Jamshedpur","Dhanbad","Deoghar"]},
    {"name": "Rajasthan Patrika", "lang": "Hindi", "cities": ["Jaipur","Jodhpur","Udaipur","Kota"]},
]

def get_papers():
    flat=[]
    for p in BASE_PAPERS:
        for c in p["cities"]: flat.append({"name":p["name"],"city":c,"lang":p["lang"]})
    return flat

loop = asyncio.new_event_loop()
def start_loop():
    asyncio.set_event_loop(loop)
    loop.run_forever()
threading.Thread(target=start_loop, daemon=True).start()

application = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb=[
        [InlineKeyboardButton("📰 Select Papers", callback_data="menu_select")],
        [InlineKeyboardButton("📋 My List", callback_data="menu_mylist"), InlineKeyboardButton("⚙️ Mode", callback_data="menu_mode")],
        [InlineKeyboardButton("🇬🇧 English Only", callback_data="lang_English"), InlineKeyboardButton("🇮🇳 Hindi Only", callback_data="lang_Hindi")],
        [InlineKeyboardButton("🌐 All Hindi+English", callback_data="lang_All")],
    ]
    await update.message.reply_text("👋 *Today All News Paper - 2 monthly users*\n\n• /select - Saare papers + cities\n• /mylist - Tumhari list\n• /mode - Bot / Channel / Group / Both\n• Auto post daily 6 AM IST\n\nThe Hindu, Business Line included ✅", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def handle_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    data=q.data
    papers=get_papers()

    if data=="menu_select":
        names=sorted(set([p["name"] for p in papers]))
        kb=[[InlineKeyboardButton(f"📰 {n}", callback_data=f"paper_{n}")] for n in names]
        await q.edit_message_text(f"Select karo - Total {len(names)} papers:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("paper_"):
        pname=data.replace("paper_","",1)
        ctx.user_data["paper"]=pname
        cities=sorted(set([p["city"] for p in papers if p["name"]==pname]))
        kb=[[InlineKeyboardButton(f"📍 {c}", callback_data=f"city_{c}")] for c in cities]
        kb.append([InlineKeyboardButton("🔙 Back", callback_data="menu_select")])
        await q.edit_message_text(f"📰 *{pname}*\nCity select karo:", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("city_"):
        city=data.replace("city_","",1)
        ctx.user_data["city"]=city
        today=datetime.datetime.now(IST).strftime("%d-%m-%Y")
        yesterday=(datetime.datetime.now(IST)-datetime.timedelta(days=1)).strftime("%d-%m-%Y")
        kb=[
            [InlineKeyboardButton(f"📅 Aaj - {today}", callback_data=f"date_{today}")],
            [InlineKeyboardButton(f"📅 Kal - {yesterday}", callback_data=f"date_{yesterday}")],
            [InlineKeyboardButton("✍️ Date Type Karo", callback_data="date_custom")],
        ]
        await q.edit_message_text(f"📰 *{ctx.user_data.get('paper')}* | 📍 {city}\n\nDate select karo:", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("date_"):
        if data=="date_custom":
            await q.edit_message_text("📅 Date is tarah type karo: `25-10-2026`\nNeeche message me likho:", parse_mode=ParseMode.MARKDOWN)
            ctx.user_data["awaiting_date"]=True
            return
        date_str=data.replace("date_","",1)
        paper=ctx.user_data.get("paper"); city=ctx.user_data.get("city")
        custom=load_json(CUSTOM_FILE, [])
        if not any(c["name"]==paper and c["city"]==city for c in custom):
            custom.append({"name":paper,"city":city}); save_json(CUSTOM_FILE, custom)
        await q.edit_message_text(f"✅ *{paper} | {city} | {date_str}*\n\nAaj ka paper ready hai!\n📋 MyList me save ho gaya - 6 AM auto post hoga", parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("lang_"):
        lang=data.replace("lang_","",1)
        if lang=="All": filtered=sorted(set([p["name"] for p in papers]))
        else: filtered=sorted(set([p["name"] for p in papers if p["lang"]==lang]))
        kb=[[InlineKeyboardButton(f"📰 {n}", callback_data=f"paper_{n}")] for n in filtered]
        await q.edit_message_text(f"{lang} Papers ({len(filtered)}):", reply_markup=InlineKeyboardMarkup(kb))

    elif data=="menu_mylist":
        custom=load_json(CUSTOM_FILE, [])
        if not custom: await q.edit_message_text("❌ List khali hai. /select se add karo")
        else:
            txt="📋 *Your List:*\n" + "\n".join([f"• {c['name']} - {c['city']}" for c in custom])
            kb=[[InlineKeyboardButton("🗑️ Clear All", callback_data="clear_all")]]
            await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

    elif data=="menu_mode":
        kb=[[InlineKeyboardButton("🤖 Bot Only", callback_data="mode_bot")],[InlineKeyboardButton("📢 Channel", callback_data="mode_channel")],[InlineKeyboardButton("👥 Group", callback_data="mode_group")],[InlineKeyboardButton("🚀 Channel+Group", callback_data="mode_channel+group")]]
        await q.edit_message_text("Mode select karo:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("mode_"):
        mode=data.replace("mode_","",1); cfg=load_json(CONFIG_FILE, default_config); cfg["mode"]=mode; save_json(CONFIG_FILE, cfg)
        await q.edit_message_text(f"✅ Mode set to *{mode}* - Ab 6 AM isi pe post hoga", parse_mode=ParseMode.MARKDOWN)

    elif data=="clear_all":
        save_json(CUSTOM_FILE, []); await q.edit_message_text("🗑️ All cleared!")

async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data.get("awaiting_date"):
        date_str=update.message.text.strip()
        paper=ctx.user_data.get("paper"); city=ctx.user_data.get("city")
        if paper and city:
            await update.message.reply_text(f"✅ *{paper} | {city} | {date_str}*\nReady! MyList me save ho gaya", parse_mode=ParseMode.MARKDOWN)
            ctx.user_data["awaiting_date"]=False
            custom=load_json(CUSTOM_FILE, [])
            if not any(c["name"]==paper and c["city"]==city for c in custom):
                custom.append({"name":paper,"city":city}); save_json(CUSTOM_FILE, custom)

application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(handle_all))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Bot Live - Full Version"
@flask_app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data=request.get_json(force=True)
        update=Update.de_json(data, application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
    except Exception as e: print(e)
    return "ok"

async def init_bot():
    await application.initialize(); await application.start()
    hostname=os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if hostname:
        url=f"https://{hostname}/webhook"
        await application.bot.delete_webhook(drop_pending_updates=True)
        await application.bot.set_webhook(url=url)
        print(f"Webhook set to {url}")

asyncio.run_coroutine_threadsafe(init_bot(), loop)

def daily_job(): print("6 AM Job - Channel/Group post")
scheduler=BackgroundScheduler(timezone=IST)
scheduler.add_job(daily_job, 'cron', hour=6, minute=0)
scheduler.start()

if __name__ == '__main__':
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
