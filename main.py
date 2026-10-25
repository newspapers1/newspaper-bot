import os, json, asyncio, threading, datetime
from pathlib import Path
from flask import Flask, request
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
from apscheduler.schedulers.background import BackgroundScheduler

BOT_TOKEN = os.getenv("BOT_TOKEN","").strip()
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
BASE_PAPERS=[
    {"name":"The Hindu","lang":"English","cities":["Delhi","Chennai","Mumbai","Patna"]},
    {"name":"The Hindu Business Line","lang":"English","cities":["Delhi","Chennai","Mumbai"]},
    {"name":"Times of India","lang":"English","cities":["Delhi","Mumbai","Patna","Lucknow"]},
    {"name":"Dainik Jagran","lang":"Hindi","cities":["Patna","Delhi","Lucknow","Kanpur","Varanasi"]},
    {"name":"Dainik Bhaskar","lang":"Hindi","cities":["Patna","Bhopal","Jaipur","Delhi"]},
    {"name":"Hindustan","lang":"Hindi","cities":["Patna","Delhi","Lucknow","Ranchi"]},
    {"name":"Prabhat Khabar","lang":"Hindi","cities":["Patna","Ranchi"]},
]

def get_papers():
    flat=[]
    for p in BASE_PAPERS:
        for c in p["cities"]: flat.append({"name":p["name"],"city":c,"lang":p["lang"]})
    return flat

application = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb=[
        [InlineKeyboardButton("📰 Select Papers", callback_data="menu_select")],
        [InlineKeyboardButton("📋 My List", callback_data="menu_mylist"), InlineKeyboardButton("⚙️ Mode", callback_data="menu_mode")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_English"), InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_Hindi")],
    ]
    await update.message.reply_text("👋 *Bot LIVE - No Error Now!*\n\nHindi+English\nThe Hindu + Business Line ✅\nAaj ka paper + Date ✅", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def handle_btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    data=q.data
    papers=get_papers()
    if data=="menu_select":
        names=sorted(set([p["name"] for p in papers]))
        kb=[[InlineKeyboardButton(f"📰 {n}", callback_data=f"paper_{n}")] for n in names]
        await q.edit_message_text("Paper select karo:", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("paper_"):
        pname=data.replace("paper_","",1)
        ctx.user_data["paper"]=pname
        cities=sorted(set([p["city"] for p in papers if p["name"]==pname]))
        kb=[[InlineKeyboardButton(f"📍 {c}", callback_data=f"city_{c}")] for c in cities]
        await q.edit_message_text(f"📰 {pname}\nCity:", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("city_"):
        city=data.replace("city_","",1)
        ctx.user_data["city"]=city
        today=datetime.datetime.now(IST).strftime("%d-%m-%Y")
        kb=[[InlineKeyboardButton(f"📅 Aaj {today}", callback_data=f"date_{today}")]]
        await q.edit_message_text(f"{ctx.user_data.get('paper')} | {city}\nDate:", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("date_"):
        date_str=data.replace("date_","",1)
        paper=ctx.user_data.get("paper"); city=ctx.user_data.get("city")
        custom=load_json(CUSTOM_FILE, [])
        if not any(c["name"]==paper and c["city"]==city for c in custom):
            custom.append({"name":paper,"city":city}); save_json(CUSTOM_FILE, custom)
        await q.edit_message_text(f"✅ *{paper} | {city} | {date_str}*\nReady!", parse_mode=ParseMode.MARKDOWN)
    elif data=="menu_mylist":
        custom=load_json(CUSTOM_FILE, [])
        txt="📋 List:\n"+"\n".join([f"• {c['name']} - {c['city']}" for c in custom]) if custom else "Empty"
        await q.edit_message_text(txt)

application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(handle_btn))

flask_app = Flask(__name__)

@flask_app.route('/')
def home(): return "Bot Live - Webhook Sync Fixed"

# === YEHI FIX HAI - async nahi, sync hai ===
@flask_app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        # Sync me async ko chalao - isse wo 500 error khatam!
        asyncio.run(application.process_update(update))
    except Exception as e:
        print(f"Webhook error: {e}")
    return "ok"

async def init_bot():
    await application.initialize()
    await application.start()
    hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if hostname:
        url = f"https://{hostname}/webhook"
        await application.bot.delete_webhook(drop_pending_updates=True)
        await application.bot.set_webhook(url=url)
        print(f"Webhook FIXED set to {url}")

def run_init(): asyncio.run(init_bot())
threading.Thread(target=run_init, daemon=True).start()

def daily_job(): print("6 AM Job")
scheduler = BackgroundScheduler(timezone=IST)
scheduler.add_job(daily_job, 'cron', hour=6, minute=0)
scheduler.start()

if __name__ == '__main__':
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
