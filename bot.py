import os
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext
import yt_dlp
import tempfile

TOKEN = os.getenv("BOT_TOKEN", "PASTE_YOUR_TOKEN_HERE")

bot = Bot(token=TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running fine!"

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok', 200

def start(update: Update, context: CallbackContext):
    update.message.reply_text("🎵 Send me a YouTube song name or link, and I'll get it for you!")

def download_music(update: Update, context: CallbackContext):
    query = update.message.text.strip()
    update.message.reply_text("⏳ Downloading your music, please wait...")

    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(tempfile.gettempdir(), '%(title)s.%(ext)s'),
            'quiet': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=True)['entries'][0]
            file_path = ydl.prepare_filename(info).replace(".webm", ".mp3")

        with open(file_path, 'rb') as f:
            update.message.reply_audio(audio=f, title=info.get('title'))

    except Exception as e:
        update.message.reply_text(f"❌ Error: {e}")

# Telegram Dispatcher
dispatcher = Dispatcher(bot, None, use_context=True)
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, download_music))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
