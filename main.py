import os
import asyncio
import aiohttp
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from flask import Flask
from threading import Thread

# ---------------- LOGGING ----------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- CONFIG ----------------
API_ID = int(os.environ.get("API_ID", "12345"))
API_HASH = os.environ.get("API_HASH", "abcdef")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

ADMINS = [5351848105]  # Your Telegram ID
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "-100123"))
DB_CHANNEL = int(os.environ.get("DB_CHANNEL", "-100456"))

app = Client("ASI_CREATOR", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

USER_STATE = {}
CONFIG = {"api": None, "url": None, "fsub": [], "admin_channels": []}

# ---------------- WEB SERVER ----------------
web_app = Flask(__name__)
@web_app.route("/")
def home(): return "Bot is Online ✅"

def run_web():
    web_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# ---------------- HELPERS ----------------
async def load_config():
    try:
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
        logger.info("Config Loaded Successfully")
    except Exception as e: 
        logger.error(f"Load Config Error: {e}")

async def update_config(key, value):
    try:
        async for m in app.search_messages(LOG_CHANNEL, query=f"SETTING:{key}"):
            await m.delete()
        await app.send_message(LOG_CHANNEL, f"SETTING:{key}:{value}")
    except Exception as e: 
        logger.error(f"Update Config Error: {e}")

async def get_short(url):
    if not CONFIG["api"] or not CONFIG["url"]: return url
    try:
        async with aiohttp.ClientSession() as session:
            params = {'api': CONFIG['api'], 'url': url}
            async with session.get(CONFIG['url'], params=params) as r:
                res = await r.json()
                return res.get("shortened_url") or res.get("short_url") or url
    except Exception as e:
        logger.error(f"Shortener Error: {e}")
        return url

# ---------------- AUTO TRACK CHANNELS ----------------
@app.on_chat_member_updated()
async def track_ch(c, cb):
    try:
        me = await c.get_me()
        if cb.new_chat_member and cb.new_chat_member.user.id == me.id:
            if cb.new_chat_member.status in ["administrator", "creator"]:
                if cb.chat.id not in CONFIG["admin_channels"]:
                    CONFIG["admin_channels"].append(cb.chat.id)
                    await update_config("ADMIN_CH", ",".join(str(i) for i in CONFIG["admin_channels"]))
                    logger.info(f"Added admin channel: {cb.chat.id}")
    except Exception as e: 
        logger.error(f"Track Error: {e}")

# ---------------- CALLBACK HANDLER ----------------
@app.on_callback_query()
async def cb_handler(c, q: CallbackQuery):
    u_id = q.from_user.id
    data = q.data
    if u_id not in ADMINS: return

    st = USER_STATE.get(u_id)
    if st is None: USER_STATE[u_id] = st = {}

    # ---------------- SETTINGS ----------------
    if data == "set_short":
        st['step'] = 'wait_short_url'
        await q.edit_message_text("Send your Shortener Dashboard API URL:")
        return

    elif data == "set_fsub":
        btns = []
        for cid in CONFIG["admin_channels"]:
            tick = "✅" if cid in CONFIG["fsub"] else "❌"
            try:
                ch = await c.get_chat(cid)
                btns.append([InlineKeyboardButton(f"{ch.title} {tick}", callback_data=f"tfsub_{cid}")])
            except: continue
        btns.append([InlineKeyboardButton("💾 Save", callback_data="save_fsub")])
        await q.edit_message_text("Select Force Sub Channels:", reply_markup=InlineKeyboardMarkup(btns))
        return

    elif data.startswith("tfsub_"):
        cid = int(data.split("_")[1])
        if cid in CONFIG["fsub"]: CONFIG["fsub"].remove(cid)
        else: CONFIG["fsub"].append(cid)
        await cb_handler(c, q.copy(data="set_fsub"))
        return

    elif data == "save_fsub":
        await update_config("FSUB_LIST", ",".join(str(i) for i in CONFIG["fsub"]))
        await q.answer("Force Sub Saved!")
        return

    # ---------------- POST PROCESS ----------------
    if st.get('selected_channels') is None:
        st['selected_channels'] = []

    if data == "type_single":
        st.update({'mode': 'single', 'step': 'wait_file'})
        await q.edit_message_text("Forward Episode File from DB Channel:")
        return

    elif data == "type_batch":
        st.update({'mode': 'batch', 'step': 'wait_start'})
        await q.edit_message_text("Forward START Episode:")
        return

    elif data == "show_ch_list":
        btns = []
        for cid in CONFIG["admin_channels"]:
            tick = "✅" if cid in st['selected_channels'] else "❌"
            try:
                ch = await c.get_chat(cid)
                btns.append([InlineKeyboardButton(f"{ch.title} {tick}", callback_data=f"tpost_{cid}")])
            except: continue
        btns.append([InlineKeyboardButton("🚀 Send Now", callback_data="final_send")])
        await q.edit_message_text("Select Channels to Post:", reply_markup=InlineKeyboardMarkup(btns))
        return

    elif data.startswith("tpost_"):
        cid = int(data.split("_")[1])
        if cid in st['selected_channels']: st['selected_channels'].remove(cid)
        else: st['selected_channels'].append(cid)
        await cb_handler(c, q.copy(data="show_ch_list"))
        return

    elif data == "final_send":
        await q.edit_message_text("Sending...")
        for cid in st.get('selected_channels', []):
            try: await st['post'].copy(cid, reply_markup=st.get('markup'))
            except Exception as e: logger.error(e)
        await q.message.reply("✅ Successfully Posted!")
        USER_STATE.pop(u_id, None)
        return

# ---------------- STEPS HANDLER ----------------
@app.on_message(filters.private & ~filters.command(["start", "settings"]))
async def handle_steps(c, m):
    u_id = m.from_user.id
    if u_id not in ADMINS: return
    st = USER_STATE.get(u_id)
    if st is None: USER_STATE[u_id] = st = {}

    # Shortener setup
    if st.get('step') == 'wait_short_url':
        st['url'] = m.text
        st['step'] = 'wait_short_api'
        return await m.reply("Send API Token:")

    if st.get('step') == 'wait_short_api':
        CONFIG["api"], CONFIG["url"] = m.text, st['url']
        await update_config("SHORTENER", f"{m.text}|{st['url']}")
        await m.reply("✅ Shortener Configured!")
        USER_STATE.pop(u_id, None)
        return

    # Post Single
    if st.get('step') == 'wait_file':
        if not m.forward_from_chat: return await m.reply("❌ Forward from DB Channel!")
        st['f_id'] = m.forward_from_message_id
        st['step'] = 'wait_num'
        return await m.reply("Enter Episode Number (e.g. 06):")

    # Post Batch
    if st.get('step') == 'wait_start':
        st['s_id'] = m.forward_from_message_id
        st['step'] = 'wait_end'
        return await m.reply("Forward END Episode:")

    if st.get('step') == 'wait_end':
        st['e_id'] = m.forward_from_message_id
        st['step'] = 'wait_num'
        return await m.reply("Enter Range (e.g. 01-12):")

    if st.get('step') == 'wait_num':
        ep_no = m.text
        log = await c.send_message(LOG_CHANNEL, "Generating...")
        token = f"t_{log.id}"

        if st.get('mode') == 'single':
            await log.edit(f"SETTING:TOKEN|FILE:{st['f_id']}")
            btn_txt = f"Episode {ep_no}"
        else:
            await log.edit(f"SETTING:TOKEN|BATCH:{st['s_id']}:{st['e_id']}")
            btn_txt = f"Episodes {ep_no}"

        long_url = f"https://t.me/{(await c.get_me()).username}?start={token}"
        short_url = await get_short(long_url)
        st['markup'] = InlineKeyboardMarkup([[InlineKeyboardButton(btn_txt, url=short_url)]])
        st['post'] = st.get('post', m)
        await st['post'].copy(m.chat.id, reply_markup=st['markup'])
        await m.reply("✅ Ready!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 Select Channels", callback_data="show_ch_list")]]))
        st['step'] = 'ready'

