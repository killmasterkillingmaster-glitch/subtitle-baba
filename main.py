import os
import time
import json
import asyncio
import threading
import tempfile
import shutil
import gc
from collections import deque
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified, MessageIdInvalid
from http.server import HTTPServer, BaseHTTPRequestHandler

# ================= CONFIGURATION =================

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEST_CHANNEL = "@Sub_and_hardsub"   # yaha channel ka username dena. Id nahi dena.
PORT = int(os.environ.get("PORT", 10000))

OWNER_ID = 5351848105       
ALLOWED_USERS = [5344078567]             
ALLOWED_GROUPS = [-1003899919015] 

app = Client("EncoderBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Global Variables
users_data = {}
task_queue = deque()
in_queue = set()
processing_lock = asyncio.Lock()
main_loop = None
edit = "Maintanence by: @Sub_and_hardsub"     

current_encoding = {}  

# ================= UTILS =================

def is_authorized(message: Message) -> bool:
    if not message.from_user: return False
    u_id = message.from_user.id    
    if message.text and message.text.lower().startswith("/start"): return True    
    if u_id == OWNER_ID or u_id in ALLOWED_USERS or message.chat.id in ALLOWED_GROUPS:
        return True
    return False

def is_owner(message: Message) -> bool:
    return message.from_user and message.from_user.id == OWNER_ID

async def get_duration(file):
    try:
        cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", file]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        data = json.loads(stdout.decode())
        return float(data.get("format", {}).get("duration", 0))
    except:
        return 0

def format_progress_bar(percent, width=10):
    filled = int(percent * width / 100)
    bar = "█" * filled + "░" * (width - filled)
    return bar

async def safe_edit(message: Message, text: str):
    try:
        await message.edit(text)
    except (MessageNotModified, MessageIdInvalid):
        pass
    except Exception:
        pass

async def download_with_verification(client, file_id, status_msg, phase="Downloading"):
    temp_dir = tempfile.gettempdir()
    base_name = f"temp_{int(time.time())}_{file_id}"
    
    for attempt in range(3): # Reduced retries to save Render memory
        temp_file = os.path.join(temp_dir, f"{base_name}_{attempt}")
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
                
            path = await client.download_media(file_id, file_name=temp_file)
            if path and os.path.exists(path) and os.path.getsize(path) > 0:
                return path
        except Exception as e:
            if attempt < 2:
                await asyncio.sleep(3)
                continue
            raise Exception(f"Download failed: {str(e)}")
    raise Exception("Download failed after 3 attempts")

async def encode_with_progress(video_path, subtitle_path, output_path, total_duration, status_msg, user_id):
    # Fix for Hardsub on Linux/Render: Copy sub to a simple path
    sub_ext = os.path.splitext(subtitle_path)[1].lower()
    safe_sub_name = f"sub_{user_id}{sub_ext}"
    safe_sub_path = os.path.join(os.getcwd(), safe_sub_name)
    shutil.copy2(subtitle_path, safe_sub_path)
    
    # Scale fix: Ensures width/height are divisible by 2 (fixes crash for odd-resolution videos)
    filter_complex = f"scale=trunc(iw/2)*2:trunc(ih/2)*2,subtitles='{safe_sub_name}'"
    
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", filter_complex,
        "-c:v", "libx264",
        "-preset", "ultrafast",  # Fastest possible CPU encoding
        "-crf", "26",            # Balanced size and quality
        "-threads", "0",
        "-c:a", "aac",           # AAC format audio support for all devices
        "-b:a", "128k",
        "-max_muxing_queue_size", "1024",
        "-progress", "pipe:1",
        "-y", output_path
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    current_encoding[user_id] = process
    
    last_update = 0
    progress_data = {}
    error_lines = []

    async def read_stdout():
        nonlocal last_update
        while True:
            line = await process.stdout.readline()
            if not line: break
            line_str = line.decode(errors="ignore").strip()
            if "=" in line_str:
                key, val = line_str.split("=", 1)
                progress_data[key] = val
            if "out_time_ms" in progress_data:
                try:
                    ms = int(progress_data["out_time_ms"])
                    current_seconds = ms / 1_000_000.0
                    percent = (current_seconds / total_duration) * 100 if total_duration > 0 else 0
                    now = time.time()
                    
                    if now - last_update > 6 or percent >= 100:
                        bar = format_progress_bar(percent)
                        await safe_edit(status_msg, f"🔥 Encoding...\n`{bar}` {percent:.1f}%")
                        last_update = now
                except Exception:
                    pass

    async def read_stderr():
        nonlocal error_lines
        while True:
            line = await process.stderr.readline()
            if not line: break
            error_lines.append(line.decode(errors="ignore"))

    await asyncio.gather(read_stdout(), read_stderr())
    returncode = await process.wait()
    
    # Cleanup safe sub
    if os.path.exists(safe_sub_path):
        os.remove(safe_sub_path)
        
    current_encoding.pop(user_id, None)
    
    if returncode != 0:
        error_text = "".join(error_lines[-15:])
        raise Exception(f"FFmpeg Error:\n{error_text}")
    if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
        raise Exception("Output file missing or too small")
    return True

# ================= HANDLERS =================

@app.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply(f"<b>🔥 Hardsub bot is Online!</b>\n\nUse /hsub to add subtitle into video\nUse /cancel to stop your task\n\n{edit}")

@app.on_message(filters.command("delete"))
async def delete_all(client, message: Message):
    if not is_owner(message): return
    global task_queue, in_queue, users_data
    task_queue.clear()
    in_queue.clear()
    users_data.clear()
    await message.reply("🗑️ All data cleared.")

@app.on_message(filters.command("cancel"))
async def cancel_task(client, message: Message):
    if not is_authorized(message): return
    user_id = message.from_user.id
    removed = False
    
    for i, task in enumerate(task_queue):
        if task["user_id"] == user_id:
            del task_queue[i]
            removed = True
            break
            
    if user_id in current_encoding:
        proc = current_encoding[user_id]
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=3)
        except:
            proc.kill()
        current_encoding.pop(user_id, None)
        await message.reply("🛑 Task cancelled.")
        return
        
    if removed:
        in_queue.discard(user_id)
        await message.reply("✅ Task removed from queue.")
    else:
        await message.reply("❌ No active task found.")

