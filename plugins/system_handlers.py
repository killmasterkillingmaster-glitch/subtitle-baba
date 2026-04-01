from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, timedelta
from config import ALLOWED_USERS, STORAGE_CHANNEL
from plugins.utils import load_json, save_json, get_short_link

# --- PUBLIC START COMMAND (DELIVERY, FSUB & PREMIUM LOGIC) ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    if not args:
        return await update.message.reply_text("Bot Started! Send me valid links.")

    payload = args[0] # e.g., S_123 ya V_S_123

    # 1. Check Force Sub
    channels = load_json("channels.json")
    join_btns = []
    is_joined_all = True
    for ch in channels:
        try:
            member = await context.bot.get_chat_member(ch['id'], user_id)
            if member.status in ['left', 'kicked']: is_joined_all = False; raise Exception
        except:
            is_joined_all = False
            if ch['link']: join_btns.append([InlineKeyboardButton(f"Join {ch['name']}", url=ch['link'])])
    
    if not is_joined_all:
        join_btns.append([InlineKeyboardButton("Try again", url=f"https://t.me/{context.bot.username}?start={payload}")])
        return await update.message.reply_text("join first", reply_markup=InlineKeyboardMarkup(join_btns))

    # 2. Check Premium
    premium_users = load_json("premium.json")
    is_premium = any(p['id'] == user_id and datetime.now() < datetime.fromisoformat(p['expiry']) for p in premium_users)

    # 3. Shortener Link Generate (Agar Free User hai aur link verify nahi kiya)
    if not payload.startswith("V_") and not is_premium:
        verify_deep_link = f"https://t.me/{context.bot.username}?start=V_{payload}"
        short_link = get_short_link(verify_deep_link)
        btn = [[InlineKeyboardButton("Click Here To Get Episode", url=short_link)]]
        return await update.message.reply_text("Aapko pehle link solve karna hoga:\n👇👇👇", reply_markup=InlineKeyboardMarkup(btn))

    # 4. Delivery File
    actual_payload = payload.replace("V_", "")
    if actual_payload.startswith("S_"):
        msg_id = int(actual_payload.split("_")[1])
        try: await context.bot.copy_message(chat_id=user_id, from_chat_id=STORAGE_CHANNEL, message_id=msg_id)
        except: await update.message.reply_text("File Delete Ho Chuki Hai!")

    elif actual_payload.startswith("B_"):
        parts = actual_payload.split("_")
        for msg_id in range(int(parts[1]), int(parts[2]) + 1):
            try: await context.bot.copy_message(chat_id=user_id, from_chat_id=STORAGE_CHANNEL, message_id=msg_id)
            except: pass

# --- OTHER COMMANDS ---
WAIT_URL, WAIT_TOKEN = range(2)
async def add_shortener_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    await update.message.reply_text("provide deskbord url\nGp link / any short")
    return WAIT_URL
async def receive_short_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['short_url'] = update.message.text.strip()
    await update.message.reply_text("successfully send Your API Token")
    return WAIT_TOKEN
async def receive_short_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_json("shorteners.json")
    data.append({"url": context.user_data['short_url'], "api": update.message.text.strip()})
    save_json("shorteners.json", data)
    await update.message.reply_text("successfully add 🤗🤗🤗")
    return ConversationHandler.END

PREM_ID, PREM_CONF = range(2)
async def add_premium_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    await update.message.reply_text("send I'd")
    return PREM_ID
async def receive_prem_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['prem_id'] = int(update.message.text)
    await update.message.reply_text("successfully add member\nPleas confirm type /hu hu")
    return PREM_CONF
async def confirm_prem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = context.user_data['prem_id']
    data = [x for x in load_json("premium.json") if x['id'] != uid]
    data.append({"id": uid, "expiry": (datetime.now() + timedelta(days=28)).isoformat()})
    save_json("premium.json", data)
    await update.message.reply_text(f"successfully add member {uid} 🪄🪄🪄")
    return ConversationHandler.END

FSUB_WAIT = range(1)
async def add_fsub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    await update.message.reply_text("please send massage and chack I'm admin gc")
    return FSUB_WAIT
async def receive_fsub_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.forward_origin and update.message.forward_origin.type == 'channel':
        chat = update.message.forward_origin.chat
        data = load_json("channels.json")
        if chat.id not in [x['id'] for x in data]:
            try:
                link = f"https://t.me/{chat.username}" if chat.username else await context.bot.export_chat_invite_link(chat.id)
                data.append({"id": chat.id, "name": chat.title, "link": link})
                save_json("channels.json", data)
                await update.message.reply_text(f"😘 adding successfully 😲 ({chat.title})")
            except:
                await update.message.reply_text("Bot Admin nahi hai ya Link nahi nikal pa raha!")
        else: await update.message.reply_text("Already Added!")
    return ConversationHandler.END
