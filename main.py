import os
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread
from pyromod import listen

# ---------------- CONFIG ----------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

PORT = int(os.getenv("PORT", 10000))

ALLOWED_USERS = [5351848105, 5344078567]

# ---------------- STORAGE ----------------
shortners = []

# ---------------- WEB ----------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Running ✅"

def run_web():
    app.run(host="0.0.0.0", port=PORT)

# ---------------- BOT ----------------
bot = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ---------------- START ----------------
@bot.on_message(filters.command("start") & filters.private)
async def start(client, message):
    await message.reply("✅ Bot Alive")

# ---------------- ADD SHORTNER ----------------
@bot.on_message(filters.command("add_shortner_account") & filters.user(ALLOWED_USERS))
async def add_short(client, message):
    url = await bot.ask(message.chat.id, "Send Dashboard URL")
    api = await bot.ask(message.chat.id, "Send API Token")

    shortners.append({
        "url": url.text,
        "api": api.text
    })

    await message.reply("✅ Shortner Added")

# ---------------- TEST ----------------
@bot.on_message(filters.command("test"))
async def test(client, message):
    link = await bot.ask(message.chat.id, "Send link")

    if shortners:
        s = shortners[0]
        api_url = f"{s['url']}/api?api={s['api']}&url={link.text}"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(api_url) as resp:
                    data = await resp.json()
                    short = data.get("shortenedUrl", link.text)
            except:
                short = link.text
    else:
        short = link.text

    btn = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Open", url=short)]]
    )

    await message.reply("Done", reply_markup=btn)

# ---------------- RUN ----------------
if __name__ == "__main__":
    Thread(target=run_web).start()
    bot.run()
