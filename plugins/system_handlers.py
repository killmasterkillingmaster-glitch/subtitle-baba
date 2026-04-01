from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from config import ALLOWED_USERS
from plugins.utils import get_short_link, send_files, is_premium_user, channels_col, shorteners_col, premium_col

# --- PUBLIC START COMMAND (MAIN LOGIC) ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    if not args:
        return await update.message.reply_text("Bot Started! Send me valid links.")

    payload = args[0] # Example: S_123 ya V_S_123

    # 1. Check Force Sub (Sirf wahi channel jahan bot admin hai)
    channels = await channels_col.find().to_list(length=100)
    join_btns = []
    is_joined_all = True
    
    for ch in channels:
        try:
            member = await context.bot.get_chat_member(int(ch['_id']), user_id)
            if member.status in ['left', 'kicked']: 
                is_joined_all = False
                raise Exception
        except:
            is_joined_all = False
            link = ch.get('link', '')
            if link: join_btns.append([InlineKeyboardButton(f"Join {ch['title']}", url=link)])
    
    if not is_joined_all:
        join_btns.append([InlineKeyboardButton("Try again", url=f"https://t.me/{context.bot.username}?start={payload}")])
        return await update.message.reply_text("join first", reply_markup=InlineKeyboardMarkup(join_btns))

    # 2. Premium Check
    is_premium = await is_premium_user(user_id)

    # 3. Shortener Logic (Bot khud check karega premium hai ya normal)
    if not payload.startswith("V_") and not is_premium:
        verify_deep_link = f"https://t.me/{context.bot.username}?start=V_{payload}"
        short_link = await get_short_link(verify_deep_link)
        btn = [[InlineKeyboardButton("Click Here To Get Episode", url=short_link)]]
        return await update.message.reply_text("Aapko pehle link solve karna hoga:\n👇👇👇", reply_markup=InlineKeyboardMarkup(btn))

    # 4. Delivery
    await send_files(context.bot, user_id, payload)

# --- SETTING / COMMAND LIST ---
async def cmd_setting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    text = """
⚙️ **Admin Control Panel** ⚙️

📝 **Post & Upload:**
`/post` - New post create karein

🔗 **Shortener System:**
`/add shortner account` - Shortener API jodein
`/remove shortner account` - Shortener hatayein

👑 **Premium System:**
`/add premium` - User ko direct access dein
`/remove premium` - User ka premium hatayein
`/show premium list` - Saare premium users dekhein

📢 **Force Subscribe:**
`/force sub` - Force sub ke liye channel jodein

❌ **Cancel:**
`/delete` - Process cancel karne ke liye
    """
    await update.message.reply_text(text)

# --- SHORTENER LOGIC ---
WAIT_URL, WAIT_TOKEN = range(2)

async def add_shortener_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return ConversationHandler.END
    await update.message.reply_text("provide deskbord url\nGp link / any short")
    return WAIT_URL

async def receive_short_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['short_url'] = update.message.text.strip()
    await update.message.reply_text("successfully send Your API Token")
    return WAIT_TOKEN

async def receive_short_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await shorteners_col.insert_one({"url": context.user_data['short_url'], "api": update.message.text.strip()})
    await update.message.reply_text("successfully add 🤗🤗🤗")
    return ConversationHandler.END

async def cmd_rem_short(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    docs = await shorteners_col.find().to_list(length=100)
    if not docs: return await update.message.reply_text("Koi account nahi hai.")
    
    btns = [[InlineKeyboardButton(f"{i+1}. {x['url']}", callback_data=f"delsh_{str(x['_id'])}")] for i, x in enumerate(docs)]
    await update.message.reply_text("select account\n\nkya aap hatana chahte hai toh /delete", reply_markup=InlineKeyboardMarkup(btns))

async def handle_del_short(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['del_short_id'] = query.data.split("_")[1]
    await query.message.reply_text("kya aap hatana chahte hai toh delete type karein /delete")

async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'del_short_id' in context.user_data:
        await shorteners_col.delete_one({"_id": ObjectId(context.user_data['del_short_id'])})
        await update.message.reply_text("successfully delete account for shortner")
        del context.user_data['del_short_id']
    return ConversationHandler.END

# --- PREMIUM LOGIC ---
PREM_ID, PREM_CONF = range(2)

async def add_premium_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return ConversationHandler.END
    await update.message.reply_text("send I'd")
    return PREM_ID

async def receive_prem_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['prem_id'] = update.message.text.strip()
    await update.message.reply_text("successfully add member\nPleas confirm type /hu hu")
    return PREM_CONF

async def confirm_prem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pid = context.user_data['prem_id']
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
        await premium_col.delete_one({"_id": update.message.text.strip()})
        await update.message.reply_text("successfully deleted and ban")
        context.user_data['wait_rem_prem'] = False

async def show_prem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    docs = await premium_col.find().to_list(length=1000)
    text = "👑 **Premium Users:**\n\n"
    for x in docs:
        text += f"ID: `{x['_id']}` | Exp: {x['expiry'][:10]}\n"
    await update.message.reply_text(text if docs else "No premium users.")

# --- FORCE SUB LOGIC ---
async def add_fsub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    await update.message.reply_text("please send massage and chack I'm admin gc")

async def receive_fsub_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.forward_origin and update.message.forward_origin.type == 'channel':
        chat = update.message.forward_origin.chat
        try:
            link = chat.invite_link or (f"https://t.me/{chat.username}" if chat.username else await context.bot.export_chat_invite_link(chat.id))
            await channels_col.update_one(
                {"_id": str(chat.id)}, 
                {"$set": {"title": chat.title, "link": link}}, 
                upsert=True
            )
            await update.message.reply_text(f"😘 adding successfully 😲 ({chat.title})")
        except:
            await update.message.reply_text("❌ Bot Admin nahi hai ya Link nikalne ki permission nahi hai!")
