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
EXTRA_CHANNEL = -1003872932495 # This is our Memory Channel

app = Client("pro_mem_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Global Data
shortener_db = [] # List of dicts: {"url": "", "api": ""}
user_data = {}

# --- MEMORY FUNCTIONS (Using EXTRA_CHANNEL) ---

async def save_settings():
    """Saves the current shortener_db to EXTRA_CHANNEL as a JSON message."""
    data_str = f"#BOT_SETTINGS\n{json.dumps(shortener_db)}"
    # Search and delete old settings message to keep it clean
    async for msg in app.search_messages(EXTRA_CHANNEL, query="#BOT_SETTINGS"):
        await msg.delete()
    await app.send_message(EXTRA_CHANNEL, data_str)

async def load_settings():
    """Loads settings from EXTRA_CHANNEL on startup."""
    global shortener_db
    async for msg in app.search_messages(EXTRA_CHANNEL, query="#BOT_SETTINGS"):
        try:
            content = msg.text.split("\n", 1)[1]
            shortener_db = json.loads(content)
            print("Settings loaded from Channel Memory!")
            break
        except: continue

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
        return m.status != enums.ChatMemberStatus.LEFT
    except: return False

# --- SETTINGS HANDLERS (Priority Group -1) ---

@app.on_message(filters.command("setting") & filters.user(ALLOWED_USERS))
async def show_settings(c, m):
    text = (
        "**🛠 Bot Control Panel**\n\n"
        "1. `/add_shortener` - Naya account jodein\n"
        "2. `/list_shortener` - Accounts manage/remove karein\n"
        "3. `/select_admin_channel` - Channel se nikalne ke liye\n"
        "4. `/force_sub` - FSub setup (Current: Extra Channel)\n\n"
        f"**Active Accounts:** {len(shortener_db)}"
    )
    await m.reply(text)

@app.on_message(filters.command("add_shortener") & filters.user(ALLOWED_USERS))
async def add_sh_start(c, m):
    user_data[m.from_user.id] = {"state": "INPUT_URL"}
    await m.reply("Step 1: Website Domain bhejein (e.g. `gplinks.com`):")

@app.on_message(filters.command("list_shortener") & filters.user(ALLOWED_USERS))
async def list_sh(c, m):
    if not shortener_db: return await m.reply("Koi account nahi mila. `/add_shortener` karein.")
    for i, sh in enumerate(shortener_db):
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Remove Account", callback_data=f"rem_sh_{i}")]])
        await m.reply(f"Account {i+1}:\nURL: `{sh['url']}`\nAPI: `{sh['api'][:10]}...`", reply_markup=btn)

@app.on_callback_query(filters.regex("rem_sh_"))
async def remove_sh(c, q: CallbackQuery):
    idx = int(q.data.split("_")[2])
    shortener_db.pop(idx)
    await save_settings()
    await q.message.edit("✅ Account removed and memory updated!")

# --- INPUT CAPTURING (Prevents 'Post' Conflict) ---
@app.on_message(filters.private & filters.user(ALLOWED_USERS), group=-1)
async def handle_all_inputs(c, m: Message):
    uid = m.from_user.id
    state = user_data.get(uid, {}).get("state")
    if not state: return # Let other handlers work

    if state == "INPUT_URL":
        user_data[uid]["new_url"] = m.text.strip()
        user_data[uid]["state"] = "INPUT_API"
        await m.reply("URL Set! Ab **API Token** bhejein:")
        m.stop_propagation() # Stop it from being treated as a post

    elif state == "INPUT_API":
        api = m.text.strip()
        shortener_db.append({"url": user_data[uid]["new_url"], "api": api})
        await save_settings() # Save to Extra Channel
        user_data[uid] = {}
        await m.reply("✅ Success! Account saved in Bot Memory.")
        m.stop_propagation()

    elif state == "WAIT_SINGLE":
        if m.forward_from_chat and m.forward_from_chat.id == DB_CHANNEL:
            user_data[uid]["fid"] = m.forward_from_message_id
            user_data[uid]["state"] = "WAIT_NUM"
            await m.reply("File OK! Ab Episode Number likho:")
        m.stop_propagation()

    elif state == "WAIT_START":
        if m.forward_from_chat and m.forward_from_chat.id == DB_CHANNEL:
            user_data[uid]["sid"] = m.forward_from_message_id
            user_data[uid]["state"] = "WAIT_END"
            await m.reply("Start File OK! Ab **End File** forward karo.")
        m.stop_propagation()

    elif state == "WAIT_END":
        if m.forward_from_chat and m.forward_from_chat.id == DB_CHANNEL:
            user_data[uid]["eid"] = m.forward_from_message_id
            user_data[uid]["state"] = "WAIT_NUM"
            await m.reply("End File OK! Ab Episode Range likho (e.g. 01-10):")
        m.stop_propagation()

    elif state == "WAIT_NUM":
        user_data[uid]["num"] = m.text
        # Ask which shortener to use
        btns = [[InlineKeyboardButton(sh['url'], callback_data=f"use_{i}")] for i, sh in enumerate(shortener_db)]
        if not btns:
            await m.reply("Error: Koi shortener account nahi mila! `/add_shortener` karein.")
        else:
            await m.reply("Kaunsa shortener account use karein?", reply_markup=InlineKeyboardMarkup(btns))
        user_data[uid]["state"] = None
        m.stop_propagation()

# --- MAIN POST PROCESSOR ---
@app.on_message(filters.private & filters.user(ALLOWED_USERS))
async def post_handler(c, m):
    if m.text and m.text.startswith("/"): return
    user_data[m.from_user.id] = {"post": m, "selected_chats": []}
    btns = [[InlineKeyboardButton("Link", callback_data="set_s"), 
             InlineKeyboardButton("Batch Link", callback_data="set_b")]]
    await m.reply("Post detected. Mode chunein:", reply_markup=InlineKeyboardMarkup(btns))

@app.on_callback_query()
async def cb_logic(c, q: CallbackQuery):
    uid = q.from_user.id
    data = q.data

    if data == "set_s":
        user_data[uid]["mode"], user_data[uid]["state"] = "s", "WAIT_SINGLE"
        await q.message.edit("Database se file forward karein.")
    elif data == "set_b":
        user_data[uid]["mode"], user_data[uid]["state"] = "b", "WAIT_START"
        await q.message.edit("Database se Start file forward karein.")
    
    elif data.startswith("use_"):
        idx = int(data.split("_")[1])
        sh = shortener_db[idx]
        await q.message.edit("⚡ Generating Link...")
        
        bot_un = (await c.get_me()).username
        path = f"{user_data[uid]['fid']}" if user_data[uid]['mode'] == "s" else f"{user_data[uid]['sid']}_{user_data[uid]['eid']}"
        
        long_url = f"https://t.me/{bot_un}?start={path}"
        short_url = await get_shortlink(long_url, sh['url'], sh['api'])
        
        user_data[uid]["markup"] = InlineKeyboardMarkup([[InlineKeyboardButton(f"Episode {user_data[uid]['num']}", url=short_url)]])
        
        # Show Channels
        btns = []
        async for d in c.get_dialogs():
            if d.chat.type in [enums.ChatType.CHANNEL, enums.ChatType.SUPERGROUP]:
                btns.append([InlineKeyboardButton(d.chat.title, callback_data=f"target_{d.chat.id}")])
        btns.append([InlineKeyboardButton("🚀 CONFIRM & SEND", callback_data="broadcast")])
        await q.message.edit("Channels select karke Send dabayein:", reply_markup=InlineKeyboardMarkup(btns))

    elif data.startswith("target_"):
        cid = int(data.split("_")[1])
        if cid not in user_data[uid]["selected_chats"]: user_data[uid]["selected_chats"].append(cid)
        else: user_data[uid]["selected_chats"].remove(cid)
        await q.answer("Updated")

    elif data == "broadcast":
        p, markup = user_data[uid]["post"], user_data[uid]["markup"]
        for cid in user_data[uid]["selected_chats"]:
            try: await p.copy(cid, reply_markup=markup)
            except: pass
        await q.message.edit("✅ Mission Accomplished! Post sent.")

# --- USER SIDE & START ---
@app.on_message(filters.command("start") & filters.private)
async def start_logic(c, m):
    if len(m.text.split()) > 1:
        if not await is_subscribed(m.from_user.id):
            invite = (await c.get_chat(EXTRA_CHANNEL)).invite_link
            return await m.reply("Join channel to get files!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel", url=invite)]]))
        
        code = m.text.split()[1]
        try:
            if "_" in code:
                s, e = map(int, code.split("_"))
                for mid in range(s, e + 1):
                    await c.copy_message(m.chat.id, DB_CHANNEL, mid)
                    await asyncio.sleep(0.5)
            else:
                await c.copy_message(m.chat.id, DB_CHANNEL, int(code))
        except: await m.reply("File expired or deleted from DB.")
        return
    await m.reply("Welcome! Send a post to start.")

@app.on_message(filters.command("select_admin_channel") & filters.user(OWNER_ID))
async def admin_ch(c, m):
    btns = [[InlineKeyboardButton(d.chat.title, callback_data=f"lv_{d.chat.id}")] async for d in c.get_dialogs() if d.chat.type == enums.ChatType.CHANNEL]
    await m.reply("Click to make bot leave channel:", reply_markup=InlineKeyboardMarkup(btns))

@app.on_callback_query(filters.regex("lv_"))
async def leave_cb(c, q):
    await c.leave_chat(int(q.data.split("_")[1]))
    await q.answer("Bot Left!")

# Startup
async def main():
    await app.start()
    await load_settings() # Memory load
    print("Bot is ready!")
    run_web_thread = Thread(target=run_web)
    run_web_thread.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
