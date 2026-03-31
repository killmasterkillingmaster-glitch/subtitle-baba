import os
import asyncio
import aiohttp
import json
from pyrogram import Client, filters, enums, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from flask import Flask
from threading import Thread

# --- WEB SERVER FOR RENDER ---
web_app = Flask(__name__)
@web_app.route('/')
def health_check(): return "Bot is Alive and Working!"
def run_web(): web_app.run(host="0.0.0.0", port=10000)

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", "12345"))
API_HASH = os.environ.get("API_HASH", "your_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_token")

OWNER_ID = 5351848105
ALLOWED_USERS = [5351848105, 5344078567]
DB_CHANNEL = -1003143681742
EXTRA_CHANNEL = -1003872932495 # Memory Channel

app = Client("pro_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Global Memory
shortener_db = [] 
user_data = {}

# --- MEMORY FUNCTIONS (Using EXTRA_CHANNEL) ---
async def save_settings():
    data_str = f"#BOT_SETTINGS\n{json.dumps(shortener_db)}"
    try:
        async for msg in app.search_messages(EXTRA_CHANNEL, query="#BOT_SETTINGS"):
            await msg.delete()
        await app.send_message(EXTRA_CHANNEL, data_str)
    except Exception as e: print(f"Save Error: {e}")

async def load_settings():
    global shortener_db
    try:
        await app.get_chat(EXTRA_CHANNEL) # Resolve Channel
        async for msg in app.search_messages(EXTRA_CHANNEL, query="#BOT_SETTINGS"):
            if msg.text and "#BOT_SETTINGS" in msg.text:
                content = msg.text.split("\n", 1)[1]
                shortener_db = json.loads(content)
                break
    except Exception as e: print(f"Load Error: {e}")

# --- UTILS ---
async def get_shortlink(url, site, api):
    site_clean = site.replace("https://", "").replace("http://", "").split('/')[0]
    api_url = f"https://{site_clean}/api?api={api}&url={url}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as res:
                data = await res.json()
                return data.get("shortenedUrl", url)
    except: return url

async def is_subscribed(user_id):
    try:
        m = await app.get_chat_member(EXTRA_CHANNEL, user_id)
        return m.status not in [enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED]
    except: return False

# --- SETTINGS & COMMANDS ---
@app.on_message(filters.command("setting") & filters.user(ALLOWED_USERS))
async def show_settings(c, m):
    text = (
        "**🛠 Bot Control Panel**\n\n"
        "1. `/add_shortener` - Add Account\n"
        "2. `/list_shortener` - Remove Account\n"
        "3. `/select_admin_channel` - Leave Channel\n\n"
        f"**Accounts Active:** `{len(shortener_db)}`"
    )
    await m.reply(text)

@app.on_message(filters.command("add_shortener") & filters.user(ALLOWED_USERS))
async def add_sh_start(c, m):
    user_data[m.from_user.id] = {"state": "ADD_URL"}
    await m.reply("Step 1: Website Domain bhejein (Example: `gplinks.com`):")

@app.on_message(filters.command("list_shortener") & filters.user(ALLOWED_USERS))
async def list_sh(c, m):
    if not shortener_db: return await m.reply("No accounts found.")
    for i, sh in enumerate(shortener_db):
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Remove", callback_data=f"rem_{i}")]])
        await m.reply(f"📍 Account {i+1}:\nURL: `{sh['url']}`", reply_markup=btn)

@app.on_callback_query(filters.regex("rem_"))
async def rem_sh_cb(c, q):
    shortener_db.pop(int(q.data.split("_")[1]))
    await save_settings()
    await q.message.edit("✅ Account removed!")

# --- INPUT HANDLERS (Priority to avoid post conflict) ---
@app.on_message(filters.private & filters.user(ALLOWED_USERS), group=-1)
async def inputs(c, m: Message):
    uid = m.from_user.id
    state = user_data.get(uid, {}).get("state")
    if not state: return

    if state == "ADD_URL":
        user_data[uid]["new_url"] = m.text.strip().replace("https://", "").replace("http://", "").split('/')[0]
        user_data[uid]["state"] = "ADD_API"
        await m.reply("Now send **API Token**:")
        m.stop_propagation()
    elif state == "ADD_API":
        shortener_db.append({"url": user_data[uid]["new_url"], "api": m.text.strip()})
        await save_settings()
        user_data[uid] = {}
        await m.reply("✅ Saved in Memory!")
        m.stop_propagation()
    elif state == "WAIT_NUM":
        user_data[uid]["num"] = m.text
        btns = [[InlineKeyboardButton(sh['url'], callback_data=f"use_{i}")] for i, sh in enumerate(shortener_db)]
        if not btns: await m.reply("Add a shortener first!")
        else: await m.reply("Select Shortener Account:", reply_markup=InlineKeyboardMarkup(btns))
        user_data[uid]["state"] = None
        m.stop_propagation()

# --- FILE CAPTURE ---
@app.on_message(filters.private & filters.user(ALLOWED_USERS) & filters.forwarded)
async def capture(c, m: Message):
    uid = m.from_user.id
    state = user_data.get(uid, {}).get("state")
    if not state or m.forward_from_chat.id != DB_CHANNEL: return

    if state == "WAIT_S":
        user_data[uid]["fid"], user_data[uid]["state"] = m.forward_from_message_id, "WAIT_NUM"
        await m.reply("File OK! Now enter Episode Number:")
    elif state == "WAIT_START":
        user_data[uid]["sid"], user_data[uid]["state"] = m.forward_from_message_id, "WAIT_END"
        await m.reply("Start OK! Now forward **End File**:")
    elif state == "WAIT_END":
        user_data[uid]["eid"], user_data[uid]["state"] = m.forward_from_message_id, "WAIT_NUM"
        await m.reply("End OK! Now enter Number/Range (e.g. 01-10):")

# --- POST HANDLER ---
@app.on_message(filters.private & filters.user(ALLOWED_USERS))
async def handle_post(c, m: Message):
    if m.text and m.text.startswith("/"): return
    user_data[m.from_user.id] = {"post": m, "selected_chats": []}
    btns = [[InlineKeyboardButton("Link", callback_data="s_mode"), InlineKeyboardButton("Batch", callback_data="b_mode")]]
    await m.reply("Post detected. Mode select karein:", reply_markup=InlineKeyboardMarkup(btns))

@app.on_callback_query()
async def callbacks(c, q: CallbackQuery):
    uid = q.from_user.id
    data = q.data

    if data == "s_mode":
        user_data[uid]["mode"], user_data[uid]["state"] = "s", "WAIT_S"
        await q.message.edit("Forward file from DB.")
    elif data == "b_mode":
        user_data[uid]["mode"], user_data[uid]["state"] = "b", "WAIT_START"
        await q.message.edit("Forward Start file.")
    elif data.startswith("use_"):
        sh = shortener_db[int(data.split("_")[1])]
        await q.message.edit("⚡ Generating Link...")
        path = f"{user_data[uid]['fid']}" if user_data[uid]["mode"] == "s" else f"{user_data[uid]['sid']}_{user_data[uid]['eid']}"
        bot_un = (await c.get_me()).username
        short_url = await get_shortlink(f"https://t.me/{bot_un}?start={path}", sh['url'], sh['api'])
        user_data[uid]["markup"] = InlineKeyboardMarkup([[InlineKeyboardButton(f"Episode {user_data[uid]['num']}", url=short_url)]])
        btns = [[InlineKeyboardButton(d.chat.title, callback_data=f"tr_{d.chat.id}")] async for d in c.get_dialogs() if d.chat.type in [enums.ChatType.CHANNEL, enums.ChatType.SUPERGROUP]]
        btns.append([InlineKeyboardButton("🚀 SEND", callback_data="push")])
        await q.message.edit("Select Channels:", reply_markup=InlineKeyboardMarkup(btns))
    elif data.startswith("tr_"):
        cid = int(data.split("_")[1])
        if cid not in user_data[uid]["selected_chats"]: user_data[uid]["selected_chats"].append(cid)
        else: user_data[uid]["selected_chats"].remove(cid)
        await q.answer("Updated")
    elif data == "push":
        for cid in user_data[uid]["selected_chats"]:
            try: await user_data[uid]["post"].copy(cid, reply_markup=user_data[uid]["markup"])
            except: pass
        await q.message.edit("✅ Mission Accomplished!")

# --- STARTUP ---
async def boot():
    Thread(target=run_web).start()
    await app.start()
    await load_settings()
    print("Bot is Live!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(boot())
