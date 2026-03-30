import os
import asyncio
import aiohttp
import json
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from flask import Flask
from threading import Thread

# --- WEB SERVER FOR RENDER ---
web_app = Flask(__name__)
@web_app.route('/')
def health_check(): return "Bot is running with Channel Memory!"
def run_web(): web_app.run(host="0.0.0.0", port=10000)

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", "12345"))
API_HASH = os.environ.get("API_HASH", "your_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_token")

OWNER_ID = 5351848105
ALLOWED_USERS = [5351848105, 5344078567]
DB_CHANNEL = -1003143681742
EXTRA_CHANNEL = -1003872932495 # Yeh aapka Memory Channel hai

app = Client("pro_mem_bot_final", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Global Data
shortener_db = [] 
user_data = {}

# --- MEMORY FUNCTIONS (Using EXTRA_CHANNEL) ---

async def save_settings():
    """Shortener settings ko EXTRA_CHANNEL mein save karta hai."""
    data_str = f"#BOT_SETTINGS\n{json.dumps(shortener_db)}"
    try:
        # Purane settings message ko dhund kar delete karo
        async for msg in app.search_messages(EXTRA_CHANNEL, query="#BOT_SETTINGS"):
            await msg.delete()
        # Naya message bhejo
        await app.send_message(EXTRA_CHANNEL, data_str)
    except Exception as e:
        print(f"Error saving to memory: {e}")

async def load_settings():
    """Startup par settings load karta hai."""
    global shortener_db
    try:
        # Crash fix: Pehle chat ko resolve karo
        await app.get_chat(EXTRA_CHANNEL)
        async for msg in app.search_messages(EXTRA_CHANNEL, query="#BOT_SETTINGS"):
            if msg.text and "#BOT_SETTINGS" in msg.text:
                content = msg.text.split("\n", 1)[1]
                shortener_db = json.loads(content)
                print("✅ Settings Loaded from Memory!")
                break
    except Exception as e:
        print(f"⚠️ Memory loading issue: {e}")

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

# --- SETTINGS COMMANDS ---

@app.on_message(filters.command("setting") & filters.user(ALLOWED_USERS))
async def cmd_settings(c, m):
    cmds = (
        "**🤖 Bot Control Panel**\n\n"
        "1. `/add_shortener` - Naya account jodein\n"
        "2. `/list_shortener` - Accounts manage/remove karein\n"
        "3. `/select_admin_channel` - Leave Channel\n\n"
        f"**Active Accounts:** `{len(shortener_db)}`"
    )
    await m.reply(cmds)

@app.on_message(filters.command("add_shortener") & filters.user(ALLOWED_USERS))
async def cmd_add_sh(c, m):
    user_data[m.from_user.id] = {"state": "INPUT_URL"}
    await m.reply("Step 1: Website Domain bhejein (Example: `gplinks.com`):")

@app.on_message(filters.command("list_shortener") & filters.user(ALLOWED_USERS))
async def cmd_list_sh(c, m):
    if not shortener_db: return await m.reply("Koi account add nahi hai.")
    for i, sh in enumerate(shortener_db):
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Remove Account", callback_data=f"rem_sh_{i}")]])
        await m.reply(f"📍 Account {i+1}:\nURL: `{sh['url']}`\nAPI: `{sh['api'][:10]}...`", reply_markup=btn)

@app.on_callback_query(filters.regex("rem_sh_"))
async def cb_rem_sh(c, q):
    idx = int(q.data.split("_")[2])
    shortener_db.pop(idx)
    await save_settings()
    await q.message.edit("✅ Removed from Memory!")

# --- INPUT HANDLERS (Priority Group -1) ---

@app.on_message(filters.private & filters.user(ALLOWED_USERS), group=-1)
async def interceptor(c, m: Message):
    uid = m.from_user.id
    state = user_data.get(uid, {}).get("state")
    if not state: return

    if state == "INPUT_URL":
        user_data[uid]["new_url"] = m.text.replace("https://", "").replace("http://", "").split('/')[0]
        user_data[uid]["state"] = "INPUT_API"
        await m.reply("URL Saved! Ab **API Token** bhejein:")
        m.stop_propagation()
    elif state == "INPUT_API":
        api = m.text.strip()
        shortener_db.append({"url": user_data[uid]["new_url"], "api": api})
        await save_settings() # Memory Update
        user_data[uid] = {}
        await m.reply("✅ Successfully Saved in Memory!")
        m.stop_propagation()
    elif state == "WAIT_NUM":
        user_data[uid]["num"] = m.text
        btns = [[InlineKeyboardButton(sh['url'], callback_data=f"use_{i}")] for i, sh in enumerate(shortener_db)]
        if not btns: await m.reply("Error: Pehle `/add_shortener` karein.")
        else: await m.reply("Select Shortener Account:", reply_markup=InlineKeyboardMarkup(btns))
        user_data[uid]["state"] = None
        m.stop_propagation()

# --- FILE CAPTURE HANDLER ---
@app.on_message(filters.private & filters.user(ALLOWED_USERS) & filters.forwarded)
async def capture_file(c, m: Message):
    uid = m.from_user.id
    state = user_data.get(uid, {}).get("state")
    if not state: return
    if m.forward_from_chat.id != DB_CHANNEL: return await m.reply("Sirf DB Channel se forward karein!")

    if state == "WAIT_SINGLE":
        user_data[uid]["fid"] = m.forward_from_message_id
        user_data[uid]["state"] = "WAIT_NUM"
        await m.reply("File OK! Ab Episode Number bhejein:")
    elif state == "WAIT_START":
        user_data[uid]["sid"] = m.forward_from_message_id
        user_data[uid]["state"] = "WAIT_END"
        await m.reply("Start OK! Ab **End File** forward karein.")
    elif state == "WAIT_END":
        user_data[uid]["eid"] = m.forward_from_message_id
        user_data[uid]["state"] = "WAIT_NUM"
        await m.reply("End OK! Ab Episode Range bhejein:")

# --- POST HANDLER ---
@app.on_message(filters.private & filters.user(ALLOWED_USERS))
async def handle_post(c, m: Message):
    if m.text and m.text.startswith("/"): return
    user_data[m.from_user.id] = {"post": m, "selected_chats": []}
    btns = [[InlineKeyboardButton("Link", callback_data="s_mode"), 
             InlineKeyboardButton("Batch Link", callback_data="b_mode")]]
    await m.reply("Post received. Mode select karein:", reply_markup=InlineKeyboardMarkup(btns))

@app.on_callback_query()
async def callbacks(c, q: CallbackQuery):
    uid = q.from_user.id
    data = q.data

    if data == "s_mode":
        user_data[uid]["mode"], user_data[uid]["state"] = "s", "WAIT_SINGLE"
        await q.message.edit("Database se Episode forward karein.")
    elif data == "b_mode":
        user_data[uid]["mode"], user_data[uid]["state"] = "b", "WAIT_START"
        await q.message.edit("Database se Start Episode forward karein.")
    
    elif data.startswith("use_"):
        idx = int(data.split("_")[1])
        sh = shortener_db[idx]
        await q.message.edit("⚡ Generating Link...")
        
        bot_un = (await c.get_me()).username
        path = f"{user_data[uid]['fid']}" if user_data[uid]['mode'] == "s" else f"{user_data[uid]['sid']}_{user_data[uid]['eid']}"
        long_url = f"https://t.me/{bot_un}?start={path}"
        short_url = await get_shortlink(long_url, sh['url'], sh['api'])
        
        user_data[uid]["markup"] = InlineKeyboardMarkup([[InlineKeyboardButton(f"Episode {user_data[uid]['num']}", url=short_url)]])
        
        btns = [[InlineKeyboardButton(d.chat.title, callback_data=f"trg_{d.chat.id}")] async for d in c.get_dialogs() if d.chat.type in [enums.ChatType.CHANNEL, enums.ChatType.SUPERGROUP]]
        btns.append([InlineKeyboardButton("🚀 SEND NOW", callback_data="push")])
        await q.message.edit("Select Channels & Send:", reply_markup=InlineKeyboardMarkup(btns))

    elif data.startswith("trg_"):
        cid = int(data.split("_")[1])
        if cid not in user_data[uid]["selected_chats"]: user_data[uid]["selected_chats"].append(cid)
        else: user_data[uid]["selected_chats"].remove(cid)
        await q.answer("Updated")

    elif data == "push":
        p, markup = user_data[uid]["post"], user_data[uid]["markup"]
        for cid in user_data[uid]["selected_chats"]:
            try: await p.copy(cid, reply_markup=markup)
            except: pass
        await q.message.edit("✅ Done! Post broadcasted.")

# --- USER INTERFACE ---
@app.on_message(filters.command("start") & filters.private)
async def on_start(c, m):
    if len(m.text.split()) > 1:
        if not await is_subscribed(m.from_user.id):
            invite = (await c.get_chat(EXTRA_CHANNEL)).invite_link
            return await m.reply("Join channel to access!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join", url=invite)]]))
        
        code = m.text.split()[1]
        try:
            if "_" in code:
                s, e = map(int, code.split("_"))
                for mid in range(s, e + 1):
                    await c.copy_message(m.chat.id, DB_CHANNEL, mid)
                    await asyncio.sleep(0.5)
            else:
                await c.copy_message(m.chat.id, DB_CHANNEL, int(code))
        except: await m.reply("DB Error.")
        return
    await m.reply("Bhai, post bhejo setup ke liye.")

@app.on_message(filters.command("select_admin_channel") & filters.user(OWNER_ID))
async def cmd_leave(c, m):
    btns = [[InlineKeyboardButton(d.chat.title, callback_data=f"lv_{d.chat.id}")] async for d in c.get_dialogs() if d.chat.type == enums.ChatType.CHANNEL]
    await m.reply("Leave Channel:", reply_markup=InlineKeyboardMarkup(btns))

@app.on_callback_query(filters.regex("lv_"))
async def cb_leave(c, q):
    await c.leave_chat(int(q.data.split("_")[1]))
    await q.answer("Left!")

# --- BOOTUP ---
async def start_bot():
    await app.start()
    await load_settings() # Memory loading fixed
    print("🚀 Bot Started & Memory Loaded!")
    Thread(target=run_web).start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_bot())
