import os
import asyncio
import aiohttp
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread

# --- WEB SERVER (For Render Free Tier) ---
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot is running perfectly on Render!"

def run_web():
    web_app.run(host="0.0.0.0", port=10000)

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID", "12345"))
API_HASH = os.environ.get("API_HASH", "your_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_token")

OWNER_ID = int(os.environ.get("OWNER_ID", "5351848105"))
ALLOWED_USERS = [int(x) for x in os.environ.get("ALLOWED_USERS", "5351848105,5344078567").split(",")]
DB_CHANNEL = int(os.environ.get("DB_CHANNEL", "-1003143681742"))
EXTRA_CHANNEL = int(os.environ.get("EXTRA_CHANNEL", "-1003872932495"))

user_data = {}
bot_settings = {
    "shortener_api": os.environ.get("SHORT_API", ""),
    "shortener_url": os.environ.get("SHORT_URL", ""),
    "fsub_channels": [EXTRA_CHANNEL]
}

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- SHORTENER LOGIC ---
async def get_shortlink(long_url):
    if not bot_settings["shortener_api"] or not bot_settings["shortener_url"]:
        return long_url

    domain = bot_settings["shortener_url"].lower()

    if "gplinks" in domain:
        api_url = f"https://api.gplinks.com/api?api={bot_settings['shortener_api']}&url={long_url}"
    else:
        api_url = f"https://{domain}/api?api={bot_settings['shortener_api']}&url={long_url}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as res:
                data = await res.json()
                return (
                    data.get("shortenedUrl")
                    or data.get("short_url")
                    or data.get("shortened_url")
                    or data.get("url")
                    or long_url
                )
    except:
        return long_url

async def is_subscribed(user_id):
    for chat_id in bot_settings["fsub_channels"]:
        try:
            member = await app.get_chat_member(chat_id, user_id)
            if member.status == enums.ChatMemberStatus.LEFT:
                return False
        except:
            continue
    return True

# --- START COMMAND ---
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    if len(message.text.split()) > 1:
        data = message.text.split()[1]
        if not await is_subscribed(message.from_user.id):
            btns = [[InlineKeyboardButton("Join Channel", url="https://t.me/your_channel_link")]]
            return await message.reply("Pehle Channel Join Karo!", reply_markup=InlineKeyboardMarkup(btns))

        ids = data.split("_")
        try:
            if len(ids) == 1:
                await client.copy_message(message.chat.id, DB_CHANNEL, int(ids[0]))
            else:
                for mid in range(int(ids[0]), int(ids[1]) + 1):
                    await client.copy_message(message.chat.id, DB_CHANNEL, mid)
                    await asyncio.sleep(0.5)
        except Exception as e:
            await message.reply(f"Error: {e}")
        return
    await message.reply("Bhai, main zinda hu! Commands dekhne ke liye /setting dabao.")

# --- SETTINGS COMMAND ---
@app.on_message(filters.command("setting") & filters.user(ALLOWED_USERS))
async def settings_cmd(client, message):
    await message.reply("""
⚙️ **Bot Commands & Settings**

/post - Naya post daalne ke liye (Pehle ye dabayein)
/link_shortener - Link shortener Setup karne ke liye
/link - Link generate karne ka final step
/setting - Commands ki list dekhne ke liye

**📌 Setup Kaise Karein:**
1️⃣ `/link_shortener` send karein aur domain + API set karein.
2️⃣ `/post` send karein, fir apna Post (Photo/Video/Text) bhejein.
3️⃣ Link / Batch Link ka option select karein.
4️⃣ Database se files forward karein.
5️⃣ `/link` command de kar Done karein aur Episode Number daalein.

🔥 Ready to use!
""")

# --- NEW: POST COMMAND (Fixes the overlapping issue) ---
@app.on_message(filters.command("post") & filters.user(ALLOWED_USERS) & filters.private)
async def post_command(client, message):
    uid = message.from_user.id
    user_data.setdefault(uid, {})
    user_data[uid]["state"] = "waiting_for_post"
    await message.reply("📸 Apna Post (Photo, Video, ya Text) bhejo jiske niche tumhe button lagana hai:")

# --- SHORTENER SETUP COMMAND ---
@app.on_message(filters.command("link_shortener") & filters.user(ALLOWED_USERS))
async def shortener_setup(client, message):
    uid = message.from_user.id
    user_data.setdefault(uid, {})
    user_data[uid]["state"] = "set_url"
    await message.reply("🌐 Shortener ka Domain bhejo (e.g., gplinks.com ya modijiurl.com):")

