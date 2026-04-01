from motor.motor_asyncio import AsyncIOMotorClient
import config
from datetime import datetime, timedelta

client = AsyncIOMotorClient(config.MONGO_URI)
db = client[config.DB_NAME]

shorteners_db = db["shorteners"]
premium_db = db["premium_users"]
banned_db = db["banned_users"]
fsub_db = db["force_sub_channels"]
admin_channels_db = db["admin_channels"]
links_db = db["links"]
tokens_db = db["tokens"]

# Helper functions
async def get_all_shorteners():
    return await shorteners_db.find().to_list(length=100)

async def add_shortener(name, api):
    await shorteners_db.insert_one({"name": name, "api": api})

async def remove_shortener(name):
    await shorteners_db.delete_one({"name": name})

async def is_premium(user_id):
    user = await premium_db.find_one({"user_id": user_id})
    if user:
        if datetime.now() < user["expiry"]:
            return True
        else:
            await premium_db.delete_one({"user_id": user_id})
    return False

async def add_premium(user_id):
    expiry = datetime.now() + timedelta(days=28)
    await premium_db.update_one({"user_id": user_id}, {"$set": {"expiry": expiry}}, upsert=True)

async def ban_user(user_id):
    await premium_db.delete_one({"user_id": user_id})
    await banned_db.insert_one({"user_id": user_id})

async def get_fsub_channels():
    return await fsub_db.find().to_list(length=10)

async def save_post_link(hash_code, data):
    await links_db.insert_one({"hash": hash_code, "data": data})

async def get_post_link(hash_code):
    return await links_db.find_one({"hash": hash_code})
