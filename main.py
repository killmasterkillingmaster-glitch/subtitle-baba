import os
import asyncio
import aiohttp
import json
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from flask import Flask
from threading import Thread
from pyrogram.errors import FloodWait

# --- WEB SERVER (RENDER KEEP ALIVE) ---
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot running ✅"

def run_web():
    web_app.run(host="0.0.0.0", port=10000)

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID", "12345"))
API_HASH = os.environ.get("API_HASH", "your_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_token")

OWNER_ID = 5351848105
ALLOWED_USERS = [5351848105, 5344078567]

DB_CHANNEL = -1003143681742
EXTRA_CHANNEL = -1003872932495

# ⚡ MANUAL CHANNEL LIST (FAST + SAFE)
TARGET_CHANNELS = [
    -100XXXXXXXXXX,
    -100YYYYYYYYYY
]

app = Client("pro_mem_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

shortener_db = []
user_data = {}

# --- MEMORY SYSTEM ---
async def save_settings():
    data = f"#BOT_SETTINGS\n{json.dumps(shortener_db)}"

    msgs = []
    async for m in app.search_messages(EXTRA_CHANNEL, query="#BOT_SETTINGS"):
        msgs.append(m)

    for m in msgs:
        try:
            await m.delete()
        except:
            pass

    await app.send_message(EXTRA_CHANNEL, data)

async def load_settings():
    global shortener_db
    async for m in app.search_messages(EXTRA_CHANNEL, query="#BOT_SETTINGS"):
        try:
            shortener_db = json.loads(m.text.split("\n", 1)[1])
            print("✅ Memory Loaded")
            break
        except:
            continue

# --- SHORTENER ---
async def get_shortlink(url, site, api):
    try:
        api_url = f"https://{site}/api?api={api}&url={url}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as res:
                data = await res.json()
                return data.get("shortenedUrl", url)
    except:
        return url

# --- SUB CHECK ---
async def is_subscribed(user_id):
    try:
        m = await app.get_chat_member(EXTRA_CHANNEL, user_id)
        return m.status != enums.ChatMemberStatus.LEFT
    except:
        return False

# --- SETTINGS ---
@app.on_message(filters.command("setting") & filters.user(ALLOWED_USERS))
async def settings(c, m):
    await m.reply(f"⚙️ Active Shorteners: {len(shortener_db)}")

@app.on_message(filters.command("add_shortener") & filters.user(ALLOWED_USERS))
async def add_sh(c, m):
    user_data[m.from_user.id] = {"state": "URL"}
    await m.reply("Domain bhejo (example: gplinks.com)")

@app.on_message(filters.command("list_shortener") & filters.user(ALLOWED_USERS))
async def list_sh(c, m):
    if not shortener_db:
        return await m.reply("No accounts")

    for i, sh in enumerate(shortener_db):
        btn = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Remove", callback_data=f"rem_{i}")]]
        )
        await m.reply(f"{sh['url']}", reply_markup=btn)

@app.on_callback_query(filters.regex("rem_"))
async def remove_sh(c, q):
    idx = int(q.data.split("_")[1])
    shortener_db.pop(idx)
    await save_settings()
    await q.message.edit("Removed ✅")

