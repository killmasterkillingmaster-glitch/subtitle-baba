from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CommandHandler
from .utils import get_short_link
import uuid

# States
SEND_POST, LINK_TYPE, SEND_EPISODE, EPISODE_NUMBER, CONFIRM = range(5)
BATCH_EPISODES, BATCH_DONE, BATCH_RANGE, BATCH_CONFIRM = range(5, 9)

async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        return
    await update.message.reply_text("send post")
    return SEND_POST

async def receive_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo or update.message.video or update.message.document:
        # Post media save
        if update.message.photo:
            context.user_data['post_media'] = update.message.photo[-1].file_id
        elif update.message.video:
            context.user_data['post_media'] = update.message.video.file_id
        elif update.message.document:
            context.user_data['post_media'] = update.message.document.file_id
        context.user_data['post_caption'] = update.message.caption or ""
        await update.message.reply_text("post successfully received \nPlease provide single ling batch link")
        return LINK_TYPE
    await update.message.reply_text("Media forward karo!")
    return SEND_POST

async def choose_link_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.lower()
    if "single" in txt:
        context.user_data['is_batch'] = False
        await update.message.reply_text("send episode")
        return SEND_EPISODE
    elif "batch" in txt:
        context.user_data['is_batch'] = True
        context.user_data['episodes'] = []
        await update.message.reply_text("send episode \n(last mein /done likho)")
        return BATCH_EPISODES
    return LINK_TYPE

# Single
async def receive_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.video or update.message.document:
        fid = update.message.video.file_id if update.message.video else update.message.document.file_id
        context.user_data['episode_file'] = fid
        await update.message.reply_text("Enter Number")
        return EPISODE_NUMBER
    await update.message.reply_text("Episode forward karo!")
    return SEND_EPISODE

async def receive_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['episode_num'] = update.message.text.strip()
    await update.message.reply_text("/confirm")
    return CONFIRM

# Batch
async def receive_batch_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "/done":
        await update.message.reply_text("Enter number \n(05-15 jaise)")
        return BATCH_RANGE
    if update.message.video or update.message.document:
        fid = update.message.video.file_id if update.message.video else update.message.document.file_id
        context.user_data['episodes'].append(fid)
        await update.message.reply_text("send next episode")
        return BATCH_EPISODES
    return BATCH_EPISODES

async def receive_batch_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['batch_range'] = update.message.text.strip()
    await update.message.reply_text("/confirm")
    return BATCH_CONFIRM

# Confirm (/hmm ya /confirm dono accept)
async def confirm_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_batch = context.user_data.get('is_batch', False)
    media = context.user_data.get('post_media')
    caption = context.user_data.get('post_caption', '')

    if is_batch:
        btn_text = f"Watch episode {context.user_data['batch_range']}"
    else:
        btn_text = f"Watch Episode {context.user_data['episode_num']}"

    # Deep link + GPLinks short
    unique = str(uuid.uuid4())[:8]
    deep = f"https://t.me/{context.bot.username}?start={unique}"
    short = get_short_link(deep)

    keyboard = [[InlineKeyboardButton(btn_text, url=short)]]
    markup = InlineKeyboardMarkup(keyboard)

    # Preview bhejta hai exactly jaise tune bataya
    if "photo" in str(media):
        await context.bot.send_photo(update.effective_chat.id, photo=media, caption=caption, reply_markup=markup)
    else:
        await context.bot.send_video(update.effective_chat.id, video=media, caption=caption, reply_markup=markup)

    await update.message.reply_text("Send ya Send more channel", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("Send", callback_data="send_single")],
        [InlineKeyboardButton("Send more channel", callback_data="send_more")]
    ]))

    context.user_data['ready_post'] = {"media": media, "caption": caption, "markup": markup}
    return ConversationHandler.END

# Send callbacks
async def handle_send_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    post = context.user_data.get('ready_post')
    if not post:
        await query.edit_message_text("Pehle /post karo!")
        return

    # ASI anime channel par post
    if "photo" in str(post['media']):
        await context.bot.send_photo(STORAGE_CHANNEL, photo=post['media'], caption=post['caption'], reply_markup=post['markup'])
    else:
        await context.bot.send_video(STORAGE_CHANNEL, video=post['media'], caption=post['caption'], reply_markup=post['markup'])

    await query.edit_message_text("✅ Post successfully published in ASI anime channel!")
    context.user_data.clear()
