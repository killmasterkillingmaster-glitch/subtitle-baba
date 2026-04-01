from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_post, is_premium, get_shortner
from config import STORAGE_CHANNEL_ID

@Client.on_message(filters.command("start"))
async def start(bot, msg):
    text = msg.text

    if len(text.split()) > 1 and "get_" in text:
        pid = text.split("_")[1]

        if await is_premium(msg.from_user.id):
            data = await get_post(pid)
            if data:
                for f in data:
                    await bot.copy_message(msg.chat.id, STORAGE_CHANNEL_ID, f)
        else:
            s = await get_shortner()
            bot_user = (await bot.get_me()).username
            link = f"https://t.me/{bot_user}?start=get_{pid}"

            if s:
                link = f"{s['url']}/api?api={s['api']}&url={link}"

            btn = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Unlock Episode", url=link)]]
            )
            await msg.reply("Solve shortner first", reply_markup=btn)
    else:
        await msg.reply("Bot Working ✅")
