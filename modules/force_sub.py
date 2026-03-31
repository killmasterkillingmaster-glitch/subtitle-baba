from modules.utils import get_db
from config import ALLOWED_USERS
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def force_sub(user_id: int, message, bot_client):
    if user_id not in ALLOWED_USERS:
        await message.reply_text("🚫 Not allowed")
        return
    await message.reply_text("📌 Forward channel message and make me admin")

async def check_channel_join(user_id: int, required_channels: list, bot_client):
    all_joined = True
    not_joined = []
    for ch_id in required_channels:
        try:
            member = await bot_client.get_chat_member(ch_id, user_id)
            if member.status in ["left","kicked"]:
                all_joined = False
                not_joined.append(ch_id)
        except: all_joined = False; not_joined.append(ch_id)
    return all_joined, not_joined

def generate_join_buttons(channels_list):
    buttons = [[InlineKeyboardButton(f"Join {name}", url=f"https://t.me/{name}")] for name, _ in channels_list]
    buttons.append([InlineKeyboardButton("Try Again", callback_data="try_again")])
    return InlineKeyboardMarkup(buttons)
