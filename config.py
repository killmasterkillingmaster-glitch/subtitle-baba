import os

# Render environment variables se aayega
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

PORT = int(os.getenv("PORT", 10000))

# Hardcoded details as requested
OWNER_ID = 5351848105
ALLOWED_USERS = [5344078567, 5351848105]
ALLOWED_GROUP = -1003899919015
STORAGE_CHANNEL = -1003096528862  # ASI anime
