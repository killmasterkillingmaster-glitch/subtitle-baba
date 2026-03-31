# modules/shortner.py
import aiohttp
from pyrogram.types import Message
from modules.utils import get_db
from config import ALLOWED_USERS

class ShortnerManager:
    def __init__(self):
        self.db = get_db()

    # ---------------- Add shortner account ----------------
    async def add_account(self, user_id: int, dashboard_url: str, api_token: str, message: Message):
        if user_id not in ALLOWED_USERS:
            await message.reply_text("🚫 You are not allowed to add shortner accounts.")
            return
        
        # Save account in MongoDB
        self.db.shortner_accounts.update_one(
            {"dashboard_url": dashboard_url},
            {"$set": {"api_token": api_token}},
            upsert=True
        )
        await message.reply_text("✅ Shortner account added successfully!")

    # ---------------- Remove shortner account ----------------
    async def remove_account(self, user_id: int, dashboard_url: str, message: Message):
        if user_id not in ALLOWED_USERS:
            await message.reply_text("🚫 You are not allowed to remove shortner accounts.")
            return

        result = self.db.shortner_accounts.delete_one({"dashboard_url": dashboard_url})
        if result.deleted_count:
            await message.reply_text("✅ Shortner account removed successfully!")
        else:
            await message.reply_text("⚠️ No account found with this URL.")

    # ---------------- Get next shortner for rotation ----------------
    def get_next_account(self):
        accounts = list(self.db.shortner_accounts.find({}))
        if not accounts:
            return None
        
        # Simple rotation using first account and moving it to the end
        account = accounts[0]
        self.db.shortner_accounts.delete_one({"dashboard_url": account["dashboard_url"]})
        self.db.shortner_accounts.insert_one(account)
        return account

    # ---------------- Generate short link ----------------
    async def generate_short_link(self, original_url: str):
        """
        Pick next account in rotation and generate short link.
        Actual API call to dashboard should be implemented here.
        For now, returns a dummy short link.
        """
        account = self.get_next_account()
        if not account:
            return None, "No shortner accounts available."
        
        # Simulate API call to shortner dashboard
        short_link = f"{account['dashboard_url']}/short/{original_url.split('/')[-1]}"
        return short_link, None
