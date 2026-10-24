import os, json, requests, pytz, asyncio, re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from bs4 import BeautifulSoup

BOT_TOKEN=os.environ.get("BOT_TOKEN")
CHANNEL_ID=os.environ.get("CHANNEL_ID","@TodayAllNewsPaper")
GROUP_ID=os.environ.get("GROUP_ID","")
POST_MODE_FILE="mode.txt"
CUSTOM_FILE="custom_papers.json"
AUTOCUSTOM_FILE="autocustom.txt"
ACCESS="https://www.tradingref.com/?accesstoken=pip0zIKMysJvmhu4y1KMx2KNxK=="

def load_papers():
    with open('all_papers.json','r') as f: return json.load(f)
def load_custom():
    return json.load(open(CUSTOM_FILE)) if os.path.exists(CUSTOM_FILE) else []
def save_custom(d): json.dump(d, open(CUSTOM_FILE,'w'))
def get_mode(): return open(POST_MODE_FILE).read().strip() if os.path.exists(POST_MODE_FILE) else os.environ.get("POST_MODE","channel")
def save_mode(m): open(POST_MODE_FILE,'w').write(m)

def find_pdf(pid):
    try:
        s=requests.Session(); s.get(ACCESS, headers={'User-Agent':'Mozilla/5.0'}, timeout=10)
        r=s.get(f"https://www.tradingref.com/{pid}", headers={'User-Agent':'Mozilla/5.0'}, timeout=20)
        soup=BeautifulSoup(r.text,'html.parser')
        for a in soup.find_all('a', href=True):
            if '.pdf' in a['href']:
                link=a['href']
                if not link.startswith('http'): link="https://www.tradingref.com"+link
                return link,s
    except: pass
    return None,None

async def send_dest(app, data, fname, cap, uid):
    mode=get_mode()
    try:
        if mode=="channel": await app.bot.send_document(CHANNEL_ID, data, filename=fname, caption=cap, parse_mode='Markdown')
        elif mode=="group": await app.bot.send_document(GROUP_ID if GROUP_ID else uid, data, filename=fname, caption=cap, parse_mode='Markdown')
        elif mode=="channel_group":
            await app.bot.send_document(CHANNEL_ID, data, filename=fname, caption=cap, parse_mode='Markdown')
            if GROUP_ID: await asyncio.sleep(2); await app.bot.send_document(GROUP_ID, data, filename=fname, caption=cap, parse_mode='Markdown')
        elif mode=="bot": await app.bot.send_document(uid, data, filename=fname, caption=cap, parse_mode='Markdown')
    except Exception as e:
        print(f"Send error: {e}")
        if uid: 
            try: await app.bot.send_document(uid, data, filename=fname, caption=cap, parse_mode='Markdown')
            except: pass

async def download_send(app, name, city, date, uid=None):
    papers=load_papers()
    t=next((p for p in papers if p['name'].lower()==name.lower() and p['city'].lower()==city.lower()), None)
    if not t: return False
    link,s=find_pdf(t['id'])
    if not link: return False
    try:
        d=s.get(link, timeout=60).content
        if len(d)<10000: return False
        await send_dest(app, d, f"{name}-{city}-{date}.pdf", f"📰 {name}\n📍 {city}\n📅 {date}", uid)
        return True
    except Exception as e:
        print(f"Download error {name}: {e}")
        return False

async def show_select_page(q, ctx, page):
    papers=load_papers(); custom=load_custom(); per=10; st=page*per; sl=papers[st:st+per]
    kb=[]
    for p in sl:
        tick="✅" if p['id'] in custom else "⬜"
        kb.append([InlineKeyboardButton(f"{tick} {p['name']} - {p['city']}", callback_data=f"tog:{p['id']}:{page}")])
    nav=[]
    if page>0: nav.append(InlineKeyboardButton("⬅️", callback_data=f"pg:{page-1}"))
    if st+per < len(papers): nav.append(InlineKeyboardButton("➡️", callback_data=f"pg:{page+1}"))
    if nav: kb.append(nav)
    kb.append([InlineKeyboardButton("✅ Select All", callback_data="all"), InlineKeyboardButton("❌ Deselect All", callback_data="none")])
    kb.append([InlineKeyboardButton("💾 Save", callback_data="save")])
    txt=f"📌 Select karo jo chahiye (Page {page+1})\nSelected: {len(custom)}/{len(papers)}\n✅ = Selected"
    if isinstance(q, Update): await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    else: await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))

