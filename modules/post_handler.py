from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from modules.utils import get_db, generate_episode_button
from config import ALLOWED_USERS, STORAGE_CHANNEL_ID

async def handle_post(user_id: int, message, bot_client):
    db = get_db()
    if user_id not in ALLOWED_USERS:
        await message.reply_text("🚫 You are not allowed to post.")
        return
    await message.reply_text("📤 Send the post (document/photo/video)")

async def receive_forwarded_post(message, bot_client):
    forwarded = await bot_client.forward_messages(
        chat_id=STORAGE_CHANNEL_ID,
        from_chat_id=message.chat.id,
        message_ids=message.message_id
    )
    await message.reply_text("✅ Post successfully received!\nPlease provide single/batch link.")

def generate_episode_buttons(start: int, end: int = None):
    if end:
        text = f"Watch episode {start}-{end}"
        callback_data = f"batch_{start}_{end}"
    else:
        text = f"Watch episode {start}"
        callback_data = f"single_{start}"
    return InlineKeyboardMarkup([[InlineKeyboardButton(text, callback_data=callback_data)]])
