import asyncio
import aiohttp
from aiohttp import web
import string
import random
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant
import config
import database as db

bot = Client(
    "AnimeBot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN
)

# State Management Dictionary
user_states = {}

# Web Server for Render (Keep Alive)
async def web_server():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Bot is Running on Port 10000!"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', config.PORT)
    await site.start()

# --- Auth Check ---
def is_auth(user_id):
    return user_id in config.ALLOWED_USERS or user_id == config.OWNER_ID

# --- Shortener Logic ---
async def get_shortlink(long_url):
    shorteners = await db.get_all_shorteners()
    if not shorteners:
        return long_url
    
    # Randomly select a shortener (Auto Rotation)
    shortener = random.choice(shorteners)
    api_url = f"https://{shortener['name']}/api?api={shortener['api']}&url={long_url}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                res = await response.json()
                if res.get("status") == "success":
                    return res.get("shortenedUrl")
    except Exception as e:
        pass
    return long_url

# --- Admin Chat Tracking ---
@bot.on_message(filters.group & filters.new_chat_members)
async def track_admin_channels(client, message):
    for member in message.new_chat_members:
        if member.id == bot.me.id:
            await db.admin_channels_db.update_one(
                {"chat_id": message.chat.id}, 
                {"$set": {"chat_name": message.chat.title}}, 
                upsert=True
            )

# --- F-Sub System ---
@bot.on_message(filters.command("Force sub") & filters.user(config.ALLOWED_USERS))
async def force_sub_setup(client, message):
    user_states[message.from_user.id] = {"state": "WAITING_FSUB"}
    await message.reply("Please send message and check I'm admin gc")

@bot.on_message(filters.forwarded & filters.user(config.ALLOWED_USERS))
async def handle_forwards(client, message):
    user_id = message.from_user.id
    state_info = user_states.get(user_id)
    
    if state_info and state_info["state"] == "WAITING_FSUB":
        chat_id = message.forward_from_chat.id
        chat_name = message.forward_from_chat.title
        try:
            link = await client.export_chat_invite_link(chat_id)
            await db.fsub_db.update_one({"chat_id": chat_id}, {"$set": {"name": chat_name, "link": link}}, upsert=True)
            await message.reply("😘 adding successfully 😲")
            del user_states[user_id]
        except Exception as e:
            await message.reply("Bot is not admin with invite link permission there!")

# --- Post System ---
@bot.on_message(filters.command("post") & filters.user(config.ALLOWED_USERS))
async def post_cmd(client, message):
    user_states[message.from_user.id] = {"state": "WAITING_POST_MEDIA"}
    await message.reply("send post")

@bot.on_message(filters.photo | filters.document)
async def handle_media(client, message):
    user_id = message.from_user.id
    if user_id not in config.ALLOWED_USERS: return
    
    state_info = user_states.get(user_id)
    if not state_info: return

    if state_info["state"] == "WAITING_POST_MEDIA":
        state_info["media"] = message.message_id
        state_info["state"] = "WAITING_POST_TYPE"
        await message.reply("post successfully received\nPlease provide single link or batch link (Reply: 'single link' or 'batch link')")
        
    elif state_info["state"] == "WAITING_SINGLE_EPISODE":
        # Forward to storage channel
        msg = await message.copy(config.STORAGE_CHANNEL)
        state_info["file_id"] = msg.id
        state_info["state"] = "WAITING_EP_NUMBER"
        await message.reply("Enter Number")

    elif state_info["state"] == "WAITING_BATCH_EPISODE":
        msg = await message.copy(config.STORAGE_CHANNEL)
        if "first_file" not in state_info:
            state_info["first_file"] = msg.id
            await message.reply("send next episode (or type /done if finished)")
        else:
            state_info["last_file"] = msg.id
            await message.reply("batch successfully adding\nSend next episode or type /done")

