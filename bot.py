# bot.py
import os
import time
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import yt_dlp

TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # e.g. https://your-service.onrender.com
if not TOKEN or not WEBHOOK_URL:
    raise RuntimeError("Set TELEGRAM_TOKEN and WEBHOOK_URL environment variables before starting.")

bot = Bot(token=TOKEN)
app = Flask(__name__)

DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def safe_filename(info_dict):
    # return yt-dlp's prepared filename would be fine, but we will use id to avoid unicode issues
    return f"{info_dict.get('id')}"

def download_youtube(url, audio_only=False):
    opts = {
        'format': 'bestaudio/best' if audio_only else 'bestvideo+bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }
    if audio_only:
        # avoid re-encoding on server; keep original audio container
        opts['format'] = 'bestaudio/best'
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filepath = ydl.prepare_filename(info)
        # if video+audio merged it may have .mkv/.mp4 etc; return path
        return filepath, info.get('title'), info.get('webpage_url')

def human_size(path):
    s = os.path.getsize(path)
    for unit in ['B','KB','MB','GB']:
        if s < 1024:
            return f"{s:.1f}{unit}"
        s /= 1024
    return f"{s:.1f}TB"

# Commands
def start(update, context):
    update.message.reply_text("👋 Send a YouTube link. I'll offer MP3 (audio) or Video download. Note: large files (>49MB) can't be uploaded via Telegram bot API.")

def help_cmd(update, context):
    update.message.reply_text("Send YouTube link (youtube.com or youtu.be). Choose format and wait.")

# When a text message arrives
def handle_message(update, context):
    text = update.message.text or ""
    if "youtube.com" in text or "youtu.be" in text:
        kb = [
            [InlineKeyboardButton("🎵 MP3 (audio)", callback_data=f"mp3|{text}"),
             InlineKeyboardButton("🎬 Video", callback_data=f"video|{text}")]
        ]
        update.message.reply_text("Choose format:", reply_markup=InlineKeyboardMarkup(kb))
    else:
        update.message.reply_text("Send a valid YouTube link (youtube.com or youtu.be).")

# When inline button clicked
def button_handler(update, context):
    query = update.callback_query
    query.answer()
    data = query.data.split("|", 1)
    if len(data) != 2:
        query.edit_message_text("Invalid action.")
        return
    mode, url = data[0], data[1]
    query.edit_message_text("⏳ Downloading... (this can take some seconds)")

    try:
        audio_only = (mode == "mp3")
        path, title, webpage = download_youtube(url, audio_only=audio_only)
        size_bytes = os.path.getsize(path)
        max_upload = 49 * 1024 * 1024  # 49 MB safe threshold
        if size_bytes > max_upload:
            # Too large to upload via bot — send link to user (webpage) + tell them to use external downloader
            query.edit_message_text(f"❌ File too large to send via Telegram ({human_size(path)}). Open original page: {webpage}")
        else:
            caption = title or ""
            if audio_only:
                # send as audio
                with open(path, "rb") as f:
                    bot.send_audio(chat_id=query.message.chat_id, audio=f, title=title, caption=caption)
            else:
                with open(path, "rb") as f:
                    bot.send_video(chat_id=query.message.chat_id, video=f, caption=caption)
            query.edit_message_text("✅ Here you go!")
    except Exception as e:
        try:
            query.edit_message_text(f"❌ Error: {e}")
        except:
            pass
    finally:
        # cleanup files older than a minute to save disk
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

# Flask webhook endpoint
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "OK"

@app.route("/")
def index():
    return "Bot running."

# Dispatcher (sync)
dispatcher = Dispatcher(bot, None, workers=0, use_context=True)
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("help", help_cmd))
dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
dispatcher.add_handler(CallbackQueryHandler(button_handler))

# Ensure webhook is set when this module is imported (gunicorn will import)
WEBHOOK_FULL = f"{WEBHOOK_URL.rstrip('/')}/{TOKEN}"
try:
    # remove previous webhook and set new
    bot.delete_webhook()
    time.sleep(0.3)
    bot.set_webhook(WEBHOOK_FULL)
    print("Webhook set to:", WEBHOOK_FULL)
except Exception as ex:
    print("Warning: could not set webhook on import:", ex)
