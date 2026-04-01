import os
import asyncio
import aiohttp
from aiohttp import web
import base64
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from motor.motor_asyncio import AsyncIOMotorClient

# ================= RENDER VARIABLES =================
# We fetch API details directly from Render Variables
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

OWNER_ID = int(os.environ.get("OWNER_ID", 5351848105))
STORAGE_CHANNEL = int(os.environ.get("STORAGE_CHANNEL", -1003096528862))
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://aasifhusenaasifkhan_db_user:64CtKuQjWL0EzYMO@botcluster.v4land1.mongodb.net/?retryWrites=true&w=majority")

# ================= DATABASE SETUP =================
client_db = AsyncIOMotorClient(MONGO_URI)
db = client_db["AnimeBotDB"]
shortener_db = db["shortener"]

# ================= BOT INITIALIZE =================
bot = Client("FileStoreBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# User States Dictionary (RAM)
user_states = {}

# Web Server (For Render Port 10000)
async def web_server():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Bot is running successfully!"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()

# ================= HELPER FUNCTIONS =================
def encode_data(data: str):
    # Data ko base64 format me encode karta hai (taaki link lambi aur professional lage)
    return base64.urlsafe_b64encode(data.encode("ascii")).decode("ascii")

def decode_data(data: str):
    # Base64 link ko wapas text me badalta hai
    try:
        return base64.urlsafe_b64decode(data.encode("ascii")).decode("ascii")
    except Exception:
        return None

async def get_shortlink(long_url, domain, api):
    # Link ko Shortener site par bhejkar short link lata hai (with safety timeout)
    api_url = f"https://{domain}/api?api={api}&url={long_url}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=5) as response:
                data = await response.json()
                if data.get("status") == "success" or "shortenedUrl" in data:
                    return data.get("shortenedUrl")
    except Exception as e:
        print(f"Shortener Error: {e}")
    return long_url # Agar error aaya toh direct link hi de dega (bot rukega nahi)

async def send_files(client, message, user_id, data_str):
    wait_msg = await message.reply_text("⏳ Processing your files... Please wait.")
    try:
        if "-" in data_str: # Batch Link Logic
            start_msg, end_msg = map(int, data_str.split("-"))
            for msg_id in range(start_msg, end_msg + 1):
                try:
                    await client.copy_message(user_id, STORAGE_CHANNEL, msg_id)
                    await asyncio.sleep(0.5) # Telegram Ban se bachne ke liye 0.5s ka aaram
                except Exception:
                    pass # Agar koi bich ki file delete ho gayi ho toh error na de
        else: # Single Link Logic
            msg_id = int(data_str)
            await client.copy_message(user_id, STORAGE_CHANNEL, msg_id)
        
        await wait_msg.delete()
    except Exception as e:
        await wait_msg.edit_text("❌ Error: File not found or deleted from database.")

# ================= MAIN COMMANDS =================

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    user_id = message.from_user.id
    text = message.text.split()
    
    # 1. Start Menu (If no payload)
    if len(text) == 1:
        return await message.reply_text(
            f"**Hello {message.from_user.first_name}!**\n\nI am an Advanced File Store Bot.\nI can store files and provide shareable links.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("About Dev", url="https://t.me/telegram")]])
        )

    # 2. Extract Payload
    payload = text[1]

    # 3. Shortener Verification Process
    if payload.startswith("verify_"):
        real_payload = payload.replace("verify_", "")
        real_data = decode_data(real_payload)
        if not real_data:
            return await message.reply_text("❌ Invalid Link!")
        
        await send_files(client, message, user_id, real_data)
        return

    # 4. Main Request Process
    real_data = decode_data(payload)
    if not real_data:
        return await message.reply_text("❌ Invalid Link!")

    # For Owner: Direct Access (No Shortener)
    if user_id == OWNER_ID:
        await send_files(client, message, user_id, real_data)
        return

    # For Normal Users: Check if shortener is active
    short_info = await shortener_db.find_one({"_id": "current"})
    
    if short_info:
        # Create Verify Link and Shorten it
        bot_uname = (await client.get_me()).username
        verify_link = f"https://t.me/{bot_uname}?start=verify_{payload}"
        
        await message.reply_text("⏳ Generating secure link...")
        short_link = await get_shortlink(verify_link, short_info["domain"], short_info["api"])
        
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("Unlock Files 🔓", url=short_link)]])
        await message.reply_text("⚠️ **You must unlock this link to get your files!**", reply_markup=btn)
    else:
        # If no shortener is added, give direct files
        await send_files(client, message, user_id, real_data)

# ================= ADMIN COMMANDS =================