@bot.on_message(filters.text & filters.user(config.ALLOWED_USERS))
async def handle_text_states(client, message):
    user_id = message.from_user.id
    text = message.text
    state_info = user_states.get(user_id)
    
    if not state_info: return

    if state_info["state"] == "WAITING_POST_TYPE":
        if text.lower() == "single link":
            state_info["type"] = "single"
            state_info["state"] = "WAITING_SINGLE_EPISODE"
            await message.reply("send episode")
        elif text.lower() == "batch link":
            state_info["type"] = "batch"
            state_info["state"] = "WAITING_BATCH_EPISODE"
            await message.reply("send episode")
            
    elif state_info["state"] == "WAITING_EP_NUMBER":
        state_info["ep_num"] = text
        state_info["state"] = "WAITING_CONFIRM_1"
        await message.reply("/confirm")

    elif text == "/done" and state_info["state"] == "WAITING_BATCH_EPISODE":
        state_info["state"] = "WAITING_BATCH_NUMBER"
        await message.reply("Enter number (Example: 05 - 15)")

    elif state_info["state"] == "WAITING_BATCH_NUMBER":
        state_info["ep_num"] = text
        state_info["state"] = "WAITING_CONFIRM_1"
        await message.reply("/confirm")

    elif text == "/confirm" and state_info["state"] == "WAITING_CONFIRM_1":
        state_info["state"] = "WAITING_HMM"
        # Dummy trigger to match your workflow
        pass 

    elif text == "/hmm" and state_info["state"] == "WAITING_HMM":
        # Generate hash and save DB
        hash_code = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        if state_info["type"] == "single":
            data = {"type": "single", "msg_id": state_info["file_id"]}
        else:
            data = {"type": "batch", "start_id": state_info["first_file"], "end_id": state_info["last_file"]}
            
        await db.save_post_link(hash_code, data)
        
        bot_usr = await client.get_me()
        bot_link = f"https://t.me/{bot_usr.username}?start={hash_code}"
        
        btn = InlineKeyboardMarkup([[InlineKeyboardButton(f"Watch episode {state_info['ep_num']}", url=bot_link)]])
        
        # Send post to admin for review
        saved_msg = await client.copy_message(user_id, user_id, state_info["media"], reply_markup=btn)
        
        state_info["final_msg"] = saved_msg.id
        state_info["state"] = "WAITING_SEND_CHOICE"
        await message.reply("[ Send ]\n[ Send more channel ]")

    elif text == "/send" and state_info["state"] == "WAITING_SEND_CHOICE":
        channels = await db.admin_channels_db.find().to_list(length=100)
        msg = "Select Channel:\n"
        for i, ch in enumerate(channels):
            msg += f"{i+1}. {ch['chat_name']} (/sel_{ch['chat_id']})\n"
        state_info["state"] = "WAITING_CHANNEL_SELECT"
        state_info["target"] = []
        await message.reply(msg)

    elif text == "/send more channel" and state_info["state"] == "WAITING_SEND_CHOICE":
        channels = await db.admin_channels_db.find().to_list(length=100)
        msg = "Select Channels (Click multiple):\n"
        for i, ch in enumerate(channels):
            msg += f"{i+1}. {ch['chat_name']} (/sel_{ch['chat_id']})\n"
        msg += "\nType /done_sel when finished"
        state_info["state"] = "WAITING_MULTI_CHANNEL"
        state_info["target"] = []
        await message.reply(msg)

    elif text.startswith("/sel_"):
        ch_id = int(text.split("_")[1])
        state_info["target"].append(ch_id)
        if state_info["state"] == "WAITING_CHANNEL_SELECT":
            state_info["state"] = "WAITING_FINAL_CONFIRM"
            await message.reply("confirm please\nType /confirm")
        else:
            await message.reply(f"Added. Select more or /done_sel")

    elif text == "/done_sel" and state_info["state"] == "WAITING_MULTI_CHANNEL":
        state_info["state"] = "WAITING_FINAL_CONFIRM"
        await message.reply("confirm please\nType /confirm")

    elif text == "/confirm" and state_info["state"] == "WAITING_FINAL_CONFIRM":
        for ch in state_info["target"]:
            await client.copy_message(ch, user_id, state_info["final_msg"])
        await message.reply("Post Successfully Sent to Channels! 🎉")
        del user_states[user_id]


# --- User Start & Unlock System ---
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    user_id = message.from_user.id
    text = message.text.split()
    
    # Check if banned
    if await db.banned_db.find_one({"user_id": user_id}):
        return await message.reply("You are banned from using this bot.")

    if len(text) > 1:
        param = text[1]
        
        # 1. Verification Process (After Shortener)
        if param.startswith("verify_"):
            token = param.split("_")[1]
            token_data = await db.tokens_db.find_one({"token": token, "user_id": user_id})
            
            if not token_data:
                return await message.reply("Link Expired or Invalid!")
            
            # CHECK FORCE SUB HERE
            fsubs = await db.get_fsub_channels()
            not_joined = []
            for ch in fsubs:
                try:
                    await client.get_chat_member(ch["chat_id"], user_id)
                except UserNotParticipant:
                    not_joined.append(ch)
            
            if not_joined:
                btns = []
                for ch in not_joined:
                    btns.append([InlineKeyboardButton(f"Join {ch['name']}", url=ch['link'])])
                btns.append([InlineKeyboardButton("Try Again", url=f"https://t.me/{(await client.get_me()).username}?start=verify_{token}")])
                return await message.reply("Join first", reply_markup=InlineKeyboardMarkup(btns))
            
            # Send Episode
            link_data = await db.get_post_link(token_data["hash"])
            await db.tokens_db.delete_one({"token": token}) # Delete token after use
            
            if link_data["data"]["type"] == "single":
                await client.copy_message(user_id, config.STORAGE_CHANNEL, link_data["data"]["msg_id"])
            else:
                for msg_id in range(link_data["data"]["start_id"], link_data["data"]["end_id"] + 1):
                    await client.copy_message(user_id, config.STORAGE_CHANNEL, msg_id)
            return

        # 2. Main Link Click Process
        hash_code = param
        link_data = await db.get_post_link(hash_code)
        if not link_data:
            return await message.reply("Invalid Link!")

        # Premium Bypass
        if await db.is_premium(user_id):
            if link_data["data"]["type"] == "single":
                await client.copy_message(user_id, config.STORAGE_CHANNEL, link_data["data"]["msg_id"])
            else:
                for msg_id in range(link_data["data"]["start_id"], link_data["data"]["end_id"] + 1):
                    await client.copy_message(user_id, config.STORAGE_CHANNEL, msg_id)
            return
        
        # Non-Premium -> Give Shortener Link
        token = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        await db.tokens_db.insert_one({"token": token, "user_id": user_id, "hash": hash_code})
        
        verify_link = f"https://t.me/{(await client.get_me()).username}?start=verify_{token}"
        short_url = await get_shortlink(verify_link)
        
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("Unlock Episode", url=short_url)]])
        await message.reply("Please solve the link to get your episode!", reply_markup=btn)
        
    else:
        await message.reply("Welcome to Anime Post Bot!")

