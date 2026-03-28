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

# --- CONFIGURATION & RENDER VARIABLES ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
HF_TOKEN = os.environ.get("HF_TOKEN", "") # Optional HuggingFace token
PORT = int(os.environ.get("PORT", "8080")) # Required for Render web service

# --- ACCESS CONTROL SYSTEM ---
# You can set these in Render Environment Variables (comma-separated for lists)
# Defaults are set to the exact IDs you provided.
OWNER_ID = int(os.environ.get("OWNER_ID", "5344078567"))

# Parse comma-separated strings into lists of integers
def parse_id_list(env_val, default_list):
    if not env_val:
        return default_list
    return [int(x.strip()) for x in env_val.split(",") if x.strip()]

ALLOWED_USERS = parse_id_list(os.environ.get("ALLOWED_USERS", ""), [5351848105])
ALLOWED_GROUPS = parse_id_list(os.environ.get("ALLOWED_GROUPS", ""), [-1003899919015])

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

if HF_TOKEN:
    os.environ["HF_TOKEN"] = HF_TOKEN

app = Client("SubGenBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- GLOBALS ---
task_queue = deque()
model = None

# --- AUTHORIZATION CHECK ---
def is_authorized(message: Message) -> bool:
    """Checks if the user or group is allowed to use the bot."""
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id

    if user_id == OWNER_ID:
        return True
    if user_id in ALLOWED_USERS:
        return True
    if chat_id in ALLOWED_GROUPS:
        return True
        
    return False

# --- MODEL LOADER ---
def load_model():
    """Lazy model loader. Only loads when a video needs processing."""
    global model
    if model is None:
        logger.info("Loading Faster-Whisper tiny model into RAM...")
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
    return model

# --- SUBTITLE FORMATTERS ---
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

def format_time_ass(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds - int(seconds)) * 100) # Centiseconds
    return f"{h}:{m:02}:{s:02}.{cs:02}"

def generate_subtitle_file(segments, output_file, sub_format):
    """Generates the requested subtitle format from Whisper segments."""
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

        elif sub_format == "ass":
            f.write("[Script Info]\nScriptType: v4.00+\nPlayResX: 384\nPlayResY: 288\n\n")
            f.write("[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
            f.write("Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1\n\n")
            f.write("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
            for segment in segments:
                start = format_time_ass(segment.start)
                end = format_time_ass(segment.end)
                f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{segment.text.strip()}\n")

# --- BACKGROUND WORKER ---
async def process_queue():
    """Worker loop running every 2 seconds to process videos one by one."""
    while True:
        if not task_queue:
            await asyncio.sleep(2)
            continue
        
        task = task_queue.popleft()
        message: Message = task["message"]
        sub_format = task["sub_format"]
        chat_id = message.chat.id
        msg_id = message.id

        status_msg = await message.reply("⏳ Downloading video...")
        
        # File paths
        video_file = f"v_{chat_id}_{msg_id}.mp4"
        audio_file = f"a_{chat_id}_{msg_id}.mp3"
        sub_file = f"sub_{chat_id}_{msg_id}.{sub_format}"

        try:
            # 1. Download Media
            await app.download_media(message.reply_to_message, file_name=video_file)

            # 2. Extract Audio via FFmpeg
            await status_msg.edit("🎵 Extracting audio...")
            process = await asyncio.create_subprocess_shell(
                f"ffmpeg -i {video_file} -vn -ar 16000 -ac 1 {audio_file} -y",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()

            # 3. Cleanup Video Immediately
            if os.path.exists(video_file):
                os.remove(video_file)

            # 4. Transcribe Audio
            await status_msg.edit("🧠 Transcribing audio...")
            whisper_model = load_model()
            
            # Blocking CPU task sent to thread
            segments_generator, info = await asyncio.to_thread(whisper_model.transcribe, audio_file)
            segments = list(segments_generator)

            # 5. Generate Subtitle File
            await status_msg.edit("📝 Generating subtitles...")
            generate_subtitle_file(segments, sub_file, sub_format)

            # 6. Upload Document
            await status_msg.edit("⬆️ Uploading...")
            await app.send_document(
                chat_id=chat_id,
                document=sub_file,
                caption="✅ Subtitle Generated Successfully",
                reply_to_message_id=msg_id
            )
            await status_msg.delete()

        except Exception as e:
            logger.error(f"Error processing {msg_id}: {e}")
            await status_msg.edit("❌ An error occurred during processing.")

        finally:
            # 7. Final Cleanup
            if os.path.exists(video_file):
                os.remove(video_file)
            if os.path.exists(audio_file):
                os.remove(audio_file)
            if os.path.exists(sub_file):
                os.remove(sub_file)
            
            # Force Garbage Collection to free RAM
            gc.collect()

# --- BOT HANDLERS ---
@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    if not is_authorized(message):
        await message.reply("❌ You are not allowed to use this bot.")
        return

    await message.reply(
        "SubGen Bot Online. Reply to any video with `/srt`, `/vtt`, or `/ass` to generate subtitles.",
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_message(filters.command(["srt", "vtt", "ass"]))
async def add_to_queue(client, message):
    if not is_authorized(message):
        await message.reply("❌ You are not allowed to use this bot.")
        return

    if not message.reply_to_message or not (message.reply_to_message.video or message.reply_to_message.document):
        await message.reply("⚠️ Please reply to a video file.")
        return
    
    command = message.text.split()[0].replace("/", "").lower()
    
    task_queue.append({
        "message": message,
        "sub_format": command
    })
    
    position = len(task_queue)
    await message.reply(f"✅ Added to queue (Position: {position}). Please wait.")

# --- DUMMY WEB SERVER FOR RENDER ---
async def web_handler(request):
    return web.Response(text="Bot is running successfully!")

async def start_web_server():
    """Starts a lightweight web server to satisfy Render's Port binding rule."""
    server = web.Application()
    server.add_routes([web.get('/', web_handler)])
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"Dummy Web Server started on port {PORT}")

# --- MAIN RUNNER ---
async def main():
    logger.info("Starting Bot...")
    await app.start()
    
    logger.info("Starting Web Server...")
    await start_web_server()
    
    logger.info("Starting Background Worker Queue...")
    asyncio.create_task(process_queue())
    
    from pyrogram import idle
    await idle()
    await app.stop()

if __name__ == "__main__":
    app.run(main())
