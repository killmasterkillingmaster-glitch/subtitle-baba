import datetime
from modules.utils import get_db
from config import ALLOWED_USERS

async def add_premium(user_id: int, target_id: int, message):
    if user_id not in ALLOWED_USERS:
        await message.reply_text("🚫 Not allowed")
        return
    db = get_db()
    expiry = datetime.datetime.utcnow() + datetime.timedelta(days=28)
    db.premium_users.update_one(
        {"user_id": target_id},
        {"$set": {"added_on": datetime.datetime.utcnow(), "expires_on": expiry}},
        upsert=True
    )
    await message.reply_text(f"✨ Premium added until {expiry}")

async def remove_premium(user_id: int, target_id: int, message):
    if user_id not in ALLOWED_USERS:
        await message.reply_text("🚫 Not allowed")
        return
    db = get_db()
    result = db.premium_users.delete_one({"user_id": target_id})
    if result.deleted_count:
        await message.reply_text(f"❌ Premium removed for {target_id}")
    else:
        await message.reply_text("⚠ User not found")

async def is_premium(user_id: int):
    db = get_db()
    user = db.premium_users.find_one({"user_id": user_id})
    if not user: return False
    if user["expires_on"] < datetime.datetime.utcnow():
        db.premium_users.delete_one({"user_id": user_id})
        return False
    return True
