import os
import gc
import logging
import asyncio
from collections import deque

# Correct Pyrogram imports
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pyrogram.enums import ParseMode

from faster_whisper import WhisperModel
from aiohttp import web

# ================= CONFIG =================
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
PORT = int(os.environ.get("PORT", "8080"))

OWNER_ID = int(os.environ.get("OWNER_ID", "5344078567"))

def parse_id_list(env_val, default_list):
    if not env_val:
        return default_list
    return [int(x.strip()) for x in env_val.split(",") if x.strip()]

ALLOWED_USERS = parse_id_list(os.environ.get("ALLOWED_USERS", ""), [])
ALLOWED_GROUPS = parse_id_list(os.environ.get("ALLOWED_GROUPS", ""), [-1003899919015])

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = Client("SubGenBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

task_queue = deque()
model = None

# ================= AUTH =================
def is_authorized(message: Message) -> bool:
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
        logger.info("Loading Whisper tiny model...")
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        logger.info("Whisper model loaded successfully")
    return model

# ================= TIME & SUBTITLE FUNCTIONS =================
def format_time_srt(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def format_time_vtt(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02}.{ms:03}"

def generate_subtitle_file(segments, output_file, sub_format):
    with open(output_file, "w", encoding="utf-8") as f:
        if sub_format == "vtt":
            f.write("WEBVTT\n\n")
            for segment in segments:
                start = format_time_vtt(segment.start)
                end = format_time_vtt(segment.end)
                f.write(f"{start} --> {end}\n{segment.text.strip()}\n\n")

        elif sub_format == "srt":
            for i, segment in enumerate(segments, 1):
                start = format_time_srt(segment.start)
                end = format_time_srt(segment.end)
                f.write(f"{i}\n{start} --> {end}\n{segment.text.strip()}\n\n")

        # ASS support bhi rakha hai agar chahiye

# ================= WORKER =================
async def process_queue():
    while True:
        if not task_queue:
            await asyncio.sleep(2)
            continue

        task = task_queue.popleft()
        message = task["message"]
        sub_format = task["sub_format"]
        chat_id = message.chat.id
        msg_id = message.id

        status_msg = await message.reply("⏳ Processing started...")
        video_file = f"v_{chat_id}_{msg_id}.mp4"
        audio_file = f"a_{chat_id}_{msg_id}.mp3"
        sub_file = f"sub_{chat_id}_{msg_id}.{sub_format}"

        try:
            await status_msg.edit("📥 Downloading video...")
            await app.download_media(message.reply_to_message, file_name=video_file)

            await status_msg.edit("🎵 Extracting audio...")
            proc = await asyncio.create_subprocess_shell(
                f"ffmpeg -i {video_file} -vn -ar 16000 -ac 1 {audio_file} -y",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()

            if os.path.exists(video_file):
                os.remove(video_file)

            await status_msg.edit("🤖 Transcribing with Whisper...")
            whisper_model = load_model()
            segments_gen, info = await asyncio.to_thread(whisper_model.transcribe, audio_file)
            segments = list(segments_gen)

            await status_msg.edit("📝 Generating subtitle...")
            generate_subtitle_file(segments, sub_file, sub_format)

            await status_msg.edit("⬆️ Uploading subtitle...")
            await app.send_document(
                chat_id=chat_id,
                document=sub_file,
                caption=f"✅ Subtitle Generated ({sub_format.upper()})",
                reply_to_message_id=msg_id
            )
            await status_msg.delete()

        except Exception as e:
            logger.error(f"Processing error: {e}", exc_info=True)
            try:
                await status_msg.edit("❌ Error occurred while processing.")
            except:
                pass
        finally:
            for f in [video_file, audio_file, sub_file]:
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
        "✅ **Subtitle Baba Bot is Online**\n\n"
        "Reply to a video with `/srt`, `/vtt` or `/ass`",
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_message(filters.command(["srt", "vtt", "ass"]))
async def add_to_queue(client, message):
    if not is_authorized(message):
        await message.reply("❌ Not authorized.")
        return

    if not message.reply_to_message or not (message.reply_to_message.video or message.reply_to_message.document):
        await message.reply("❌ Please reply to a video file.")
        return

    fmt = message.command[0]
    task_queue.append({"message": message, "sub_format": fmt})
    await message.reply(f"✅ Added to queue (Position: {len(task_queue)})")

# ================= WEB SERVER (for Render) =================
async def web_handler(request):
    return web.Response(text="✅ Subtitle Baba Bot is running!")

async def start_web_server():
    server = web.Application()
    server.router.add_get('/', web_handler)
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"🌐 Web server started on port {PORT}")

# ================= MAIN =================
async def main():
    await app.start()
    logger.info("✅ Pyrogram Bot Started")

    asyncio.create_task(start_web_server())
    asyncio.create_task(process_queue())

    logger.info("🚀 Bot is fully ready and listening!")
    await idle()  # Yeh line ab sahi se chalegi

if __name__ == "__main__":
    asyncio.run(main())