# --- LINK COMMAND ---
@app.on_message(filters.command("link") & filters.user(ALLOWED_USERS))
async def get_link_command(client, message):
    await message.reply("Agar file forward kar di hai toh Done pe click karein:", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Done", callback_data="gen_link")]
    ]))

# --- MASTER INPUT HANDLER (Handles Post, URL, API, and Episode Number) ---
@app.on_message(filters.private & filters.user(ALLOWED_USERS) & ~filters.command(["start","link","link_shortener","setting","post"]))
async def master_input_handler(client, message):
    uid = message.from_user.id
    if uid not in user_data:
        return

    state = user_data[uid].get("state")

    # 1. Handling the Post
    if state == "waiting_for_post":
        user_data[uid]["post"] = message
        user_data[uid]["selected_chats"] = []
        user_data[uid]["state"] = None # State clear kar diya

        btns = [[
            InlineKeyboardButton("Single Link", callback_data="set_single"),
            InlineKeyboardButton("Batch Link", callback_data="set_batch")
        ]]
        await message.reply("✅ Post save ho gaya! Ab option select karo:", reply_markup=InlineKeyboardMarkup(btns))

    # 2. Handling Shortener URL
    elif state == "set_url":
        if not message.text:
            return await message.reply("Bhai text format me URL bhejo!")
        bot_settings["shortener_url"] = message.text.strip().replace("https://","").replace("http://","").replace("/","")
        user_data[uid]["state"] = "set_api"
        await message.reply(f"Domain set: `{bot_settings['shortener_url']}`\n\nAb API Token bhejo:")

    # 3. Handling Shortener API
    elif state == "set_api":
        if not message.text:
            return await message.reply("Bhai text format me API bhejo!")
        bot_settings["shortener_api"] = message.text.strip()
        user_data[uid]["state"] = None # State clear
        await message.reply("✅ Shortener successfully Set Ho Gya hai!")

    # 4. Handling Episode Number
    elif state == "waiting_num":
        if not message.text:
            return await message.reply("Number bhejo!")
        num = message.text

        bot_user = (await client.get_me()).username
        # Yahan tumhara file_id ka logic aayega (abhi dummy start parameter hai)
        f_link = f"https://t.me/{bot_user}?start=file_id_here" 
        
        await message.reply("⏳ Shortlink generate ho raha hai, wait...")
        s_link = await get_shortlink(f_link)

        markup = InlineKeyboardMarkup([[InlineKeyboardButton(f"Episode {num}", url=s_link)]])
        user_data[uid]["final_markup"] = markup
        user_data[uid]["state"] = None # State clear

        btns = [[InlineKeyboardButton("🚀 Send to Channel", callback_data="send_now")]]
        await message.reply("Sab set hai! Button daba ke channel me bhejo:", reply_markup=InlineKeyboardMarkup(btns))

# --- CALLBACKS (Buttons) ---
@app.on_callback_query(filters.regex("^(set_single|set_batch|sel_|gen_link|send_now)"))
async def callbacks(client, query):
    uid = query.from_user.id
    data = query.data

    if data == "set_single":
        user_data[uid]["mode"] = "single"
        await query.message.edit("Database channel se 1 episode bot me forward karo, fir `/link` command do.")

    elif data == "set_batch":
        user_data[uid]["mode"] = "batch"
        await query.message.edit("Start & End episode bot me forward karo, fir `/link` command do.")

    elif data.startswith("sel_"):
        chat_id = int(data.split("_")[1])
        user_data[uid]["selected_chats"].append(chat_id)
        await query.answer("Channel Added!")

    elif data == "gen_link":
        user_data[uid]["state"] = "waiting_num"
        await query.message.edit("📝 Button me likhne ke liye Episode Number daalo (e.g. 1, 2, 3):")

    elif data == "send_now":
        post = user_data[uid].get("post")
        markup = user_data[uid].get("final_markup")
        
        if not post or not markup:
            return await query.answer("Error: Data lost! Wapis /post se start karo.", show_alert=True)

        await post.copy(DB_CHANNEL, reply_markup=markup)
        await query.message.edit("🎉 Post successfully channel me send ho gaya!")

# --- RUN ---
if __name__ == "__main__":
    Thread(target=run_web).start()
    print("Bot Started...")
    app.run()
