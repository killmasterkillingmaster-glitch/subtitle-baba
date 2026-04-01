from flask import Flask
import threading
from telegram.ext import Application, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from config import BOT_TOKEN, PORT, ALLOWED_USERS, STORAGE_CHANNEL
from plugins.utils import get_short_link
from plugins.shortner import add_shortner_start, receive_url, receive_token, cancel_add, WAITING_URL, WAITING_TOKEN, remove_shortner, remove_callback
from plugins.post_system import post_start, receive_post, choose_link_type, receive_episode, receive_number, receive_batch_episode, receive_batch_range, confirm_post, handle_send_callback

app = Flask(__name__)
@app.route('/')
def home(): return "Bot Running ✅"

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()

    application = Application.builder().token(BOT_TOKEN).build()

    # Shortner conversation
    short_conv = ConversationHandler(
        entry_points=[CommandHandler("add shortner account", add_shortner_start)],
        states={WAITING_URL: [MessageHandler(filters.TEXT & \~filters.COMMAND, receive_url)],
                WAITING_TOKEN: [MessageHandler(filters.TEXT & \~filters.COMMAND, receive_token)]},
        fallbacks=[CommandHandler("cancel", cancel_add)]
    )
    application.add_handler(short_conv)
    application.add_handler(CommandHandler("remove shortner account", remove_shortner))
    application.add_handler(CallbackQueryHandler(remove_callback, pattern=r"^del_"))

    # Post system (exact tere document jaisa)
    post_conv = ConversationHandler(
        entry_points=[CommandHandler("post", post_start)],
        states={
            0: [MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, receive_post)],
            1: [MessageHandler(filters.TEXT & \~filters.COMMAND, choose_link_type)],
            2: [MessageHandler(filters.VIDEO | filters.Document.ALL, receive_episode)],
            3: [MessageHandler(filters.TEXT & \~filters.COMMAND, receive_number)],
            4: [CommandHandler("hmm", confirm_post), CommandHandler("confirm", confirm_post)],
            5: [MessageHandler(filters.VIDEO | filters.Document.ALL, receive_batch_episode), CommandHandler("done", receive_batch_episode)],
            6: [MessageHandler(filters.TEXT & \~filters.COMMAND, receive_batch_range)],
            7: [CommandHandler("hmm", confirm_post), CommandHandler("confirm", confirm_post)],
        },
        fallbacks=[CommandHandler("cancel", lambda u,c: ConversationHandler.END)]
    )
    application.add_handler(post_conv)
    application.add_handler(CallbackQueryHandler(handle_send_callback, pattern=r"^send_"))

    # Extra commands
    application.add_handler(CommandHandler("start", lambda u,c: u.message.reply_text("Bot Started!")))
    application.add_handler(CommandHandler("link", lambda u,c: u.message.reply_text(get_short_link("https://example.com"))))

    print("🚀 Bot Started...")
    application.run_polling(drop_pending_updates=True)
