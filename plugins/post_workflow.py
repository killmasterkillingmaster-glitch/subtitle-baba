from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import ALLOWED_USERS, STORAGE_CHANNEL_ID
from database import save_batch
import pyromod # Handles the .ask() function

@Client.on_message(filters.command("post") & filters.user(ALLOWED_USERS))
async def post_workflow(bot, message):
    chat_id = message.chat.id
    
    # Step 1: Get Post
    post_msg = await bot.ask(chat_id, "Bot reply - send post")
    if not post_msg.media:
        return await message.reply("Please send a valid file/media.")
    
    # Step 2: Forward to storage
    stored_msg = await post_msg.copy(STORAGE_CHANNEL_ID)
    file_ids = [stored_msg.id]
    
    # Step 3: Single or Batch
    link_type = await bot.ask(chat_id, "Bot reply - post successfully received\nPlease provide 'single link' or 'batch link'")
    is_batch = link_type.text.lower() == "batch link"
    
    if is_batch:
        while True:
            next_ep = await bot.ask(chat_id, "Send next episode (or type /done to finish)")
            if next_ep.text == "/done":
                break
            st_msg = await next_ep.copy(STORAGE_CHANNEL_ID)
            file_ids.append(st_msg.id)
            await message.reply("batch successfully adding")
            
    # Step 4: Episode Number
    ep_num = await bot.ask(chat_id, "Enter Number (e.g. 07 or 05 - 15)")
    
    # Step 5: Confirm
    await bot.ask(chat_id, "/confirm please (Type /hmm to proceed)")
    
    # Generate Database Link
    post_db_id = await save_batch(file_ids, is_batch)
    bot_username = (await bot.get_me()).username
    deep_link = f"https://t.me/{bot_username}?start=get_{post_db_id}"
    
    # Preview
    btn = InlineKeyboardMarkup([[InlineKeyboardButton(f"Watch episode {ep_num.text}", url=deep_link)]])
    preview = await stored_msg.copy(chat_id, reply_markup=btn)
    
    # Step 6: Send to channels
    send_cmd = await bot.ask(chat_id, "Type /send (for 1 channel) or /send more channel")
    
    # Demo logic for sending (Aap database se channels fetch kar sakte ho)
    if send_cmd.text == "/send" or send_cmd.text == "/send more channel":
        target_channel = await bot.ask(chat_id, "Send Target Channel ID (e.g. @gyaanibaba or -100xxx)")
        confirm = await bot.ask(chat_id, "Bot reply - confirm please (Type /confirm)")
        
        if confirm.text == "/confirm":
            await stored_msg.copy(target_channel.text, reply_markup=btn)
            await message.reply("Successfully posted to channels! 🎉")
