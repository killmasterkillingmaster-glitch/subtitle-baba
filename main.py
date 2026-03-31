import os
import asyncio
import datetime
import string
import random
from aiohttp import web, ClientSession
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient

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

# ================= STATE MANAGEMENT =================
# Ye dictionary bot ko yaad dilayegi ki user kis step par hai (No timeouts!)
USER_STATE = {}

# ================= WEB SERVER FOR RENDER =================
async def handle_web(request):
    return web.Response(text="Bot is running smoothly on Render!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()

# ================= HELPER FUNCTIONS =================
def is_admin(user_id):
    return user_id == OWNER or user_id in ALLOWED_USERS

async def get_shortlink(url):
    shorteners = await shorteners_db.find().to_list(length=100)
    if not shorteners:
        return url
    shortener = random.choice(shorteners)
    api_url = shortener['url']
    if not api_url.endswith('/'): api_url += '/'
    api_token = shortener['token']
    
    try:
        req_url = f"{api_url}api?api={api_token}&url={url}"
        async with ClientSession() as session:
            async with session.get(req_url) as resp:
                data = await resp.json()
                if data.get("status") == "success":
                    return data.get("shortenedUrl")
                return url
    except Exception:
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

# ================= START & FILE DELIVERY =================
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    user_id = message.from_user.id
    text = message.text

    USER_STATE.pop(user_id, None) # Clear any pending states

    user_data = await premium_db.find_one({"user_id": user_id})
    if user_data and user_data.get("is_banned", False):
        return await message.reply("You are banned from using this bot.")

    if len(text.split()) > 1:
        payload = text.split()[1]
        
        fsub_channels = await check_fsub(client, user_id)
        if fsub_channels:
            buttons = []
            for i, ch in enumerate(fsub_channels):
                buttons.append([InlineKeyboardButton(f"Join Channel {i+1}", url=ch['invite_link'])])
            buttons.append([InlineKeyboardButton("Try Again", url=f"https://t.me/{client.me.username}?start={payload}")])
            return await message.reply("Join first \nPlease join all channels below.", reply_markup=InlineKeyboardMarkup(buttons))

        is_premium = False
        if user_data:
            expiry = user_data.get("expiry")
            if expiry and datetime.datetime.now() < expiry:
                is_premium = True

        if not is_premium and not payload.startswith("verify_"):
            verify_url = f"https://t.me/{client.me.username}?start=verify_{payload}"
            short_url = await get_shortlink(verify_url)
            btn = [[InlineKeyboardButton("Get Episode / Verify", url=short_url)]]
            return await message.reply("Please solve the shortener to get the file.", reply_markup=InlineKeyboardMarkup(btn))

        actual_payload = payload.replace("verify_", "")
        file_data = await files_db.find_one({"hash": actual_payload})
        if file_data:
            msg_ids = file_data['msg_ids']
            await client.forward_messages(chat_id=user_id, from_chat_id=STORAGE_CHANNEL_ID, message_ids=msg_ids)
            return
        else:
            return await message.reply("File not found.")

    await message.reply("Hii! Welcome to the Bot. I am working perfectly.")

# ================= MASTER STATE HANDLER =================
@bot.on_message(filters.private & ~filters.command("start"))
async def master_handler(client, message):
    user_id = message.from_user.id
    text = message.text

    if not is_admin(user_id):
        return

    # Check Commands to initialize states
    if text == "/add shortner account":
        USER_STATE[user_id] = {"cmd": "add_short", "step": 1}
        return await message.reply("Bot reply - provide deskbord url (e.g., https://gplinks.in/)")
        
    elif text == "/remove shortner account":
        shorteners = await shorteners_db.find().to_list(length=100)
        if not shorteners: return await message.reply("No accounts found.")
        msg_text = "Select account:\n"
        for i, s in enumerate(shorteners):
            msg_text += f"{i}. {s['url']} - {s['token'][:5]}...\n"
        msg_text += "\nEnter number:"
        USER_STATE[user_id] = {"cmd": "rem_short", "step": 1, "list": shorteners}
        return await message.reply(msg_text)

    elif text == "/add premium":
        USER_STATE[user_id] = {"cmd": "add_prem", "step": 1}
        return await message.reply("Bot reply - send I'd")

    elif text == "/remove premium":
        USER_STATE[user_id] = {"cmd": "rem_prem", "step": 1}
        return await message.reply("Bot reply - send I'd")

    elif text == "/show premium list":
        users = await premium_db.find({"is_banned": False}).to_list(length=100)
        txt = "Premium Users:\n"
        for u in users: txt += f"ID: {u['user_id']} | Expiry: {u['expiry'].strftime('%Y-%m-%d')}\n"
        return await message.reply(txt if users else "No premium users.")

    elif text == "/Force sub":
        USER_STATE[user_id] = {"cmd": "fsub", "step": 1}
        return await message.reply("Bot reply please send massage and chack I'm admin gc")

    elif text == "/post":
        USER_STATE[user_id] = {"cmd": "post", "step": 1, "data": {}}
        return await message.reply("Bot reply - send post")

    # If user is in a state, process steps
    if user_id in USER_STATE:
        state = USER_STATE[user_id]
        cmd = state["cmd"]
        step = state["step"]

        # === ADD SHORTENER ===
        if cmd == "add_short":
            if step == 1:
                state["url"] = text
                state["step"] = 2
                await message.reply("Bot reply - successfully send Your API Token")
            elif step == 2:
                await shorteners_db.insert_one({"url": state["url"], "token": text})
                await message.reply("Bot reply - successfully add 🤗🤗🤗")
                del USER_STATE[user_id]

        # === REMOVE SHORTENER ===
        elif cmd == "rem_short":
            if step == 1:
                try:
                    state["selected"] = state["list"][int(text)]
                    state["step"] = 2
                    await message.reply("Bot reply - kya aap hatana chahte hai\nToh delete (Send /delete)")
                except:
                    await message.reply("Invalid number. Try again.")
            elif step == 2 and text == "/delete":
                await shorteners_db.delete_one({"_id": state["selected"]["_id"]})
                await message.reply("Bot reply - successfully delete account for shortner")
                del USER_STATE[user_id]

        # === ADD PREMIUM ===
        elif cmd == "add_prem":
            if step == 1:
                state["target_id"] = int(text)
                state["step"] = 2
                await message.reply("Pleas confirm type /hu hu")
            elif step == 2 and text == "/hu hu":
                expiry = datetime.datetime.now() + datetime.timedelta(days=28)
                await premium_db.update_one({"user_id": state["target_id"]}, {"$set": {"expiry": expiry, "is_banned": False}}, upsert=True)
                await message.reply(f"Bot - successfully add member {state['target_id']} 🪄🪄🪄")
                del USER_STATE[user_id]

        # === REMOVE PREMIUM ===
        elif cmd == "rem_prem":
            if step == 1:
                await premium_db.update_one({"user_id": int(text)}, {"$set": {"is_banned": True}})
                await message.reply("Bot reply - successfully deleted and ban")
                del USER_STATE[user_id]

        # === FORCE SUB ===
        elif cmd == "fsub":
            if step == 1 and message.forward_from_chat:
                chat_id = message.forward_from_chat.id
                try:
                    invite_link = await client.export_chat_invite_link(chat_id)
                    await fsub_db.update_one({"chat_id": chat_id}, {"$set": {"invite_link": invite_link}}, upsert=True)
                    await message.reply("Bot reply - 😘 adding successfully 😲")
                    del USER_STATE[user_id]
                except Exception as e:
                    await message.reply(f"Make sure I am admin. Error: {e}")

        # === POST WORKFLOW ===
        elif cmd == "post":
            data = state["data"]
            
            if step == 1:
                # User sent the post (photo/video/doc)
                # Backup to Storage Channel directly
                copied_post = await message.copy(STORAGE_CHANNEL_ID)
                data["post_msg_id"] = copied_post.id
                state["step"] = 2
                await message.reply("Bot reply - post successfully received \nPlease provide single link or batch link")

            elif step == 2:
                if text.lower() == "single link":
                    data["type"] = "single"
                    state["step"] = 3
                    await message.reply("Bot reply - send episode")
                elif text.lower() == "batch link":
                    data["type"] = "batch"
                    state["step"] = 4
                    await message.reply("Bot reply - send episode (First)")
                else:
                    await message.reply("Type 'single link' or 'batch link'")

            elif step == 3: # Single link ep
                copied_ep = await message.copy(STORAGE_CHANNEL_ID)
                data["file_ids"] = [copied_ep.id]
                state["step"] = 6
                await message.reply("Bot Reply - Enter Number")

            elif step == 4: # Batch link first ep
                copied_ep = await message.copy(STORAGE_CHANNEL_ID)
                data["first_id"] = copied_ep.id
                state["step"] = 5
                await message.reply("Bot reply - send next episode")

            elif step == 5: # Batch link second ep
                copied_ep = await message.copy(STORAGE_CHANNEL_ID)
                data["last_id"] = copied_ep.id
                start_id = min(data["first_id"], data["last_id"])
                end_id = max(data["first_id"], data["last_id"])
                data["file_ids"] = list(range(start_id, end_id + 1))
                state["step"] = 6
                await message.reply("Bot reply - batch successfully adding\nEnter number")

            elif step == 6: # Enter number
                data["ep_num"] = text
                state["step"] = 7
                await message.reply("Bot reply - /confirm")

            elif step == 7 and text == "/confirm":
                state["step"] = 8
                await message.reply("Send /hmm")

            elif step == 8 and text == "/hmm":
                unique_hash = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
                await files_db.insert_one({"hash": unique_hash, "msg_ids": data["file_ids"]})
                
                bot_url = f"https://t.me/{client.me.username}?start={unique_hash}"
                data["btn"] = InlineKeyboardMarkup([[InlineKeyboardButton(f"Watch episode {data['ep_num']}", url=bot_url)]])
                
                # Fetch post from Storage Channel and send preview to user
                post_msg = await client.get_messages(STORAGE_CHANNEL_ID, data["post_msg_id"])
                await post_msg.copy(user_id, reply_markup=data["btn"])
                
                await message.reply("Fetching admin channels...")
                channels = []
                async for dialog in client.get_dialogs():
                    if dialog.chat.type == enums.ChatType.CHANNEL and dialog.chat.id != STORAGE_CHANNEL_ID:
                        channels.append({"name": dialog.chat.title, "id": dialog.chat.id})
                data["channels"] = channels
                
                state["step"] = 9
                await message.reply("Bot uske baad reply dega \n[ Send ]\n[ Send more channel]")

            elif step == 9:
                if text == "/send":
                    ch_text = "Select 1 Channel:\n"
                    for i, ch in enumerate(data["channels"]): ch_text += f"{i}. {ch['name']}\n"
                    state["step"] = 10
                    data["send_type"] = "single"
                    await message.reply(ch_text + "Enter Number:")
                elif text == "/send more channel":
                    ch_text = "Select Channels:\n"
                    for i, ch in enumerate(data["channels"]): ch_text += f"{i}. {ch['name']}\n"
                    state["step"] = 10
                    data["send_type"] = "multi"
                    await message.reply(ch_text + "Enter Numbers (e.g., 0, 1):")

            elif step == 10:
                try:
                    if data["send_type"] == "single":
                        data["selected"] = [data["channels"][int(text.strip())]]
                    else:
                        indexes = [int(x.strip()) for x in text.split(",")]
                        data["selected"] = [data["channels"][i] for i in indexes]
                    
                    state["step"] = 11
                    await message.reply("Bot reply - confirm please (/confirm)")
                except:
                    await message.reply("Invalid input. Try again.")

            elif step == 11 and text == "/confirm":
                post_msg = await client.get_messages(STORAGE_CHANNEL_ID, data["post_msg_id"])
                for ch in data["selected"]:
                    try:
                        await post_msg.copy(ch['id'], reply_markup=data["btn"])
                        await message.reply(f"Success -> {ch['name']}")
                    except Exception as e:
                        await message.reply(f"Failed -> {ch['name']}: {e}")
                del USER_STATE[user_id]

# ================= STARTING =================
async def main():
    await bot.start()
    print("Bot is successfully Started!")
    await start_web_server()
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
