from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, timedelta
from config import ALLOWED_USERS, STORAGE_CHANNEL
from plugins.utils import load_json, save_json

# --- SHORTENER SYSTEM ---
WAIT_URL, WAIT_TOKEN = range(2)

async def add_shortener_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return ConversationHandler.END
    await update.message.reply_text("provide deskbord url\nGp link / any short")
    return WAIT_URL

async def receive_short_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url.endswith("/"): url += "/"
    context.user_data['short_url'] = url
    await update.message.reply_text("successfully send Your API Token")
    return WAIT_TOKEN

async def receive_short_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = update.message.text
    url = context.user_data['short_url']
    
    data = load_json("shorteners.json")
    data.append({"url": url, "api": token})
    save_json("shorteners.json", data)
    
    await update.message.reply_text("successfully add 🤗🤗🤗")
    return ConversationHandler.END

async def remove_shortener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    data = load_json("shorteners.json")
    if not data:
        return await update.message.reply_text("Koi account nahi hai.")
    
    btns = [[InlineKeyboardButton(f"{i+1}. {x['url']}", callback_data=f"delshort_{i}")] for i, x in enumerate(data)]
    await update.message.reply_text("select account", reply_markup=InlineKeyboardMarkup(btns))

async def handle_del_shortener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split("_")[1])
    data = load_json("shorteners.json")
    del data[idx]
    save_json("shorteners.json", data)
    await query.edit_message_text("successfully delete account for shortner")


# --- PREMIUM SYSTEM ---
PREM_ID, PREM_CONFIRM = range(2)

async def add_premium_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    await update.message.reply_text("send I'd")
    return PREM_ID

async def receive_prem_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['prem_id'] = int(update.message.text)
    await update.message.reply_text("successfully add member\nPleas confirm type /hu hu")
    return PREM_CONFIRM

async def confirm_prem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = context.user_data['prem_id']
    expiry = (datetime.now() + timedelta(days=28)).isoformat()
    
    data = load_json("premium.json")
    # Clean old records for this user
    data = [x for x in data if x['id'] != uid]
    data.append({"id": uid, "expiry": expiry})
    save_json("premium.json", data)
    
    await update.message.reply_text(f"successfully add member {uid} 🪄🪄🪄")
    return ConversationHandler.END

async def remove_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    try:
        uid = int(update.message.text.split(" ")[1])
        data = load_json("premium.json")
        data = [x for x in data if x['id'] != uid]
        save_json("premium.json", data)
        await update.message.reply_text("successfully deleted and ban")
    except:
        await update.message.reply_text("Usage: /remove premium [ID]")


# --- FORCE SUB SYSTEM ---
async def add_fsub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    await update.message.reply_text("please send massage and chack I'm admin gc")

async def receive_fsub_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    if update.message.forward_origin and update.message.forward_origin.type == 'channel':
        chat = update.message.forward_origin.chat
        data = load_json("channels.json")
        if chat.id not in [x['id'] for x in data]:
            data.append({"id": chat.id, "name": chat.title, "link": f"https://t.me/{chat.username}" if chat.username else ""})
            save_json("channels.json", data)
            await update.message.reply_text("😘 adding successfully 😲")
        else:
            await update.message.reply_text("Already Added!")

# --- BOT PUBLIC USER HANDLER (GIVING FILES) ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    if not args:
        return await update.message.reply_text("Bot Started! Send me valid links.")

    payload = args[0]
    
    # Check FSub
    channels = load_json("channels.json")
    join_btns = []
    for ch in channels:
        try:
            member = await context.bot.get_chat_member(ch['id'], user_id)
            if member.status in ['left', 'kicked']: raise Exception
        except:
            if ch['link']: join_btns.append([InlineKeyboardButton(f"Join {ch['name']}", url=ch['link'])])
    
    if join_btns:
        join_btns.append([InlineKeyboardButton("Try again", url=f"https://t.me/{context.bot.username}?start={payload}")])
        return await update.message.reply_text("join first", reply_markup=InlineKeyboardMarkup(join_btns))

    # Provide Episode (Works for both Free and Premium, Shortener is solved before they reach here)
    if payload.startswith("S_"):
        msg_id = int(payload.split("_")[1])
        await context.bot.copy_message(chat_id=user_id, from_chat_id=STORAGE_CHANNEL, message_id=msg_id)
        
    elif payload.startswith("B_"):
        parts = payload.split("_")
        start_id, end_id = int(parts[1]), int(parts[2])
        for msg_id in range(start_id, end_id + 1):
            try:
                await context.bot.copy_message(chat_id=user_id, from_chat_id=STORAGE_CHANNEL, message_id=msg_id)
            except:
                pass # Skip if deleted msg in between
