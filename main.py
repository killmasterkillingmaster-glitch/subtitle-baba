import threading
from flask import Flask
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters
)
from config import BOT_TOKEN, PORT

# Plugins Imports
from plugins.post_system import (
    post_start, receive_post, choose_link_type, receive_episode, receive_number,
    receive_batch_episode, receive_batch_range, confirm_post,
    cmd_send, cmd_send_more, handle_push_callback, final_send_confirm,
    SEND_POST, LINK_TYPE, SEND_EPISODE, EPISODE_NUMBER, CONFIRM,
    BATCH_EPISODES, BATCH_RANGE, BATCH_CONFIRM
)

from plugins.system_handlers import (
    start_cmd, cmd_setting,
    add_shortener_start, receive_short_url, receive_short_token,
    cmd_rem_short, handle_del_short, cmd_delete, WAIT_URL, WAIT_TOKEN,
    add_premium_start, receive_prem_id, confirm_prem, PREM_ID, PREM_CONF,
    cmd_rem_prem, process_rem_prem, show_prem,
    add_fsub, receive_fsub_msg
)

app_flask = Flask(__name__)
@app_flask.route('/')
def home(): return "Bot Running Properly! 🚀"

def run_flask(): app_flask.run(host='0.0.0.0', port=PORT)

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()

    # Base Handlers
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("setting", cmd_setting))
    
    # Send & Confirm Logic
    app.add_handler(CommandHandler("send", cmd_send))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^/send$"), cmd_send))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^/send more channel$"), cmd_send_more))
    
    app.add_handler(CommandHandler("confirm", final_send_confirm))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^/confirm$"), final_send_confirm))
    
    app.add_handler(CallbackQueryHandler(handle_push_callback, pattern=r"^p(single|multi)_"))
    app.add_handler(CallbackQueryHandler(handle_del_short, pattern=r"^delsh_"))
    
    app.add_handler(CommandHandler("delete", cmd_delete))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^/delete$"), cmd_delete))

    # Post Conversation
    post_conv = ConversationHandler(
        entry_points=[CommandHandler("post", post_start), MessageHandler(filters.Regex(r"(?i)^/post$"), post_start)],
        states={
            SEND_POST: [MessageHandler(filters.ALL & ~filters.COMMAND, receive_post)],
            LINK_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_link_type)],
            SEND_EPISODE: [MessageHandler(filters.ALL & ~filters.COMMAND, receive_episode)],
            EPISODE_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_number)],
            CONFIRM: [MessageHandler(filters.Regex(r"(?i)^/hmm$|^/confirm$"), confirm_post)],
            BATCH_EPISODES: [
                MessageHandler(filters.ALL & ~filters.COMMAND, receive_batch_episode),
                MessageHandler(filters.Regex(r"(?i)^/done$"), receive_batch_episode)
            ],
            BATCH_RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_batch_range)],
            BATCH_CONFIRM: [MessageHandler(filters.Regex(r"(?i)^/hmm$|^/confirm$"), confirm_post)]
        },
        fallbacks=[CommandHandler("delete", cmd_delete)]
    )
    app.add_handler(post_conv)

    # Shortener System
    short_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"(?i)^/add shortner account$"), add_shortener_start)],
        states={
            WAIT_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_short_url)],
            WAIT_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_short_token)]
        },
        fallbacks=[CommandHandler("delete", cmd_delete)]
    )
    app.add_handler(short_conv)
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^/remove shortner account$"), cmd_rem_short))

    # Premium System
    prem_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"(?i)^/add premium$"), add_premium_start)],
        states={
            PREM_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_prem_id)],
            PREM_CONF: [MessageHandler(filters.Regex(r"(?i)^/hu hu$"), confirm_prem)]
        },
        fallbacks=[CommandHandler("delete", cmd_delete)]
    )
    app.add_handler(prem_conv)
    
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^/remove premium$"), cmd_rem_prem))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^/show premium list$"), show_prem))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_rem_prem), group=1)

    # Force Sub System
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^/force sub$|^/Force sub$"), add_fsub))
    app.add_handler(MessageHandler(filters.FORWARDED & ~filters.COMMAND, receive_fsub_msg))

    print("🚀 Auto Post Bot Started Successfully!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
