import os
import aiohttp
from pyrogram import Client, filters
import pyromod.listen

# -------- CONFIG --------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# 👉 Yaha apna shortner set karo
SHORTNER_URL = "https://gplinks.in"
API_TOKEN = "df1dda439a2bf7d2cc04ad2c6a555515d451e417"

# -------- BOT --------
bot = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# -------- START --------
@bot.on_message(filters.command("start") & filters.private)
async def start(_, message):
    await message.reply_text("✅ Bot Alive")

# -------- TEST SHORTNER --------
@bot.on_message(filters.command("test") & filters.private)
async def test(client, message):
    msg = await client.ask(message.chat.id, "Send link")
    link = msg.text.strip()

    api_url = f"{SHORTNER_URL}/api?api={API_TOKEN}&url={link}&format=json"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:

                raw = await resp.text()
                print("RAW RESPONSE:", raw)  # 🔥 Debug

                try:
                    data = await resp.json()
                except:
                    return await message.reply_text(f"❌ Not JSON:\n{raw}")

        if data.get("status") == "success":
            short = data.get("shortenedUrl") or data.get("shortened_url")
            await message.reply_text(f"✅ Short Link:\n{short}")
        else:
            await message.reply_text(f"❌ API ERROR:\n{data}")

    except Exception as e:
        await message.reply_text(f"❌ ERROR:\n{e}")

# -------- RUN --------
bot.run()
