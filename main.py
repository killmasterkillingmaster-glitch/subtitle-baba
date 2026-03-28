import os
import gc
import logging
import asyncio
from collections import deque
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from faster_whisper import WhisperModel
from aiohttp import web

# ================= CONFIG =================
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
PORT = int(os.getenv("PORT", "8080"))

OWNER_ID = int(os.getenv("OWNER_ID", "5344078567"))

def parse_ids(value, default):
    if not value:
        return default
    return [int(x.strip()) for x in value.split(",") if x.strip()]

ALLOWED_USERS = parse_ids(os.getenv("ALLOWED_USERS"), [5351848105])
ALLOWED_GROUPS = parse_ids(os.getenv("ALLOWED_GROUPS"), [-1003899919015])

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Client("SubGenBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ================= GLOBALS =================
task_queue = deque()
model = None

# ================= AUTH =================
def is_authorized(message: Message):
    if not message.from_user:
        return False
    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id == OWNER_ID or user_id in ALLOWED_USERS or chat_id in ALLOWED_GROUPS:
        return True
    return False

# ================= MODEL =================
def load_model():
    global model
    if model is None:
        logger.info("Loading Whisper Tiny Model (this may take a few seconds)...")
        try:
            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise
    return model

# ================= TIME FORMAT =================
def srt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def vtt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02}.{ms:03}"

# ================= SUBTITLE GENERATOR =================
def generate_subtitles(segments, file, fmt):
    with open(file, "w", encoding="utf-8") as f:
        if fmt == "vtt":
            f.write("WEBVTT\n\n")

        for i, seg in enumerate(segments, 1):
            text = seg.text.strip()
            if not text:
                continue

            if fmt == "srt":
                start = srt_time(seg.start)
                end = srt_time(seg.end)
                f.write(f"{i}\n{start} --> {end}\n{text}\n\n")
            else:  # vtt
                start = vtt_time(seg.start)
                end = vtt_time(seg.end)
                f.write(f"{start} --> {end}\n{text}\n\n")

# ================= WORKER =================
async def worker():
    while True:
        if not task_queue:
            await asyncio.sleep(2)
            continue

        task = task_queue.popleft()
        message = task["message"]
        fmt = task["format"]

        chat_id = message.chat.id
        msg_id = message.id

        status = await message.reply("⏳ Processing started...")
        video = f"v_{chat_id}_{msg_id}.mp4"
        audio = f"a_{chat_id}_{msg_id}.mp3"
        sub = f"sub_{chat_id}_{msg_id}.{fmt}"

        try:
            await status.edit("📥 Downloading video...")
            await app.download_media(message.reply_to_message, file_name=video)

            await status.edit("🎵 Extracting audio...")
            process = await asyncio.create_subprocess_shell(
                f"ffmpeg -i {video} -vn -ar 16000 -ac 1 {audio} -y",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()

            if os.path.exists(video):
                os.remove(video)

            await status.edit("🤖 AI Transcribing with Whisper...")
            mdl = load_model()
            segments_gen, info = await asyncio.to_thread(mdl.transcribe, audio, beam_size=5)
            segments = list(segments_gen)

            logger.info(f"Transcription done - Detected language: {info.language} (prob: {info.language_probability:.2f})")

            await status.edit("📝 Generating subtitle file...")
            generate_subtitles(segments, sub, fmt)

            await status.edit("⬆️ Uploading subtitle...")
            await app.send_document(
                chat_id=chat_id,
                document=sub,
                caption=f"✅ Subtitle Generated Successfully\nFormat: {fmt.upper()}\nLanguage: {info.language}",
                reply_to_message_id=msg_id
            )

            await status.delete()

        except Exception as e:
            logger.error(f"Error processing task: {e}", exc_info=True)
            await status.edit(f"❌ Error: {str(e)[:200]}")
        finally:
            for f in [video, audio, sub]:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except:
                        pass
            gc.collect()

# ================= COMMANDS =================
@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    if not is_authorized(message):
        await message.reply("❌ You are not authorized to use this bot.")
        return

    await message.reply(
        "✅ **SubGen Bot is Online**\n\n"
        "Reply to any video with `/srt` or `/vtt` to generate subtitles.\n"
        "It uses Whisper Tiny model (fast on CPU).",
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_message(filters.command(["srt", "vtt"]))
async def add_queue(client, message):
    if not is_authorized(message):
        await message.reply("❌ You are not authorized.")
        return

    if not message.reply_to_message or not message.reply_to_message.video:
        await message.reply("❌ Please reply to a **video** file.")
        return

    fmt = message.command[0]
    task_queue.append({"message": message, "format": fmt})

    queue_len = len(task_queue)
    await message.reply(f"✅ Added to queue (Position: {queue_len})\nIt will be processed soon.")

# ================= WEB SERVER =================
async def health(request):
    return web.Response(text="SubGen Bot is running ✅")

async def start_web():
    try:
        app_web = web.Application()
        app_web.router.add_get("/", health)
        runner = web.AppRunner(app_web)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        logger.info(f"🌐 Web server started on port {PORT}")
    except Exception as e:
        logger.error(f"Web server failed to start: {e}")

# ================= MAIN =================
async def main():
    await app.start()
    logger.info("✅ Pyrogram Bot Started Successfully")

    asyncio.create_task(start_web())
    asyncio.create_task(worker())

    logger.info("🚀 All tasks started - Bot is ready!")
    await idle()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Critical error: {e}")
