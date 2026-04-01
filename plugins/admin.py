from pyrogram import Client, filters
import database as db
from config import ALLOWED_USERS
import pyromod

@Client.on_message(filters.command("add shortner account") & filters.user(ALLOWED_USERS))
async def add_short(bot, msg):
    url = await bot.ask(msg.chat.id, "provide deskbord url")
    api = await bot.ask(msg.chat.id, "send api token")
    await db.add_shortner(url.text, api.text)
    await msg.reply("successfully add 🤗")

@Client.on_message(filters.command("remove shortner account") & filters.user(ALLOWED_USERS))
async def remove_short(bot, msg):
    await db.remove_shortner()
    await msg.reply("deleted shortner")

@Client.on_message(filters.command("add premium") & filters.user(ALLOWED_USERS))
async def add_p(bot, msg):
    uid = await bot.ask(msg.chat.id, "send id")
    await db.add_premium(int(uid.text))
    confirm = await bot.ask(msg.chat.id, "type /hu hu")
    if confirm.text == "/hu hu":
        await msg.reply("premium added")

@Client.on_message(filters.command("remove premium") & filters.user(ALLOWED_USERS))
async def rem_p(bot, msg):
    uid = await bot.ask(msg.chat.id, "send id")
    await db.remove_premium(int(uid.text))
    await msg.reply("premium removed")

@Client.on_message(filters.command("show premium list") & filters.user(ALLOWED_USERS))
async def show(bot, msg):
    await msg.reply("premium list not persistent (memory)")
