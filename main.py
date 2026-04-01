import os
import random
import asyncio
import threading
from datetime import datetime, timedelta
from flask import Flask
import aiohttp

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)
from motor.motor_asyncio import AsyncIOMotorClient

# ================= CONFIGURATION =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
PORT = int(os.getenv("PORT", 10000))

# Hardcoded Details
OWNER_ID = 5351848105
ALLOWED_USERS = [5344078567, 5351848105]
ALLOWED_GROUP = -1003899919015
STORAGE_CHANNEL = -1003096528862  # ASI anime

# ================= MONGODB SETUP =================
MONGO_URL = "mongodb+srv://aasifhusenaasifkhan_db_user:64CtKuQjWL0EzYMO@botcluster.v4land1.mongodb.net/?retryWrites=true&w=majority"
db_client = AsyncIOMotorClient(MONGO_URL)
db = db_client['anime_bot_db']
shorteners_col = db['shorteners']
premium_col = db['premium']
channels_col = db['channels']

# ================= FLASK SERVER (For Render) =================
app_flask = Flask(__name__)
@app_flask.route('/')
def home():
    return "Bot is Running Extremely Smooth with MongoDB! 🚀✅"

def run_flask():
    app_flask.run(host='0.0.0.0', port=PORT)

# ================= HELPER FUNCTIONS =================
async def is_user_premium(user_id):
    user = await premium_col.find_one({"_id": str(user_id)})
    if user:
        expiry = datetime.fromisoformat(user['expiry'])
        if datetime.now() < expiry:
            return True
        else:
            await premium_col.delete_one({"_id": str(user_id)}) # Delete if expired
    return False

async def get_short_link(long_url):
    docs = await shorteners_col.find().to_list(length=100)
    if not docs:
        return long_url
    
    shortener = random.choice(docs)
    try:
        async with aiohttp.ClientSession() as session:
            api_url = f"{shortener['url']}api?api={shortener['api']}&url={long_url}"
            async with session.get(api_url, timeout=10) as resp:
                data = await resp.json()
                if data.get("status") == "success":
                    return data.get("shortenedUrl")
    except Exception as e:
        print(f"Shortener API Error: {e}")
    return long_url

async def send_files(bot, user_id, data):
    try:
        if data.startswith("S_"):
            msg_id = int(data.split("_")[1])
            await bot.copy_message(chat_id=user_id, from_chat_id=STORAGE_CHANNEL, message_id=msg_id)
        elif data.startswith("B_"):
            parts = data.split("_")
            start_id, end_id = int(parts[1]), int(parts[2])
            for msg_id in range(start_id, end_id + 1):
                try:
                    await bot.copy_message(chat_id=user_id, from_chat_id=STORAGE_CHANNEL, message_id=msg_id)
                    await asyncio.sleep(0.5) # Anti-flood delay
                except:
                    pass # Ignore if a message was deleted in between
    except Exception as e:
        await bot.send_message(user_id, "File not found or deleted from server!")

# ================= USER BOT WORKFLOW =================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    if not args:
        return await update.message.reply_text("Bot Started Successfully! ✅ Send valid links to get files.")

    payload = args[0] # Example: req_S_123 or file_S_123

    # 1. Force Sub Check
    channels = await channels_col.find().to_list(length=100)
    not_joined = []
    
    for ch in channels:
        try:
            member = await context.bot.get_chat_member(int(ch['_id']), user_id)
            if member.status in ['left', 'kicked']:
                not_joined.append(ch)
        except:
            not_joined.append(ch) # User has not interacted with channel

    if not_joined:
        buttons = []
        for ch in not_joined:
            chat = await context.bot.get_chat(int(ch['_id']))
            link = chat.invite_link or (f"https://t.me/{chat.username}" if chat.username else None)
            if link:
                buttons.append([InlineKeyboardButton(f"Join {ch['title']}", url=link)])
        
        buttons.append([InlineKeyboardButton("Try again", url=f"https://t.me/{context.bot.username}?start={payload}")])
        return await update.message.reply_text("join first", reply_markup=InlineKeyboardMarkup(buttons))

    # 2. Premium Check & File Delivery
    is_prem = await is_user_premium(user_id)

    if payload.startswith("req_"):
        real_data = payload.replace("req_", "")
        
        if is_prem or (await shorteners_col.count_documents({})) == 0:
            await send_files(context.bot, user_id, real_data)
        else:
            bot_link = f"https://t.me/{context.bot.username}?start=file_{real_data}"
            short_url = await get_short_link(bot_link)
            
            await update.message.reply_text(
                f"📥 **Link Generated!**\n\nBina ads ke dekhne ke liye premium lijiye.\n\nPlease solve this link to get your episode:\n👉 {short_url}",
                disable_web_page_preview=True
            )
            
    elif payload.startswith("file_"):
        real_data = payload.replace("file_", "")
        await send_files(context.bot, user_id, real_data)

