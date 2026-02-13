# -*- coding: utf-8 -*-
import asyncio
import logging
import json
import os
import time
from datetime import timedelta
from aiohttp import ClientSession
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ChatMemberHandler,
    ConversationHandler
)

# ================= Configuration =================
OWNER_ID = 7333244376
BOT_TOKEN_FILE = "token.txt"
BOT_NAME = "Hinata"
BOT_USERNAME = "@Hinata_00_bot"

INBOX_FORWARD_GROUP_ID = -1003113491147

LOG_FILE = "hinata.log"
MAX_LOG_SIZE = 200 * 1024

# ================= NEW APIs =================
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

def read_file(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""

BOT_TOKEN = read_file(BOT_TOKEN_FILE)

start_time = time.time()

def get_uptime():
    return str(timedelta(seconds=int(time.time() - start_time)))

# ================= AI COMMANDS =================

async def gemini3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("💡 Usage: /gemini <prompt>")
        return
    prompt = " ".join(context.args)
    await update.message.reply_text("🤖 Gemini 3 is thinking...")

    async with ClientSession() as session:
        async with session.get(GEMINI3_API.format(prompt.replace(" ", "+"))) as r:
            data = await r.json()
            reply = data.get("response", "No reply.")

    await update.message.reply_text(f"🧠 *Gemini 3 Response*\n\n{reply}", parse_mode="Markdown")


async def deepseek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("💡 Usage: /deepseek <prompt>")
        return
    prompt = " ".join(context.args)
    await update.message.reply_text("🚀 DeepSeek 3.2 thinking...")

    async with ClientSession() as session:
        async with session.get(DEEPSEEK_API.format(prompt.replace(" ", "+"))) as r:
            reply = await r.text()

    await update.message.reply_text(f"🔥 *DeepSeek 3.2*\n\n{reply}", parse_mode="Markdown")


# ================= Insta Info =================
INSTA_USERNAME = 1

async def insta_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📸 Send Instagram username:")
    return INSTA_USERNAME

async def insta_fetch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()

    async with ClientSession() as session:
        async with session.get(INSTA_API.format(username)) as r:
            data = await r.json()

    if data.get("status") != "ok":
        await update.message.reply_text("❌ Failed to fetch data.")
        return ConversationHandler.END

    p = data["profile"]

    text = (
        f"📸 *Instagram Info*\n\n"
        f"👤 Name: {p['full_name']}\n"
        f"🔖 Username: @{p['username']}\n"
        f"📝 Bio: {p['biography']}\n"
        f"👥 Followers: {p['followers']}\n"
        f"➡ Following: {p['following']}\n"
        f"📦 Posts: {p['posts']}\n"
        f"📅 Created: {p['account_creation_year']}\n"
        f"✅ Verified: {p['is_verified']}"
    )

    await update.message.reply_photo(photo=p["profile_pic_url_hd"], caption=text, parse_mode="Markdown")
    return ConversationHandler.END


# ================= Free Fire Info =================
FF_UID = 2

async def ff_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎮 Send Free Fire UID:")
    return FF_UID

async def ff_fetch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.text.strip()

    async with ClientSession() as session:
        async with session.get(FF_API.format(uid)) as r:
            data = await r.json()

    await update.message.reply_text(f"🎯 *Free Fire Player Info*\n\n```{json.dumps(data, indent=2)}```", parse_mode="Markdown")
    return ConversationHandler.END


# ================= Basic Commands =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"✨ *Welcome to {BOT_NAME}*\n\n"
        f"🤖 /gemini - Gemini 3 AI\n"
        f"🔥 /deepseek - DeepSeek 3.2 AI\n"
        f"📸 /insta - Instagram Info\n"
        f"🎮 /ff - Free Fire Info\n"
        f"🏓 /ping - Check bot speed",
        parse_mode="Markdown"
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🏓 Pinging...")
    await msg.edit_text(
        f"⚡ Pong!\n\n🕒 Uptime: {get_uptime()}"
    )

# ================= Run Bot =================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # AI
    app.add_handler(CommandHandler("gemini", gemini3))
    app.add_handler(CommandHandler("deepseek", deepseek))

    # Insta Conversation
    insta_conv = ConversationHandler(
        entry_points=[CommandHandler("insta", insta_start)],
        states={INSTA_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, insta_fetch)]},
        fallbacks=[]
    )
    app.add_handler(insta_conv)

    # FF Conversation
    ff_conv = ConversationHandler(
        entry_points=[CommandHandler("ff", ff_start)],
        states={FF_UID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ff_fetch)]},
        fallbacks=[]
    )
    app.add_handler(ff_conv)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))

    app.run_polling()

if __name__ == "__main__":
    main()
