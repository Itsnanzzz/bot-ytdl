import os
import logging
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode
import yt_dlp

# ================== LOAD ENV ==================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN tidak ditemukan di file .env")

DOWNLOAD_DIR = "downloads"
MAX_FILE_SIZE_MB = 48
COOKIES_FILE = "cookies.txt"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ================== FUNGSI DOWNLOAD ==================
def download_audio(url: str) -> tuple[str | None, str | None]:
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        }],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    # Gunakan cookies jika tersedia
    if os.path.exists(COOKIES_FILE):
        ydl_opts["cookiefile"] = COOKIES_FILE
    else:
        logger.warning("File cookies.txt tidak ditemukan!")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "Unknown")
            filename = ydl.prepare_filename(info)
            mp3_path = os.path.splitext(filename)[0] + ".mp3"

            if os.path.exists(mp3_path):
                return mp3_path, title
            elif os.path.exists(filename):
                return filename, title
            return None, "File gagal dibuat setelah download."
    except Exception as e:
        return None, str(e)

# ================== HANDLER ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 *YouTube Music Downloader*\n\n"
        "Kirim link YouTube / YouTube Music, saya akan download musiknya dengan kualitas terbaik (MP3 320kbps).\n\n"
        "Contoh:\n"
        "`https://www.youtube.com/watch?v=xxxxx`\n"
        "`https://music.youtube.com/watch?v=xxxxx`",
        parse_mode=ParseMode.MARKDOWN
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Cara pakai:\n"
        "1. Kirim link YouTube\n"
        "2. Tunggu proses download\n"
        "3. Terima file MP3 kualitas terbaik\n\n"
        "Catatan: File maksimal ~48MB (batasan Telegram)."
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if "youtube.com" not in url and "youtu.be" not in url and "music.youtube.com" not in url:
        await update.message.reply_text("❌ Link tidak valid. Kirim link YouTube yang benar.")
        return

    status_msg = await update.message.reply_text("⏳ Sedang memproses... mohon tunggu.")

    try:
        loop = asyncio.get_event_loop()
        file_path, result = await loop.run_in_executor(None, download_audio, url)

        if file_path is None:
            await status_msg.edit_text(f"❌ Gagal download:\n`{result}`", parse_mode=ParseMode.MARKDOWN)
            return

        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            os.remove(file_path)
            await status_msg.edit_text(
                f"❌ File terlalu besar ({file_size_mb:.1f} MB).\n"
                f"Batas Telegram untuk bot adalah ~50MB."
            )
            return

        await status_msg.edit_text("📤 Mengirim file...")

        with open(file_path, "rb") as audio_file:
            await update.message.reply_audio(
                audio=audio_file,
                title=result,
                caption=f"🎵 *{result}*\n\nKualitas: MP3 320kbps",
                parse_mode=ParseMode.MARKDOWN
            )

        await status_msg.delete()

    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text(f"❌ Terjadi kesalahan:\n`{str(e)}`", parse_mode=ParseMode.MARKDOWN)

    finally:
        if "file_path" in locals() and file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

# ================== MAIN ==================
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    print("Bot sedang berjalan...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()