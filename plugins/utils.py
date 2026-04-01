import random
import asyncio
import aiohttp
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URL, STORAGE_CHANNEL

# MongoDB Setup
db_client = AsyncIOMotorClient(MONGO_URL)
db = db_client['anime_bot_db']
shorteners_col = db['shorteners']
premium_col = db['premium']
channels_col = db['channels']

# Premium User Check (28 Days Logic)
async def is_premium_user(user_id):
    user = await premium_col.find_one({"_id": str(user_id)})
    if user:
        expiry = datetime.fromisoformat(user['expiry'])
        if datetime.now() < expiry:
            return True
        else:
            await premium_col.delete_one({"_id": str(user_id)}) # 28 din baad auto-delete
    return False

# Shortener Link Generator
async def get_short_link(long_url: str) -> str:
    docs = await shorteners_col.find().to_list(length=100)
    if not docs:
        return long_url # Agar shortener add nahi hai toh direct link dega
    
    short = random.choice(docs) # Auto-Rotate
    
    # GP Links aur baaki APIs ka support
    if "gplinks" in short['url'].lower():
        api_url = "https://api.gplinks.com/api"
    else:
        api_url = f"{short['url'].rstrip('/')}/api"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, params={"api": short['api'], "url": long_url}, timeout=10) as resp:
                data = await resp.json()
                if data.get("status") == "success":
                    return data["shortenedUrl"]
    except Exception as e:
        print(f"Shortener API Error: {e}")
    return long_url

# Final File Delivery
async def send_files(bot, user_id, payload):
    actual_payload = payload.replace("V_", "")
    try:
        if actual_payload.startswith("S_"):
            msg_id = int(actual_payload.split("_")[1])
            await bot.copy_message(chat_id=user_id, from_chat_id=STORAGE_CHANNEL, message_id=msg_id)
            
        elif actual_payload.startswith("B_"):
            parts = actual_payload.split("_")
            start_id, end_id = int(parts[1]), int(parts[2])
            for msg_id in range(start_id, end_id + 1):
                try:
                    await bot.copy_message(chat_id=user_id, from_chat_id=STORAGE_CHANNEL, message_id=msg_id)
                    await asyncio.sleep(0.5) # Flood wait se bachne ke liye thoda delay
                except:
                    pass
    except Exception:
        await bot.send_message(user_id, "❌ File Server Par Nahi Hai ya Delete Ho Chuki Hai!")
