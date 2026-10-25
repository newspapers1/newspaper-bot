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

default_config={"mode":"channel+group"}

BASE_PAPERS = [
    {"name": "The Hindu", "lang": "English", "cities": ["Delhi","Chennai","Mumbai","Patna","Lucknow"]},
    {"name": "The Hindu Business Line", "lang": "English", "cities": ["Delhi","Chennai","Mumbai"]},
    {"name": "Times of India", "lang": "English", "cities": ["Delhi","Mumbai","Patna","Lucknow","Bangalore"]},
    {"name": "Dainik Jagran", "lang": "Hindi", "cities": ["Patna","Delhi","Lucknow","Kanpur","Varanasi","Gorakhpur"]},
    {"name": "Dainik Bhaskar", "lang": "Hindi", "cities": ["Patna","Bhopal","Jaipur","Delhi","Raipur"]},
    {"name": "Amar Ujala", "lang": "Hindi", "cities": ["Delhi","Lucknow","Kanpur","Meerut"]},
    {"name": "Hindustan", "lang": "Hindi", "cities": ["Patna","Delhi","Lucknow","Ranchi","Muzaffarpur","Gaya"]},
    {"name": "Prabhat Khabar", "lang": "Hindi", "cities": ["Patna","Ranchi","Jamshedpur","Dhanbad"]},
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

async def send_paper_now(chat_id, paper, city, date_str, bot):
    # Yahan aapka real PDF send hoga - Abhi ke liye message + auto channel post
    text = f"📰 *{paper} | {city} | {date_str}*\n\n📥 *Abhi ka Paper Ready!*\n\n✅ Channel/Group me bhej diya gaya hai\n⏰ Auto List me bhi save ho gaya"
    await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
    # Auto Channel/Group me bhi bhejo
    try:
        cfg=load_json(CONFIG_FILE, default_config)
        if CHANNEL_ID and cfg["mode"] in ["channel","channel+group"]:
            await bot.send_message(chat_id=CHANNEL_ID, text=f"📰 {paper} | {city} | {date_str}\nAaj ka paper", parse_mode=ParseMode.MARKDOWN)
        if GROUP_ID and cfg["mode"] in ["group","channel+group"]:
            await bot.send_message(chat_id=GROUP_ID, text=f"📰 {paper} | {city} | {date_str}\nAaj ka paper", parse_mode=ParseMode.MARKDOWN)
    except: pass

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb=[
        [InlineKeyboardButton("📰 Select Papers", callback_data="menu_select")],
        [InlineKeyboardButton("📋 My List", callback_data="menu_mylist"), InlineKeyboardButton("⚙️ Mode", callback_data="menu_mode")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_English"), InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_Hindi")],
    ]
    await update.message.reply_text("👋 *Today All News Paper*\n\n📰 Select Papers = Abhi Download + Auto Save\n📋 My List = Jo 6 AM auto post honge\n⚙️ Mode = Kahan post hoga", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def handle_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    data=q.data
    papers=get_papers()

    if data=="menu_select":
        names=sorted(set([p["name"] for p in papers]))
        kb=[[InlineKeyboardButton(f"📰 {n}", callback_data=f"paper_{n}")] for n in names]
        await q.edit_message_text(f"Paper chuno - Abhi + Auto dono milega:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("paper_"):
        pname=data.replace("paper_","",1)
        ctx.user_data["paper"]=pname
        cities=sorted(set([p["city"] for p in papers if p["name"]==pname]))
        kb=[[InlineKeyboardButton(f"📍 {c}", callback_data=f"city_{c}")] for c in cities]
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
        await q.edit_message_text(f"📰 *{ctx.user_data.get('paper')}* | 📍 {city}\nDate chuno:", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("date_"):
        if data=="date_custom":
            await q.edit_message_text("Date likho jaise `25-10-2026`", parse_mode=ParseMode.MARKDOWN)
            ctx.user_data["awaiting_date"]=True
            return
        date_str=data.replace("date_","",1)
        paper=ctx.user_data.get("paper"); city=ctx.user_data.get("city")
        # Auto save
        custom=load_json(CUSTOM_FILE, [])
        if not any(c["name"]==paper and c["city"]==city for c in custom):
            custom.append({"name":paper,"city":city}); save_json(CUSTOM_FILE, custom)
        # Abhi download bhi
        await send_paper_now(q.message.chat_id, paper, city, date_str, ctx.bot)
        await q.edit_message_text(f"✅ *{paper} | {city} | {date_str}*\n\n📥 Abhi bhej diya!\n⏰ Auto List me save ho gaya - 6 AM ko bhi ayega", parse_mode=ParseMode.MARKDOWN)

    elif data=="menu_mylist":
        custom=load_json(CUSTOM_FILE, [])
        if not custom: await q.edit_message_text("❌ List khali hai")
        else:
            txt="📋 *Your Auto List (6 AM):*\n" + "\n".join([f"• {c['name']} - {c['city']}" for c in custom])
            kb=[[InlineKeyboardButton("🗑️ Clear All", callback_data="clear_all")]]
            await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

    elif data=="menu_mode":
        kb=[[InlineKeyboardButton("🤖 Bot Only", callback_data="mode_bot")],[InlineKeyboardButton("📢 Channel", callback_data="mode_channel")],[InlineKeyboardButton("👥 Group", callback_data="mode_group")],[InlineKeyboardButton("🚀 Channel+Group", callback_data="mode_channel+group")]]
        await q.edit_message_text("Kahan post karna hai 6 AM?", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("mode_"):
        mode=data.replace("mode_","",1); cfg=load_json(CONFIG_FILE, default_config); cfg["mode"]=mode; save_json(CONFIG_FILE, cfg)
        await q.edit_message_text(f"✅ Mode *{mode}* set! Ab {mode} pe auto ayega", parse_mode=ParseMode.MARKDOWN)

    elif data=="clear_all":
        save_json(CUSTOM_FILE, []); await q.edit_message_text("🗑️ Auto list clear!")

async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data.get("awaiting_date"):
        date_str=update.message.text.strip()
        paper=ctx.user_data.get("paper"); city=ctx.user_data.get("city")
        custom=load_json(CUSTOM_FILE, [])
        if not any(c["name"]==paper and c["city"]==city for c in custom):
            custom.append({"name":paper,"city":city}); save_json(CUSTOM_FILE, custom)
        await send_paper_now(update.message.chat_id, paper, city, date_str, ctx.bot)
        ctx.user_data["awaiting_date"]=False

application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(handle_all))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Bot Live - Abhi + Auto Both"
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

def daily_job():
    async def job():
        custom=load_json(CUSTOM_FILE, [])
        cfg=load_json(CONFIG_FILE, default_config)
        date_str=datetime.datetime.now(IST).strftime("%d-%m-%Y")
        for item in custom:
            try:
                if CHANNEL_ID and cfg["mode"] in ["channel","channel+group"]:
                    await application.bot.send_message(chat_id=CHANNEL_ID, text=f"📰 {item['name']} | {item['city']} | {date_str}\nAuto 6 AM Post", parse_mode=ParseMode.MARKDOWN)
                if GROUP_ID and cfg["mode"] in ["group","channel+group"]:
                    await application.bot.send_message(chat_id=GROUP_ID, text=f"📰 {item['name']} | {item['city']} | {date_str}\nAuto 6 AM Post", parse_mode=ParseMode.MARKDOWN)
                await asyncio.sleep(1)
            except: continue
    asyncio.run_coroutine_threadsafe(job(), loop)

scheduler=BackgroundScheduler(timezone=IST)
scheduler.add_job(daily_job, 'cron', hour=6, minute=0)
scheduler.start()

if __name__ == '__main__':
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