@app.on_message(filters.command("hsub"))
async def hsub_cmd(client, message: Message):
    if not is_authorized(message): return
    replied = message.reply_to_message
    if not replied or not (replied.video or replied.document):
        return await message.reply("❌ Reply to a video file with /hsub")
    
    media = replied.video or replied.document
    users_data[message.from_user.id] = {
        "video": {"file_id": media.file_id, "file_name": media.file_name or "video.mp4"},
        "chat_id": message.chat.id,
        "state": "WAIT_SUB"
    }
    await message.reply("📄 Now send the Subtitle file (.srt / .ass)")

@app.on_message(filters.document | filters.video | filters.text)
async def handle_all_inputs(client, message: Message):
    if not is_authorized(message): return
    user_id = message.from_user.id
    if user_id not in users_data: return
    state = users_data[user_id].get("state")

    if state == "WAIT_SUB" and message.document:
        if message.document.file_name.lower().endswith((".srt", ".ass")):
            users_data[user_id]["subtitle"] = {"file_id": message.document.file_id, "file_name": message.document.file_name}
            users_data[user_id]["state"] = "WAIT_RENAME_CHOICE"
            btn = InlineKeyboardMarkup([[
                InlineKeyboardButton("Rename", callback_data="rn_yes"),
                InlineKeyboardButton("Skip", callback_data="rn_skip")
            ]])
            await message.reply("Do you want to rename the output file?", reply_markup=btn)
        return

    if state == "WAIT_RENAME_TEXT" and message.text:
        new_name = message.text.strip()
        base = os.path.splitext(new_name)[0]
        users_data[user_id]["video"]["file_name"] = base + ".mp4"
        await add_to_queue(user_id, message)
        return

