import os
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise RuntimeError("Set TELEGRAM_TOKEN environment variable")

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"  # no key required

# start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! Mujhe song ka naam bhejo. Main top results dikhauga — preview ke liye click karo.")

# handle text search
async def search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not query:
        await update.message.reply_text("Kuch type karo (artist ya song name).")
        return

    params = {"term": query, "media": "music", "limit": 5, "country": "IN"}
    resp = requests.get(ITUNES_SEARCH_URL, params=params, timeout=10)
    if resp.status_code != 200:
        await update.message.reply_text("Search failed, thoda baad mein try karo.")
        return

    data = resp.json()
    results = data.get("results", [])
    if not results:
        await update.message.reply_text("Koi result nahi mila.")
        return

    keyboard = []
    for item in results:
        track_name = item.get("trackName") or item.get("collectionName") or "Unknown"
        artist = item.get("artistName", "Unknown")
        # store preview url + track info in callback_data (encode limited info)
        preview = item.get("previewUrl")  # may be None
        # We'll send an index as callback and store results in user_data
        keyboard.append([InlineKeyboardButton(f"{artist} — {track_name}", callback_data=f"pick:{results.index(item)}")])

    # save results in user_data for this chat
    context.user_data["last_search"] = results
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select a track:", reply_markup=reply_markup)

# when user picks one
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith("pick:"):
        await query.message.reply_text("Unknown action.")
        return

    idx = int(data.split(":", 1)[1])
    results = context.user_data.get("last_search") or []
    if idx < 0 or idx >= len(results):
        await query.message.reply_text("Invalid selection.")
        return

    item = results[idx]
    track_name = item.get("trackName") or item.get("collectionName") or "Unknown"
    artist = item.get("artistName", "Unknown")
    preview = item.get("previewUrl")
    track_view = item.get("trackViewUrl") or item.get("collectionViewUrl") or ""

    text = f"🎵 {artist} — {track_name}\n{track_view}\n"
    if preview:
        # send preview audio (Telegram will stream or allow user to save)
        try:
            await query.message.reply_audio(preview, caption=text + "\n(30s preview)")
        except Exception as e:
            # fallback: send link
            await query.message.reply_text(text + "\nPreview URL: " + preview)
    else:
        await query.message.reply_text(text + "\nPreview not available.")

    await query.message.reply_text("Agar yeh sahi hai, preview pe long-press karke 'Save' kar sakte ho.")

# simple /help
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Search: kisi bhi gaane/artist ka naam bhejo. Fir list se choose karo.")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_handler))

    print("Bot started (polling)...")
    app.run_polling()

if __name__ == "__main__":
    main()
