import os, json, threading, datetime, asyncio
from pathlib import Path
from flask import Flask
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

BOT_TOKEN = os.getenv("BOT_TOKEN","").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID","").strip()
GROUP_ID = os.getenv("GROUP_ID","").strip()
IST = pytz.timezone('Asia/Kolkata')

CONFIG_FILE = Path("config.json")
CUSTOM_FILE = Path("custom_list.json")

def load_json(path, default):
    if path.exists():
        try: return json.loads(path.read_text(encoding="utf-8"))
        except: return default
    return default
def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

default_config = {"mode": "channel+group", "enabled": True}

BASE_PAPERS = [
    {"name": "The Hindu", "lang": "English", "cities": ["Delhi","Chennai","Mumbai","Hyderabad","Kolkata","Bangalore","Patna","Lucknow"]},
    {"name": "The Hindu Business Line", "lang": "English", "cities": ["Delhi","Chennai","Mumbai","Hyderabad","Kolkata","Bangalore"]},
    {"name": "Business Line", "lang": "English", "cities": ["Delhi","Chennai","Mumbai"]},
    {"name": "The Indian Express", "lang": "English", "cities": ["Delhi","Mumbai","Pune"]},
    {"name": "Hindustan Times", "lang": "English", "cities": ["Delhi","Mumbai","Patna","Lucknow"]},
    {"name": "Times of India", "lang": "English", "cities": ["Delhi","Mumbai","Kolkata","Chennai","Patna","Lucknow","Bangalore"]},
    {"name": "Dainik Jagran", "lang": "Hindi", "cities": ["Patna","Delhi","Lucknow","Kanpur","Varanasi","Gorakhpur","Meerut","Agra","Dhanbad","Ranchi"]},
    {"name": "Dainik Bhaskar", "lang": "Hindi", "cities": ["Patna","Bhopal","Jaipur","Raipur","Indore","Delhi"]},
    {"name": "Amar Ujala", "lang": "Hindi", "cities": ["Delhi","Lucknow","Kanpur","Meerut","Agra","Dehradun"]},
    {"name": "Hindustan", "lang": "Hindi", "cities": ["Patna","Delhi","Lucknow","Varanasi","Ranchi"]},
    {"name": "Prabhat Khabar", "lang": "Hindi", "cities": ["Patna","Ranchi","Jamshedpur","Dhanbad"]},
]

