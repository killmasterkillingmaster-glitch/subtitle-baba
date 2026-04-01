from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import ALLOWED_USERS, STORAGE_CHANNEL_ID
from database import save_post
import pyromod

@Client.on_message(filters.command("post") & filters.user(ALLOWED_USERS))
async def post(bot, msg):

    # Step 1
    m = await bot.ask(msg.chat.id, "send post")
    stored = await m.copy(STORAGE_CHANNEL_ID)

    files = [stored.id]

    # Step 2
    link_type = await bot.ask(msg.chat.id, "single link or batch link")

    if link_type.text.lower() == "batch link":
        while True:
            nxt = await bot.ask(msg.chat.id, "send next episode or /done")
            if nxt.text == "/done":
                break
            s = await nxt.copy(STORAGE_CHANNEL_ID)
            files.append(s.id)

    # Step 3
    ep = await bot.ask(msg.chat.id, "Enter Number")

    # Step 4
    await bot.ask(msg.chat.id, "/confirm")

    await bot.ask(msg.chat.id, "/hmm")

    # Step 5
    pid = await save_post(files)

    bot_user = (await bot.get_me()).username
    link = f"https://t.me/{bot_user}?start=get_{pid}"

    btn = InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"Watch episode {ep.text}", url=link)]]
    )

    preview = await stored.copy(msg.chat.id, reply_markup=btn)

    # Step 6
    send = await bot.ask(msg.chat.id, "/send or /send more channel")

    ch = await bot.ask(msg.chat.id, "send channel id")

    confirm = await bot.ask(msg.chat.id, "/confirm")

    if confirm.text == "/confirm":
        await stored.copy(ch.text, reply_markup=btn)

    await msg.reply("Posted ✅")
