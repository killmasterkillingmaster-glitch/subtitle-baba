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
def health_check(): return "Bot is running perfectly!"
def run_web(): web_app.run(host="0.0.0.0", port=10000)

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", "12345"))
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")

OWNER_ID = 5351848105
ALLOWED_USERS = [5351848105, 5344078567]
DB_CHANNEL = -1003143681742
EXTRA_CHANNEL = -1003872932495 # Memory Channel

app = Client("pro_bot_final", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Global Data
shortener_db = [] 
user_data = {}

# --- MEMORY FUNCTIONS (Using EXTRA_CHANNEL) ---

async def save_settings():
    """Saves the current shortener_db to EXTRA_CHANNEL as a JSON message."""
    data_str = f"#BOT_SETTINGS\n{json.dumps(shortener_db)}"
    try:
        # Purani settings delete karein
        async for msg in app.search_messages(EXTRA_CHANNEL, query="#BOT_SETTINGS"):
            await msg.delete()
        # Nayi settings bhejein
        await app.send_message(EXTRA_CHANNEL, data_str)
    except Exception as e:
        print(f"Error saving settings: {e}")

async def load_settings():
    """Loads settings from EXTRA_CHANNEL on startup."""
    global shortener_db
    try:
        # Force Pyrogram to resolve the peer before searching
        await app.get_chat(EXTRA_CHANNEL)
        async for msg in app.search_messages(EXTRA_CHANNEL, query="#BOT_SETTINGS"):
            if msg.text:
                content = msg.text.split("\n", 1)[1]
                shortener_db = json.loads(content)
                print("✅ Settings Loaded Successfully!")
                break
    except Exception as e:
        print(f"⚠️ Error loading settings (Maybe first run?): {e}")

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

# --- COMMANDS ---

@app.on_message(filters.command("setting") & filters.user(ALLOWED_USERS))
async def show_settings(c, m):
    text = (
        "**🛠 Bot Control Panel**\n\n"
        "1. `/add_shortener` - Naya account jodein\n"
        "2. `/list_shortener` - Accounts Manage/Remove karein\n"
        "3. `/select_admin_channel` - Leave Channel\n\n"
        f"**Total Accounts:** `{len(shortener_db)}`"
    )
    await m.reply(text)

@app.on_message(filters.command("add_shortener") & filters.user(ALLOWED_USERS))
async def add_sh_start(c, m):
    user_data[m.from_user.id] = {"state": "INPUT_URL"}
    await m.reply("Step 1: Website Domain bhejein (Example: `gplinks.com`):")

@app.on_message(filters.command("list_shortener") & filters.user(ALLOWED_USERS))
async def list_sh(c, m):
    if not shortener_db: return await m.reply("Koi account add nahi hai. `/add_shortener` use karein.")
    for i, sh in enumerate(shortener_db):
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Remove Account", callback_data=f"rem_sh_{i}")]])
        await m.reply(f"📍 Account {i+1}:\nURL: `{sh['url']}`\nAPI: `{sh['api'][:10]}...`", reply_markup=btn)

@app.on_callback_query(filters.regex("rem_sh_"))
async def remove_sh(c, q: CallbackQuery):
    idx = int(q.data.split("_")[2])
    shortener_db.pop(idx)
    await save_settings()
    await q.message.edit("✅ Account removed and Memory updated!")

# --- INPUT HANDLERS (Priority Group -1 to avoid Post Conflict) ---

@app.on_message(filters.private & filters.user(ALLOWED_USERS), group=-1)
async def handle_all_inputs(c, m: Message):
    uid = m.from_user.id
    state = user_data.get(uid, {}).get("state")
    if not state: return

    # Shortener Link/API Setup
    if state == "INPUT_URL":
        user_data[uid]["new_url"] = m.text.replace("https://", "").replace("http://", "").split('/')[0]
        user_data[uid]["state"] = "INPUT_API"
        await m.reply("URL Saved! Ab **API Token** bhejein:")
        m.stop_propagation()
    elif state == "INPUT_API":
        api = m.text.strip()
        shortener_db.append({"url": user_data[uid]["new_url"], "api": api})
        await save_settings()
        user_data[uid] = {}
        await m.reply("✅ Shortener Account Saved Successfully!")
        m.stop_propagation()

    # Episode Number Setup
    elif state == "WAIT_NUM":
        user_data[uid]["num"] = m.text
        btns = [[InlineKeyboardButton(sh['url'], callback_data=f"use_{i}")] for i, sh in enumerate(shortener_db)]
        if not btns:
            await m.reply("Error: Pehle ek shortener add karo `/add_shortener` se.")
        else:
            await m.reply("Kaunsa shortener account use karna hai?", reply_markup=InlineKeyboardMarkup(btns))
        user_data[uid]["state"] = None
        m.stop_propagation()

# --- FILE CAPTURE HANDLER (Priority Group 0) ---
@app.on_message(filters.private & filters.user(ALLOWED_USERS) & filters.forwarded, group=0)
async def file_capture(c, m: Message):
    uid = m.from_user.id
    state = user_data.get(uid, {}).get("state")
    if not state: return

    if m.forward_from_chat.id != DB_CHANNEL:
        return await m.reply("Sirf Database Channel se file forward karein!")

    if state == "WAIT_SINGLE":
        user_data[uid]["fid"] = m.forward_from_message_id
        user_data[uid]["state"] = "WAIT_NUM"
        await m.reply("File OK! Ab Episode Number bhejein (e.g. 06):")
    elif state == "WAIT_START":
        user_data[uid]["sid"] = m.forward_from_message_id
        user_data[uid]["state"] = "WAIT_END"
        await m.reply("Start File OK! Ab **Aakhri (End)** file forward karein.")
    elif state == "WAIT_END":
        user_data[uid]["eid"] = m.forward_from_message_id
        user_data[uid]["state"] = "WAIT_NUM"
        await m.reply("End File OK! Ab Episode Range bhejein (e.g. 01-10):")

# --- MAIN POST HANDLER ---
@app.on_message(filters.private & filters.user(ALLOWED_USERS))
async def post_receiver(c, m: Message):
    if m.text and m.text.startswith("/"): return
    user_data[m.from_user.id] = {"post": m, "selected_chats": []}
    btns = [[InlineKeyboardButton("Link", callback_data="set_s"), 
             InlineKeyboardButton("Batch Link", callback_data="set_b")]]
    await m.reply("Post received. Mode select karein:", reply_markup=InlineKeyboardMarkup(btns))

@app.on_callback_query()
async def cb_manager(c, q: CallbackQuery):
    uid = q.from_user.id
    data = q.data

    if data == "set_s":
        user_data[uid]["mode"], user_data[uid]["state"] = "s", "WAIT_SINGLE"
        await q.message.edit("Database se 1 file forward karein.")
    elif data == "set_b":
        user_data[uid]["mode"], user_data[uid]["state"] = "b", "WAIT_START"
        await q.message.edit("Database se Start file forward karein.")
    
    elif data.startswith("use_"):
        idx = int(data.split("_")[1])
        sh = shortener_db[idx]
        await q.message.edit("⚡ Generating Short Link...")
        
        bot_un = (await c.get_me()).username
        path = f"{user_data[uid]['fid']}" if user_data[uid]['mode'] == "s" else f"{user_data[uid]['sid']}_{user_data[uid]['eid']}"
        long_url = f"https://t.me/{bot_un}?start={path}"
        short_url = await get_shortlink(long_url, sh['url'], sh['api'])
        
        user_data[uid]["markup"] = InlineKeyboardMarkup([[InlineKeyboardButton(f"Episode {user_data[uid]['num']}", url=short_url)]])
        
        # Admin Channels list
        btns = []
        async for d in c.get_dialogs():
            if d.chat.type in [enums.ChatType.CHANNEL, enums.ChatType.SUPERGROUP]:
                btns.append([InlineKeyboardButton(d.chat.title, callback_data=f"target_{d.chat.id}")])
        btns.append([InlineKeyboardButton("🚀 CONFIRM & BROADCAST", callback_data="broadcast")])
        await q.message.edit("Channels select karke Broadcast dabayein:", reply_markup=InlineKeyboardMarkup(btns))

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
        await q.message.edit("✅ Success! Post sent to channels.")

# --- USER START ---
@app.on_message(filters.command("start") & filters.private)
async def start_logic(c, m):
    if len(m.text.split()) > 1:
        if not await is_subscribed(m.from_user.id):
            invite = (await c.get_chat(EXTRA_CHANNEL)).invite_link
            return await m.reply("Join channel to access files!", 
                               reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel", url=invite)]]))
        
        code = m.text.split()[1]
        try:
            if "_" in code:
                s, e = map(int, code.split("_"))
                for mid in range(s, e + 1):
                    await c.copy_message(m.chat.id, DB_CHANNEL, mid)
                    await asyncio.sleep(0.5)
            else:
                await c.copy_message(m.chat.id, DB_CHANNEL, int(code))
        except: await m.reply("File expired or DB error.")
        return
    await m.reply("Bhai, post bhejo setup karne ke liye.")

@app.on_message(filters.command("select_admin_channel") & filters.user(OWNER_ID))
async def leave_mgr(c, m):
    btns = [[InlineKeyboardButton(d.chat.title, callback_data=f"lv_{d.chat.id}")] async for d in c.get_dialogs() if d.chat.type == enums.ChatType.CHANNEL]
    await m.reply("Click to leave channel:", reply_markup=InlineKeyboardMarkup(btns))

@app.on_callback_query(filters.regex("lv_"))
async def leave_cb(c, q):
    await c.leave_chat(int(q.data.split("_")[1]))
    await q.answer("Left!")

# --- RUN BOT ---
async def main():
    await app.start()
    await load_settings() # Resolved Peer issue fixed here
    print("Bot is Alive & Settings Loaded!")
    Thread(target=run_web).start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
