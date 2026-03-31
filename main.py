import os
import asyncio
import tempfile
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from faster_whisper import WhisperModel
from aiohttp import web

# ================= CONFIGURATION =================
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

OWNER_ID = 5351848105
ALLOWED_USER = 5344078567
ALLOWED_GROUP = -1003899919015
PORT = int(os.getenv("PORT", 10000))

app = Client("subtitle_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Global
active_tasks = {}
task_lock = asyncio.Lock()  # Lock for active_tasks

# ================= WEB SERVER (KEEP ALIVE) =================
async def web_server():
    async def handle(request):
        return web.Response(text="Bot is running FAST with Streaming!")
    web_app = web.Application()
    web_app.router.add_get("/", handle)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()

# ================= HELPERS =================
def format_time(seconds, srt=True):
    """Convert seconds to SRT or VTT timestamp"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    if srt:
        return f"{h:02}:{m:02}:{s:02},{ms:03}"
    else:
        return f"{h:02}:{m:02}:{s:02}.{ms:03}"

async def timer_bar(message, text, stop_event):
    """Simple animated progress bar while processing"""
    count = 0
    while not stop_event.is_set():
        try:
            bar_fill = (count % 10) + 1
            bar = "█" * bar_fill + "▒" * (10 - bar_fill)
            await message.edit_text(f"{text}\n[{bar}] {count}s")
            await asyncio.sleep(2)
            count += 2
        except:
            break

async def cancel_user_task(user_id):
    """Cancel active task for a user"""
    async with task_lock:
        if user_id in active_tasks:
            task = active_tasks[user_id]
            task["stop_event"].set()
            if task.get("proc"):
                try:
                    task["proc"].kill()
                    await task["proc"].wait()
                except Exception:
                    pass
            del active_tasks[user_id]
            return "Process Skipped/Cancelled ⏭️"
    return "Koi process active nahi hai."

def run_whisper(audio_path, out_file, req_format, stop_event):
    """Run faster_whisper model to generate subtitles"""
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio_path, beam_size=1, vad_filter=True)
    
    if stop_event.is_set():
        return False

    with open(out_file, "w", encoding="utf-8") as f:
        if req_format == "vtt":
            f.write("WEBVTT\n\n")
        for i, seg in enumerate(segments, start=1):
            start = format_time(seg.start, srt=(req_format=="srt"))
            end = format_time(seg.end, srt=(req_format=="srt"))
            text = seg.text.strip()
            if req_format == "srt":
                f.write(f"{i}\n{start} --> {end}\n{text}\n\n")
            else:
                f.write(f"{start} --> {end}\n{text}\n\n")
    return True

# ================= COMMANDS =================
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "Welcome 🤗\nReply any video or document and send /vtt or /srt to generate subtitles.\nExtra commands: /refresh, /skip",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Refresh /refresh", callback_data="refresh"),
             InlineKeyboardButton("Skip /skip", callback_data="skip")]
        ])
    )

# Buttons handler
@app.on_callback_query(filters.regex("^(skip|refresh)$"))
async def handle_buttons(client, query):
    user_id = query.from_user.id
    if user_id not in [OWNER_ID, ALLOWED_USER]:
        return await query.answer("Aap authorized nahi ho!", show_alert=True)
    msg_text = "Bot Refreshed! 🔄 Nayi file send karein." if query.data=="refresh" else await cancel_user_task(user_id)
    await query.answer(msg_text, show_alert=True)
    await query.message.reply_text(msg_text)

# Skip/Refresh via text
@app.on_message(filters.regex(r"(?i)^[/#](skip|refresh)"))
async def skip_refresh(client, message):
    user_id = message.from_user.id if message.from_user else 0
    if user_id not in [OWNER_ID, ALLOWED_USER] and message.chat.id != ALLOWED_GROUP:
        return
    msg_text = "Bot Refreshed! 🔄 Nayi file send karein." if "refresh" in message.text.lower() else await cancel_user_task(user_id)
    await message.reply_text(msg_text)

# ================= SUBTITLE PROCESS =================
@app.on_message(filters.regex(r"(?i)^[/#](vtt|srt)"))
async def generate_subs(client, message):
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id
    
    if user_id not in [OWNER_ID, ALLOWED_USER] and chat_id != ALLOWED_GROUP:
        return

    async with task_lock:
        if user_id in active_tasks:
            return await message.reply_text("Ek process pehle se chal raha hai. Pehle use /skip karein.")

    if not message.reply_to_message or not (message.reply_to_message.video or message.reply_to_message.document):
        return await message.reply_text("Reply to a video/document and use /vtt or /srt")

    req_format = "vtt" if "vtt" in message.text.lower() else "srt"
    reply_msg = message.reply_to_message

    stop_event = asyncio.Event()
    timer_msg = await message.reply_text("Processing... ⏳ (Extracting Audio)")
    timer_task = asyncio.create_task(timer_bar(timer_msg, "Processing...", stop_event))

    # Create temp files
    audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    out_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{req_format}").name

    async with task_lock:
        active_tasks[user_id] = {"proc": None, "stop_event": stop_event}

    try:
        # ----------------- Audio Extraction -----------------
        cmd = [
            "ffmpeg", "-y", "-i", "pipe:0",
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", audio_file
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        async with task_lock:
            active_tasks[user_id]["proc"] = proc

        async for chunk in client.stream_media(reply_msg):
            if stop_event.is_set():
                break
            try:
                proc.stdin.write(chunk)
                await asyncio.wait_for(proc.stdin.drain(), timeout=5)
            except:
                break

        if proc.stdin:
            proc.stdin.close()
        await proc.wait()

        if stop_event.is_set():
            raise Exception("Process Cancelled/Skipped")

        # ----------------- Whisper Processing -----------------
        stop_event.clear()
        timer_task = asyncio.create_task(timer_bar(timer_msg, "Generating Subtitles... ⚙️", stop_event))
        await asyncio.to_thread(run_whisper, audio_file, out_file, req_format, stop_event)

        if stop_event.is_set():
            raise Exception("Process Cancelled/Skipped")

        stop_event.set()
        await timer_msg.delete()

        # Send final subtitle file
        caption = "WEBVTT ✅" if req_format=="vtt" else "SRT ✅"
        await message.reply_document(out_file, caption=caption)

    except Exception as e:
        stop_event.set()
        if timer_msg: await timer_msg.edit(f"❌ Error: {str(e)}")
    finally:
        async with task_lock:
            if user_id in active_tasks:
                del active_tasks[user_id]
        for f in [audio_file, out_file]:
            if os.path.exists(f):
                os.remove(f)

# ================= MAIN =================
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(web_server())
    app.run()
