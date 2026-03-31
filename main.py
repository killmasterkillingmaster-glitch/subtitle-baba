import os
import random
import asyncio
from datetime import datetime, timedelta
from threading import Thread

import aiohttp
from flask import Flask
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

# ---------------- CONFIG ----------------
OWNER_ID = 5351848105
ALLOWED_USERS = [5344078567]
DB_CHANNEL = 5344078567
ALLOWED_GROUP = -1003899919015

# Port for Web Server (Render/Koyeb compat)
PORT = int(os.environ.get("PORT", 10000))

# API credentials
API_ID = int(os.environ.get("API_ID", "123456"))
API_HASH = os.environ.get("API_HASH", "abcdef123456")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "123456:ABCDEF")

# ---------------- MONGO SETUP ----------------
MONGO_URI = "mongodb+srv://aasifhusenaasifkhan_db_user:64CtKuQjWL0EzYMO@botcluster.v4land1.mongodb.net/?retryWrites=true&w=majority"
DB_NAME = "subtitle_baba"

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

posts_col = db.posts
premium_col = db.premium
shortners_col = db.shortners
channels_col = db.channels

# ---------------- FLASK KEEP-ALIVE ----------------
web_app = Flask(__name__)

@web_app.route("/")
def health_check():
    return "Bot is running perfectly!"

def run_web():
    web_app.run(host="0.0.0.0", port=PORT)

Thread(target=run_web, daemon=True).start()

# ---------------- PYROGRAM CLIENT ----------------
app = Client("anime_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ---------------- UTILITY FUNCTIONS ----------------
def is_owner(user_id):
    return user_id == OWNER_ID

def is_allowed(user_id):
    return user_id in ALLOWED_USERS or is_owner(user_id)

async def is_premium(user_id):
    member = await premium_col.find_one({"user_id": user_id})
    if not member:
        return False
    expire = member.get("expires_at")
    if expire and datetime.utcnow() > expire:
        await premium_col.delete_one({"user_id": user_id})
        return False
    return True

# MULTI-SHORTENER API LOGIC
async def get_short_link(long_url):
    # Fetch all shorteners from DB
    cursor = shortners_col.find({})
    shorteners = await cursor.to_list(length=100)
    
    if not shorteners:
        return long_url # Agar DB me koi shortener nahi hai, direct link de do
        
    # Randomly select one shortener account (Distributes traffic)
    selected = random.choice(shorteners)
    domain = selected['domain']
    api_key = selected['api_key']
    
    # API Call format (Works for 90% of shorteners like GPLinks, Shareus, etc.)
    api_url = f"https://{domain}/api?api={api_key}&url={long_url}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                data = await response.json()
                if data.get("status") == "success" or data.get("shortenedUrl"):
                    return data.get("shortenedUrl")
                return long_url
    except Exception as e:
        print(f"Shortener API Error: {e}")
        return long_url

# ---------------- COMMANDS ----------------

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    await message.reply_text("Hello 🤗 Anime Bot is Active!")

@app.on_message(filters.command("post") & filters.private)
async def post_cmd(client, message: Message):
    if not is_allowed(message.from_user.id):
        return
    if not message.reply_to_message:
        await message.reply_text("Please reply to a document/image/video to create a post.")
        return
        
    post = message.reply_to_message
    result = await posts_col.insert_one({
        "file_id": post.id,
        "chat_id": post.chat.id,
        "created_at": datetime.utcnow()
    })
    
    # Adding basic Send buttons as per your documentation
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Send to DB Channel", callback_data=f"send_{result.inserted_id}")]
    ])
    await message.reply_text(f"Post received 🤗\nPost ID: `{result.inserted_id}`", reply_markup=keyboard)

@app.on_message(filters.command("getlink") & filters.private)
async def getlink_cmd(client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("Usage: `/getlink <episode_number>`")
        return
    try:
        episode_num = message.command[1]
        
        # User ki long URL (Yaha aap apne telegram bot ki start link laga sakte ho jisme file id pass ho)
        # Abhi ke liye ek dummy telegram link le raha hu jisko short karna hai
        long_url = f"https://t.me/your_bot_username?start=ep_{episode_num}"
        
        # Premium Check
        if await is_premium(message.from_user.id):
            final_url = long_url # Premium walo ko direct link
            msg = "💎 Premium User! Here is your direct link:"
        else:
            final_url = await get_short_link(long_url) # Normal walo ko short link
            msg = "Here is your episode link:"
            
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Watch Episode {episode_num}", url=final_url)]
        ])
        await message.reply_text(msg, reply_markup=keyboard)
    except Exception as e:
        await message.reply_text(f"Error: {e}")

# ----- SHORTENER MANAGEMENT (Owner Only) -----
@app.on_message(filters.command("addshortner") & filters.private)
async def add_shortner_cmd(client, message: Message):
    if not is_owner(message.from_user.id):
        return
    if len(message.command) < 3:
        await message.reply_text("Usage: `/addshortner <domain.com> <api_key>`\nExample: `/addshortner gplinks.in 12345abcde`")
        return
        
    domain = message.command[1]
    api_key = message.command[2]
    
    await shortners_col.update_one(
        {"domain": domain},
        {"$set": {"api_key": api_key}},
        upsert=True
    )
    await message.reply_text(f"✅ Shortener Added: **{domain}**")

@app.on_message(filters.command("removeshortner") & filters.private)
async def remove_shortner_cmd(client, message: Message):
    if not is_owner(message.from_user.id):
        return
    if len(message.command) < 2:
        await message.reply_text("Usage: `/removeshortner <domain.com>`")
        return
        
    domain = message.command[1]
    await shortners_col.delete_one({"domain": domain})
    await message.reply_text(f"🗑 Shortener Removed: **{domain}**")

# ----- PREMIUM & FORCE SUB -----
@app.on_message(filters.command("addpremium") & filters.private)
async def add_premium_cmd(client, message: Message):
    if not is_owner(message.from_user.id):
        return
    try:
        user_id = int(message.command[1])
        expires_at = datetime.utcnow() + timedelta(days=28)
        await premium_col.update_one(
            {"user_id": user_id},
            {"$set": {"expires_at": expires_at}},
            upsert=True
        )
        await message.reply_text(f"✅ Premium activated for `{user_id}` till {expires_at.strftime('%Y-%m-%d')} UTC")
    except:
        await message.reply_text("Usage: `/addpremium <user_id>`")

@app.on_message(filters.command("forcesub") & filters.private)
async def force_sub_cmd(client, message: Message):
    if not is_owner(message.from_user.id):
        return
    if not message.reply_to_message or not message.reply_to_message.forward_from_chat:
        await message.reply_text("Please forward a message strictly from a **Channel**.")
        return
        
    channel = message.reply_to_message.forward_from_chat
    await channels_col.update_one(
        {"type": "force_sub"},
        {"$set": {"channel_id": channel.id, "title": channel.title}},
        upsert=True
    )
    await message.reply_text(f"✅ Force Sub set to:\n**{channel.title}** (`{channel.id}`)")

# ---------------- RUN BOT ----------------
if __name__ == "__main__":
    print("Bot is starting...")
    app.run()
