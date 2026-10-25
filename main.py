import os, json, threading, datetime, re, asyncio
from pathlib import Path
from flask import Flask
import pytz
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

BOT_TOKEN = os.getenv("BOT_TOKEN","").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID","").strip()
GROUP_ID = os.getenv("GROUP_ID","").strip()
IST = pytz.timezone('Asia/Kolkata')

CONFIG_FILE = Path("config.json")
CUSTOM_FILE = Path("custom_list.json")
PAPERS_FILE = Path("all_papers.json")

def load_json(path, default):
    if path.exists():
        try: return json.loads(path.read_text(encoding="utf-8"))
        except: return default
    return default
def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

default_config = {"mode": "channel+group", "time": "06:00", "lang_filter": ["English","Hindi"], "enabled": True}

BASE_PAPERS = [
    {"name": "The Hindu", "lang": "English", "cities": ["Delhi","Chennai","Mumbai","Hyderabad","Kolkata","Bangalore","Patna","Lucknow"]},
    {"name": "The Hindu Business Line", "lang": "English", "cities": ["Delhi","Chennai","Mumbai","Hyderabad","Kolkata","Bangalore"]},
    {"name": "Business Line", "lang": "English", "cities": ["Delhi","Chennai","Mumbai"]},
    {"name": "The Indian Express", "lang": "English", "cities": ["Delhi","Mumbai","Pune","Ahmedabad","Chandigarh"]},
    {"name": "Hindustan Times", "lang": "English", "cities": ["Delhi","Mumbai","Patna","Lucknow","Chandigarh"]},
    {"name": "Times of India", "lang": "English", "cities": ["Delhi","Mumbai","Kolkata","Chennai","Patna","Lucknow","Bangalore","Hyderabad"]},
    {"name": "Economic Times", "lang": "English", "cities": ["Delhi","Mumbai","Kolkata","Chennai","Bangalore"]},
    {"name": "Deccan Chronicle", "lang": "English", "cities": ["Hyderabad","Chennai","Bangalore"]},
    {"name": "The Telegraph", "lang": "English", "cities": ["Kolkata","Patna"]},
    {"name": "Dainik Jagran", "lang": "Hindi", "cities": ["Patna","Delhi","Lucknow","Kanpur","Varanasi","Gorakhpur","Meerut","Agra","Bareilly","Dhanbad","Ranchi"]},
    {"name": "Dainik Bhaskar", "lang": "Hindi", "cities": ["Patna","Bhopal","Jaipur","Raipur","Indore","Nagpur","Delhi","Ahmedabad"]},
    {"name": "Amar Ujala", "lang": "Hindi", "cities": ["Delhi","Lucknow","Kanpur","Meerut","Agra","Bareilly","Dehradun","Chandigarh"]},
    {"name": "Hindustan", "lang": "Hindi", "cities": ["Patna","Delhi","Lucknow","Varanasi","Kanpur","Ranchi","Dhanbad"]},
    {"name": "Prabhat Khabar", "lang": "Hindi", "cities": ["Patna","Ranchi","Jamshedpur","Dhanbad","Kolkata"]},
    {"name": "Navbharat Times", "lang": "Hindi", "cities": ["Delhi","Mumbai","Lucknow"]},
]

def build_all_papers():
    flat = []
    for p in BASE_PAPERS:
        for city in p["cities"]:
            flat.append({"name": p["name"], "city": city, "lang": p["lang"]})
    save_json(PAPERS_FILE, flat)
    return flat

def get_papers():
    if PAPERS_FILE.exists():
        try:
            data = load_json(PAPERS_FILE, [])
            if data: return data
        except: pass
    return build_all_papers()

