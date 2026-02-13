# -*- coding: utf-8 -*-
"""
Hinata Bot - Final (httpx, inline buttons, restored features)
- Uses httpx.AsyncClient to avoid building native wheels
- Restored keywords, forwarding, tracked users, broadcasts, group tracking
- Inline buttons to start Gemini / DeepSeek / Insta / FF flows
- Deployable to Render (use python 3.11 recommended)
"""
import asyncio
import logging
import json
import os
import time
from datetime import timedelta
import httpx
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ChatMemberHandler,
    CallbackQueryHandler,
)

# ================= Configuration =================
OWNER_ID = 7333244376
BOT_TOKEN_FILE = "token.txt"
BOT_NAME = "Hinata"
BOT_USERNAME = "@Hinata_00_bot"

INBOX_FORWARD_GROUP_ID = -1003113491147

# tracked users -> forward groups
TRACKED_USER1_ID = 7039869055
FORWARD_USER1_GROUP_ID = -1002768142169
TRACKED_USER2_ID = 7209584974
FORWARD_USER2_GROUP_ID = -1002536019847

# source/destination
SOURCE_GROUP_ID = -4767799138
DESTINATION_GROUP_ID = -1002510490386

KEYWORDS = [
    "shawon", "shawn", "sn", "@shawonxnone", "shwon", "shaun", "sahun", "sawon",
    "sawn", "nusu", "nusrat", "saun", "ilma", "izumi", "🎀꧁𖨆❦︎ 𝑰𝒁𝑼𝑴𝑰 𝑼𝒄𝒉𝒊𝒉𝒂 ❦︎𖨆꧂🎀"
]

LOG_FILE = "hinata.log"
MAX_LOG_SIZE = 200 * 1024  # 200 KB

# Old ChatGPT style API (kept for compatibility)
CHATGPT_API_URL = "https://addy-chatgpt-api.vercel.app/?text={prompt}"

# ================= NEW APIs (user-provided) =================
GEMINI3_API = "https://shawon-gemini-3-api.onrender.com/api/ask?prompt={}"
DEEPSEEK_API = "https://void-deep.hosters.club/api/?q={}"
INSTA_API = "https://instagram-api-ashy.vercel.app/api/ig-profile.php?username={}"
FF_API = "http://danger-info-alpha.vercel.app/accinfo?uid={}&key=DANGERxINFO"

# ================= Logging =================
def setup_logger():
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_SIZE:
        open(LOG_FILE, "w").close()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
    )
    return logging.getLogger("hinata")

logger = setup_logger()

