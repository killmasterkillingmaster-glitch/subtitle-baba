from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from modules.utils import get_db
from config import ALLOWED_USERS

def generate_channel_buttons(channels_list):
    buttons = []
    for name, ch_id in channels_list:
        buttons.append([InlineKeyboardButton(name, callback_data=f"ch_{ch_id}")])
    return InlineKeyboardMarkup(buttons)

async def handle_send(user_id: int, message, bot_client):
    db = get_db()
    if user_id not in ALLOWED_USERS:
        await message.reply_text("🚫 Not allowed")
        return
    channels = list(db.channels.find({"is_admin": True}))
    if not channels:
        await message.reply_text("⚠️ No channels")
        return
    channels_list = [(ch["name"], ch["channel_id"]) for ch in channels]
    markup = generate_channel_buttons(channels_list)
    await message.reply_text("📤 Select channel:", reply_markup=markup)

async def distribute_post(post_message, selected_channel_ids: list, bot_client):
    for ch_id in selected_channel_ids:
        try:
            await bot_client.forward_messages(chat_id=ch_id, from_chat_id=post_message.chat.id, message_ids=post_message.message_id)
        except Exception as e:
            print(f"Error {ch_id}: {e}")