# ---------------- COMMANDS ----------------
@app.on_message(filters.command("settings") & filters.private)
async def open_settings(c, m):
    if m.from_user.id not in ADMINS: return
    await m.reply("⚙️ Settings", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Shortener", callback_data="set_short"), InlineKeyboardButton("📢 Force Sub", callback_data="set_fsub")]
    ]))

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(c, m):
    if len(m.command) < 2: return await m.reply("Hi! Send me media to start.")

    # Force Sub Check
    for cid in CONFIG["fsub"]:
        try:
            await c.get_chat_member(cid, m.from_user.id)
        except:
            try:
                ch = await c.get_chat(cid)
                link = await ch.export_invite_link()
                return await m.reply("❌ Join first!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join", url=link)]]))
            except: continue

    token = m.command[1]
    try:
        msg_id = int(token.split("_")[1])
        log = await c.get_messages(LOG_CHANNEL, msg_id)
        data = log.text.split("|")[1]
        if "FILE:" in data:
            f = await c.get_messages(DB_CHANNEL, int(data.split(":")[1]))
            await f.copy(m.chat.id)
        elif "BATCH:" in data:
            _, s, e = data.split(":")
            for i in range(int(s), int(e)+1):
                f = await c.get_messages(DB_CHANNEL, i)
                await f.copy(m.chat.id)
                await asyncio.sleep(1)
    except: await m.reply("Expired!")

@app.on_message(filters.private & (filters.photo | filters.video | filters.document))
async def on_media(c, m):
    if m.from_user.id not in ADMINS: return
    USER_STATE[m.from_user.id] = {'post': m}
    await m.reply("✅ Media Received!", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Single", callback_data="type_single"), InlineKeyboardButton("📦 Batch", callback_data="type_batch")]
    ]))

# ---------------- BOOT ----------------
if __name__ == "__main__":
    Thread(target=run_web).start()
    app.start()
    asyncio.get_event_loop().run_until_complete(load_config())
    print("Bot is Alive! ✅")
    app.run()