def get_papers():
    flat = []
    for p in BASE_PAPERS:
        for city in p["cities"]:
            flat.append({"name": p["name"], "city": city, "lang": p["lang"]})
    return flat

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📰 Select Papers", callback_data="menu_select")],
        [InlineKeyboardButton("📋 My List", callback_data="menu_mylist"), InlineKeyboardButton("⚙️ Mode", callback_data="menu_mode")],
        [InlineKeyboardButton("🇬🇧 English Only", callback_data="lang_English"), InlineKeyboardButton("🇮🇳 Hindi Only", callback_data="lang_Hindi")],
        [InlineKeyboardButton("🌐 All Hindi+English", callback_data="lang_All")],
    ]
    await update.message.reply_text("👋 *6 AM Bot Ready - Hindi + English Only*\n\n• /select - Saare papers + cities\n• /mylist - Tumhari list\n• /mode - Bot / Channel / Group / Both\n• Auto post daily 6 AM IST\n\nThe Hindu, Business Line included ✅", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def handle_all_buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        q = update.callback_query
        await q.answer()
        data = q.data
        papers = get_papers()
        print(f"Button clicked: {data}")

        if data == "menu_select":
            names = sorted(set([p["name"] for p in papers]))
            kb = [[InlineKeyboardButton(f"📰 {n}", callback_data=f"paper_{n}")] for n in names]
            await q.edit_message_text(f"Select karo - Total {len(names)} papers:", reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith("paper_"):
            pname = data.replace("paper_", "", 1)
            ctx.user_data["paper"] = pname
            cities = sorted(set([p["city"] for p in papers if p["name"]==pname]))
            kb = [[InlineKeyboardButton(f"📍 {c}", callback_data=f"city_{c}")] for c in cities]
            kb.append([InlineKeyboardButton("🔙 Back", callback_data="menu_select")])
            await q.edit_message_text(f"📰 *{pname}*\nCity select karo:", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

        elif data.startswith("city_"):
            city = data.replace("city_", "", 1)
            ctx.user_data["city"] = city
            today = datetime.datetime.now(IST).strftime("%d-%m-%Y")
            yesterday = (datetime.datetime.now(IST)-datetime.timedelta(days=1)).strftime("%d-%m-%Y")
            kb = [
                [InlineKeyboardButton(f"📅 Aaj - {today}", callback_data=f"date_{today}")],
                [InlineKeyboardButton(f"📅 Kal - {yesterday}", callback_data=f"date_{yesterday}")],
                [InlineKeyboardButton("✍️ Date Type Karo", callback_data="date_custom")],
            ]
            await q.edit_message_text(f"📰 *{ctx.user_data.get('paper')}* | 📍 {city}\n\nDate select karo:", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

        elif data.startswith("date_"):
            if data == "date_custom":
                await q.edit_message_text("📅 Date is tarah type karo: `25-10-2026`", parse_mode=ParseMode.MARKDOWN)
                ctx.user_data["awaiting_date"] = True
                return
            date_str = data.replace("date_", "", 1)
            paper = ctx.user_data.get("paper")
            city = ctx.user_data.get("city")
            custom = load_json(CUSTOM_FILE, [])
            if not any(c["name"]==paper and c["city"]==city for c in custom):
                custom.append({"name": paper, "city": city})
                save_json(CUSTOM_FILE, custom)
            # FIXED - Ab CallbackQuery error nahi ayega
            await ctx.application.bot.send_message(chat_id=q.message.chat_id, text=f"📰 *{paper}* | {city} | {date_str}\n📅 Aaj ka paper ready hai!\n\n✅ MyList me save ho gaya - 6 AM auto post hoga\n/mode se Channel/Group set karo", parse_mode=ParseMode.MARKDOWN)

        elif data.startswith("lang_"):
            lang = data.replace("lang_", "", 1)
            if lang == "All": filtered = sorted(set([p["name"] for p in papers]))
            else: filtered = sorted(set([p["name"] for p in papers if p["lang"]==lang]))
            kb = [[InlineKeyboardButton(f"📰 {n}", callback_data=f"paper_{n}")] for n in filtered]
            await q.edit_message_text(f"{lang} Papers ({len(filtered)}):", reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith("mode_"):
            mode = data.replace("mode_", "", 1)
            cfg = load_json(CONFIG_FILE, default_config); cfg["mode"]=mode; save_json(CONFIG_FILE, cfg)
            await q.edit_message_text(f"✅ Mode set to *{mode}*", parse_mode=ParseMode.MARKDOWN)

        elif data == "menu_mylist":
            custom = load_json(CUSTOM_FILE, [])
            if not custom: await q.edit_message_text("❌ List khali hai.")
            else:
                txt = "📋 *Your List:*\n" + "\n".join([f"• {c['name']} - {c['city']}" for c in custom])
                kb = [[InlineKeyboardButton("🗑️ Clear All", callback_data="clear_all")]]
                await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

        elif data == "menu_mode":
            kb = [[InlineKeyboardButton("🤖 Bot Only", callback_data="mode_bot")],[InlineKeyboardButton("📢 Channel", callback_data="mode_channel")],[InlineKeyboardButton("👥 Group", callback_data="mode_group")],[InlineKeyboardButton("🚀 Channel+Group", callback_data="mode_channel+group")]]
            await q.edit_message_text("Mode select karo:", reply_markup=InlineKeyboardMarkup(kb))

        elif data == "clear_all":
            save_json(CUSTOM_FILE, []); await q.edit_message_text("🗑️ All cleared!")

    except Exception as e:
        print(f"Handler error {e}")

async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data.get("awaiting_date"):
        date_str = update.message.text.strip()
        paper = ctx.user_data.get("paper"); city = ctx.user_data.get("city")
        if paper and city:
            await ctx.application.bot.send_message(chat_id=update.message.chat_id, text=f"📰 *{paper}* | {city} | {date_str}\nDownload ho raha hai...", parse_mode=ParseMode.MARKDOWN)
            ctx.user_data["awaiting_date"] = False

async def daily_job(app):
    try:
        cfg = load_json(CONFIG_FILE, default_config)
        custom = load_json(CUSTOM_FILE, [])
        date_str = datetime.datetime.now(IST).strftime("%d-%m-%Y")
        for item in custom[:5]:
            try:
                chat_ids = []
                if cfg["mode"] in ["channel","channel+group"] and CHANNEL_ID: chat_ids.append(CHANNEL_ID)
                if cfg["mode"] in ["group","channel+group"] and GROUP_ID: chat_ids.append(GROUP_ID)
                for cid in chat_ids:
                    await app.bot.send_message(chat_id=cid, text=f"📰 {item['name']} | {item['city']} | {date_str}", parse_mode=ParseMode.MARKDOWN)
                await asyncio.sleep(1)
            except: continue
    except Exception as e: print(e)

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Bot Live - Fixed"
def run_flask(): flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_all_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    scheduler = AsyncIOScheduler(timezone=IST)
    scheduler.add_job(lambda: asyncio.create_task(daily_job(app)), 'cron', hour=6, minute=0, id="daily_6am")
    scheduler.start()
    print("READY - Buttons Fixed - No CallbackQuery Error")
    threading.Thread(target=run_flask, daemon=True).start()
    async def on_startup(app_):
        try: await app_.bot.delete_webhook(drop_pending_updates=True); print("Webhook deleted")
        except: pass
    app.post_init = on_startup
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__': main()
