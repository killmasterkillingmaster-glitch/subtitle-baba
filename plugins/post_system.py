from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import ALLOWED_USERS, STORAGE_CHANNEL
from plugins.utils import channels_col

SEND_POST, LINK_TYPE, SEND_EPISODE, EPISODE_NUMBER, CONFIRM = range(5)
BATCH_EPISODES, BATCH_RANGE, BATCH_CONFIRM = range(5, 8)

async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return ConversationHandler.END
    await update.message.reply_text("send post")
    return SEND_POST

async def receive_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['post_msg'] = update.message
    await update.message.reply_text("post successfully received \nPlease provide single link batch link")
    return LINK_TYPE

async def choose_link_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.lower()
    if "single" in txt:
        context.user_data['is_batch'] = False
        await update.message.reply_text("send episode")
        return SEND_EPISODE
    elif "batch" in txt:
        context.user_data['is_batch'] = True
        context.user_data['batch_ids'] = []
        await update.message.reply_text("send episode")
        return BATCH_EPISODES
    return LINK_TYPE

async def receive_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.forward_origin and update.message.forward_origin.type == 'channel':
        context.user_data['file_msg_id'] = update.message.forward_origin.message_id
        await update.message.reply_text("Enter Number")
        return EPISODE_NUMBER
    else:
        await update.message.reply_text("❌ Galat! Please Episode ko Database Channel se forward karein.")
        return SEND_EPISODE

async def receive_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['episode_num'] = update.message.text.strip()
    await update.message.reply_text("/confirm")
    return CONFIRM

async def receive_batch_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "/done":
        await update.message.reply_text("batch successfully adding\nEnter number")
        return BATCH_RANGE
    
    if update.message.forward_origin and update.message.forward_origin.type == 'channel':
        context.user_data['batch_ids'].append(update.message.forward_origin.message_id)
        await update.message.reply_text("send next episode\n(jab ho jaye toh /done bhejein)")
        return BATCH_EPISODES
    else:
        await update.message.reply_text("❌ Galat! Please Database Channel se forward karein.")
        return BATCH_EPISODES

async def receive_batch_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['batch_range'] = update.message.text.strip()
    await update.message.reply_text("/confirm")
    return BATCH_CONFIRM

async def confirm_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_batch = context.user_data.get('is_batch', False)
    post_msg = context.user_data['post_msg']

    if is_batch:
        first_id = context.user_data['batch_ids'][0]
        last_id = context.user_data['batch_ids'][-1]
        payload = f"B_{first_id}_{last_id}"
        btn_text = f"Watch episode {context.user_data['batch_range']}"
    else:
        payload = f"S_{context.user_data['file_msg_id']}"
        btn_text = f"Watch Episode {context.user_data['episode_num']}"

    # Ye rahi wo jadoo wali link jo bot check karegi
    deep_link = f"https://t.me/{context.bot.username}?start={payload}"
    markup = InlineKeyboardMarkup([[InlineKeyboardButton(btn_text, url=deep_link)]])
    
    await post_msg.copy(update.effective_chat.id, reply_markup=markup)
    await update.message.reply_text("[ Send ]\n[ Send more channel ]")
    context.bot_data['final_post'] = {'msg': post_msg, 'markup': markup}
    return ConversationHandler.END

# --- SEND SYSTEM LOGIC (With /confirm feature) ---
async def cmd_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    channels = await channels_col.find().to_list(length=100)
    if not channels: return await update.message.reply_text("Koi channel nahi hai. Pehle /force sub karein.")

    btns = [[InlineKeyboardButton(ch['title'], callback_data=f"psingle_{ch['_id']}")] for ch in channels]
    await update.message.reply_text("Select One Channel to Send:", reply_markup=InlineKeyboardMarkup(btns))

async def cmd_send_more(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    channels = await channels_col.find().to_list(length=100)
    context.user_data['selected_chs'] = []
    
    btns = [[InlineKeyboardButton(f"⭕️ {ch['title']}", callback_data=f"pmulti_{ch['_id']}")] for ch in channels]
    await update.message.reply_text("Select Multiple Channels:", reply_markup=InlineKeyboardMarkup(btns))

async def handle_push_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("psingle_"):
        ch_id = int(data.split("_")[1])
        context.user_data['ready_to_send'] = [ch_id]
        await query.message.reply_text("confirm please")

    elif data.startswith("pmulti_"):
        ch_id = int(data.split("_")[1])
        selected = context.user_data.get('selected_chs', [])
        if ch_id in selected: selected.remove(ch_id)
        else: selected.append(ch_id)
        
        context.user_data['ready_to_send'] = selected

        channels = await channels_col.find().to_list(length=100)
        btns = []
        for ch in channels:
            mark = "✅" if int(ch['_id']) in selected else "⭕️"
            btns.append([InlineKeyboardButton(f"{mark} {ch['title']}", callback_data=f"pmulti_{ch['_id']}")])
            
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btns))
        await query.message.reply_text("confirm please")

async def final_send_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    targets = context.user_data.get('ready_to_send', [])
    post = context.bot_data.get('final_post')
    
    if not targets or not post: return
    
    for ch_id in targets:
        try: await post['msg'].copy(ch_id, reply_markup=post['markup'])
        except: pass
    
    await update.message.reply_text("✅ Post successfully published on selected channels!")
    context.user_data['ready_to_send'] = []