async def send_paper(app, paper, city, date_str, target_mode):
    config = load_json(CONFIG_FILE, default_config)
    mode = target_mode or config.get("mode","bot")
    caption = f"📰 *{paper}* | {city} | {date_str}"
    chat_ids = []
    if mode in ["channel","channel+group"]:
        if CHANNEL_ID: chat_ids.append(CHANNEL_ID)
    if mode in ["group","channel+group"]:
        if GROUP_ID: chat_ids.append(GROUP_ID)
    try:
        text = f"{caption}\n\n✅ Ready - Original website se PDF auto link hoga."
        for cid in chat_ids:
            try: await app.bot.send_message(chat_id=cid, text=text, parse_mode=ParseMode.MARKDOWN)
            except: pass
        return True
    except: return False

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📰 Select Papers", callback_data="menu_select")],
        [InlineKeyboardButton("📋 My List", callback_data="menu_mylist"), InlineKeyboardButton("⚙️ Mode", callback_data="menu_mode")],
        [InlineKeyboardButton("🇬🇧 English Only", callback_data="lang_English"), InlineKeyboardButton("🇮🇳 Hindi Only", callback_data="lang_Hindi")],
        [InlineKeyboardButton("🌐 All Hindi+English", callback_data="lang_All")],
    ]
    await update.message.reply_text("👋 *6 AM Bot Ready - Hindi + English Only*\n\n• /select - Saare papers + cities\n• /mylist - Tumhari list\n• /mode - Bot / Channel / Group / Both\n• Auto post daily 6 AM IST\n\nThe Hindu, Business Line included ✅", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def select_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    papers = get_papers()
    names = sorted(set([p["name"] for p in papers if p["lang"] in ["English","Hindi"]]))
    kb = [[InlineKeyboardButton(f"📰 {n}", callback_data=f"paper_{n}")] for n in names]
    await update.message.reply_text(f"Select karo - Total {len(names)} papers (Hindi+English):", reply_markup=InlineKeyboardMarkup(kb[:30]))

async def mylist_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    custom = load_json(CUSTOM_FILE, [])
    if not custom: await update.message.reply_text("❌ List khali hai. /select se add karo"); return
    txt = "📋 *Your List:*\n" + "\n".join([f"• {c['name']} - {c['city']}" for c in custom])
    kb = [[InlineKeyboardButton("🗑️ Clear All", callback_data="clear_all")]]
    await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def mode_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🤖 Bot Only", callback_data="mode_bot")],[InlineKeyboardButton("📢 Channel Only", callback_data="mode_channel")],[InlineKeyboardButton("👥 Group Only", callback_data="mode_group")],[InlineKeyboardButton("🚀 Channel+Group", callback_data="mode_channel+group")]]
    config = load_json(CONFIG_FILE, default_config)
    await update.message.reply_text(f"Current Mode: *{config['mode']}*\nSelect new:", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def handle_buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); data = q.data; papers = get_papers()
    if data.startswith("paper_"):
        pname = data.replace("paper_",""); cities = sorted(set([p["city"] for p in papers if p["name"]==pname]))
        kb = [[InlineKeyboardButton(f"📍 {c}", callback_data=f"city_{pname}__{c}")] for c in cities]
        kb.append([InlineKeyboardButton("🔙 Back", callback_data="menu_select")])
        await q.edit_message_text(f"📰 *{pname}*\nCity select karo:", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    elif data.startswith("city_"):
        rest = data.split("city_",1)[1]; pname, city = rest.split("__",1)
        custom = load_json(CUSTOM_FILE, []); 
        if not any(c["name"]==pname and c["city"]==city for c in custom):
            custom.append({"name": pname, "city": city}); save_json(CUSTOM_FILE, custom)
        await q.edit_message_text(f"✅ Added: *{pname} - {city}*", parse_mode=ParseMode.MARKDOWN)
    elif data.startswith("lang_"):
        lang = data.replace("lang_",""); 
        if lang=="All": filtered = sorted(set([p["name"] for p in papers]))
        else: filtered = sorted(set([p["name"] for p in papers if p["lang"]==lang]))
        kb = [[InlineKeyboardButton(f"📰 {n}", callback_data=f"paper_{n}")] for n in filtered[:30]]
        await q.edit_message_text(f"{lang} Papers ({len(filtered)}):", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("mode_"):
        mode = data.replace("mode_",""); cfg = load_json(CONFIG_FILE, default_config); cfg["mode"]=mode; save_json(CONFIG_FILE, cfg)
        await q.edit_message_text(f"✅ Mode set to *{mode}*", parse_mode=ParseMode.MARKDOWN)
    elif data=="menu_select":
        names = sorted(set([p["name"] for p in papers])); kb = [[InlineKeyboardButton(f"📰 {n}", callback_data=f"paper_{n}")] for n in names[:30]]
        await q.edit_message_text(f"Select karo - Total {len(names)} papers:", reply_markup=InlineKeyboardMarkup(kb))
    elif data=="clear_all": save_json(CUSTOM_FILE, []); await q.edit_message_text("🗑️ All cleared!")

async def daily_job(app):
    try:
        cfg = load_json(CONFIG_FILE, default_config); custom = load_json(CUSTOM_FILE, [])
        if not custom: custom = [{"name": p["name"], "city": p["cities"][0]} for p in BASE_PAPERS]
        date_str = datetime.datetime.now(IST).strftime("%d-%m-%Y")
        for item in custom:
            try: await send_paper(app, item["name"], item["city"], date_str, cfg["mode"]); await asyncio.sleep(1.2)
            except: continue
    except Exception as e: print(f"Daily job error {e}")

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Bot Live - Hindi+English - 6AM Ready"
def run_flask(): flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def main():
    get_papers()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("select", select_cmd))
    app.add_handler(CommandHandler("mylist", mylist_cmd))
    app.add_handler(CommandHandler("mode", mode_cmd))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    scheduler = AsyncIOScheduler(timezone=IST)
    scheduler.add_job(lambda: asyncio.create_task(daily_job(app)), 'cron', hour=6, minute=0, id="daily_6am")
    scheduler.start()
    print("READY - Hindi+English - 6 AM Auto - Channel+Bot+Group Modes")
    threading.Thread(target=run_flask, daemon=True).start()
    async def on_startup(app_):
        try: await app_.bot.delete_webhook(drop_pending_updates=True); print("Webhook deleted - No Conflict")
        except: pass
    app.post_init = on_startup
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__': main()
