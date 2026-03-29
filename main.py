import os
import gc
import logging
import asyncio
from collections import deque
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from faster_whisper import WhisperModel
from aiohttp import web

# ================= CONFIG =================

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN missing! Set it in Render ENV")

OWNER_ID = int(os.getenv("OWNER_ID", "5344078567"))

def parse_ids(value, default):
    if not value:
        return default
    return [int(x.strip()) for x in value.split(",") if x.strip()]

ALLOWED_USERS = parse_ids(os.getenv("ALLOWED_USERS"), [])
ALLOWED_GROUPS = parse_ids(os.getenv("ALLOWED_GROUPS"), [-1003899919015])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Client("SubGenBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ================= GLOBALS =================
task_queue = deque()
model = None

# ================= AUTH =================
def is_authorized(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id

    return (
        user_id == OWNER_ID
        or user_id in ALLOWED_USERS
        or chat_id in ALLOWED_GROUPS
    )

# ================= MODEL =================
def load_model():
    global model
    if model is None:
        logger.info("Loading Whisper Tiny Model...")
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
    return model

# ================= TIME =================
def srt_time(s):
    return f"{int(s//3600):02}:{int((s%3600)//60):02}:{int(s%60):02},{int((s%1)*1000):03}"

def vtt_time(s):
    return f"{int(s//3600):02}:{int((s%3600)//60):02}:{int(s%60):02}.{int((s%1)*1000):03}"

# ================= SUB =================
def generate_sub(segments, file, fmt):
    with open(file, "w", encoding="utf-8") as f:
        if fmt == "vtt":
            f.write("WEBVTT\n\n")

        for i, seg in enumerate(segments, 1):
            text = seg.text.strip()
            if not text:
                continue

            if fmt == "srt":
                f.write(f"{i}\n{srt_time(seg.start)} --> {srt_time(seg.end)}\n{text}\n\n")
            else:
                f.write(f"{vtt_time(seg.start)} --> {vtt_time(seg.end)}\n{text}\n\n")

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

        status = await message.reply("⏳ Processing...")

        video = f"v_{chat_id}_{msg_id}.mp4"
        audio = f"a_{chat_id}_{msg_id}.mp3"
        sub = f"sub_{chat_id}_{msg_id}.{fmt}"

        try:
            await app.download_media(message.reply_to_message, file_name=video)

            await status.edit("🎵 Extracting audio...")

            proc = await asyncio.create_subprocess_shell(
                f"ffmpeg -i {video} -vn -ar 16000 -ac 1 {audio} -y",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await proc.wait()

            os.remove(video)

            await status.edit("🤖 Transcribing...")

            mdl = load_model()
            seg_gen, _ = await asyncio.to_thread(mdl.transcribe, audio)
            segments = list(seg_gen)

            generate_sub(segments, sub, fmt)

            await status.edit("⬆️ Uploading...")

            await app.send_document(chat_id, sub, reply_to_message_id=msg_id)

            await status.delete()

        except Exception as e:
            logger.error(e)
            await status.edit("❌ Error")

        finally:
            for f in [video, audio, sub]:
                if os.path.exists(f):
                    os.remove(f)
            gc.collect()

# ================= COMMANDS =================
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply("✅ Bot Working!\nReply video with /srt or /vtt")

@app.on_message(filters.command(["srt","vtt"]))
async def add(client, message):
    if not message.reply_to_message:
        return await message.reply("Reply to video")

    task_queue.append({
        "message": message,
        "format": message.command[0]
    })

    await message.reply(f"✅ Added to queue ({len(task_queue)})")

# ================= WEB =================
async def health(request):
    return web.Response(text="OK")

async def start_web():
    app_web = web.Application()
    app_web.router.add_get("/", health)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

# ================= MAIN =================
async def main():
    await app.start()
    await start_web()
    asyncio.create_task(worker())
    print("BOT STARTED")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
