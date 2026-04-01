import os
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread

# ---------------- CONFIG ----------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

OWNER_ID = 5351848105
ALLOWED_USERS = [5351848105, 5344078567]

PORT = int(os.getenv("PORT", 10000))

# ---------------- SHORTNER STORAGE ----------------
shortners = []   # yaha store honge accounts

# ---------------- WEB SERVER ----------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot running"

def run_web():
    app.run(host="0.0.0.0", port=PORT)

# ---------------- BOT ----------------
bot = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ---------------- START ----------------
@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply("Bot is alive 🤖")

# ---------------- ADD SHORTNER ----------------
@bot.on_message(filters.command("add_shortner_account") & filters.user(ALLOWED_USERS))
async def add_short(client, message):
    url = await bot.ask(message.chat.id, "Send Shortner API URL")
    api = await bot.ask(message.chat.id, "Send API Token")

    shortners.append({
        "url": url.text,
        "api": api.text
    })

    await message.reply("✅ Shortner Added")

# ---------------- REMOVE SHORTNER ----------------
@bot.on_message(filters.command("remove_shortner_account") & filters.user(ALLOWED_USERS))
async def remove_short(client, message):
    if not shortners:
        return await message.reply("No shortner found")

    text = "Shortners:\n"
    for i, s in enumerate(shortners):
        text += f"{i} → {s['url']}\n"

    idx = await bot.ask(message.chat.id, text + "\nSend index to remove")

    try:
        shortners.pop(int(idx.text))
        await message.reply("✅ Removed")
    except:
        await message.reply("Invalid index")

# ---------------- GENERATE SHORT LINK ----------------
async def generate_short_link(link):
    if not shortners:
        return link

    s = shortners[0]  # simple rotation later karenge

    api_url = f"{s['url']}/api?api={s['api']}&url={link}"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(api_url) as resp:
                data = await resp.json()
                return data.get("shortenedUrl", link)
        except:
            return link

# ---------------- TEST SHORTNER ----------------
@bot.on_message(filters.command("test"))
async def test_short(client, message):
    link = await bot.ask(message.chat.id, "Send link to short")

    short = await generate_short_link(link.text)

    btn = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Open Link", url=short)]]
    )

    await message.reply("Here is your short link", reply_markup=btn)

# ---------------- RUN ----------------
if __name__ == "__main__":
    Thread(target=run_web).start()
    bot.run()
