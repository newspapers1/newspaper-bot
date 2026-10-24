import os
import json
import threading
import datetime
import pytz
from pathlib import Path
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN","").strip()

# --- Flask for Render FREE ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return "Bot is Live - 6 AM Ready"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

def load_papers():
    try:
        if Path("all_papers.json").exists():
            with open("all_papers.json","r",encoding="utf-8") as f:
                data=json.load(f)
                if data:
                    return data
    except Exception as e:
        print(f"load error {e}")
    return [{"name":"The Hindu","city":"Delhi"},{"name":"Dainik Jagran","city":"Patna"},{"name":"Eenadu","city":"Hyderabad"}]

def load_custom():
    if Path("autocustom.json").exists():
        try:
            with open("autocustom.json","r") as f:
                return json.load(f)
        except:
            return []
    return []

async def download_send(app,paper,city,date,chat_id):
    await app.bot.send_message(chat_id=chat_id, text=f"📰 {paper} - {city} - {date}\nDownload ho raha hai...")

async def show_select_page(update,ctx,page):
    papers=load_papers()
    names=sorted(set([p.get('name','') for p in papers if isinstance(p,dict) and p.get('name')]))
    kb=[[InlineKeyboardButton(n,callback_data=f"paper:{n}")] for n in names[page*10:(page+1)*10]]
    if update.callback_query:
        await update.callback_query.edit_message_text(f"Select karo - Page {page}", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(f"Select karo - Page {page}", reply_markup=InlineKeyboardMarkup(kb))

async def btn(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    d=q.data
    if d.startswith("city:"):
        city=d.split(":",1)[1]
        ctx.user_data['city']=city
        today=datetime.datetime.now().strftime("%d-%m-%Y")
        kb=[[InlineKeyboardButton(f"📅 {today}",callback_data=f"date:{today}")]]
        await q.edit_message_text(f"📍 {ctx.user_data.get('paper')} - {city} - Date:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("date:"):
        date=d.split(":",1)[1]
        await q.edit_message_text(f"⏳ {ctx.user_data.get('paper')} - {ctx.user_data.get('city')} - {date}")
        await download_send(ctx.application, ctx.user_data.get('paper'), ctx.user_data.get('city'), date, q.message.chat_id)
    elif d.startswith("paper:"):
        paper=d.split(":",1)[1]
        ctx.user_data['paper']=paper
        papers=load_papers()
        cities=[]
        for p in papers:
            if isinstance(p,dict) and p.get('name')==paper and p.get('city'):
                cities.append(p.get('city'))
        cities=sorted(set(cities)) if cities else ["Delhi","Patna","Mumbai"]
        kb=[[InlineKeyboardButton(c,callback_data=f"city:{c}")] for c in cities[:20]]
        await q.edit_message_text(f"📰 {paper} - City select karo:", reply_markup=InlineKeyboardMarkup(kb))

async def start(update,ctx):
    papers=load_papers()
    names=sorted(set([p.get('name','') for p in papers if isinstance(p,dict) and p.get('name')]))
    kb=[[InlineKeyboardButton(n,callback_data=f"paper:{n}")] for n in names[:20]]
    await update.message.reply_text("👋 **6 AM Bot Ready - Ab Kaam Karega**\n\n/select - Papers select karo\n/mylist - List dekho", reply_markup=InlineKeyboardMarkup(kb))

async def select_cmd(update,ctx): await show_select_page(update,ctx,0)
async def mylist_cmd(update,ctx):
    c=load_custom()
    if not c:
        await update.message.reply_text("❌ Empty. /select se banao")
        return
    await update.message.reply_text("📋 Selected:\n" + "\n".join([f"• {x}" for x in c]))
async def settings_cmd(update,ctx): await update.message.reply_text("Settings - Channel + Group")

def main_bot():
    if not BOT_TOKEN:
        print("BOT_TOKEN missing!")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("select", select_cmd))
    app.add_handler(CommandHandler("mylist", mylist_cmd))
    app.add_handler(CommandHandler("settings", settings_cmd))
    app.add_handler(CommandHandler("mode", settings_cmd))
    app.add_handler(CallbackQueryHandler(btn))
    print("READY 6 AM - BOT STARTING")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    main_bot()
