from flask import Flask
import threading
from telegram.ext import Application, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from config import BOT_TOKEN, PORT

from plugins.post_system import post_start, receive_post, choose_link_type, receive_episode, receive_number, receive_batch_episode, receive_batch_range, confirm_post, handle_send_callback, handle_push_callback
from plugins.system_handlers import start_cmd, add_shortener_start, receive_short_url, receive_short_token, add_premium_start, receive_prem_id, confirm_prem, add_fsub, receive_fsub_msg

app = Flask(__name__)
@app.route('/')
def home(): return "Bot Running ✅"

def run_flask(): app.run(host='0.0.0.0', port=PORT)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_cmd))

    post_conv = ConversationHandler(
        entry_points=[CommandHandler("post", post_start)],
        states={
            0: [MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, receive_post)],
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_link_type)],
            2: [MessageHandler(filters.ForwardedFrom(chat_id=None), receive_episode)],
            3: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_number)],
            4: [CommandHandler("hmm", confirm_post), CommandHandler("confirm", confirm_post)],
            5: [MessageHandler(filters.ForwardedFrom(chat_id=None), receive_batch_episode), CommandHandler("done", receive_batch_episode)],
            6: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_batch_range)],
            7: [CommandHandler("hmm", confirm_post), CommandHandler("confirm", confirm_post)]
        },
        fallbacks=[]
    )
    application.add_handler(post_conv)
    application.add_handler(CallbackQueryHandler(handle_send_callback, pattern=r"^send_"))
    application.add_handler(CallbackQueryHandler(handle_push_callback, pattern=r"^p(single|multi)_"))

    short_conv = ConversationHandler(
        entry_points=[CommandHandler("addshort", add_shortener_start)],
        states={0: [MessageHandler(filters.TEXT, receive_short_url)], 1: [MessageHandler(filters.TEXT, receive_short_token)]},
        fallbacks=[]
    )
    application.add_handler(short_conv)

    prem_conv = ConversationHandler(
        entry_points=[CommandHandler("addpremium", add_premium_start)],
        states={0: [MessageHandler(filters.TEXT, receive_prem_id)], 1: [CommandHandler("hu", confirm_prem)]},
        fallbacks=[]
    )
    application.add_handler(prem_conv)

    fsub_conv = ConversationHandler(
        entry_points=[CommandHandler("forcesub", add_fsub)],
        states={0: [MessageHandler(filters.FORWARDED, receive_fsub_msg)]},
        fallbacks=[]
    )
    application.add_handler(fsub_conv)

    print("🚀 Bot Started with FSub & Smart Bypass...")
    application.run_polling(drop_pending_updates=True)
