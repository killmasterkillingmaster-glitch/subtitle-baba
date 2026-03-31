import asyncio
from aiohttp import web
from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN, PORT

# Basic web server route
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"Web server started on port {PORT}")

# Pyrogram Client
bot = Client(
    "AnimeBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=dict(root="plugins") # Yeh jaruri hai taki plugins folder load ho
)

async def main():
    await start_web_server()
    print("Starting Telegram Bot...")
    await bot.start()
    from pyrogram import idle
    await idle()
    await bot.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
