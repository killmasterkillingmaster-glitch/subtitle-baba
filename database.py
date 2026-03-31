from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI
import datetime

client = AsyncIOMotorClient(MONGO_URI)
db = client["Anime_Bot_DB"]

# -- Post Storage --
async def save_batch(file_ids, is_batch=False):
    doc = {"file_ids": file_ids, "is_batch": is_batch, "date": datetime.datetime.utcnow()}
    result = await db.posts.insert_one(doc)
    return str(result.inserted_id)

async def get_post(post_id):
    from bson.objectid import ObjectId
    return await db.posts.find_one({"_id": ObjectId(post_id)})

# -- Premium --
async def add_premium_user(user_id):
    expiry = datetime.datetime.utcnow() + datetime.timedelta(days=28)
    await db.premium.update_one({"user_id": user_id}, {"$set": {"expiry": expiry}}, upsert=True)

async def remove_premium_user(user_id):
    await db.premium.delete_one({"user_id": user_id})

async def is_premium(user_id):
    user = await db.premium.find_one({"user_id": user_id})
    if not user: return False
    if user["expiry"] < datetime.datetime.utcnow():
        await remove_premium_user(user_id)
        return False
    return True

# -- Shorteners --
async def add_shortener(url, api):
    await db.shorteners.insert_one({"url": url, "api": api})

async def get_random_shortener():
    shorteners = await db.shorteners.find().to_list(length=None)
    import random
    return random.choice(shorteners) if shorteners else None

async def remove_shortener(url):
    await db.shorteners.delete_one({"url": url})

# -- Force Sub --
async def set_force_sub(channel_id):
    await db.fsub.update_one({"_id": "fsub"}, {"$addToSet": {"channels": channel_id}}, upsert=True)

async def get_force_sub():
    data = await db.fsub.find_one({"_id": "fsub"})
    return data["channels"] if data and "channels" in data else []