# ================= ADMIN POST SYSTEM =================
(
    WAIT_POST, WAIT_LINK_TYPE, WAIT_SINGLE_EP, WAIT_NUMBER, WAIT_CONFIRM_POST,
    WAIT_BATCH_EP, WAIT_BATCH_RANGE
) = range(7)

async def cmd_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return ConversationHandler.END
    await update.message.reply_text("send post")
    return WAIT_POST

async def receive_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['post_msg'] = update.message
    await update.message.reply_text("post successfully received \nPlease provide single link batch link")
    return WAIT_LINK_TYPE

async def receive_link_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if text == "single link":
        context.user_data['is_batch'] = False
        await update.message.reply_text("send episode")
        return WAIT_SINGLE_EP
    elif text == "batch link":
        context.user_data['is_batch'] = True
        context.user_data['batch_ids'] = []
        await update.message.reply_text("send episode")
        return WAIT_BATCH_EP
    return WAIT_LINK_TYPE

async def receive_single_ep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fwd = await update.message.forward(chat_id=STORAGE_CHANNEL)
    context.user_data['msg_id'] = fwd.message_id
    await update.message.reply_text("Enter Number")
    return WAIT_NUMBER

async def receive_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ep_num'] = update.message.text
    await update.message.reply_text("/confirm")
    return WAIT_CONFIRM_POST

async def receive_batch_ep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "/done":
        await update.message.reply_text("batch successfully adding\nEnter number")
        return WAIT_BATCH_RANGE
    fwd = await update.message.forward(chat_id=STORAGE_CHANNEL)
    context.user_data['batch_ids'].append(fwd.message_id)
    await update.message.reply_text("send next episode\n(jab ho jaye toh /done bhejein)")
    return WAIT_BATCH_EP

async def receive_batch_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ep_num'] = update.message.text
    await update.message.reply_text("/confirm")
    return WAIT_CONFIRM_POST

async def confirm_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_batch = context.user_data.get('is_batch')
    ep_num = context.user_data.get('ep_num')
    
    if is_batch:
        first_id = context.user_data['batch_ids'][0]
        last_id = context.user_data['batch_ids'][-1]
        payload = f"req_B_{first_id}_{last_id}"
    else:
        msg_id = context.user_data['msg_id']
        payload = f"req_S_{msg_id}"

    btn_url = f"https://t.me/{context.bot.username}?start={payload}"
    markup = InlineKeyboardMarkup([[InlineKeyboardButton(f"Watch episode {ep_num}", url=btn_url)]])
    
    post_msg = context.user_data['post_msg']
    context.user_data['final_post'] = {"msg": post_msg, "markup": markup}
    
    await post_msg.copy(update.effective_chat.id, reply_markup=markup)
    await update.message.reply_text("[ Send ]\n[ Send more channel ]")
    return ConversationHandler.END

# ================= CHANNEL SEND SYSTEM =================
async def cmd_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    if 'final_post' not in context.user_data: return await update.message.reply_text("Pehle /post banayein.")
    
    channels = await channels_col.find().to_list(length=100)
    if not channels: return await update.message.reply_text("Koi channel add nahi hai. Pehle /force sub karein.")

    btns = [[InlineKeyboardButton(ch['title'], callback_data=f"send1_{ch['_id']}")] for ch in channels]
    await update.message.reply_text("Select channel:", reply_markup=InlineKeyboardMarkup(btns))

