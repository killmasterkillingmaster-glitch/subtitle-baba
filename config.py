import os
from dotenv import load_dotenv
load_dotenv()


BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

OWNER_ID = 5351848105
ALLOWED_USERS = [5351848105, 5344078567]
ALLOWED_GROUP = -1003899919015
STORAGE_CHANNEL = -1003096528862

STORAGE_CHANNEL = -1003096528862   # ASI anime (tu ne full admin diya hai)
PORT = int(os.getenv("PORT", 10000))
