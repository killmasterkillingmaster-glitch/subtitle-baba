import os
import asyncio
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from flask import Flask
from threading import Thread

# --- BASIC CONFIG ---
API_ID = int(os.environ.get("API_ID", "12345"))
API_HASH = os.environ.get("API_HASH", "abcdef")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7123:AAH...")
ADMINS = [int(i) for i in os.environ.get("ADMINS", "12345").split()]
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "-100456"))
DB_CHANNEL = int(os.environ.get("DB_CHANNEL", "-100123"))

app = Client("ASI_V9_FINAL", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Temporary Memory
USER_STATE = {} 
CONFIG = {"api": None, "url": None, "fsub": []} # Startup pe Log Channel se load hoga

# --- WEB SERVER ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "Bot is Online"
def run_web(): web_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# --- 🛠 DATABASE HELPERS (Using Log Channel) ---

async def load_config():
    """Bot start hote hi settings load karega"""
    async for m in app.search_messages(LOG_CHANNEL, query="SETTING:"):
        if "SHORTENER:" in m.text:
            # Format: SETTING:SHORTENER:api|url
            data = m.text.split("SHORTENER:")[1].split("|")
            CONFIG["api"], CONFIG["url"] = data[0], data[1]
        elif "FSUB_LIST:" in m.text:
            # Format: SETTING:FSUB_LIST:id1,id2
            ids = m.text.split("FSUB_LIST:")[1].split(",")
            CONFIG["fsub"] = [int(i) for i in ids if i]

async def update_config(key, value):
    """Log channel mein setting update karega"""
    async for m in app.search_messages(LOG_CHANNEL, query=f"SETTING:{key}"):
        await m.delete() # Purani setting delete
    await app.send_message(LOG_CHANNEL, f"SETTING:{key}:{value}")

# --- 🔗 SHORTENER LOGIC ---

async def get_short(long_url):
    if not CONFIG["api"]: return long_url
    try:
        async with aiohttp.ClientSession() as session:
            # Most common shortener API format
            params = {'api': CONFIG['api'], 'url': long_url}
            async with session.get(CONFIG['url'], params=params) as r:
                res = await r.json()
                return res.get("shortened_url") or long_url
    except: return long_url

# --- 🛠 ADMIN SETTINGS FLOW ---

@app.on_message(filters.command("settings") & filters.private)
async def settings_panel(c, m):
    if m.from_user.id not in ADMINS: return
    await m.reply("⚙️ **Bot Settings Dashboard**\n\nChoose an option to configure:", 
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Shortener Setup", callback_data="set_short")],
            [InlineKeyboardButton("📢 Force Sub Setup", callback_data="set_fsub")],
            [InlineKeyboardButton("📊 Bot Stats", callback_data="stats")]
        ]))

@app.on_callback_query()
async def cb_handler(c, q: CallbackQuery):
    u_id = q.from_user.id
    if u_id not in ADMINS: return
    
    # --- Shortener Flow ---
    if q.data == "set_short":
        await q.edit_message_text("Kya aap Shortener account add/change karna chahte hain?", 
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Yes", callback_data="add_short_start")],
                [InlineKeyboardButton("❌ Remove Current", callback_data="del_short")]
            ]))

    elif q.data == "add_short_start":
        USER_STATE[u_id] = {'step': 'wait_short_url'}
        await q.edit_message_text("Please forward/send your **Dashboard API URL**\n(e.g., `https://anyshorturl.com/api`)")

    elif q.data == "del_short":
        CONFIG["api"], CONFIG["url"] = None, None
        await update_config("SHORTENER", "None")
        await q.answer("✅ Shortener Removed!", show_alert=True)
        await q.message.delete()

    # --- Force Sub Flow ---
    elif q.data == "set_fsub":
        # Bot jahan admin hai unki list dikhao (Mapping memory se)
        channels = {} # Logic to get discovered channels
        async for m in c.search_messages(LOG_CHANNEL, query="CH_DATA:"):
            p = m.text.replace("CH_DATA:", "").split("|")
            channels[p[1]] = int(p[0])
        
        btns = []
        for name, cid in channels.items():
            tick = "✅" if cid in CONFIG["fsub"] else "❌"
            btns.append([InlineKeyboardButton(f"{name} {tick}", callback_data=f"toggle_fsub_{cid}")])
        
        btns.append([InlineKeyboardButton("💾 Save Force Sub", callback_data="save_fsub")])
        await q.edit_message_text("Select channels for **Force Sub**:", reply_markup=InlineKeyboardMarkup(btns))

    elif q.data.startswith("toggle_fsub_"):
        cid = int(q.data.split("_")[2])
        if cid in CONFIG["fsub"]: CONFIG["fsub"].remove(cid)
        else: CONFIG["fsub"].append(cid)
        await cb_handler(c, q.copy(data="set_fsub"))

    elif q.data == "save_fsub":
        val = ",".join([str(i) for i in CONFIG["fsub"]])
        await update_config("FSUB_LIST", val)
        await q.answer("✅ Force Sub Updated!", show_alert=True)

# --- 📩 MESSAGE HANDLER (Steps) ---

@app.on_message(filters.private & filters.incoming)
async def admin_steps(c, m):
    u_id = m.from_user.id
    if u_id not in ADMINS: return
    st = USER_STATE.get(u_id)
    if not st: return

    if st['step'] == 'wait_short_url':
        st['short_url'] = m.text
        st['step'] = 'wait_short_api'
        await m.reply("✅ URL Saved! Now send your **API Token**:")
    
    elif st['step'] == 'wait_short_api':
        api_key = m.text
        CONFIG["api"], CONFIG["url"] = api_key, st['short_url']
        await update_config("SHORTENER", f"{api_key}|{st['short_url']}")
        await m.reply("✅ Successfully Completed! Shortener added.")
        del USER_STATE[u_id]

# --- 🚀 FILE SHARING LOGIC (Same as you described) ---

@app.on_message(filters.private & (filters.photo | filters.video | filters.document))
async def post_gen(c, m):
    if m.from_user.id not in ADMINS: return
    # Flow: Ask Single/Batch -> Forward DB File -> Enter Ep Number
    # Jab admin Episode Number (e.g. 06) likhega:
    # Bot link generate karega: t.me/bot?start=t_MESSAGEID
    # Bot post bhejega aur niche button hoga: [ Episode 06 ]
    # Us button mein SHORTURL hoga.

# --- 👥 USER SIDE JOURNEY ---

@app.on_message(filters.command("start") & filters.private)
async def start_handler(c, m):
    if len(m.command) < 2: return await m.reply("Hi!")

    # Check if coming back from Shortener
    # Shortener solve karke user aayega: /start verify_TOKEN
    data = m.command[1]
    
    # 1. Force Sub Check (Multi-channel)
    not_joined = []
    for cid in CONFIG["fsub"]:
        try:
            await c.get_chat_member(cid, m.from_user.id)
        except:
            chat = await c.get_chat(cid)
            not_joined.append(InlineKeyboardButton(f"Join {chat.title}", url=(await chat.export_invite_link())))
    
    if not_joined:
        return await m.reply("❌ Sabhi channels join karein file paane ke liye:", 
            reply_markup=InlineKeyboardMarkup([not_joined]))

    # 2. Give File
    # Token decode and send file from DB_CHANNEL...

# --- START ---
if __name__ == "__main__":
    Thread(target=run_web).start()
    asyncio.get_event_loop().run_until_complete(load_config())
    app.run()
