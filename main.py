import os
import asyncio
import datetime
from aiohttp import web, ClientSession
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
import pyromod # Import pyromod for conversation (client.ask)

# ================= VARIABLES =================
API_ID = os.environ.get("API_ID", "YOUR_API_ID_HERE") 
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH_HERE")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

ALLOWED_USERS = [5344078567]
OWNER = 5351848105
ALLOWED_GROUP = -1003899919015
STORAGE_CHANNEL_ID = -1003096528862
MONGO_URI = "mongodb+srv://aasifhusenaasifkhan_db_user:64CtKuQjWL0EzYMO@botcluster.v4land1.mongodb.net/?retryWrites=true&w=majority"

# ================= DATABASE SETUP =================
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client["AnimeBotDB"]
shorteners_db = db["shorteners"]
premium_db = db["premium_users"]
fsub_db = db["fsub_channels"]
files_db = db["saved_files"]

bot = Client("MyBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ================= WEB SERVER FOR RENDER (Port 10000) =================
async def handle_web(request):
    return web.Response(text="Bot is running on Render free tier!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()
    print("Web server started on port 10000")

# ================= HELPER FUNCTIONS =================
def is_admin(user_id):
    return user_id == OWNER or user_id in ALLOWED_USERS

async def get_shortlink(url):
    # Shortener link rotation logic
    shorteners = await shorteners_db.find().to_list(length=100)
    if not shorteners:
        return url
    
    import random
    shortener = random.choice(shorteners)
    api_url = shortener['url']
    api_token = shortener['token']
    
    try:
        # Example for GP Link / URL ShortX etc.
        req_url = f"{api_url}api?api={api_token}&url={url}"
        async with ClientSession() as session:
            async with session.get(req_url) as resp:
                data = await resp.json()
                if data.get("status") == "success":
                    return data.get("shortenedUrl")
                return url
    except Exception as e:
        print(f"Shortener Error: {e}")
        return url

async def check_fsub(client, user_id):
    channels = await fsub_db.find().to_list(length=100)
    not_joined = []
    for ch in channels:
        try:
            member = await client.get_chat_member(ch['chat_id'], user_id)
            if member.status in [enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED]:
                not_joined.append(ch)
        except Exception:
            not_joined.append(ch)
    return not_joined

# ================= START COMMAND & FILE DELIVERY =================
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    user_id = message.from_user.id
    text = message.text

    # Ban Check
    user_data = await premium_db.find_one({"user_id": user_id})
    if user_data and user_data.get("is_banned", False):
        return await message.reply("You are banned from using this bot.")

    if len(text.split()) > 1:
        payload = text.split()[1]
        
        # Check Force Sub
        fsub_channels = await check_fsub(client, user_id)
        if fsub_channels:
            buttons = []
            for i, ch in enumerate(fsub_channels):
                buttons.append([InlineKeyboardButton(f"Join Channel {i+1}", url=ch['invite_link'])])
            buttons.append([InlineKeyboardButton("Try Again", url=f"https://t.me/{client.me.username}?start={payload}")])
            return await message.reply("Join first \nPlease join all channels below to get your file.", reply_markup=InlineKeyboardMarkup(buttons))

        # Check Premium
        is_premium = False
        if user_data:
            expiry = user_data.get("expiry")
            if expiry and datetime.datetime.now() < expiry:
                is_premium = True

        if not is_premium and not payload.startswith("verify_"):
            # Ager premium nahi hai to pehle shortener dena hai
            # Hum ek verify link banayenge taaki jab wo shortener solve karke aaye to detect ho
            bot_username = client.me.username
            verify_url = f"https://t.me/{bot_username}?start=verify_{payload}"
            short_url = await get_shortlink(verify_url)
            
            btn = [[InlineKeyboardButton("Get Episode / Verify", url=short_url)]]
            return await message.reply("Please solve the shortener to get the file.", reply_markup=InlineKeyboardMarkup(btn))

        # Deliver Files
        actual_payload = payload.replace("verify_", "")
        file_data = await files_db.find_one({"hash": actual_payload})
        if file_data:
            msg_ids = file_data['msg_ids']
            await client.forward_messages(chat_id=user_id, from_chat_id=STORAGE_CHANNEL_ID, message_ids=msg_ids)
            return
        else:
            return await message.reply("File not found or link expired.")

    await message.reply("Hii! Welcome to the Bot. I am working perfectly.")

# ================= SHORTENER MANAGEMENT =================
@bot.on_message(filters.command("add shortner account") & filters.private)
async def add_shortener(client, message):
    if not is_admin(message.from_user.id): return
    
    url_msg = await client.ask(message.chat.id, "Bot reply - provide deskbord url (with / at end like https://gplinks.in/)")
    url = url_msg.text
    
    token_msg = await client.ask(message.chat.id, "Bot reply - successfully send Your API Token")
    token = token_msg.text
    
    await shorteners_db.insert_one({"url": url, "token": token})
    await message.reply("Bot reply - successfully add 🤗🤗🤗")

@bot.on_message(filters.command("remove shortner account") & filters.private)
async def remove_shortener(client, message):
    if not is_admin(message.from_user.id): return
    
    shorteners = await shorteners_db.find().to_list(length=100)
    if not shorteners: return await message.reply("No accounts found.")
    
    text = "Select account:\n"
    for i, s in enumerate(shorteners):
        text += f"{i}. {s['url']} - {s['token'][:5]}...\n"
    
    sel_msg = await client.ask(message.chat.id, text + "\nEnter number to delete:")
    try:
        idx = int(sel_msg.text)
        selected = shorteners[idx]
        
        del_confirm = await client.ask(message.chat.id, "Bot reply - kya aap hatana chahte hai\nToh delete (Type /delete)")
        if del_confirm.text == "/delete":
            await shorteners_db.delete_one({"_id": selected["_id"]})
            await message.reply("Bot reply - successfully delete account for shortner")
    except:
        await message.reply("Invalid selection.")

# ================= PREMIUM MANAGEMENT =================
@bot.on_message(filters.command("add premium") & filters.private)
async def add_premium(client, message):
    if not is_admin(message.from_user.id): return
    
    id_msg = await client.ask(message.chat.id, "Bot reply - send I'd")
    target_id = int(id_msg.text)
    
    confirm_msg = await client.ask(message.chat.id, f"Bot reply - successfully add member {target_id}\nPleas confirm type /hu hu")
    if confirm_msg.text == "/hu hu":
        expiry = datetime.datetime.now() + datetime.timedelta(days=28)
        await premium_db.update_one(
            {"user_id": target_id},
            {"$set": {"expiry": expiry, "is_banned": False}},
            upsert=True
        )
        await message.reply(f"Bot - successfully add member {target_id} 🪄🪄🪄")

@bot.on_message(filters.command("remove premium") & filters.private)
async def remove_premium(client, message):
    if not is_admin(message.from_user.id): return
    
    id_msg = await client.ask(message.chat.id, "Bot reply - send I'd")
    target_id = int(id_msg.text)
    
    await premium_db.update_one(
        {"user_id": target_id},
        {"$set": {"is_banned": True}} # Ban the user permanently
    )
    await message.reply("Bot reply - successfully deleted and ban")

@bot.on_message(filters.command("show premium list") & filters.private)
async def show_premium(client, message):
    if not is_admin(message.from_user.id): return
    users = await premium_db.find({"is_banned": False}).to_list(length=100)
    text = "Premium Users:\n"
    for u in users:
        text += f"ID: {u['user_id']} | Expiry: {u['expiry'].strftime('%Y-%m-%d')}\n"
    await message.reply(text if users else "No premium users.")

# ================= FORCE SUB MANAGEMENT =================
@bot.on_message(filters.command("Force sub") & filters.private)
async def force_sub(client, message):
    if not is_admin(message.from_user.id): return
    
    fwd_msg = await client.ask(message.chat.id, "Bot reply please send massage and chack I'm admin gc (Forward message here)")
    if fwd_msg.forward_from_chat:
        chat_id = fwd_msg.forward_from_chat.id
        try:
            invite_link = await client.export_chat_invite_link(chat_id)
            await fsub_db.update_one(
                {"chat_id": chat_id},
                {"$set": {"invite_link": invite_link}},
                upsert=True
            )
            await message.reply("Bot reply - 😘 adding successfully 😲")
        except Exception as e:
            await message.reply(f"Failed. Make sure I am admin. Error: {e}")

# ================= POSTING WORKFLOW (Single & Batch) =================
@bot.on_message(filters.command("post") & filters.private)
async def post_workflow(client, message):
    if not is_admin(message.from_user.id): return
    
    # 02 Bot reply - send post
    post_msg = await client.ask(message.chat.id, "Bot reply - send post")
    
    # Bot reply - Please provide single link or batch link
    link_type_msg = await client.ask(message.chat.id, "Bot reply - post successfully received\nPlease provide single link or batch link (Type 'single link' or 'batch link')")
    
    msg_ids = []
    
    if link_type_msg.text.lower() == "single link":
        ep_msg = await client.ask(message.chat.id, "Bot reply - send episode (Forward from database)")
        # Save to storage (if not already there) or just get ID. 
        # For safety, we forward it to STORAGE_CHANNEL_ID
        copied = await ep_msg.copy(STORAGE_CHANNEL_ID)
        msg_ids.append(copied.id)
        
    elif link_type_msg.text.lower() == "batch link":
        first_ep = await client.ask(message.chat.id, "Bot reply - send episode (First episode)")
        copied_first = await first_ep.copy(STORAGE_CHANNEL_ID)
        
        last_ep = await client.ask(message.chat.id, "Bot reply - send next episode (Last episode)")
        copied_last = await last_ep.copy(STORAGE_CHANNEL_ID)
        
        # Add all message IDs between first and last (assuming sequential in DB)
        # Actually in TG, forwarded messages don't retain sequence. Users forward them.
        # But we copied them to DB. We will provide range
        start_id = min(copied_first.id, copied_last.id)
        end_id = max(copied_first.id, copied_last.id)
        msg_ids = list(range(start_id, end_id + 1))
        
        await message.reply("Bot reply - batch successfully adding")

    # Bot Reply - Enter Number
    num_msg = await client.ask(message.chat.id, "Bot Reply - Enter Number (e.g., 07 or 05 - 15)")
    ep_num = num_msg.text
    
    # Bot reply - confirm
    confirm_msg = await client.ask(message.chat.id, "Bot reply - /confirm")
    if confirm_msg.text != "/confirm": return
    
    # Bot reply - /hmm wait
    hmm_msg = await client.ask(message.chat.id, "Send /hmm")
    if hmm_msg.text != "/hmm": return
    
    # Create DB Entry for File Links
    import string
    import random
    unique_hash = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    await files_db.insert_one({"hash": unique_hash, "msg_ids": msg_ids})
    
    bot_username = client.me.username
    button_url = f"https://t.me/{bot_username}?start={unique_hash}"
    
    btn = InlineKeyboardMarkup([[InlineKeyboardButton(f"Watch episode {ep_num}", url=button_url)]])
    
    # Send Post preview back to User
    preview = await post_msg.copy(message.chat.id, reply_markup=btn)
    
    # Ask for broadcasting
    send_type = await client.ask(message.chat.id, "Bot uske baad reply dega\nType /send OR /send more channel")
    
    channels = [{"name": "Hindi sub anime", "id": -1001234567890}, {"name": "Gyaani baba", "id": -1009876543210}] 
    # NOTE: Yaha channel dictionary me apne actual channel ID dalna hoga jaha bot admin hai.
    # Abhi ke liye ye demo list banayi hai. Aap isko DB me add karwa sakte ho force_sub ki tarah.
    
    if send_type.text == "/send":
        ch_text = "Select 1 Channel:\n"
        for i, ch in enumerate(channels):
            ch_text += f"{i}. {ch['name']}\n"
        sel_ch = await client.ask(message.chat.id, ch_text + "\nEnter Number:")
        selected = [channels[int(sel_ch.text)]]
        
    elif send_type.text == "/send more channel":
        ch_text = "Select Channels (comma separated, e.g. 0, 1):\n"
        for i, ch in enumerate(channels):
            ch_text += f"{i}. {ch['name']}\n"
        sel_ch = await client.ask(message.chat.id, ch_text + "\nEnter Numbers:")
        indexes = [int(x.strip()) for x in sel_ch.text.split(",")]
        selected = [channels[i] for i in indexes]
        
    fin_confirm = await client.ask(message.chat.id, "Bot reply - confirm please (Type /confirm)")
    if fin_confirm.text == "/confirm":
        for ch in selected:
            try:
                # Update this line to use your real channel IDs 
                # e.g., await preview.copy(ch['id'], reply_markup=btn)
                await message.reply(f"Post successful to {ch['name']} (Demo mode - update channel IDs in code)")
            except Exception as e:
                await message.reply(f"Error posting to {ch['name']}: {e}")

# ================= STARTING BOT & SERVER =================
async def main():
    await bot.start()
    print("Bot is successfully Started!")
    await start_web_server()
    # Idle loop
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
