import os
import asyncio
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
from flask import Flask
from threading import Thread

# ---------------- WEB ----------------
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot Running 🔥"

def run_web():
    web_app.run(host="0.0.0.0", port=10000)

# ---------------- CONFIG ----------------
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

OWNER_ID = int(os.environ.get("OWNER_ID"))
DB_CHANNEL = int(os.environ.get("DB_CHANNEL"))

MONGO_URI = os.environ.get("MONGO_URI")

# ---------------- DB ----------------
mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo.bot
settings_db = db.settings

# ---------------- BOT ----------------
app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_state = {}

# ---------------- SHORTENER ----------------
async def get_shortener():
    data = await settings_db.find_one({"_id": "shortener"})
    if data:
        return data.get("api"), data.get("url")
    return None, None

async def short_link(url):
    api, domain = await get_shortener()

    if not api or not domain:
        return url

    link = f"https://{domain}/api?api={api}&url={url}"

    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(link) as r:
                data = await r.json()
                return data.get("shortenedUrl") or data.get("short_url") or url
    except:
        return url

# ---------------- START ----------------
@app.on_message(filters.command("start"))
async def start(client, message):
    if len(message.command) > 1:
        data = message.command[1]
        ids = data.split("_")

        if len(ids) == 1:
            await client.copy_message(message.chat.id, DB_CHANNEL, int(ids[0]))
        else:
            for i in range(int(ids[0]), int(ids[1]) + 1):
                await client.copy_message(message.chat.id, DB_CHANNEL, i)
                await asyncio.sleep(0.3)
    else:
        await message.reply("Bot Alive 🔥")

# ---------------- POST ----------------
@app.on_message(filters.command("post") & filters.user(OWNER_ID))
async def post(client, message):
    user_state[message.from_user.id] = {"state": "post"}
    await message.reply("📤 Post bhejo (photo/video/text)")

# ---------------- SHORTENER SET ----------------
@app.on_message(filters.command("shortener") & filters.user(OWNER_ID))
async def set_shortener(client, message):
    user_state[message.from_user.id] = {"state": "set_domain"}
    await message.reply("🌐 Domain bhejo (example: gplinks.com)")

# ---------------- DONE ----------------
@app.on_message(filters.command("done") & filters.user(OWNER_ID))
async def done(client, message):
    user_state[message.from_user.id]["state"] = "number"
    await message.reply("🔢 Episode number bhejo")

# ---------------- HANDLER ----------------
@app.on_message(filters.private & filters.user(OWNER_ID))
async def handler(client, message):
    uid = message.from_user.id

    if uid not in user_state:
        return

    state = user_state[uid]["state"]

    # POST SAVE
    if state == "post":
        user_state[uid]["post"] = message
        user_state[uid]["files"] = []
        user_state[uid]["state"] = "mode"

        btn = [[
            InlineKeyboardButton("Single", callback_data="single"),
            InlineKeyboardButton("Batch", callback_data="batch")
        ]]
        await message.reply("Select mode", reply_markup=InlineKeyboardMarkup(btn))

    # FILE SAVE
    elif message.forward_from_chat and message.forward_from_chat.id == DB_CHANNEL:
        user_state[uid]["files"].append(message.forward_from_message_id)
        await message.reply(f"✅ Saved: {message.forward_from_message_id}")

    # EPISODE NUMBER
    elif state == "number":
        num = message.text
        files = user_state[uid]["files"]

        if not files:
            return await message.reply("❌ Pehle file forward karo")

        bot_user = (await app.get_me()).username

        if user_state[uid]["mode"] == "single":
            param = str(files[0])
        else:
            param = f"{files[0]}_{files[-1]}"

        link = f"https://t.me/{bot_user}?start={param}"
        short = await short_link(link)

        btn = [[InlineKeyboardButton(f"Episode {num}", url=short)]]

        user_state[uid]["markup"] = InlineKeyboardMarkup(btn)
        user_state[uid]["state"] = "send"

        send_btn = [[InlineKeyboardButton("🚀 Send", callback_data="send")]]
        await message.reply("Ready 🚀", reply_markup=InlineKeyboardMarkup(send_btn))

    # SET DOMAIN
    elif state == "set_domain":
        user_state[uid]["domain"] = message.text.strip().replace("https://", "").replace("/", "")
        user_state[uid]["state"] = "set_api"
        await message.reply("🔑 API bhejo")

    # SET API
    elif state == "set_api":
        domain = user_state[uid]["domain"]
        api = message.text.strip()

        await settings_db.update_one(
            {"_id": "shortener"},
            {"$set": {"url": domain, "api": api}},
            upsert=True
        )

        user_state[uid]["state"] = None
        await message.reply("✅ Shortener set ho gaya")

# ---------------- CALLBACK ----------------
@app.on_callback_query()
async def cb(client, query):
    uid = query.from_user.id

    if uid not in user_state:
        return

    data = query.data

    if data == "single":
        user_state[uid]["mode"] = "single"
        await query.message.edit("1 file forward karo phir /done")

    elif data == "batch":
        user_state[uid]["mode"] = "batch"
        await query.message.edit("multiple files forward karo phir /done")

    elif data == "send":
        post = user_state[uid]["post"]
        markup = user_state[uid]["markup"]

        await post.copy(DB_CHANNEL, reply_markup=markup)
        await query.message.edit("✅ Posted")

# ---------------- RUN ----------------
if __name__ == "__main__":
    Thread(target=run_web).start()
    app.run()
