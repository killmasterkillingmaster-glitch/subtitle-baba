import os
import asyncio
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from flask import Flask
from threading import Thread

# ---------------- CONFIG ----------------
API_ID = int(os.environ.get("API_ID", "12345"))
API_HASH = os.environ.get("API_HASH", "abcdef")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7123:AAH...")

ADMINS = [5351848105, ]  # Allowed users
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "-100123"))
DB_CHANNEL = int(os.environ.get("DB_CHANNEL", "-100456"))

app = Client("ASI_CREATOR", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ---------------- MEMORY ----------------
USER_STATE = {}
CONFIG = {"api": None, "url": None, "fsub": [], "admin_channels": []}

# ---------------- WEB SERVER ----------------
web_app = Flask(__name__)

@web_app.route("/")
def home(): return "Bot is Online ✅"

def run_web():
    web_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# ---------------- HELPERS ----------------
async def load_config():
    async for m in app.search_messages(LOG_CHANNEL, query="SETTING:"):
        if "SHORTENER:" in m.text:
            data = m.text.split("SHORTENER:")[1].split("|")
            CONFIG["api"], CONFIG["url"] = data[0], data[1]
        elif "FSUB_LIST:" in m.text:
            ids = m.text.split("FSUB_LIST:")[1].split(",")
            CONFIG["fsub"] = [int(i) for i in ids if i]
        elif "ADMIN_CH:" in m.text:
            ids = m.text.split("ADMIN_CH:")[1].split(",")
            CONFIG["admin_channels"] = [int(i) for i in ids if i]

async def update_config(key, value):
    async for m in app.search_messages(LOG_CHANNEL, query=f"SETTING:{key}"):
        await m.delete()
    await app.send_message(LOG_CHANNEL, f"SETTING:{key}:{value}")

async def get_short(url):
    if not CONFIG["api"] or not CONFIG["url"]: return url
    try:
        async with aiohttp.ClientSession() as session:
            params = {'api': CONFIG['api'], 'url': url}
            async with session.get(CONFIG['url'], params=params) as r:
                res = await r.json()
                return res.get("shortened_url") or url
    except: return url

# ---------------- AUTO TRACK ADMIN CHANNEL ----------------
@app.on_chat_member_updated()
async def track_ch(c, cb):
    me = await c.get_me()
    if cb.new_chat_member and cb.new_chat_member.user.id == me.id:
        if cb.new_chat_member.status in ["administrator", "creator"]:
            if cb.chat.id not in CONFIG["admin_channels"]:
                CONFIG["admin_channels"].append(cb.chat.id)
                await update_config("ADMIN_CH", ",".join(str(i) for i in CONFIG["admin_channels"]))
                await c.send_message(LOG_CHANNEL, f"CH_ADDED:{cb.chat.id}|{cb.chat.title}")

# ---------------- SETTINGS / DASHBOARD ----------------
@app.on_message(filters.command("settings") & filters.private)
async def settings(c, m):
    if m.from_user.id not in ADMINS: return
    await m.reply("⚙️ Dashboard", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Shortener", callback_data="set_short")],
        [InlineKeyboardButton("📢 Force Subscribe", callback_data="set_fsub")],
        [InlineKeyboardButton("🛠 Manage Admin Channels", callback_data="admin_ch")],
    ]))

# ---------------- ADMIN CHANNEL MANAGEMENT ----------------
@app.on_callback_query()
async def handle_admin_channel(c, q: CallbackQuery):
    u_id = q.from_user.id
    data = q.data
    if u_id not in ADMINS: return

    if data == "admin_ch":
        # Show admin channels
        buttons = [[InlineKeyboardButton(f"{i}", callback_data=f"remove_ch_{i}") ] for i in CONFIG["admin_channels"]]
        buttons.append([InlineKeyboardButton("✅ Done", callback_data="admin_done")])
        await q.edit_message_text("Select channel to remove:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("remove_ch_"):
        cid = int(data.split("_")[2])
        if cid in CONFIG["admin_channels"]:
            CONFIG["admin_channels"].remove(cid)
            await update_config("ADMIN_CH", ",".join(str(i) for i in CONFIG["admin_channels"]))
        await handle_admin_channel(c, q)  # Refresh list

    elif data == "admin_done":
        await q.edit_message_text("✅ Done managing admin channels.")

# ---------------- POST GENERATION FLOW ----------------
@app.on_message(filters.private & (filters.photo | filters.video | filters.document) & filters.incoming)
async def start_post(c, m):
    if m.from_user.id not in ADMINS: return
    USER_STATE[m.from_user.id] = {'post': m, 'selected_channels': []}
    await m.reply("✅ Post Received! Select Type:", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Single Link", callback_data="type_single")],
        [InlineKeyboardButton("📦 Batch Link", callback_data="type_batch")]
    ]))