# --- Shortener & Premium Admin Commands ---
@bot.on_message(filters.command("add shortner account") & filters.user(config.ALLOWED_USERS))
async def add_shortener_cmd(client, message):
    user_states[message.from_user.id] = {"state": "WAITING_SHORT_URL"}
    await message.reply("provide deskbord url (e.g. gplinks.in)")

@bot.on_message(filters.command("remove shortner account") & filters.user(config.ALLOWED_USERS))
async def remove_shortener_cmd(client, message):
    shorts = await db.get_all_shorteners()
    msg = "Select account:\n"
    for s in shorts:
        msg += f"- {s['name']} (/delshort_{s['name'].replace('.', '')})\n"
    await message.reply(msg)

@bot.on_message(filters.regex(r"/delshort_") & filters.user(config.ALLOWED_USERS))
async def del_short_trigger(client, message):
    user_states[message.from_user.id] = {"state": "WAITING_DELETE_CONFIRM", "target": message.text.split("_")[1]}
    await message.reply("kya aap hatana chahte hai\nToh delete\nType /delete")

@bot.on_message(filters.command("delete") & filters.user(config.ALLOWED_USERS))
async def del_short_confirm(client, message):
    state = user_states.get(message.from_user.id)
    if state and state.get("state") == "WAITING_DELETE_CONFIRM":
        await db.shorteners_db.delete_many({"name": {"$regex": state["target"]}})
        await message.reply("successfully delete account for shortner")
        del user_states[message.from_user.id]

@bot.on_message(filters.command("add premium") & filters.user(config.ALLOWED_USERS))
async def add_prem_cmd(client, message):
    user_states[message.from_user.id] = {"state": "WAITING_PREM_ID"}
    await message.reply("send I'd")

@bot.on_message(filters.command("remove premium") & filters.user(config.ALLOWED_USERS))
async def rem_prem_cmd(client, message):
    user_states[message.from_user.id] = {"state": "WAITING_REM_PREM_ID"}
    await message.reply("send I'd")

@bot.on_message(filters.text & filters.user(config.ALLOWED_USERS), group=2)
async def handle_misc_text(client, message):
    user_id = message.from_user.id
    text = message.text
    state_info = user_states.get(user_id)
    
    if not state_info: return

    if state_info.get("state") == "WAITING_SHORT_URL":
        state_info["short_url"] = text
        state_info["state"] = "WAITING_SHORT_API"
        await message.reply("successfully send Your API Token")
        
    elif state_info.get("state") == "WAITING_SHORT_API":
        await db.add_shortener(state_info["short_url"], text)
        await message.reply("successfully add 🤗🤗🤗")
        del user_states[user_id]
        
    elif state_info.get("state") == "WAITING_PREM_ID":
        state_info["prem_id"] = int(text)
        state_info["state"] = "WAITING_HUHU"
        await message.reply("successfully add member\nPlease confirm type /hu hu")
        
    elif state_info.get("state") == "WAITING_HUHU" and text == "/hu hu":
        await db.add_premium(state_info["prem_id"])
        await message.reply(f"successfully add member {state_info['prem_id']} 🪄🪄🪄")
        del user_states[user_id]
        
    elif state_info.get("state") == "WAITING_REM_PREM_ID":
        await db.ban_user(int(text))
        await message.reply("successfully deleted and ban")
        del user_states[user_id]


async def main():
    await bot.start()
    print("Bot is started!")
    await web_server() # Render Web server
    from pyrogram import idle
    await idle()

if __name__ == "__main__":
    bot.run(main())
