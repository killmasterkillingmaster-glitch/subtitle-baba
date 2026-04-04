import os
import time
import json
import asyncio
import threading
import tempfile
from collections import deque
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified, MessageIdInvalid
from http.server import HTTPServer, BaseHTTPRequestHandler

================= CONFIG =================

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEST_CHANNEL = "@Sub_and_hardsub"
PORT = 10000

OWNER_ID = 5351848105
ALLOWED_USERS = [5344078567]
ALLOWED_GROUPS = [-1003899919015]

app = Client("EncoderBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

================= GLOBAL =================

users_data = {}
task_queue = deque()
in_queue = set()
current_encoding = {}

================= UTILS =================

def is_authorized(message: Message):
if not message.from_user:
return False
u_id = message.from_user.id
if message.text and message.text.startswith("/start"):
return True
return u_id == OWNER_ID or u_id in ALLOWED_USERS or message.chat.id in ALLOWED_GROUPS

def is_owner(message: Message):
return message.from_user and message.from_user.id == OWNER_ID

async def safe_edit(message: Message, text: str):
try:
await message.edit(text)
except:
pass

def format_progress_bar(percent, width=10):
filled = int(percent * width / 100)
return "█" * filled + "░" * (width - filled)

async def get_duration(file):
try:
cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", file]
proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE)
stdout, _ = await proc.communicate()
return float(json.loads(stdout.decode())["format"]["duration"])
except:
return 0

async def download_with_verification(client, file_id):
path = await client.download_media(file_id)
if not path or not os.path.exists(path):
raise Exception("Download failed")
return path

================= ENCODER =================

async def encode_with_progress(video_path, subtitle_path, output_path, duration, status, uid):
sub = subtitle_path.replace("\", "\\").replace("'", "\'")

cmd = [  
    "ffmpeg", "-i", video_path,  
    "-vf", f"subtitles='{sub}'",  
    "-c:v", "libx264",  
    "-preset", "ultrafast",  
    "-crf", "24",  
    "-c:a", "copy",  
    "-progress", "pipe:1",  
    "-y", output_path  
]  

process = await asyncio.create_subprocess_exec(  
    *cmd,  
    stdout=asyncio.subprocess.PIPE,  
    stderr=asyncio.subprocess.PIPE  
)  

current_encoding[uid] = process  

last_update = 0  
progress = {}  

while True:  
    line = await process.stdout.readline()  
    if not line:  
        break  

    line = line.decode().strip()  

    if "=" in line:  
        k, v = line.split("=", 1)  
        progress[k] = v  

    if "out_time_ms" in progress:  
        try:  
            ms = int(progress["out_time_ms"])  
            sec = ms / 1_000_000  
            percent = (sec / duration) * 100 if duration else 0  

            now = time.time()  
            if now - last_update > 5:  
                bar = format_progress_bar(percent)  
                await safe_edit(status, f"🔥 Encoding...\n`{bar}` {percent:.1f}%")  
                last_update = now  
        except:  
            pass  

rc = await process.wait()  
current_encoding.pop(uid, None)  

if rc != 0:  
    raise Exception("FFmpeg failed")  

return True

================= COMMANDS =================

@app.on_message(filters.command("start"))
async def start(_, m: Message):
await m.reply("🔥 Hardsub Bot Online!\nUse /hsub")

@app.on_message(filters.command("cancel"))
async def cancel(_, m: Message):
uid = m.from_user.id
if uid in current_encoding:
current_encoding[uid].kill()
await m.reply("🛑 Cancelled")

@app.on_message(filters.command("hsub"))
async def hsub(_, m: Message):
if not is_authorized(m):
return

r = m.reply_to_message  
if not r or not (r.video or r.document):  
    return await m.reply("Reply to video")  

media = r.video or r.document  

users_data[m.from_user.id] = {  
    "video": {"file_id": media.file_id, "name": media.file_name or "video.mp4"},  
    "chat": m.chat.id,  
    "state": "WAIT_SUB"  
}  

await m.reply("📄 Send subtitle")

@app.on_message(filters.document)
async def sub_handler(_, m: Message):
uid = m.from_user.id
if uid not in users_data:
return

if not m.document.file_name.endswith((".srt", ".ass")):  
    return  

users_data[uid]["sub"] = m.document.file_id  

task_queue.append({  
    "user_id": uid,  
    "video": users_data[uid]["video"],  
    "sub": users_data[uid]["sub"],  
    "chat": users_data[uid]["chat"]  
})  

users_data.pop(uid)  
await m.reply("✅ Added to queue")

================= WORKER =================

async def worker():
while True:
if not task_queue:
await asyncio.sleep(5)
continue

t = task_queue.popleft()  
    uid = t["user_id"]  

    try:  
        v = await download_with_verification(app, t["video"]["file_id"])  
        s = await download_with_verification(app, t["sub"])  
        out = t["video"]["name"]  

        status = await app.send_message(t["chat"], "⏳ Starting...")  

        dur = await get_duration(v)  

        await encode_with_progress(v, s, out, dur, status, uid)  

        await app.send_video(  
            chat_id=DEST_CHANNEL,  
            video=out,  
            caption=out,  
            supports_streaming=True  
        )  

        await safe_edit(status, "✅ Done")  

    except Exception as e:  
        await app.send_message(t["chat"], f"❌ {e}")  

    finally:  
        for f in [locals().get(x) for x in ["v", "s", "out"]]:  
            if f and os.path.exists(f):  
                os.remove(f)

================= KEEP ALIVE =================

class Handler(BaseHTTPRequestHandler):
def do_GET(self):
self.send_response(200)
self.end_headers()
self.wfile.write(b"Running")

def run_server():
HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

================= MAIN =================

async def main():
await app.start()
print("Bot started")
asyncio.create_task(worker())
await idle()

if name == "main":
threading.Thread(target=run_server, daemon=True).start()
asyncio.get_event_loop().run_until_complete(main())
