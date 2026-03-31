import os
from pyrogram import Client, filters
from flask import Flask
from threading import Thread
from config import API_ID, API_HASH, BOT_TOKEN, PORT

# --- WEB SERVER FOR RENDER ---
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot is running perfectly!"

def run_web():
    web_app.run(host="0.0.0.0", port=PORT)

# --- TELEGRAM BOT ---
bot = Client(
    "hmm_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- Basic Commands ---
@bot.on_message(filters.command("start") & filters.private)
async def start(client, message):
    await message.reply_text(
        f"Hello 🤗 Welcome to HMM Bot!\nOwner: {os.getenv('OWNER_ID')}"
    )

@bot.on_message(filters.command("help") & filters.private)
async def help_cmd(client, message):
    await message.reply_text(
        "Available commands:\n"
        "/start\n"
        "/post\n"
        "/add_shortner_account\n"
        "/remove_shortner_account\n"
        "/send\n"
        "/send_more_channel\n"
        "/force_sub\n"
        "/addpremium\n"
        "/removepremium"
    )

# --- RUN BOT & WEB ---
if __name__ == "__main__":
    Thread(target=run_web).start()
    bot.run()