# --- INPUT HANDLER ---
@app.on_message(filters.private & filters.user(ALLOWED_USERS), group=-1)
async def input_handler(c, m: Message):
    uid = m.from_user.id
    state = user_data.get(uid, {}).get("state")

    if not state:
        return

    if state == "URL":
        user_data[uid]["url"] = m.text.strip()
        user_data[uid]["state"] = "API"
        await m.reply("API bhejo")
        return

    elif state == "API":
        shortener_db.append({
            "url": user_data[uid]["url"],
            "api": m.text.strip()
        })
        await save_settings()
        user_data[uid] = {}
        await m.reply("Saved ✅")
        return

    elif state == "WAIT_SINGLE":
        if m.forward_from_chat and m.forward_from_chat.id == DB_CHANNEL:
            user_data[uid]["fid"] = m.forward_from_message_id
            user_data[uid]["state"] = "WAIT_NUM"
            await m.reply("Episode number bhejo")
        return

    elif state == "WAIT_START":
        if m.forward_from_chat and m.forward_from_chat.id == DB_CHANNEL:
            user_data[uid]["sid"] = m.forward_from_message_id
            user_data[uid]["state"] = "WAIT_END"
            await m.reply("End file bhejo")
        return

    elif state == "WAIT_END":
        if m.forward_from_chat and m.forward_from_chat.id == DB_CHANNEL:
            user_data[uid]["eid"] = m.forward_from_message_id
            user_data[uid]["state"] = "WAIT_NUM"
            await m.reply("Range bhejo (01-10)")
        return

    elif state == "WAIT_NUM":
        user_data[uid]["num"] = m.text

        if not shortener_db:
            return await m.reply("Add shortener first")

        btns = [
            [InlineKeyboardButton(sh['url'], callback_data=f"use_{i}")]
            for i, sh in enumerate(shortener_db)
        ]

        await m.reply("Shortener select karo", reply_markup=InlineKeyboardMarkup(btns))
        user_data[uid]["state"] = None
        return

# --- POST HANDLER ---
@app.on_message(filters.private & filters.user(ALLOWED_USERS))
async def post_handler(c, m):
    if user_data.get(m.from_user.id, {}).get("state"):
        return

    if m.text and m.text.startswith("/"):
        return

    user_data[m.from_user.id] = {"post": m}

    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("Single", callback_data="single"),
         InlineKeyboardButton("Batch", callback_data="batch")]
    ])

    await m.reply("Mode choose karo", reply_markup=btn)

# --- CALLBACK ---
@app.on_callback_query()
async def cb(c, q: CallbackQuery):
    uid = q.from_user.id
    data = q.data

    if data == "single":
        user_data[uid]["mode"] = "s"
        user_data[uid]["state"] = "WAIT_SINGLE"
        await q.message.edit("File forward karo")

    elif data == "batch":
        user_data[uid]["mode"] = "b"
        user_data[uid]["state"] = "WAIT_START"
        await q.message.edit("Start file bhejo")

    elif data.startswith("use_"):
        idx = int(data.split("_")[1])
        sh = shortener_db[idx]

        await q.message.edit("Generating link...")

        bot_un = (await c.get_me()).username

        if user_data[uid]["mode"] == "s":
            path = str(user_data[uid]["fid"])
        else:
            path = f"{user_data[uid]['sid']}_{user_data[uid]['eid']}"

        long_url = f"https://t.me/{bot_un}?start={path}"
        short = await get_shortlink(long_url, sh["url"], sh["api"])

        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Episode {user_data[uid]['num']}", url=short)]
        ])

        # SEND DIRECT (FAST)
        sent = 0
        for cid in TARGET_CHANNELS:
            try:
                await user_data[uid]["post"].copy(cid, reply_markup=markup)
                sent += 1
                await asyncio.sleep(1)
            except FloodWait as e:
                await asyncio.sleep(e.value)

        await q.message.edit(f"✅ Sent in {sent} channels")

# --- START ---
@app.on_message(filters.command("start") & filters.private)
async def start(c, m):
    if len(m.text.split()) > 1:

        if not await is_subscribed(m.from_user.id):
            chat = await c.get_chat(EXTRA_CHANNEL)
            invite = chat.invite_link or "https://t.me/yourchannel"

            return await m.reply(
                "Join first",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Join", url=invite)]]
                )
            )

        code = m.text.split()[1]

        try:
            if "_" in code:
                s, e = map(int, code.split("_"))
                for i in range(s, e + 1):
                    await c.copy_message(m.chat.id, DB_CHANNEL, i)
                    await asyncio.sleep(0.5)
            else:
                await c.copy_message(m.chat.id, DB_CHANNEL, int(code))
        except:
            await m.reply("File not found")

        return

    await m.reply("Send post")

# --- MAIN ---
async def main():
    await app.start()
    await load_settings()

    Thread(target=run_web).start()
    print("🔥 BOT STARTED")

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
