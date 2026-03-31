from pyrogram import Client, filters
from config import ALLOWED_USERS
import database as db
import pyromod

# -- Premium Commands --
@Client.on_message(filters.command("add premium") & filters.user(ALLOWED_USERS))
async def add_prem(bot, message):
    chat_id = message.chat.id
    target = await bot.ask(chat_id, "send I'd")
    confirm = await bot.ask(chat_id, "successfully add member\nPleas confirm type /hu hu")
    if confirm.text == "/hu hu":
        await db.add_premium_user(int(target.text))
        await message.reply(f"successfully add member {target.text} 🪄🪄🪄")

@Client.on_message(filters.command("remove premium") & filters.user(ALLOWED_USERS))
async def remove_prem(bot, message):
    target = await bot.ask(message.chat.id, "send I'd")
    await db.remove_premium_user(int(target.text))
    await message.reply("successfully deleted and ban")

# -- Shortener Commands --
@Client.on_message(filters.command("add shortner account") & filters.user(ALLOWED_USERS))
async def add_short(bot, message):
    chat_id = message.chat.id
    url = await bot.ask(chat_id, "provide deskbord url (e.g. https://gplinks.in)")
    api = await bot.ask(chat_id, "successfully send Your API Token")
    await db.add_shortener(url.text, api.text)
    await message.reply("successfully add 🤗🤗🤗")

@Client.on_message(filters.command("remove shortner account") & filters.user(ALLOWED_USERS))
async def remove_short(bot, message):
    url = await bot.ask(message.chat.id, "Enter shortner URL to delete")
    confirm = await bot.ask(message.chat.id, "kya aap hatana chahte hai\nToh type /delete")
    if confirm.text == "/delete":
        await db.remove_shortener(url.text)
        await message.reply("successfully delete account for shortner")
