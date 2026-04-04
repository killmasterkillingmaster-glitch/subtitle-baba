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

API_ID = int(os.getenv("API_ID", "1234567")) 
API_HASH = os.getenv("API_HASH", "your_api_hash_here")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token_here")

DEST_CHANNEL = "@Sub_and_hardsub"   
PORT = int(os.getenv("PORT", 10000)) 

OWNER_ID = 5351848105
ALLOWED_USERS = [5344078567]
ALLOWED_GROUPS =[-1003899919015]

app = Client("EncoderBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Global Variables
users_data = {}
task_queue = deque()
in_queue = set()
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
        cmd =["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", file]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        data = json.loads(stdout.decode())
        return float(data.get("format", {}).get("duration", 0))
    except:
        return 0

def format_progress_bar(percent, width=12):
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

# FIX 1: Extension preserve karna aur Subtitle par ffprobe bypass karna
async def download_with_verification(client, file_id, file_name, status_msg, is_video=True):
    temp_dir = tempfile.gettempdir()
    ext = os.path.splitext(file_name)[1].lower()
    if not ext and not is_video: ext = ".srt" # Default sub extension
    
    base_name = f"temp_{int(time.time())}_{str(file_id)[:8]}"

    for attempt in range(3):  
        temp_file = os.path.join(temp_dir, f"{base_name}_{attempt}{ext}")  
        try:  
            if os.path.exists(temp_file):  
                os.remove(temp_file)  
                  
            path = await client.download_media(file_id, file_name=temp_file)  
            if path and os.path.exists(path) and os.path.getsize(path) > 0:  
                # Sirf video file ka verification karo, subtitle ka nahi
                if is_video:
                    cmd =["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path]  
                    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)  
                    await proc.communicate()  
                    if proc.returncode != 0:  
                        raise Exception("Video File corrupt")  
                return path  
        except Exception as e:  
            if attempt < 2:  
                await asyncio.sleep(3)  
                continue  
            raise Exception(f"Download failed: {str(e)}")  
    raise Exception("Download failed after 3 attempts")


async def encode_with_progress(video_path, subtitle_path, output_path, total_duration, status_msg, user_id):
    # FIX 2: Path escaping se bachne ke liye subtitle ko current folder me safe name se copy karna
    sub_ext = os.path.splitext(subtitle_path)[1].lower()
    safe_sub_name = f"sub_{user_id}{sub_ext}"
    safe_sub_path = os.path.join(os.getcwd(), safe_sub_name)
    shutil.copy2(subtitle_path, safe_sub_path)

    # FIX 3: Scale filter add kiya (odd resolution par x264 crash nahi hoga)
    filter_complex = f"scale=trunc(iw/2)*2:trunc(ih/2)*2,subtitles='{safe_sub_name}'"

    # Fast & Stable Render Setup (threads=1 for 512MB RAM absolute safety)
    cmd =[  
        "ffmpeg", "-hide_banner", "-i", video_path,  
        "-vf", filter_complex,  
        "-c:v", "libx264",  
        "-preset", "ultrafast",  
        "-crf", "28", # Slightly higher CRF to save RAM and output size
        "-threads", "1", # 1 thread ensures Render doesn't OOM kill the bot
        "-max_muxing_queue_size", "4096",
        "-c:a", "copy",  
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
    error_lines =[]

    async def read_stdout():  
        nonlocal last_update  
        while True:  
            line = await process.stdout.readline()  
            if not line: break  
            line_str = line.decode(errors="ignore").strip()  
            if "=" in line_str:  
                key, val = line_str.split("=", 1)  
                progress_data[key] = val  
                
                # FIX 4: Prevent "N/A" crash
                if key == "out_time_ms" and val != "N/A":  
                    try:  
                        ms = int(val)  
                        percent = ((ms / 1_000_000.0) / total_duration) * 100 if total_duration > 0 else 0  
                        now = time.time()  
                          
                        if now - last_update > 6 or percent >= 100:  
                            bar = format_progress_bar(percent)  
                            await safe_edit(status_msg, f"🔥 **Encoding Process:**\n\n`{bar}` **{percent:.1f}%**")  
                            last_update = now  
                    except Exception:  
                        pass  

    async def read_stderr():  
        while True:  
            line = await process.stderr.readline()  
            if not line: break  
            error_lines.append(line.decode(errors="ignore"))

    await asyncio.gather(read_stdout(), read_stderr())  

    returncode = await process.wait()  
    
    # Cleanup safe subtitle
    if os.path.exists(safe_sub_path):
        os.remove(safe_sub_path)
        
    current_encoding.pop(user_id, None)  
      
    if returncode != 0:  
        err = "".join(error_lines[-10:])
        raise Exception(f"FFmpeg failed with code {returncode}\n{err}")  
    if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:  
        raise Exception("Output file is missing or corrupted.")  
    return True

# ================= HANDLERS =================

@app.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply(f"<b>🔥 Hardsub bot is Online & Fast!</b>\n\nUse /hsub to add subtitle into video\nUse /cancel to stop your current task\nUse /delete to clear all tasks (owner only)\n\n{edit}")

@app.on_message(filters.command("delete"))
async def delete_all(client, message: Message):
    if not is_owner(message):
        return await message.reply("❌ Only the bot owner can use this command.")
    global task_queue, in_queue, users_data
    task_queue.clear()
    in_queue.clear()
    users_data.clear()
    await message.reply("🗑️ All data and queues cleared.")

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
            await asyncio.wait_for(proc.wait(), timeout=5)  
        except:  
            proc.kill()  
        current_encoding.pop(user_id, None)  
        return await message.reply("🛑 Your active encoding task has been cancelled.")  
      
    if removed:  
        in_queue.discard(user_id)  
        await message.reply("✅ Your task has been removed from the queue.")  
    else:  
        await message.reply("❌ No active task found for you.")

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
        if not new_name.lower().endswith(".mp4"):
            new_name += ".mp4"
        users_data[user_id]["video"]["file_name"] = new_name  
        await add_to_queue(user_id, message)  
        return

@app.on_callback_query(filters.regex("^rn_"))
async def callback_rename(client, query: CallbackQuery):
    user_id = query.from_user.id
    if user_id not in users_data:
        return await query.answer("Session expired! Start again.", show_alert=True)

    if query.data == "rn_yes":  
        users_data[user_id]["state"] = "WAIT_RENAME_TEXT"  
        await query.message.edit("📝 Send new name for the video (without extension)\n\nEx: `[S01 - Ep 02] Oshi no Ko - HD`")  
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
    await message.reply(f"✅ Added to Queue.\n🔢 Your Position: {len(task_queue)}")

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
                channel_log = await app.send_message(DEST_CHANNEL, f"<b>🔄 Encoding Started:</b> {v_info['file_name']}")  

            await safe_edit(status, "📥 Downloading Video... (Fast Mode)")  
            # Passed file_name and is_video=True
            v_path = await download_with_verification(app, v_info["file_id"], v_info["file_name"], status, is_video=True)  

            # Render 512MB RAM Limit ke hisaab se 600MB tak allow karte hai safe side ke liye
            if os.path.getsize(v_path) > 600 * 1024 * 1024:  
                await safe_edit(status, "❌ Video is larger than 600MB. Free server limit exceeded.")  
                continue 

            await safe_edit(status, "📥 Downloading Subtitle...")  
            # Passed file_name and is_video=False (Isse sub pe ffprobe check bypass hoga)
            s_path = await download_with_verification(app, s_info["file_id"], s_info["file_name"], status, is_video=False)  

            dur = await get_duration(v_path)  
            
            # Temporary output must have .mp4 extension
            out_path = os.path.join(tempfile.gettempdir(), f"out_{int(time.time())}.mp4")

            await safe_edit(status, "🔥 Encoding started...")  
            success = await encode_with_progress(v_path, s_path, out_path, dur, status, uid)  

            if success:  
                await safe_edit(status, "📤 Uploading File...")  
                upload_target = DEST_CHANNEL if DEST_CHANNEL else original_chat  
                  
                await app.send_document(  
                    chat_id=upload_target,  
                    document=out_path,  
                    file_name=v_info["file_name"],
                    caption=f"**{v_info['file_name']}**\n\n{edit}"  
                )  
                  
                await safe_edit(status, f"✅ Successfully Completed!\n\n📤 File sent to {DEST_CHANNEL}")  
                if channel_log:  
                    await channel_log.delete()  
            else:  
                await safe_edit(status, "❌ Encoding Failed.")  
                  
        except Exception as e:  
            await app.send_message(original_chat, f"❌ Error occurred: `{str(e)}`")  
        finally:  
            in_queue.discard(uid)  
            # Force Memory cleanup
            for f in[v_path, s_path, out_path]:  
                if f and os.path.exists(f):  
                    try: os.remove(f)  
                    except: pass
            gc.collect() # Har encode ke baad RAM free karna zaroori hai

# ================= RENDER KEEP ALIVE =================

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is Running & Healthy!")
    def log_message(self, format, *args):
        pass

def run_health_server():
    try:
        server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
        print(f"Health server running on port {PORT}")
        server.serve_forever()
    except Exception as e:
        pass

# ================= MAIN =================

async def main():
    if edit != "Maintanence by: @Sub_and_hardsub":
        return
    global main_loop
    main_loop = asyncio.get_event_loop()
    await app.start()
    print("Bot is Started & Fixed for Render!")
    asyncio.create_task(worker())
    await idle()

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
