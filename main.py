from flask import Flask
import threading
from telegram.ext import Application, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from config import BOT_TOKEN, PORT

# Import Handlers
from plugins.post_system import (
    post_start, receive_post, choose_link_type, receive_episode, 
    receive_number, receive_batch_episode, receive_batch_range, 
    confirm_post, handle_send_callback, handle_push_callback
)
from plugins.system_handlers import (
    add_shortener_start, receive_short_url, receive_short_token, 
    remove_shortener, handle_del_shortener,
    add_premium_start, receive_prem_id, confirm_prem, remove_premium,
    add_fsub, receive_fsub_msg, start_cmd
)

# Flask Server for Render (Keep Alive)
app = Flask(__name__)
@app.route('/')
def home(): return "Bot Running ✅ Database free architecture!"

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()

    application = Application.builder().token(BOT_TOKEN).build()

    # User Start Handler
    application.add_handler(CommandHandler("start", start_cmd))

    # Post Conversation
    post_conv = ConversationHandler(
        entry_points=[CommandHandler("post", post_start)],
        states={
            0: [MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, receive_post)],
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_link_type)],
            2: [MessageHandler(filters.VIDEO | filters.Document.ALL, receive_episode)],
            3: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_number)],
            4: [CommandHandler("hmm", confirm_post), CommandHandler("confirm", confirm_post)],
            5: [MessageHandler(filters.VIDEO | filters.Document.ALL, receive_batch_episode), CommandHandler("done", receive_batch_episode)],
            6: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_batch_range)],
            7: [CommandHandler("hmm", confirm_post), CommandHandler("confirm", confirm_post)]
        },
        fallbacks=[]
    )
    application.add_handler(post_conv)
    application.add_handler(CallbackQueryHandler(handle_send_callback, pattern=r"^send_"))
    application.add_handler(CallbackQueryHandler(handle_push_callback, pattern=r"^push_"))

    # Shortener Conversation
    short_conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_shortener_start)], # using /add shortner account via regex was complex, using simple commands
        states={
            0: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_short_url)],
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_short_token)]
        },
        fallbacks=[]
    )
    application.add_handler(short_conv)
    application.add_handler(CommandHandler("remove", remove_shortener))
    application.add_handler(CallbackQueryHandler(handle_del_shortener, pattern=r"^delshort_"))

    # Premium Conversation
    prem_conv = ConversationHandler(
        entry_points=[CommandHandler("addpremium", add_premium_start)],
        states={
            0: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_prem_id)],
            1: [CommandHandler("hu", confirm_prem, filters.Regex("^/hu hu$"))]
        },
        fallbacks=[]
    )
    application.add_handler(prem_conv)
    application.add_handler(CommandHandler("removepremium", remove_premium))

    # Force Sub logic
    application.add_handler(CommandHandler("forcesub", add_fsub))
    application.add_handler(MessageHandler(filters.FORWARDED, receive_fsub_msg))

    print("🚀 Bot Started...")
    application.run_polling(drop_pending_updates=True)