async def btn(update, ctx):
    q=update.callback_query; await q.answer(); d=q.data; papers=load_papers()
    if d.startswith("tog:"):
        _, pid, pg = d.split(":"); pg=int(pg); c=load_custom()
        if pid in c: c.remove(pid)
        else: c.append(pid)
        save_custom(c); await show_select_page(q, ctx, pg)
    elif d.startswith("pg:"): await show_select_page(q, ctx, int(d.split(":")[1]))
    elif d=="all": save_custom([p['id'] for p in papers]); await show_select_page(q, ctx, 0)
    elif d=="none": save_custom([]); await show_select_page(q, ctx, 0)
    elif d=="save": await q.edit_message_text(f"✅ Save ho gaya! {len(load_custom())} papers select hai.\nAb /autocustom ON karo to 6 AM pe sirf yehi jayenge")
    elif d.startswith("mode:"): save_mode(d.split(":")[1]); await q.edit_message_text(f"✅ Mode: {d.split(':')[1]} set")
    elif d.startswith("paper:"):
        name=d.split(":",1)[1]; ctx.user_data['paper']=name
        cities=sorted(list(set([p['city'] for p in papers if p['name']==name])))
        kb=[[InlineKeyboardButton(c, callback_data=f"city:{c}")] for c in cities]
        await q.edit_message_text(f"📰 {name} - City chuniye:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("city:"):
        city=d.split(":",1)[1]; ctx.user_data['city']=city
        today=datetime.now().strftime("%d-%m-%Y")
        kb=[[InlineKeyboardButton(f"📅 {today} (Aaj)", callback_data=f"date:{today}")],[InlineKeyboardButton("📅 Custom ke liye /get use karo", callback_data="noop")]]
        await q.edit_message_text(f"📍 {ctx.user_data['paper']} - {city} - Date:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("date:"):
        date=d.split(":")[1]; await q.edit_message_text(f"⏳ {ctx.user_data['paper']} - {ctx.user_data['city']} - {date}")
        await download_send(ctx.application, ctx.user_data['paper'], ctx.user_data['city'], date, q.message.chat_id)

async def start(update, ctx):
    papers=load_papers(); names=sorted(set([p['name'] for p in papers]))
    kb=[[InlineKeyboardButton(n, callback_data=f"paper:{n}")] for n in names[:20]]
    await update.message.reply_text("👋 **6 AM Bot Ready**\n\n/select - Alag-alag ya Sab select karo\n/mylist - Meri list dekho\n/autocustom - 6 AM pe sirf meri list bhejo\n/settings - Channel/Group/Bot set karo\n/get - Date wise lena", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

async def select_cmd(update, ctx): await show_select_page(update, ctx, 0)
async def mylist_cmd(update, ctx):
    c=load_custom(); papers=load_papers()
    if not c: await update.message.reply_text("❌ Empty. /select se banao"); return
    txt="📋 Selected:\n"+"\n".join([f"• {next((p['name']+' - '+p['city'] for p in papers if p['id']==x), x)}" for x in c])
    await update.message.reply_text(txt)
async def settings_cmd(update, ctx):
    kb=[[InlineKeyboardButton("📢 Only Channel", callback_data="mode:channel")],[InlineKeyboardButton("👥 Only Group", callback_data="mode:group")],[InlineKeyboardButton("📢+👥 Channel+Group", callback_data="mode:channel_group")],[InlineKeyboardButton("🤖 Only Bot", callback_data="mode:bot")]]
    await update.message.reply_text(f"Current: {get_mode()}\n{CHANNEL_ID}\n{GROUP_ID}", reply_markup=InlineKeyboardMarkup(kb))
async def autocustom_cmd(update, ctx):
    if os.path.exists(AUTOCUSTOM_FILE): os.remove(AUTOCUSTOM_FILE); await update.message.reply_text("🔄 OFF: Ab 6 AM pe SAare papers jayenge")
    else: open(AUTOCUSTOM_FILE,'w').write("1"); await update.message.reply_text(f"✅ ON: Ab 6 AM pe sirf {len(load_custom())} selected papers hi jayenge")
async def get_cmd(update, ctx):
    if len(ctx.args)<2: await update.message.reply_text("Use: /get PaperName City DD-MM-YYYY\nEx: /get Dainik Jagran Patna 24-10-2026"); return
    date=datetime.now().strftime("%d-%m-%Y")
    if re.match(r'\d{2}-\d{2}-\d{4}', ctx.args[-1]): date=ctx.args[-1]; city=ctx.args[-2]; name=" ".join(ctx.args[:-2])
    else: city=ctx.args[-1]; name=" ".join(ctx.args[:-1])
    await update.message.reply_text(f"⏳ {name} - {city} - {date}"); await download_send(ctx.application, name, city, date, update.message.chat_id)

async def auto_job(app):
    papers=load_papers(); custom=load_custom()
    use_custom=os.path.exists(AUTOCUSTOM_FILE) and len(custom)>0
    to_dl=[p for p in papers if p['id'] in custom] if use_custom else papers
    for p in to_dl:
        await download_send(app, p['name'], p['city'], datetime.now().strftime("%d-%m-%Y"), None)
        await asyncio.sleep(3)

def main():
    if not BOT_TOKEN:
        print("BOT_TOKEN missing!")
        return
    app=Application.builder().token(BOT_TOKEN).build()
    for cmd, fn in [("start",start),("select",select_cmd),("mylist",mylist_cmd),("settings",settings_cmd),("mode",settings_cmd),("autocustom",autocustom_cmd),("get",get_cmd)]:
        app.add_handler(CommandHandler(cmd, fn))
    app.add_handler(CallbackQueryHandler(btn))

    scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Kolkata'))
    async def job_wrapper():
        await auto_job(app)
    scheduler.add_job(job_wrapper, 'cron', hour=6, minute=0)
    scheduler.start()

    print("READY 6 AM - CUSTOM SELECT - 4 MODES")
    app.run_polling()

if __name__=='__main__': main()
