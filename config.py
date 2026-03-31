import os

API_ID = int(os.environ.get("API_ID", "123456"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

OWNER_ID = int(os.environ.get("OWNER_ID", "5351848105"))
ALLOWED_USERS = [5344078567, OWNER_ID]
ALLOWED_GROUPS = [-1003899919015]

MONGO_URI = os.environ.get("MONGO_URI", "")
STORAGE_CHANNEL_ID = int(os.environ.get("STORAGE_CHANNEL_ID", "-1003096528862"))
PORT = int(os.environ.get("PORT", "10000"))
