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
STORAGE_CHANNEL = -1003096528862

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
    url = await client.ask(message.chat.id, "Send Shortner URL\nExample: https://gplinks.in")
    api = await client.ask(message.chat.id, "Send API Token")

    clean_url = url.text.strip().rstrip("/")  # fix slash issue

    text = f"#SHORTNER\nURL={clean_url}\nAPI={api.text.strip()}"

    await client.send_message(STORAGE_CHANNEL, text)

    await message.reply_text("✅ Shortner Added & Saved")

# ---------------- GET ALL SHORTNERS ----------------
async def get_shortners(client):
    data = []

    async for msg in client.get_chat_history(STORAGE_CHANNEL, limit=100):
        if msg.text and msg.text.startswith("#SHORTNER"):
            try:
                lines = msg.text.split("\n")
                url = lines[1].split("=")[1]
                api = lines[2].split("=")[1]
                data.append({"url": url, "api": api, "msg_id": msg.id})
            except:
                continue

    return data

# ---------------- REMOVE SHORTNER ----------------
@bot.on_message(filters.command("remove_shortner_account") & filters.user(ALLOWED_USERS))
async def remove_short(client, message):
    shortners = await get_shortners(client)

    if not shortners:
        return await message.reply_text("⚠️ No shortner found")

    buttons = []
    for s in shortners:
        buttons.append([
            InlineKeyboardButton(s["url"], callback_data=f"del_{s['msg_id']}")
        ])

    await message.reply_text("Select account to delete:", reply_markup=InlineKeyboardMarkup(buttons))

# ---------------- DELETE CALLBACK ----------------
@bot.on_callback_query(filters.regex("^del_"))
async def delete_short(client, query):
    msg_id = int(query.data.split("_")[1])

    await client.delete_messages(STORAGE_CHANNEL, msg_id)
    await query.message.edit_text("❌ Shortner Deleted")

# ---------------- ROTATION ----------------
index = 0

async def get_next_shortner(client):
    global index
    shortners = await get_shortners(client)

    if not shortners:
        return None

    if index >= len(shortners):
        index = 0

    s = shortners[index]
    index += 1

    return s

# ---------------- GPLinks SHORTNER ----------------
async def generate_short_link(url, api, link):
    api_url = f"{url}/api?api={api}&url={link}"

    timeout = aiohttp.ClientTimeout(total=10)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.get(api_url) as resp:
                try:
                    # Try JSON
                    data = await resp.json()
                    if data.get("status") == "success":
                        return data.get("shortenedUrl")
                except:
                    # Try TEXT
                    text = await resp.text()
                    if "http" in text:
                        return text.strip()
        except:
            pass

    return link  # fallback

# ---------------- TEST ----------------
@bot.on_message(filters.command("test"))
async def test(client, message):
    link = await client.ask(message.chat.id, "Send link")

    s = await get_next_shortner(client)

    if s:
        short = await generate_short_link(s["url"], s["api"], link.text)
    else:
        short = link.text

    btn = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Open", url=short)]]
    )

    await message.reply_text("✅ Done", reply_markup=btn)

# ---------------- RUN ----------------
if __name__ == "__main__":
    Thread(target=run_web).start()
    bot.run()