async def cmd_send_more(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    if 'final_post' not in context.user_data: return await update.message.reply_text("Pehle /post banayein.")
    
    channels = await channels_col.find().to_list(length=100)
    context.user_data['multi_ch'] = []
    
    btns = [[InlineKeyboardButton(ch['title'], callback_data=f"sendM_{ch['_id']}")] for ch in channels]
    await update.message.reply_text("Select channels (ek ek karke select karein):", reply_markup=InlineKeyboardMarkup(btns))

async def handle_send_clicks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("send1_"):
        ch_id = int(data.split("_")[1])
        context.user_data['ready_to_send'] = [ch_id]
        await query.message.reply_text("confirm please")
    
    elif data.startswith("sendM_"):
        ch_id = int(data.split("_")[1])
        if ch_id not in context.user_data['multi_ch']:
            context.user_data['multi_ch'].append(ch_id)
        context.user_data['ready_to_send'] = context.user_data['multi_ch']
        await query.message.reply_text(f"Selected! (Total: {len(context.user_data['multi_ch'])})\nconfirm please (type /confirm)")

async def cmd_confirm_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    targets = context.user_data.get('ready_to_send', [])
    post = context.user_data.get('final_post')
    
    if not targets or not post: return
    
    for ch_id in targets:
        try:
            await post['msg'].copy(ch_id, reply_markup=post['markup'])
        except Exception as e:
            await update.message.reply_text(f"Failed to send in channel {ch_id}: {e}")
            
    await update.message.reply_text("Post successfully sent! ✅")
    context.user_data['ready_to_send'] = []

# ================= SHORTENER SYSTEM =================
WAIT_S_URL, WAIT_S_TOKEN = range(2)

async def cmd_add_short(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return ConversationHandler.END
    await update.message.reply_text("provide deskbord url \nGp link / any short")
    return WAIT_S_URL

async def rec_s_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url.endswith("/"): url += "/"
    context.user_data['s_url'] = url
    await update.message.reply_text("successfully send Your API Token")
    return WAIT_S_TOKEN

async def rec_s_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    api = update.message.text
    await shorteners_col.insert_one({"url": context.user_data['s_url'], "api": api})
    await update.message.reply_text("successfully add 🤗🤗🤗")
    return ConversationHandler.END

async def cmd_rem_short(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    docs = await shorteners_col.find().to_list(length=100)
    if not docs: return await update.message.reply_text("No shorteners found.")
    
    btns = [[InlineKeyboardButton(f"{i+1}. {x['url']}", callback_data=f"delsh_{str(x['_id'])}")] for i, x in enumerate(docs)]
    await update.message.reply_text("select account\n\nkya aap hatana chahte hai toh /delete", reply_markup=InlineKeyboardMarkup(btns))

async def handle_del_short(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['del_short_id'] = query.data.split("_")[1]
    await query.message.reply_text("kya aap hatana chahte hai toh delete type karein /delete")

from bson.objectid import ObjectId
async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'del_short_id' in context.user_data:
        _id = context.user_data['del_short_id']
        await shorteners_col.delete_one({"_id": ObjectId(_id)})
        await update.message.reply_text("successfully delete account for shortner")
        del context.user_data['del_short_id']
    return ConversationHandler.END

# ================= PREMIUM SYSTEM =================
WAIT_P_ID, WAIT_P_CONFIRM = range(2)

async def cmd_add_prem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return ConversationHandler.END
    await update.message.reply_text("send I'd")
    return WAIT_P_ID

async def rec_p_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_id'] = update.message.text.strip()
    await update.message.reply_text("successfully add member \nPleas confirm type /hu hu")
    return WAIT_P_CONFIRM

async def confirm_prem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pid = context.user_data['p_id']
    expiry = (datetime.now() + timedelta(days=28)).isoformat()
    await premium_col.update_one({"_id": pid}, {"$set": {"expiry": expiry}}, upsert=True)
    await update.message.reply_text(f"successfully add member {pid} 🪄🪄🪄")
    return ConversationHandler.END

async def cmd_rem_prem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    await update.message.reply_text("send I'd")
    context.user_data['wait_rem_prem'] = True

async def process_rem_prem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('wait_rem_prem'):
        pid = update.message.text.strip()
        await premium_col.delete_one({"_id": pid})
        await update.message.reply_text("successfully deleted and ban")
        context.user_data['wait_rem_prem'] = False

async def cmd_show_prem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    docs = await premium_col.find().to_list(length=1000)
    text = "👑 **Premium Users:**\n\n"
    for x in docs:
        text += f"ID: `{x['_id']}` | Exp: {x['expiry'][:10]}\n"
    await update.message.reply_text(text if docs else "No premium users.")

# ================= FORCE SUB SYSTEM =================
async def cmd_fsub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    await update.message.reply_text("please send massage and chack I'm admin gc")

async def receive_fsub_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    if update.message.forward_origin and update.message.forward_origin.type == 'channel':
        chat = update.message.forward_origin.chat
        await channels_col.update_one(
            {"_id": str(chat.id)}, 
            {"$set": {"title": chat.title}}, 
            upsert=True
        )
        await update.message.reply_text("😘 adding successfully 😲")

# ================= MAIN RUNNER =================
def main():
    threading.Thread(target=run_flask, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()

    # Handlers Base
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("send", cmd_send))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^/send$"), cmd_send))
    
    app.add_handler(CommandHandler("send_more_channel", cmd_send_more))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^/send more channel$"), cmd_send_more))
    
    app.add_handler(CommandHandler("confirm", cmd_confirm_send))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^/confirm$"), cmd_confirm_send))
    
    app.add_handler(CallbackQueryHandler(handle_send_clicks, pattern=r"^send"))
    app.add_handler(CallbackQueryHandler(handle_del_short, pattern=r"^delsh_"))
    
    app.add_handler(CommandHandler("delete", cmd_delete))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^/delete$"), cmd_delete))

    # Premium Commands
    app.add_handler(CommandHandler("remove_premium", cmd_rem_prem))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^/remove premium$"), cmd_rem_prem))
    app.add_handler(CommandHandler("show_premium_list", cmd_show_prem))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^/show premium list$"), cmd_show_prem))
    
    # Text catcher for Remove Premium
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_rem_prem), group=1)

    # Force Sub Commands
    app.add_handler(CommandHandler("force_sub", cmd_fsub))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^/force sub$|^/Force sub$"), cmd_fsub))
    app.add_handler(MessageHandler(filters.FORWARDED & ~filters.COMMAND, receive_fsub_msg))

    # Post Conversation
    post_conv = ConversationHandler(
        entry_points=[CommandHandler("post", cmd_post), MessageHandler(filters.Regex(r"(?i)^/post$"), cmd_post)],
        states={
            WAIT_POST: [MessageHandler(filters.ALL & ~filters.COMMAND, receive_post)],
            WAIT_LINK_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_link_type)],
            WAIT_SINGLE_EP: [MessageHandler(filters.ALL & ~filters.COMMAND, receive_single_ep)],
            WAIT_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_number)],
            WAIT_CONFIRM_POST: [MessageHandler(filters.Regex(r"(?i)^/hmm$|^/confirm$"), confirm_post)],
            WAIT_BATCH_EP: [
                MessageHandler(filters.ALL & ~filters.COMMAND, receive_batch_ep), 
                CommandHandler("done", receive_batch_ep),
                MessageHandler(filters.Regex(r"(?i)^/done$"), receive_batch_ep)
            ],
            WAIT_BATCH_RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_batch_range)]
        },
        fallbacks=[CommandHandler("delete", cmd_delete)]
    )
    app.add_handler(post_conv)

    # Shortener Conversation
    short_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"(?i)^/add shortner account$"), cmd_add_short)],
        states={
            WAIT_S_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, rec_s_url)],
            WAIT_S_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, rec_s_token)]
        },
        fallbacks=[CommandHandler("delete", cmd_delete)]
    )
    app.add_handler(short_conv)
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^/remove shortner account$"), cmd_rem_short))

    # Premium Add Conversation
    prem_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"(?i)^/add premium$"), cmd_add_prem)],
        states={
            WAIT_P_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, rec_p_id)],
            WAIT_P_CONFIRM: [MessageHandler(filters.Regex(r"(?i)^/hu hu$"), confirm_prem)]
        },
        fallbacks=[CommandHandler("delete", cmd_delete)]
    )
    app.add_handler(prem_conv)

    print("🚀 Bot Started Extremely Smoothly with Async MongoDB!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
