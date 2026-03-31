import os
import asyncio
import aiohttp
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread
from pymongo import MongoClient
from datetime import datetime

# --- WEB SERVER ---
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot is running perfectly on Render!"

def run_web():
    web_app.run(host="0.0.0.0", port=10000)

# --- CONFIG ---
API_ID = 12345  # Your API_ID
API_HASH = "your_api_hash"
BOT_TOKEN = "your_bot_token"
OWNER_ID = 5351848105
DB_CHANNEL = -1003143681742

# --- MongoDB (HARD CODED for now) ---
MONGO_URI = "mongodb+srv://aasifhusenaasifkhan_db_user:64CtKuQjWL0EzYMO@botcluster.v4land1.mongodb.net/?retryWrites=true&w=majority"
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["BotDatabase"]
collection = db["Posts"]

# --- Bot Settings ---
bot_settings = {
    "shortener_api": "",
    "shortener_url": "",
    "fsub_channels": [-1003872932495]  # Channels for forced subscription
}

user_data = {}

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- SHORTENER FUNCTION ---
async def get_shortlink(long_url):
    if not bot_settings["shortener_api"] or not bot_settings["shortener_url"]:
        return long_url
    domain = bot_settings["shortener_url"].lower()
    if "gplinks" in domain:
        api_url = f"https://api.gplinks.com/api?api={bot_settings['shortener_api']}&url={long_url}"
    else:
        api_url = f"https://{domain}/api?api={bot_settings['shortener_api']}&url={long_url}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as res:
                data = await res.json()
                return data.get("shortenedUrl") or data.get("short_url") or data.get("shortened_url") or data.get("url") or long_url
    except:
        return long_url

# --- Subscription Check ---
async def is_subscribed(user_id):
    for chat_id in bot_settings["fsub_channels"]:
        try:
            member = await app.get_chat_member(chat_id, user_id)
            if member.status == enums.ChatMemberStatus.LEFT:
                return False
        except:
            continue
    return True

# --- START ---
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    await message.reply("Bhai, main zinda hu! Commands dekhne ke liye /setting dabao.")

# --- SETTINGS ---
@app.on_message(filters.command("setting") & filters.user([OWNER_ID]))
async def settings_cmd(client, message):
    await message.reply("""
⚙️ Bot Commands
/post - New post
/link_shortener - Shortener setup
/link - Generate link
/setting - List commands
""")

# --- POST ---
@app.on_message(filters.command("post") & filters.user([OWNER_ID]) & filters.private)
async def post_command(client, message):
    uid = message.from_user.id
    user_data.setdefault(uid, {})
    user_data[uid]["state"] = "waiting_for_post"
    await message.reply("📸 Apna Post bhejo (Photo, Video, ya Text)")

# --- SHORTENER SETUP ---
@app.on_message(filters.command("link_shortener") & filters.user([OWNER_ID]))
async def shortener_setup(client, message):
    uid = message.from_user.id
    user_data.setdefault(uid, {})
    user_data[uid]["state"] = "set_url"
    await message.reply("🌐 Shortener Domain bhejo (e.g., gplinks.com)")

# --- LINK GENERATION ---
@app.on_message(filters.command("link") & filters.user([OWNER_ID]))
async def get_link_command(client, message):
    await message.reply("✅ Done? Click the button:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Done", callback_data="gen_link")]]))

# --- MASTER INPUT ---
@app.on_message(filters.private & filters.user([OWNER_ID]) & ~filters.command(["start","link","link_shortener","setting","post"]))
async def master_input_handler(client, message):
    uid = message.from_user.id
    if uid not in user_data:
        return
    state = user_data[uid].get("state")
    
    if state == "waiting_for_post":
        # Save post to MongoDB
        post_doc = {
            "user_id": uid,
            "message_id": message.message_id,
            "chat_id": message.chat.id,
            "content_type": message.media.value if message.media else "text",
            "text": message.text or "",
            "timestamp": datetime.utcnow()
        }
        collection.insert_one(post_doc)
        user_data[uid]["state"] = None
        btns = [[InlineKeyboardButton("Single Link", callback_data="set_single"), InlineKeyboardButton("Batch Link", callback_data="set_batch")]]
        await message.reply("✅ Post saved! Option choose karo:", reply_markup=InlineKeyboardMarkup(btns))
        
    elif state == "set_url":
        bot_settings["shortener_url"] = message.text.strip().replace("https://","").replace("http://","").replace("/","")
        user_data[uid]["state"] = "set_api"
        await message.reply(f"Domain set: `{bot_settings['shortener_url']}`\nAb API bhejo:")
        
    elif state == "set_api":
        bot_settings["shortener_api"] = message.text.strip()
        user_data[uid]["state"] = None
        await message.reply("✅ Shortener set ho gaya!")

# --- CALLBACK HANDLER ---
@app.on_callback_query(filters.regex("^(set_single|set_batch|gen_link)"))
async def callbacks(client, query):
    uid = query.from_user.id
    data = query.data
    if data == "set_single":
        user_data[uid]["mode"] = "single"
        await query.message.edit("Database channel se 1 episode forward karo, fir `/link`")
    elif data == "set_batch":
        user_data[uid]["mode"] = "batch"
        await query.message.edit("Start & End episode forward karo, fir `/link`")
    elif data == "gen_link":
        user_data[uid]["state"] = "waiting_num"
        await query.message.edit("Episode Number daalo:")

# --- RUN BOT ---
if __name__ == "__main__":
    Thread(target=run_web).start()
    print("Bot Started...")
    app.run()
