import os

# ------------------ TELEGRAM BOT ------------------
API_ID = int(os.getenv("API_ID", "123456"))
API_HASH = os.getenv("API_HASH", "your_api_hash_here")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token_here")

OWNER_ID = int(os.getenv("OWNER_ID", "5351848105"))
ALLOWED_USERS = [5344078567]
ALLOWED_GROUPS = [-1003899919015]

# ------------------ DATABASE ------------------
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://YOUR_USER:YOUR_PASS@cluster.mongodb.net/?retryWrites=true&w=majority")
STORAGE_CHANNEL_ID = -1003096528862

# ------------------ BOT CONFIG ------------------
PORT = int(os.getenv("PORT", 10000))
SHORTNER_ACCOUNTS = []