@bot.on_message(filters.command("genlink") & filters.user(OWNER_ID))
async def genlink_cmd(client, message: Message):
    user_states[message.from_user.id] = "WAIT_SINGLE"
    await message.reply_text("📌 Please forward a message from your **Storage Channel** to generate a Single Link.\n\nType /cancel to cancel.")

@bot.on_message(filters.command("batch") & filters.user(OWNER_ID))
async def batch_cmd(client, message: Message):
    user_states[message.from_user.id] = "WAIT_BATCH_1"
    await message.reply_text("📌 Forward the **FIRST** message of the batch from your **Storage Channel**.\n\nType /cancel to cancel.")

@bot.on_message(filters.command("shortener") & filters.user(OWNER_ID))
async def shortener_cmd(client, message: Message):
    user_states[message.from_user.id] = {"state": "WAIT_DOMAIN"}
    await message.reply_text("📌 Send your Shortener Domain (Example: `gplinks.in` or `shrinkme.io`)\n\nType /cancel to abort.")

@bot.on_message(filters.command("delshortener") & filters.user(OWNER_ID))
async def delshortener_cmd(client, message: Message):
    await shortener_db.delete_one({"_id": "current"})
    await message.reply_text("✅ Shortener successfully removed! Direct links will now be given.")

@bot.on_message(filters.command("cancel") & filters.private)
async def cancel_cmd(client, message: Message):
    user_id = message.from_user.id
    if user_id in user_states:
        del user_states[user_id]
        await message.reply_text("✅ Process cancelled successfully.")
    else:
        await message.reply_text("You have no active process to cancel.")

# ================= STATE HANDLERS (BUG FIX) =================
# Group 1 ensures this text handler does not conflict with main commands

@bot.on_message(filters.private & filters.text & filters.user(OWNER_ID), group=1)
async def text_state_handler(client, message: Message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    text = message.text

    if not state or text.startswith("/"):
        return # Ignore if no state or user typed a command

    if isinstance(state, dict):
        if state.get("state") == "WAIT_DOMAIN":
            user_states[user_id] = {"state": "WAIT_API", "domain": text}
            await message.reply_text(f"✅ Domain `{text}` Saved.\n\n📌 Now send your **API Token**:")
        
        elif state.get("state") == "WAIT_API":
            domain = state["domain"]
            api_token = text
            await shortener_db.update_one({"_id": "current"}, {"$set": {"domain": domain, "api": api_token}}, upsert=True)
            await message.reply_text(f"🎉 **Shortener Successfully Attached!**\n\nDomain: `{domain}`\nAll new requests will now use this shortener.")
            del user_states[user_id]

@bot.on_message(filters.forwarded & filters.private & filters.user(OWNER_ID), group=1)
async def forward_state_handler(client, message: Message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    
    if not state:
        return

    if message.forward_from_chat and message.forward_from_chat.id == STORAGE_CHANNEL:
        msg_id = message.forward_from_message_id
        bot_uname = (await client.get_me()).username

        if state == "WAIT_SINGLE":
            code = encode_data(str(msg_id))
            link = f"https://t.me/{bot_uname}?start={code}"
            await message.reply_text(f"🔗 **Here is your Single Link:**\n\n{link}", disable_web_page_preview=True)
            del user_states[user_id]

        elif state == "WAIT_BATCH_1":
            user_states[user_id] = {"state": "WAIT_BATCH_2", "start_id": msg_id}
            await message.reply_text("✅ First message saved!\n\n📌 Now forward the **LAST** message of the batch.")

        elif isinstance(state, dict) and state.get("state") == "WAIT_BATCH_2":
            start_id = state["start_id"]
            end_id = msg_id
            
            # Agar Admin ne galti se pichli file aage select kar di ho, to Bot use automatically seedha kar dega (Auto-Fix)
            if start_id > end_id:
                start_id, end_id = end_id, start_id 

            code = encode_data(f"{start_id}-{end_id}")
            link = f"https://t.me/{bot_uname}?start={code}"
            await message.reply_text(f"🔗 **Here is your Batch Link:**\n\n{link}", disable_web_page_preview=True)
            del user_states[user_id]
    else:
        await message.reply_text(f"❌ Error: Please forward the message **ONLY** from your specified Storage Channel.")

# ================= RUNNER =================
async def main():
    if not API_ID or not BOT_TOKEN:
        print("CRITICAL ERROR: API_ID or BOT_TOKEN is missing from Render Variables!")
        return
    await bot.start()
    print("=======================================")
    print("BOT IS SUCCESSFULLY RUNNING!")
    print("=======================================")
    await web_server()
    from pyrogram import idle
    await idle()

if __name__ == "__main__":
    bot.run(main())
