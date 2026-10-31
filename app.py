import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode
import yt_dlp

# ================== KONFIGURASI ==================
BOT_TOKEN = "GANTI_DENGAN_TOKEN_BOT_KAMU"
DOWNLOAD_DIR = "downloads"
MAX_FILE_SIZE_MB = 48

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ================== FUNGSI DOWNLOAD ==================
def download_audio(url: str, format_choice: str) -> tuple[str | None, str | None]:
    """
    Download audio sesuai pilihan format.
    Return: (path_file, judul) atau (None, error_message)
    """
    if format_choice == "mp3":
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
        ext = "mp3"

    elif format_choice == "m4a":
        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
            }],
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }
        ext = "m4a"

    elif format_choice == "flac":
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "flac",
            }],
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }
        ext = "flac"

    else:
        return None, "Format tidak dikenali."

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "Unknown")
            filename = ydl.prepare_filename(info)
            final_path = os.path.splitext(filename)[0] + f".{ext}"

            if os.path.exists(final_path):
                return final_path, title
            else:
                # Kadang file masih pakai ekstensi asli
                if os.path.exists(filename):
                    return filename, title
                return None, "File gagal dibuat setelah download."
    except Exception as e:
        return None, str(e)

# ================== HANDLER ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 *YouTube Music Downloader*\n\n"
        "Kirim link YouTube / YouTube Music, lalu pilih format yang kamu inginkan.\n\n"
        "Format tersedia:\n"
        "• MP3 320kbps → paling kompatibel\n"
        "• M4A Best → kualitas tinggi, ukuran lebih kecil\n"
        "• FLAC Lossless → kualitas terbaik (tanpa kompresi)\n\n"
        "Contoh link:\n"
        "`https://www.youtube.com/watch?v=xxxxx`",
        parse_mode=ParseMode.MARKDOWN
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Cara pakai:\n"
        "1. Kirim link YouTube\n"
        "2. Pilih format (MP3 / M4A / FLAC)\n"
        "3. Tunggu proses download\n"
        "4. Terima file audio\n\n"
        "Catatan: File maksimal ~48MB (batasan Telegram)."
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if "youtube.com" not in url and "youtu.be" not in url and "music.youtube.com" not in url:
        await update.message.reply_text("❌ Link tidak valid. Kirim link YouTube yang benar.")
        return

    # Simpan URL di user_data
    context.user_data["url"] = url

    keyboard = [
        [
            InlineKeyboardButton("MP3 320kbps", callback_data="format_mp3"),
            InlineKeyboardButton("M4A Best", callback_data="format_m4a"),
        ],
        [
            InlineKeyboardButton("FLAC Lossless", callback_data="format_flac"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Pilih format yang diinginkan:",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("format_"):
        return

    format_choice = data.replace("format_", "")  # mp3 / m4a / flac
    url = context.user_data.get("url")

    if not url:
        await query.edit_message_text("❌ URL tidak ditemukan. Silakan kirim ulang link.")
        return

    format_name = {
        "mp3": "MP3 320kbps",
        "m4a": "M4A Best",
        "flac": "FLAC Lossless"
    }.get(format_choice, format_choice)

    await query.edit_message_text(f"⏳ Sedang mendownload dalam format *{format_name}*...\nMohon tunggu.", parse_mode=ParseMode.MARKDOWN)

    try:
        loop = asyncio.get_event_loop()
        file_path, result = await loop.run_in_executor(None, download_audio, url, format_choice)

        if file_path is None:
            await query.edit_message_text(f"❌ Gagal download:\n`{result}`", parse_mode=ParseMode.MARKDOWN)
            return

        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            os.remove(file_path)
            await query.edit_message_text(
                f"❌ File terlalu besar ({file_size_mb:.1f} MB).\n"
                f"Batas Telegram untuk bot adalah ~50MB.\n\n"
                f"Coba pilih format MP3 atau M4A."
            )
            return

        await query.edit_message_text("📤 Mengirim file...")

        with open(file_path, "rb") as audio_file:
            # Kirim sebagai audio supaya bisa diputar langsung di Telegram
            await context.bot.send_audio(
                chat_id=query.message.chat_id,
                audio=audio_file,
                title=result,
                caption=f"🎵 *{result}*\n\nFormat: {format_name}",
                parse_mode=ParseMode.MARKDOWN
            )

        await query.delete_message()

    except Exception as e:
        logger.error(f"Error: {e}")
        await query.edit_message_text(f"❌ Terjadi kesalahan:\n`{str(e)}`", parse_mode=ParseMode.MARKDOWN)

    finally:
        if "file_path" in locals() and file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        # Bersihkan URL
        context.user_data.pop("url", None)

# ================== MAIN ==================
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    application.add_handler(CallbackQueryHandler(button_callback))

    print("Bot sedang berjalan...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()