# ---------------- CALLBACK HANDLER ----------------
@app.on_callback_query()
async def handle_cb(c, q: CallbackQuery):
    u_id = q.from_user.id
    data = q.data
    st = USER_STATE.get(u_id)
    if not st: return

    # ---------------- TYPE SELECTION ----------------
    if data == "type_single":
        st.update({'mode':'single','step':'wait_file'})
        await q.edit_message_text("Forward Episode File from DB Channel:")

    elif data == "type_batch":
        st.update({'mode':'batch','step':'wait_start'})
        await q.edit_message_text("Forward START Episode:")

    # ---------------- CHANNEL SELECTION ----------------
    elif data == "show_ch_list":
        btns = []
        for cid in CONFIG["admin_channels"]:
            tick = "✅" if cid in st['selected_channels'] else "❌"
            chat = await c.get_chat(cid)
            btns.append([InlineKeyboardButton(f"{chat.title} {tick}", callback_data=f"toggle_post_{cid}")])
        btns.append([InlineKeyboardButton("🚀 Confirm & Send", callback_data="final_broadcast")])
        await q.edit_message_text("Select Channels:", reply_markup=InlineKeyboardMarkup(btns))

    elif data.startswith("toggle_post_"):
        cid = int(data.split("_")[2])
        if cid in st['selected_channels']: st['selected_channels'].remove(cid)
        else: st['selected_channels'].append(cid)
        await handle_cb(c, q.copy(data="show_ch_list"))

    elif data == "final_broadcast":
        await q.edit_message_text("Sending...")
        for cid in st['selected_channels']:
            try: await st['post'].copy(cid, reply_markup=st.get('markup'))
            except: pass
        await q.message.reply("✅ Successfully Posted!")
        del USER_STATE[u_id]

# ---------------- POST STEPS ----------------
@app.on_message(filters.private & filters.incoming)
async def steps(c, m):
    u_id = m.from_user.id
    st = USER_STATE.get(u_id)
    if not st: return

    # ---------------- SINGLE ----------------
    if st.get('step') == 'wait_file':
        if not m.forward_from_message_id:
            return await m.reply("❌ Forward message from DB channel!")
        st.update({'f_id': m.forward_from_message_id, 'step':'wait_num'})
        return await m.reply("Enter Episode Number (e.g. 06):")

    if st.get('step') == 'wait_num':
        ep_no = m.text
        log = await c.send_message(LOG_CHANNEL, "...")
        token = f"t_{log.id}"
        await log.edit(f"TOKEN:{token}|FILE:{st['f_id']}")
        long_url = f"https://t.me/{(await c.get_me()).username}?start={token}"
        short_url = await get_short(long_url)
        st['markup'] = InlineKeyboardMarkup([[InlineKeyboardButton(f"Episode {ep_no}", url=short_url)]])
        await st['post'].copy(u_id, reply_markup=st['markup'])
        await m.reply("Post Ready!", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Select Channels", callback_data="show_ch_list")]
        ]))
        st['step'] = 'ready'

    # ---------------- BATCH ----------------
    if st.get('step') == 'wait_start':
        st.update({'s_id': m.forward_from_message_id, 'step':'wait_end'})
        return await m.reply("Forward END Episode:")

    if st.get('step') == 'wait_end':
        st.update({'e_id': m.forward_from_message_id, 'step':'wait_num'})
        return await m.reply("Enter Range (e.g. 01-12):")

# ---------------- USER START ----------------
@app.on_message(filters.command("start") & filters.private)
async def start(c, m):
    if len(m.command) < 2: return await m.reply("Hi!")
    token = m.command[1]
    try:
        msg_id = int(token.split("_")[1])
        log = await c.get_messages(LOG_CHANNEL, msg_id)
        data = log.text.split("|")[1].strip()
        if "FILE:" in data:
            f = await c.get_messages(DB_CHANNEL, int(data.split(":")[1]))
            await f.copy(m.chat.id)
        elif "BATCH:" in data:
            _, s, e = data.split(":")
            for i in range(int(s), int(e)+1):
                f = await c.get_messages(DB_CHANNEL, i)
                await f.copy(m.chat.id)
                await asyncio.sleep(1)
    except: pass

# ---------------- RUN BOT ----------------
if __name__ == "__main__":
    Thread(target=run_web).start()
    app.start()
    asyncio.get_event_loop().run_until_complete(load_config())
    print("Bot is Live ✅")
    app.run()