# ================= Utilities =================
def read_file(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""

def read_json(path, default=None):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        logger.exception("Failed to read JSON: %s", path)
    return default if default is not None else []

def write_json(path, data):
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        logger.exception("Failed to write JSON: %s", path)

BOT_TOKEN = read_file(BOT_TOKEN_FILE)

start_time = time.time()
def get_uptime() -> str:
    elapsed = time.time() - start_time
    return str(timedelta(seconds=int(elapsed)))

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

# ================= Forward Helper =================
async def forward_or_copy(update: Update, context: ContextTypes.DEFAULT_TYPE, command_text: str = None):
    user = update.effective_user
    msg_type = "Command" if command_text else "Message"
    try:
        caption = f"📨 From: {user.full_name} (@{user.username})\nID: <code>{user.id}</code>\nType: {msg_type}"
        if command_text:
            caption += f"\nCommand: {command_text}"
        elif update.message and update.message.text:
            caption += f"\nMessage: {update.message.text}"

        await context.bot.send_message(chat_id=INBOX_FORWARD_GROUP_ID, text=caption, parse_mode="HTML")
        if update.message:
            await update.message.forward(chat_id=INBOX_FORWARD_GROUP_ID)
    except Exception as e:
        logger.warning(f"Failed to forward: {e}")
        try:
            if update.message:
                text = update.message.text or "<Media/Sticker/Other>"
                safe_text = f"📨 From: {user.full_name} (@{user.username})\nID: <code>{user.id}</code>\nType: {msg_type}\nContent: {text}"
                await context.bot.send_message(chat_id=INBOX_FORWARD_GROUP_ID, text=safe_text, parse_mode="HTML")
        except Exception as e2:
            logger.warning(f"Failed fallback forward: {e2}")

# ================= HTTP Helpers using httpx =================
async def fetch_json(client: httpx.AsyncClient, url: str):
    try:
        resp = await client.get(url, timeout=30.0)
        text = resp.text
        try:
            return json.loads(text)
        except Exception:
            return {"raw": text}
    except Exception as e:
        logger.exception("HTTP GET failed for %s", url)
        return {"error": str(e)}

async def fetch_text(client: httpx.AsyncClient, url: str):
    try:
        resp = await client.get(url, timeout=30.0)
        return resp.text
    except Exception as e:
        logger.exception("HTTP GET failed for %s", url)
        return f"Error: {e}"

async def fetch_chatgpt(client: httpx.AsyncClient, prompt: str):
    url = CHATGPT_API_URL.format(prompt=prompt.replace(" ", "+"))
    data = await fetch_json(client, url)
    if isinstance(data, dict):
        return data.get("reply") or data.get("response") or data.get("answer") or json.dumps(data)
    return str(data)

async def fetch_gemini3(client: httpx.AsyncClient, prompt: str):
    try:
        url = GEMINI3_API.format(prompt.replace(" ", "+"))
        data = await fetch_json(client, url)
        if isinstance(data, dict):
            return data.get("response") or data.get("reply") or data.get("answer") or json.dumps(data)
        return str(data)
    except Exception as e:
        logger.exception("Gemini3 fetch failed")
        return f"Error: {e}"

async def fetch_deepseek(client: httpx.AsyncClient, prompt: str):
    try:
        url = DEEPSEEK_API.format(prompt.replace(" ", "+"))
        text = await fetch_text(client, url)
        return text
    except Exception as e:
        logger.exception("DeepSeek fetch failed")
        return f"Error: {e}"

# ================= Broadcast Helpers =================
def update_stats(sent_users=0, failed_users=0, sent_groups=0, failed_groups=0):
    stats = read_json("stats.json", {"sent_users":0,"failed_users":0,"sent_groups":0,"failed_groups":0})
    stats["sent_users"] += sent_users
    stats["failed_users"] += failed_users
    stats["sent_groups"] += sent_groups
    stats["failed_groups"] += failed_groups
    write_json("stats.json", stats)

# ================= Commands =================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_or_copy(update, context, "/start")
    user = update.effective_user
    users = read_json("users.json", [])
    if user.id not in users:
        users.append(user.id)
        write_json("users.json", users)

    msg = (f"👤 <b>New User Started Bot</b>\n"
           f"Name: {user.full_name}\nUsername: @{user.username}\nID: <code>{user.id}</code>")
    try:
        await context.bot.send_message(chat_id=OWNER_ID, text=msg, parse_mode="HTML")
    except Exception:
        pass

    buttons = [
        [InlineKeyboardButton("🧠 Gemini 3", callback_data="btn_gemini"),
         InlineKeyboardButton("🔥 DeepSeek", callback_data="btn_deepseek")],
        [InlineKeyboardButton("📸 Insta Info", callback_data="btn_insta"),
         InlineKeyboardButton("🎮 FF Player", callback_data="btn_ff")],
        [InlineKeyboardButton("🏓 Ping", callback_data="btn_ping"),
         InlineKeyboardButton("❓ Help", callback_data="btn_help")]
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    await update.message.reply_text(
        f"✨ *Welcome to {BOT_NAME}*\n\n"
        "Use the buttons below or commands:\n"
        "• /gemini <prompt>\n"
        "• /deepseek <prompt>\n"
        "• /insta (or press button)\n"
        "• /ff (or press button)\n"
        "• /ping\n\n"
        "Tip: press a button and then send the prompt/username/uid as the next message ✅",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_or_copy(update, context, "/ping")
    start_ping = time.time()
    msg = await update.message.reply_text("🏓 Pinging...")
    ping_ms = int((time.time() - start_ping) * 1000)
    await msg.edit_text(
        f"💫 <i>Hi! I’m {BOT_NAME}</i>\n\n"
        f"🤖 <i>Bot Username:</i> <code>{BOT_USERNAME}</code>\n"
        f"⚡ <i>Ping:</i> <code>{ping_ms} ms</code>\n"
        f"🕒 <i>Uptime:</i> <code>{get_uptime()}</code>\n"
        f"📡 <i>Status:</i> Active ✅",
        parse_mode="HTML"
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🛠️ *Commands*\n"
        "• /gemini <prompt> - Gemini 3 AI\n"
        "• /deepseek <prompt> - DeepSeek 3.2 AI\n"
        "• /ai <prompt> - Run ChatGPT + Gemini3 (combined)\n"
        "• /insta - Get Instagram profile (bot will ask username)\n"
        "• /ff - Free Fire player info (bot will ask UID)\n"
        "• /ping - Bot status\n"
        "• /broadcast <group_id> <message> (owner only)\n"
        "• /broadcastall <message> (owner only)\n"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# ================= AI Commands (command-based) =================
async def cmd_gemini(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_or_copy(update, context, "/gemini")
    if not context.args:
        await update.message.reply_text("💡 Usage: /gemini <prompt>\nOr press *Gemini 3* button and send prompt.", parse_mode="Markdown")
        return
    prompt = " ".join(context.args)
    msg = await update.message.reply_text("🤖 Gemini 3 is thinking... ⏳")
    async with httpx.AsyncClient() as client:
        reply = await fetch_gemini3(client, prompt)
    await msg.edit_text(f"🧠 *Gemini 3 Response*\n\n{reply}", parse_mode="Markdown")

async def cmd_deepseek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_or_copy(update, context, "/deepseek")
    if not context.args:
        await update.message.reply_text("💡 Usage: /deepseek <prompt>\nOr press *DeepSeek* button and send prompt.", parse_mode="Markdown")
        return
    prompt = " ".join(context.args)
    msg = await update.message.reply_text("🚀 DeepSeek 3.2 is thinking... ⏳")
    async with httpx.AsyncClient() as client:
        reply = await fetch_deepseek(client, prompt)
    await msg.edit_text(f"🔥 *DeepSeek 3.2 Response*\n\n{reply}", parse_mode="Markdown")

async def cmd_ai_combined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_or_copy(update, context, "/ai")
    if not context.args:
        await update.message.reply_text("💡 Usage: /ai <prompt> - runs ChatGPT + Gemini3", parse_mode="Markdown")
        return
    prompt = " ".join(context.args)
    msg = await update.message.reply_text("🤖 Asking both AI engines... ⏳")
    async with httpx.AsyncClient() as client:
        task1 = fetch_chatgpt(client, prompt)
        task2 = fetch_gemini3(client, prompt)
        chatgpt_reply, gemini_reply = await asyncio.gather(task1, task2)
    text = f"💡 *AI Responses*\n\n*ChatGPT:*\n{chatgpt_reply}\n\n*Gemini 3:*\n{gemini_reply}"
    await msg.edit_text(text, parse_mode="Markdown")

# ================= Insta & FF helper flows (button or command) =================
AWAIT_GEMINI = "await_gemini"
AWAIT_DEEPSEEK = "await_deepseek"
AWAIT_INSTA = "await_insta"
AWAIT_FF = "await_ff"

async def start_insta_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await forward_or_copy(update, context, "/insta")
        await update.message.reply_text("📸 Send Instagram username (e.g. zuck):")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="📸 Send Instagram username (e.g. zuck):")
    context.user_data[AWAIT_INSTA] = True

async def do_insta_fetch_by_text(update: Update, context: ContextTypes.DEFAULT_TYPE, username: str):
    msg = await update.message.reply_text("🔎 Fetching Instagram info...")
    async with httpx.AsyncClient() as client:
        data = await fetch_json(client, INSTA_API.format(username))
    if not isinstance(data, dict) or data.get("status") != "ok":
        await msg.edit_text("❌ Failed to fetch Instagram data.")
        return
    p = data.get("profile", {})
    caption = (
        f"📸 *Instagram Info*\n\n"
        f"👤 Name: {p.get('full_name')}\n"
        f"🔖 Username: @{p.get('username')}\n"
        f"📝 Bio: {p.get('biography')}\n"
        f"👥 Followers: {p.get('followers')}\n"
        f"➡ Following: {p.get('following')}\n"
        f"📦 Posts: {p.get('posts')}\n"
        f"📅 Created: {p.get('account_creation_year')}\n"
        f"✅ Verified: {p.get('is_verified')}"
    )
    pic = p.get("profile_pic_url_hd")
    try:
        if pic:
            await msg.delete()
            await update.message.reply_photo(photo=pic, caption=caption, parse_mode="Markdown")
        else:
            await msg.edit_text(caption, parse_mode="Markdown")
    except Exception:
        await msg.edit_text(caption, parse_mode="Markdown")

async def start_ff_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await forward_or_copy(update, context, "/ff")
        await update.message.reply_text("🎮 Send Free Fire UID:")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="🎮 Send Free Fire UID:")
    context.user_data[AWAIT_FF] = True

async def do_ff_fetch_by_text(update: Update, context: ContextTypes.DEFAULT_TYPE, uid: str):
    msg = await update.message.reply_text("🎯 Fetching Free Fire player info...")
    async with httpx.AsyncClient() as client:
        data = await fetch_json(client, FF_API.format(uid))
    text = f"🎮 *Free Fire Player Info*\n\n```{json.dumps(data, indent=2)}```"
    await msg.edit_text(text, parse_mode="Markdown")

# ================= Callback Query Handler (buttons) =================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    if data == "btn_gemini":
        context.user_data[AWAIT_GEMINI] = True
        await query.edit_message_text("🧠 Send your *Gemini 3* prompt now (just type message):", parse_mode="Markdown")
    elif data == "btn_deepseek":
        context.user_data[AWAIT_DEEPSEEK] = True
        await query.edit_message_text("🔥 Send your *DeepSeek 3.2* prompt now (just type message):", parse_mode="Markdown")
    elif data == "btn_insta":
        context.user_data[AWAIT_INSTA] = True
        await query.edit_message_text("📸 Send Instagram username (e.g. zuck):", parse_mode="Markdown")
    elif data == "btn_ff":
        context.user_data[AWAIT_FF] = True
        await query.edit_message_text("🎮 Send Free Fire UID:", parse_mode="Markdown")
    elif data == "btn_ping":
        await query.edit_message_text("🏓 Use /ping or press again if needed.")
    elif data == "btn_help":
        await query.edit_message_text("❓ Use /help or type a command. Buttons start a flow that expects the next message to be the input.")
    else:
        await query.edit_message_text("Unknown action.")

# ================= Message Handler (restored features + flows) =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return
    user = msg.from_user
    ud = context.user_data

    # GEMINI via button
    if ud.pop(AWAIT_GEMINI, False):
        prompt = msg.text or ""
        sent = await msg.reply_text("🤖 Gemini 3 is thinking... ⏳")
        async with httpx.AsyncClient() as client:
            reply = await fetch_gemini3(client, prompt)
        await sent.edit_text(f"🧠 *Gemini 3 Response*\n\n{reply}", parse_mode="Markdown")
        return

    # DEEPSEEK via button
    if ud.pop(AWAIT_DEEPSEEK, False):
        prompt = msg.text or ""
        sent = await msg.reply_text("🚀 DeepSeek is thinking... ⏳")
        async with httpx.AsyncClient() as client:
            reply = await fetch_deepseek(client, prompt)
        await sent.edit_text(f"🔥 *DeepSeek 3.2 Response*\n\n{reply}", parse_mode="Markdown")
        return

    # INSTA via button or command
    if ud.pop(AWAIT_INSTA, False):
        username = (msg.text or "").strip()
        await do_insta_fetch_by_text(update, context, username)
        return

    # FF via button or command
    if ud.pop(AWAIT_FF, False):
        uid = (msg.text or "").strip()
        await do_ff_fetch_by_text(update, context, uid)
        return

    # Forward private messages
    if msg.chat.type == "private":
        await forward_or_copy(update, context)

    # Keyword alerts
    if msg.text:
        lowered = msg.text.lower()
        for keyword in KEYWORDS:
            try:
                if keyword.lower() in lowered:
                    alert = (
                        f"🚨 <b>Keyword Mention Detected!</b>\n"
                        f"<b>Keyword:</b> <code>{keyword}</code>\n"
                        f"<b>From:</b> {msg.from_user.full_name} (@{msg.from_user.username})\n"
                        f"<b>Chat:</b> {msg.chat.title if msg.chat.title else 'Private'}\n"
                        f"<b>Message:</b> {msg.text}"
                    )
                    await context.bot.send_message(chat_id=OWNER_ID, text=alert, parse_mode="HTML")
                    break
            except Exception:
                continue

    # Tracked users forwarding
    try:
        if msg.from_user.id == TRACKED_USER1_ID:
            await context.bot.send_message(chat_id=FORWARD_USER1_GROUP_ID,
                                           text=f"📨 Message from tracked user in <b>{msg.chat.title}</b>",
                                           parse_mode="HTML")
            await msg.forward(chat_id=FORWARD_USER1_GROUP_ID)
        if msg.from_user.id == TRACKED_USER2_ID:
            await context.bot.send_message(chat_id=FORWARD_USER2_GROUP_ID,
                                           text=f"📨 Message from tracked user in <b>{msg.chat.title}</b>",
                                           parse_mode="HTML")
            await msg.forward(chat_id=FORWARD_USER2_GROUP_ID)
    except Exception:
        logger.exception("Tracked forward failed")

    # Source -> Destination
    try:
        if msg.chat.id == SOURCE_GROUP_ID:
            try:
                await msg.forward(chat_id=DESTINATION_GROUP_ID)
            except Exception:
                if msg.text:
                    copy_text = f"📨 From: {msg.from_user.full_name} (@{msg.from_user.username})\nContent: {msg.text}"
                    await context.bot.send_message(chat_id=DESTINATION_GROUP_ID, text=copy_text)
    except Exception:
        pass

# ================= Group Tracking Handler =================
async def track_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.my_chat_member.chat
    if chat.type in ["group", "supergroup"]:
        groups = read_json("groups.json", [])
        if chat.id not in groups:
            groups.append(chat.id)
            write_json("groups.json", groups)

# ================= Broadcast Commands (owner only) =================
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /broadcast <group_id> <message>")
        return
    try:
        group_id = int(context.args[0])
    except:
        await update.message.reply_text("Invalid group id.")
        return
    text = " ".join(context.args[1:])
    sent = failed = 0
    try:
        await context.bot.send_message(chat_id=group_id, text=text)
        sent += 1
    except:
        failed += 1
    await update.message.reply_text(f"✅ Sent: {sent}, ❌ Failed: {failed}")
    update_stats(sent_groups=sent, failed_groups=failed)

async def broadcastall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcastall <message>")
        return
    text = " ".join(context.args)
    groups = read_json("groups.json", [])
    sent = failed = 0
    for gid in groups:
        try:
            await context.bot.send_message(chat_id=gid, text=text)
            sent += 1
        except:
            failed += 1
    await update.message.reply_text(f"✅ Sent: {sent}, ❌ Failed: {failed}")
    update_stats(sent_groups=sent, failed_groups=failed)

async def broadcast_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /broadcast_media <media_url> <caption>")
        return
    media_url = context.args[0]
    caption = " ".join(context.args[1:])
    groups = read_json("groups.json", [])
    sent = failed = 0
    for gid in groups:
        try:
            await context.bot.send_photo(chat_id=gid, photo=media_url, caption=caption)
            sent += 1
        except:
            failed += 1
    await update.message.reply_text(f"✅ Sent: {sent}, ❌ Failed: {failed}")
    update_stats(sent_groups=sent, failed_groups=failed)

# ================= Run Bot =================
def main():
    if not BOT_TOKEN:
        logger.error("Bot token not found. Please put token in token.txt")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("help", cmd_help))

    # AI
    app.add_handler(CommandHandler("gemini", cmd_gemini))
    app.add_handler(CommandHandler("deepseek", cmd_deepseek))
    app.add_handler(CommandHandler("ai", cmd_ai_combined))

    # Insta / FF
    app.add_handler(CommandHandler("insta", start_insta_flow))
    app.add_handler(CommandHandler("ff", start_ff_flow))

    # Broadcasts
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("broadcastall", broadcastall))
    app.add_handler(CommandHandler("broadcast_media", broadcast_media))

    # Callback button handler
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Message handler
    app.add_handler(MessageHandler(filters.ALL, handle_message))

    # Track bot added to group
    app.add_handler(ChatMemberHandler(track_group, ChatMemberHandler.MY_CHAT_MEMBER))

    logger.info("Hinata Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
