import asyncio
from pymongo import MongoClient
from config import MONGO_URI, SHORTNER_ACCOUNTS
from datetime import datetime
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_db():
    client = MongoClient(MONGO_URI)
    db = client["anime_bot"]
    return db

async def save_post_to_db(message):
    db = get_db()
    post_data = {
        "chat_id": message.chat.id,
        "message_id": message.message_id,
        "from_user": message.from_user.id,
        "date": datetime.utcnow()
    }
    result = db["posts"].insert_one(post_data)
    return str(result.inserted_id)

def generate_episode_button(start, end=None):
    if end:
        button_text = f"Watch episode {start}-{end}"
        callback_data = f"batch_{start}_{end}"
    else:
        button_text = f"Watch episode {start}"
        callback_data = f"single_{start}"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(button_text, callback_data=callback_data)]])
    return keyboard

def get_next_shortner_account():
    if not SHORTNER_ACCOUNTS:
        return None
    account = SHORTNER_ACCOUNTS.pop(0)
    SHORTNER_ACCOUNTS.append(account)
    return account

def is_allowed_user(user_id, allowed_list):
    return user_id in allowed_list

async def async_sleep(seconds=1):
    await asyncio.sleep(seconds)
