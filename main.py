import os
import asyncio
import aiohttp
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread

# --- WEB SERVER ---
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot is running perfectly!"

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

# --- SHORTENER ---
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

# --- START ---
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    if len(message.text.split()) > 1:
        data = message.text.split()[1]
        if not await is_subscribed(message.from_user.id):
            btns = [[InlineKeyboardButton("Join Channel", url="https://t.me/your_channel_link")]]
            return await message.reply("Pehle Join Karo!", reply_markup=InlineKeyboardMarkup(btns))

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
    await message.reply("Bhai, post bhejo pehle!")

# --- SETTINGS ---
@app.on_message(filters.command("setting") & filters.user(ALLOWED_USERS))
async def settings_cmd(client, message):
    await message.reply("""
⚙️ **Bot Commands**

/start - Bot start  
/link - Link generate  
/link_shortener - Shortener set  
/setting - Commands list  

**Setup:**
1. Post bhejo  
2. Link / Batch select karo  
3. /link  
4. Done → Number → Send  

🔥 Ready!
""")

# --- POST HANDLER ---
@app.on_message(filters.user(ALLOWED_USERS) & filters.private & ~filters.command(["start","link","link_shortener","setting"]))
async def process_post(client, message):
    uid = message.from_user.id

    if uid in user_data and user_data[uid].get("state"):
        return

    if message.text or message.caption or message.photo or message.video or message.document:
        user_data[uid] = {"post": message, "selected_chats": []}

        btns = [[
            InlineKeyboardButton("Link", callback_data="set_single"),
            InlineKeyboardButton("Batch Link", callback_data="set_batch")
        ]]
        await message.reply("Option select karo:", reply_markup=InlineKeyboardMarkup(btns))

# --- SHORTENER SETUP ---
@app.on_message(filters.command("link_shortener") & filters.user(ALLOWED_USERS))
async def shortener_setup(client, message):
    uid = message.from_user.id
    user_data.setdefault(uid, {})
    user_data[uid]["state"] = "set_url"
    await message.reply("Shortener domain bhejo (e.g. gplinks.com):")

# --- CALLBACK FIXED ---
@app.on_callback_query(filters.regex("^(set_single|set_batch|sel_)"))
async def callbacks(client, query):
    uid = query.from_user.id
    data = query.data

    if data == "set_single":
        user_data[uid]["mode"] = "single"
        await query.message.edit("Database se 1 episode forward karo, fir /link command do.")

    elif data == "set_batch":
        user_data[uid]["mode"] = "batch"
        await query.message.edit("Start & End episode forward karo, fir /link command do.")

    elif data.startswith("sel_"):
        chat_id = int(data.split("_")[1])
        user_data[uid]["selected_chats"].append(chat_id)
        await query.answer("Added!")

# --- LINK ---
@app.on_message(filters.command("link") & filters.user(ALLOWED_USERS))
async def get_link_command(client, message):
    await message.reply("Done pe click karein", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("Done", callback_data="gen_link")]
    ]))

@app.on_callback_query(filters.regex("gen_link"))
async def generate_final_step(client, query):
    uid = query.from_user.id
    user_data[uid]["state"] = "waiting_num"
    await query.message.edit("Episode Number daalo:")

# --- INPUT HANDLER ---
@app.on_message(filters.private & filters.user(ALLOWED_USERS) & filters.text & ~filters.command(["start","link","link_shortener","setting"]))
async def handle_inputs(client, message):
    uid = message.from_user.id
    if uid not in user_data:
        return

    state = user_data[uid].get("state")

    if state == "set_url":
        bot_settings["shortener_url"] = message.text.strip().replace("https://","").replace("/","")
        user_data[uid]["state"] = "set_api"
        await message.reply("API Token bhejo:")

    elif state == "set_api":
        bot_settings["shortener_api"] = message.text.strip()
        user_data[uid]["state"] = None
        await message.reply("✅ Shortener Set Ho Gya!")

    elif state == "waiting_num":
        num = message.text

        bot_user = (await client.get_me()).username
        f_link = f"https://t.me/{bot_user}?start=file_id_here"
        s_link = await get_shortlink(f_link)

        markup = InlineKeyboardMarkup([[InlineKeyboardButton(f"Episode {num}", url=s_link)]])
        user_data[uid]["final_markup"] = markup

        btns = [[InlineKeyboardButton("Send to Channel", callback_data="send_now")]]
        await message.reply("Done dabao:", reply_markup=InlineKeyboardMarkup(btns))

# --- FINAL SEND ---
@app.on_callback_query(filters.regex("send_now"))
async def final_send(client, query):
    uid = query.from_user.id
    post = user_data[uid]["post"]
    markup = user_data[uid]["final_markup"]

    await post.copy(DB_CHANNEL, reply_markup=markup)
    await query.message.edit("Post send ho gaya ✅")

# --- RUN ---
if __name__ == "__main__":
    Thread(target=run_web).start()
    app.run()
