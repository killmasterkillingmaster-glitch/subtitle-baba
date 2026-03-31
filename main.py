import os
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

# Port automatically fetch hoga hosting se, warna 8080 use karega
PORT = int(os.environ.get("PORT", 8080))

# API credentials via environment variables (secure)
API_ID = int(os.environ.get("API_ID", "123456"))
API_HASH = os.environ.get("API_HASH", "abcdef123456")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "123456:ABCDEF")

# ---------------- MONGO SETUP (Async Motor) ----------------
MONGO_URI = "mongodb+srv://aasifhusenaasifkhan_db_user:64CtKuQjWL0EzYMO@botcluster.v4land1.mongodb.net/?retryWrites=true&w=majority"
DB_NAME = "subtitle_baba"

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

posts_col = db.posts
premium_col = db.premium
shortner_col = db.shortners
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

async def send_to_channels(message_id, from_chat, chat_list):
    for chat_id in chat_list:
        try:
            await app.forward_messages(chat_id=chat_id, from_chat_id=from_chat, message_ids=message_id)
        except Exception as e:
            print(f"Error sending to {chat_id}: {e}")

# ---------------- COMMANDS ----------------
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    await message.reply_text("Hello 🤗 Anime Bot is Active!")

@app.on_message(filters.command("post") & filters.private)
async def post_cmd(client, message: Message):
    if not is_allowed(message.from_user.id):
        await message.reply_text("❌ You are not allowed to use this command.")
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
    await message.reply_text(f"Post received 🤗\nPost ID: `{result.inserted_id}`\nPlease forward episode from DB channel to continue.")

@app.on_message(filters.command("getlink") & filters.private)
async def getlink_cmd(client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("Usage: `/getlink <episode_number>`")
        return
    try:
        episode_num = message.command[1]
        cursor = posts_col.find().sort("created_at", -1).limit(1)
        last_posts = await cursor.to_list(length=1)
        if not last_posts:
            await message.reply_text("Database is empty. No posts found.")
            return
        short_url = f"https://gplinks.in/short/{episode_num}"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Watch Episode {episode_num}", url=short_url)]
        ])
        await message.reply_text("Here is your episode link:", reply_markup=keyboard)
    except Exception as e:
        await message.reply_text(f"Error: {e}")

@app.on_message(filters.command("batchlink") & filters.private)
async def batchlink_cmd(client, message: Message):
    if not is_allowed(message.from_user.id):
        return
    await message.reply_text("Batchlink system active.\nForward first & last episodes from DB to generate batch.")

@app.on_message(filters.command("addpremium") & filters.private)
async def add_premium_cmd(client, message: Message):
    if not is_allowed(message.from_user.id):
        await message.reply_text("❌ You are not allowed to use this command.")
        return
    try:
        user_id = int(message.command[1])
        expires_at = datetime.utcnow() + timedelta(days=28)
        await premium_col.update_one(
            {"user_id": user_id},
            {"$set": {"expires_at": expires_at}},
            upsert=True
        )
        await message.reply_text(f"✅ Premium activated for `{user_id}` till {expires_at.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    except IndexError:
        await message.reply_text("Usage: `/addpremium <user_id>`")
    except ValueError:
        await message.reply_text("Error: User ID must be a number.")
    except Exception as e:
        await message.reply_text(f"An error occurred: {e}")

@app.on_message(filters.command("forcesub") & filters.private)
async def force_sub_cmd(client, message: Message):
    if not is_owner(message.from_user.id):
        await message.reply_text("❌ Only owner can set Force Sub channel.")
        return
    if not message.reply_to_message:
        await message.reply_text("Please forward a message from the channel to activate Force Sub.")
        return
    forwarded = message.reply_to_message
    if not forwarded.forward_from_chat or forwarded.forward_from_chat.type != enums.ChatType.CHANNEL:
        await message.reply_text("❌ Invalid input! Please forward a message strictly from a **Channel**.")
        return
    channel_id = forwarded.forward_from_chat.id
    channel_title = forwarded.forward_from_chat.title
    await channels_col.update_one(
        {"type": "force_sub"},
        {"$set": {
            "channel_id": channel_id, 
            "message_id": forwarded.id,
            "title": channel_title
        }},
        upsert=True
    )
    await message.reply_text(f"✅ Force Sub successfully set to channel:\n**{channel_title}** (`{channel_id}`)")

# ---------------- RUN BOT ----------------
if __name__ == "__main__":
    print("Bot is starting...")
    app.run()
