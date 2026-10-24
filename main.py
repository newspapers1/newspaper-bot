import threading
from flask import Flask
import os
import json
import datetime
import pytz
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN","").strip()

def load_papers():
    try:
        if Path("all_papers.json").exists():
            with open("all_papers.json","r",encoding="utf-8") as f:
                data=json.load(f)
                if data: return data
    except Exception as e:
        print(e)
    return [{"id":"1","name":"The Hindu","city":"Delhi"},{"id":"2","name":"Dainik Jagran","city":"Patna"},{"id":"3","name":"Dainik Bhaskar","city":"Patna"},{"id":"4","name":"Eenadu","city":"Hyderabad"}]

def get_mode(): return "Channel + Group"
def load_custom():
    if Path("autocustom.json").exists():
        try:
            with open("autocustom.json") as f: return json.load(f)
        except: return []
    return []

async def download_send(app,paper,city,date,chat_id):
    await app.bot.send_message(chat_id=chat_id,text=f"📰 {paper} - {city} - {date}")

async def show_select_page(update,ctx,page):
    papers=load_papers()
    if isinstance(papers[0],dict):
        names=sorted(set([p.get('name','') for p in papers if p.get('name')]))
    else:
        names=sorted(set(papers))
    kb=[[InlineKeyboardButton(n,callback_data=f"paper:{n}")] for n in names[page*10:(page+1)*10]]
    if update.callback_query:
        await update.callback_query.edit_message_text(f"Select karo - Page {page}",reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(f"Select karo - Page {page}",reply_markup=InlineKeyboardMarkup(kb))

async def btn(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    d=q.data
    if d.startswith("city:"):
        city=d.split(":",1)[1]
        ctx.user_data['city']=city
        today=datetime.datetime.now().strftime("%d-%m-%Y")
        kb=[[InlineKeyboardButton(f"📅 {today} (Aaj)",callback_data=f"date:{today}")],[InlineKeyboardButton("📝 Custom ke liye /get use karo",callback_data="noop")]]
        await q.edit_message_text(f"📍 {ctx.user_data.get('paper')} - {city} - Date:",reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("date:"):
        date=d.split(":",1)[1]
        await q.edit_message_text(f"⏳ {ctx.user_data.get('paper')} - {ctx.user_data.get('city')} - {date}")
        await download_send(ctx.application,ctx.user_data.get('paper'),ctx.user_data.get('city'),date,q.message.chat_id)
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
        await q.edit_message_text(f"📰 {paper} - City select karo:",reply_markup=InlineKeyboardMarkup(kb))

async def start(update,ctx):
    papers=load_papers()
    if not papers:
        await update.message.reply_text("❌ No papers found!")
        return
    if isinstance(papers[0],dict):
        names=sorted(set([p.get('name','') for p in papers if p.get('name')]))
    else:
        names=sorted(set(papers))
    kb=[[InlineKeyboardButton(n,callback_data=f"paper:{n}")] for n in names[:20]]
    await update.message.reply_text("👋 **6 AM Bot Ready**\n\n/select - Alag-alag ya Sab select karo\n/mylist - Meri list dekho\n/autocustom - 6 AM pe sirf meri list",reply_markup=InlineKeyboardMarkup(kb))

async def select_cmd(update,ctx): await show_select_page(update,ctx,0)
async def mylist_cmd(update,ctx):
    c=load_custom()
    if not c:
        await update.message.reply_text("❌ Empty. /select se banao")
        return
    txt="📋 Selected:\n"+"\n".join([f"• {x}" for x in c])
    await update.message.reply_text(txt)

async def settings_cmd(update,ctx):
    kb=[[InlineKeyboardButton("📢 Only Channel",callback_data="mode:channel")],[InlineKeyboardButton("👥 Only Group",callback_data="mode:group")],[InlineKeyboardButton("📢+👥 Both",callback_data="mode:both")]]
    await update.message.reply_text(f"Current: {get_mode()}",reply_markup=InlineKeyboardMarkup(kb))

async def autocustom_cmd(update,ctx):
    if not Path("autocustom.json").exists():
        await update.message.reply_text("❌ OFF. Ab 6 AM pe Saare papers jayega")
        return
    await update.message.reply_text("✅ Autocustom ON hai")

async def get_cmd(update,ctx): await update.message.reply_text("Use: /get PaperName City DD-MM-YYYY")
async def auto_job(app): print("6 AM Auto job running...")

def main():
    if not BOT_TOKEN:
        print("BOT_TOKEN missing!")
        return
    app=Application.builder().token(BOT_TOKEN).build()
    for cmd,fn in [("start",start),("select",select_cmd),("mylist",mylist_cmd),("settings",settings_cmd),("mode",settings_cmd),("autocustom",autocustom_cmd),("get",get_cmd)]:
        app.add_handler(CommandHandler(cmd,fn))
    app.add_handler(CallbackQueryHandler(btn))
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    scheduler=AsyncIOScheduler(timezone=pytz.timezone('Asia/Kolkata'))
    async def job_wrapper(): await auto_job(app)
    scheduler.add_job(job_wrapper,'cron',hour=6,minute=0)
    scheduler.start()
    print("READY 6 AM - CUSTOM SELECT - 4 MODES")
    app.run_polling(drop_pending_updates=True)
# --- Render FREE Web Service ke liye Dummy Server ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Bot is Live - 6 AM Ready"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)
threading.Thread(target=run_flask, daemon=True).start()
# --- End Dummy Server ---
if __name__=='__main__': main()