@app.on_callback_query(filters.regex("^rn_"))
async def callback_rename(client, query: CallbackQuery):
    user_id = query.from_user.id
    if user_id not in users_data:
        return await query.answer("Not Yours!", show_alert=True)

    if query.data == "rn_yes":
        users_data[user_id]["state"] = "WAIT_RENAME_TEXT"
        await query.message.edit("📝 Send new name for the video (without extension)")
    else:
        original = users_data[user_id]["video"]["file_name"]
        base = os.path.splitext(original)[0]
        users_data[user_id]["video"]["file_name"] = base + ".mp4"
        await query.message.edit("🚀 Processing with original name...")
        await add_to_queue(user_id, query.message)

async def add_to_queue(user_id, message):
    data = users_data.pop(user_id)
    task_queue.append({
        "user_id": user_id,
        "video": data["video"],
        "subtitle": data["subtitle"],
        "chat_id": data["chat_id"]
    })
    in_queue.add(user_id)
    await message.reply(f"✅ Added to Queue. Position: {len(task_queue)}")

# ================= CORE ENCODER =================

async def worker():
    while True:
        if not task_queue:
            await asyncio.sleep(5)
            continue
        
        task = task_queue.popleft()
        uid = task["user_id"]
        v_info = task["video"]
        s_info = task["subtitle"]
        original_chat = task["chat_id"]
        
        status = await app.send_message(original_chat, "⏳ Starting Process...")
        channel_log = None
        v_path = s_path = out_path = None
        
        try:
            if DEST_CHANNEL:
                channel_log = await app.send_message(DEST_CHANNEL, f"<b>🔄 Starting:</b> {v_info['file_name']}")

            await safe_edit(status, "📥 Downloading video...")
            v_path = await download_with_verification(app, v_info["file_id"], status, "Downloading video")

            # Max 400 MB to prevent Render Server Crash (512MB RAM Limit)
            if os.path.getsize(v_path) > 400 * 1024 * 1024:
                await safe_edit(status, "❌ Video size > 400MB. Not allowed on Render free tier.")
                continue

            await safe_edit(status, "📥 Downloading subtitle...")
            s_path = await download_with_verification(app, s_info["file_id"], status, "Downloading subtitle")

            dur = await get_duration(v_path)
            out_path = os.path.join(os.getcwd(), v_info["file_name"])
            
            await safe_edit(status, "🔥 Encoding Video...")
            success = await encode_with_progress(v_path, s_path, out_path, dur, status, uid)

            if success:
                await safe_edit(status, "📤 Uploading Output...")
                upload_target = DEST_CHANNEL if DEST_CHANNEL else original_chat
                await app.send_document(
                    chat_id=upload_target,
                    document=out_path,
                    caption=f"🎥 **{v_info['file_name']}**\n{edit}"
                )
                await safe_edit(status, f"✅ Successfully Completed!\n\nSent to {DEST_CHANNEL}")
                if channel_log:
                    await channel_log.delete()
            else:
                await safe_edit(status, "❌ Encoding Failed.")
                
        except Exception as e:
            await app.send_message(original_chat, f"❌ Error:\n`{str(e)}`")
        finally:
            # Memory Cleanup - Very important for Render!
            in_queue.discard(uid)
            for f in [v_path, s_path, out_path]:
                if f and os.path.exists(f):
                    try: os.remove(f)
                    except: pass
            gc.collect() # Force free RAM

# ================= RENDER KEEP ALIVE =================

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Running")
    def log_message(self, format, *args):
        pass # Disable logging to save console space

def run_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    server.serve_forever()

# ================= MAIN =================

async def main():
    if edit != "Maintanence by: @Sub_and_hardsub":
        print("credit hataya isiliye nahi chala. Sahi karo wo pehele.")
        return
    global main_loop
    main_loop = asyncio.get_event_loop()
    await app.start()
    print("Bot is started successfully!")
    asyncio.create_task(worker())
    await idle()

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
