from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import ALLOWED_USERS, STORAGE_CHANNEL
from plugins.utils import get_short_link, load_json

# Conversation States
SEND_POST, LINK_TYPE, SEND_EPISODE, EPISODE_NUMBER, CONFIRM = range(5)
BATCH_EPISODES, BATCH_RANGE, BATCH_CONFIRM = range(5, 8)

async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        return ConversationHandler.END
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

# Single Link System
async def receive_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Telegram Database Logic: Forwards media to Storage Channel immediately
    fwd = await update.message.forward(chat_id=STORAGE_CHANNEL)
    context.user_data['file_msg_id'] = fwd.message_id
    await update.message.reply_text("Enter Number")
    return EPISODE_NUMBER

async def receive_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['episode_num'] = update.message.text.strip()
    await update.message.reply_text("/confirm")
    return CONFIRM

# Batch Link System
async def receive_batch_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "/done":
        await update.message.reply_text("batch successfully adding\nEnter number")
        return BATCH_RANGE
    
    # Store episodes in Storage Channel
    fwd = await update.message.forward(chat_id=STORAGE_CHANNEL)
    context.user_data['batch_ids'].append(fwd.message_id)
    await update.message.reply_text("send next episode\n(jab ho jaye toh /done bhejein)")
    return BATCH_EPISODES

async def receive_batch_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['batch_range'] = update.message.text.strip()
    await update.message.reply_text("/confirm")
    return BATCH_CONFIRM

# Final Confirmation Output
async def confirm_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_batch = context.user_data.get('is_batch', False)
    post_msg = context.user_data['post_msg']
    bot_username = context.bot.username

    if is_batch:
        first_id = context.user_data['batch_ids'][0]
        last_id = context.user_data['batch_ids'][-1]
        payload = f"B_{first_id}_{last_id}"
        btn_text = f"Watch episode {context.user_data['batch_range']}"
    else:
        payload = f"S_{context.user_data['file_msg_id']}"
        btn_text = f"Watch Episode {context.user_data['episode_num']}"

    deep_link = f"https://t.me/{bot_username}?start={payload}"
    short_link = get_short_link(deep_link)

    markup = InlineKeyboardMarkup([[InlineKeyboardButton(btn_text, url=short_link)]])
    
    # Show Preview to Admin
    await post_msg.copy(update.effective_chat.id, reply_markup=markup)
    
    await update.message.reply_text("Send ya Send more channel", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("Send", callback_data="send_single")],
        [InlineKeyboardButton("Send more channel", callback_data="send_more")]
    ]))

    # Save to context for sending
    context.user_data['final_post'] = {'msg': post_msg, 'markup': markup}
    return ConversationHandler.END

# Callback Handlers for Sending
async def handle_send_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "send_single":
        channels = load_json("channels.json")
        if not channels:
            await query.edit_message_text("Pehle /force sub karke channels add karein.")
            return
        
        btns = [[InlineKeyboardButton(ch['name'], callback_data=f"push_{ch['id']}")] for ch in channels]
        await query.edit_message_text("Select Channel:", reply_markup=InlineKeyboardMarkup(btns))

    elif query.data == "send_more":
        channels = load_json("channels.json")
        btns = [[InlineKeyboardButton(ch['name'], callback_data=f"push_{ch['id']}")] for ch in channels]
        btns.append([InlineKeyboardButton("Send To All Selected ✅", callback_data="push_all")])
        context.user_data['selected_channels'] = []
        await query.edit_message_text("Select Multiple Channels:", reply_markup=InlineKeyboardMarkup(btns))

async def handle_push_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    post = context.user_data.get('final_post')

    if data.startswith("push_all"):
        for ch_id in context.user_data.get('selected_channels', []):
            await post['msg'].copy(ch_id, reply_markup=post['markup'])
        await query.edit_message_text("✅ Multiple Channels me Post bhej di gayi!")
        context.user_data.clear()
        
    elif data.startswith("push_"):
        ch_id = int(data.split("_")[1])
        if "selected_channels" in context.user_data: # Multi-select mode
            context.user_data['selected_channels'].append(ch_id)
            await query.message.reply_text(f"Selected! Select more or click Send To All ✅")
        else: # Single select mode
            await post['msg'].copy(ch_id, reply_markup=post['markup'])
            await query.edit_message_text("✅ Post successfully published!")
            context.user_data.clear()
