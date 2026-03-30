import os
import asyncio
import random
import string
import aiohttp
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant, FloodWait
from flask import Flask
from threading import Thread

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG (NO DEFAULT VALUES) ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

DB_CHANNEL = int(os.environ.get("DB_CHANNEL"))
LINK_DB_CHANNEL = int(os.environ.get("LINK_DB_CHANNEL"))

ADMINS = [int(i) for i in os.environ.get("ADMINS").split()]

FSUB_LINK = os.environ.get("FSUB_LINK")
FSUB_ID = int(os.environ.get("FSUB_ID"))

SHORTENERS = [
    {"url": os.environ.get("SHORTENER1_URL"), "api": os.environ.get("SHORTENER1_API")},
    {"url": os.environ.get("SHORTENER2_URL"), "api": os.environ.get("SHORTENER2_API")}
]

BOT_USERNAME = None

app = Client("ASI_ELITE_V4", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot Running"

def run_web():
    web_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# --- UTILS ---

def generate_token():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))

async def get_shortlink(long_url):
    s = random.choice(SHORTENERS)
    try:
        async with aiohttp.ClientSession() as session:
            params = {'api': s['api'], 'url': long_url}
            async with session.get(s['url'], params=params, timeout=10) as res:
                data = await res.json()
                return data.get("shortened_url") or data.get("short_url") or long_url
    except Exception as e:
        logger.error(f"Shortener failed: {e}")
        return long_url

async def delete_after(msg, delay):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception as e:
        logger.error(f"Delete error: {e}")

# --- START HANDLER ---

@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    global BOT_USERNAME

    user_id = message.from_user.id

    # Cache bot username
    if not BOT_USERNAME:
        BOT_USERNAME = (await client.get_me()).username

    # USER TRACKING
    try:
        await client.send_message(LINK_DB_CHANNEL, f"USER:{user_id}")
    except:
        pass

    # FORCE SUB
    try:
        await client.get_chat_member(FSUB_ID, user_id)
    except UserNotParticipant:
        btn = [[InlineKeyboardButton("📢 Join Channel", url=FSUB_LINK)]]
        if len(message.command) > 1:
            btn.append([InlineKeyboardButton("🔄 Try Again",
                url=f"https://t.me/{BOT_USERNAME}?start={message.command[1]}")])
        return await message.reply("❌ Join channel first!", reply_markup=InlineKeyboardMarkup(btn))

    # NORMAL START
    if len(message.command) < 2:
        return await message.reply(
            "👋 Welcome!\nSend file to generate secure link.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛠 Help", callback_data="help"),
                 InlineKeyboardButton("📊 Stats", callback_data="stats")]
            ])
        )

    token = message.command[1]

    # FAST TOKEN FETCH
    try:
        msg_id = int(token.split("_")[1])
        mapping = await client.get_messages(LINK_DB_CHANNEL, msg_id)
    except:
        return await message.reply("❌ Invalid Link")

    if not mapping or not mapping.text or "|" not in mapping.text:
        return await message.reply("❌ Link Expired or Invalid")

    try:
        data = mapping.text.split("|")[1].strip()

        # SINGLE FILE
        if data.startswith("FILE:"):
            file_id = int(data.split(":")[1])
            file = await client.get_messages(DB_CHANNEL, file_id)
            sent = await file.copy(message.chat.id)

            await message.reply("⚠️ File 2 min me delete ho jayegi!")
            asyncio.create_task(delete_after(sent, 120))

        # BATCH
        elif data.startswith("BATCH:"):
            _, start, end = data.split(":")
            start, end = int(start), int(end)

            if end - start > 30:
                return await message.reply("❌ Batch limit 30")

            await message.reply("📦 Sending files...")
            for i in range(start, end + 1):
                try:
                    f = await client.get_messages(DB_CHANNEL, i)
                    s = await f.copy(message.chat.id)
                    asyncio.create_task(delete_after(s, 600))
                    await asyncio.sleep(1.2)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except:
                    continue

    except Exception as e:
        logger.error(e)
        await message.reply("❌ Error occurred")

# --- GENERATE LINK ---

@app.on_message((filters.document | filters.video | filters.audio | filters.photo) & filters.private)
async def gen(client, message):
    if message.from_user.id not in ADMINS:
        return

    global BOT_USERNAME
    if not BOT_USERNAME:
        BOT_USERNAME = (await client.get_me()).username

    db_msg = await message.copy(DB_CHANNEL)

    log_msg = await client.send_message(LINK_DB_CHANNEL, "TEMP")
    token = f"t_{log_msg.id}"

    await log_msg.edit(f"TOKEN:{token} | FILE:{db_msg.id}")

    long_url = f"https://t.me/{BOT_USERNAME}?start={token}"
    short = await get_shortlink(long_url)

    await message.reply(f"🔒 Link:\n{short}")

# --- BATCH ---

@app.on_message(filters.command("batch") & filters.private)
async def batch(client, message):
    if message.from_user.id not in ADMINS:
        return

    global BOT_USERNAME
    if not BOT_USERNAME:
        BOT_USERNAME = (await client.get_me()).username

    try:
        start = int(message.command[1])
        end = int(message.command[2])

        if end - start > 30:
            return await message.reply("❌ Max 30 files")

        log_msg = await client.send_message(LINK_DB_CHANNEL, "TEMP")
        token = f"t_{log_msg.id}"

        await log_msg.edit(f"TOKEN:{token} | BATCH:{start}:{end}")

        link = f"https://t.me/{BOT_USERNAME}?start={token}"
        short = await get_shortlink(link)

        await message.reply(f"📦 Batch Link:\n{short}")

    except:
        await message.reply("Usage: /batch 100 120")

# --- CALLBACK ---

@app.on_callback_query()
async def cb(client, query):
    await query.answer()

    if query.data == "help":
        await query.message.reply("Click link → complete steps → get file")
    elif query.data == "stats":
        await query.message.reply("Bot running smooth 🚀")

# --- START ---

if __name__ == "__main__":
    Thread(target=run_web).start()
    print("🔥 ELITE BOT FINAL RUNNING")
    app.run()
