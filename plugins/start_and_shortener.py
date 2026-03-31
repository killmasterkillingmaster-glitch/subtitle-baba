from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_post, is_premium, get_random_shortener, get_force_sub
from config import STORAGE_CHANNEL_ID
import aiohttp

async def get_short_link(original_url):
    shortener = await get_random_shortener()
    if not shortener: return original_url # Agar shortener add nahi kiya toh direct link
    
    api_url = f"{shortener['url']}/api?api={shortener['api']}&url={original_url}"
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url) as response:
            data = await response.json()
            if data.get("status") == "success":
                return data["shortenedUrl"]
            return original_url

@Client.on_message(filters.command("start"))
async def start_cmd(bot, message):
    text = message.text
    user_id = message.from_user.id
    
    # Force Sub Check
    fsub_channels = await get_force_sub()
    not_joined = []
    for ch in fsub_channels:
        try:
            member = await bot.get_chat_member(ch, user_id)
            if member.status in ["left", "kicked"]:
                not_joined.append(ch)
        except:
            not_joined.append(ch)
            
    if not_joined:
        btn = [[InlineKeyboardButton("Join Channel", url=f"https://t.me/c/{str(ch)[4:]}/1")] for ch in not_joined]
        return await message.reply("Bot reply - join first\nTry again after joining.", reply_markup=InlineKeyboardMarkup(btn))

    # File Provide Logic
    if len(text.split()) > 1 and text.split()[1].startswith("get_"):
        post_id = text.split()[1].split("_")[1]
        
        premium = await is_premium(user_id)
        
        # Shortener bypass check (Is token verified?)
        if "verify" in text:
            premium = True # Temporary allow for this request
            
        if premium:
            post_data = await get_post(post_id)
            if post_data:
                for file_id in post_data["file_ids"]:
                    await bot.copy_message(user_id, STORAGE_CHANNEL_ID, file_id)
            else:
                await message.reply("File not found in database.")
        else:
            # Free user - generate shortener link
            bot_username = (await bot.get_me()).username
            verify_link = f"https://t.me/{bot_username}?start=get_{post_id}_verify"
            short_url = await get_short_link(verify_link)
            
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("Unlock Episode", url=short_url)]])
            await message.reply("Please solve the shortener to get the episode direct!", reply_markup=btn)
