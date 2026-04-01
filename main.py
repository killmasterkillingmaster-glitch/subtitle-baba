import os
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread
import pyromod.listen

# ---------------- CONFIG ----------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

PORT = int(os.getenv("PORT", 10000))

ALLOWED_USERS = [5351848105, 5344078567]
STORAGE_CHANNEL = -1003096528862  # 🔥 tera channel

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
    bot_token=BOT_TOKEN,
    workers=10
)

# ---------------- START ----------------
@bot.on_message(filters.command("start") & filters.private)
async def start(client, message):
    await message.reply_text("✅ Bot Alive")

# ---------------- ADD SHORTNER ----------------
@bot.on_message(filters.command("add_shortner_account") & filters.user(ALLOWED_USERS))
async def add_short(client, message):
    url = await client.ask(message.chat.id, "Send API URL")
    api = await client.ask(message.chat.id, "Send API Token")

    data = f"SHORTNER\n{url.text.strip()}\n{api.text.strip()}"

    # Save in storage channel
    await client.send_message(STORAGE_CHANNEL, data)

    await message.reply_text("✅ Shortner Saved in Storage Channel")

# ---------------- GET SHORTNER ----------------
async def get_shortner(client):
    shortners = []

    async for msg in client.get_chat_history(STORAGE_CHANNEL, limit=50):
        if msg.text and msg.text.startswith("SHORTNER"):
            try:
                _, url, api = msg.text.split("\n")
                shortners.append({"url": url, "api": api})
            except:
                pass

    return shortners

# ---------------- TEST SHORTNER ----------------
@bot.on_message(filters.command("test") & filters.private)
async def test(client, message):
    link = await client.ask(message.chat.id, "Send link")

    shortners = await get_shortner(client)

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

    await message.reply_text("✅ Done", reply_markup=btn)

# ---------------- REMOVE SHORTNER ----------------
@bot.on_message(filters.command("remove_shortner_account") & filters.user(ALLOWED_USERS))
async def remove_short(client, message):
    msgs = []

    async for msg in client.get_chat_history(STORAGE_CHANNEL, limit=50):
        if msg.text and msg.text.startswith("SHORTNER"):
            msgs.append(msg)

    if not msgs:
        return await message.reply_text("⚠️ No shortner found")

    buttons = []
    for i, m in enumerate(msgs):
        buttons.append([InlineKeyboardButton(f"Account {i+1}", callback_data=f"del_{m.id}")])

    await message.reply_text("Select account:", reply_markup=InlineKeyboardMarkup(buttons))

# ---------------- DELETE CALLBACK ----------------
@bot.on_callback_query(filters.regex("^del_"))
async def delete_shortner(client, query):
    msg_id = int(query.data.split("_")[1])

    await client.delete_messages(STORAGE_CHANNEL, msg_id)

    await query.message.edit_text("✅ Shortner Deleted")

# ---------------- RUN ----------------
if __name__ == "__main__":
    Thread(target=run_web).start()
    bot.run()
