import os
import re
import asyncio
import logging
from pyrogram import Client, filters, idle
from pyrogram.errors import RPCError

# --- LOGGING AGAR LEBIH MUDAH DILIHAT DI RAILWAY ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- AMBIL KREDENSIAL DARI ENVIRONMENT RAILWAY ---
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
STRING_SESSION = os.environ.get("STRING_SESSION")

# Periksa apakah semua variabel sudah diisi
missing_vars = []
if not API_ID: missing_vars.append("API_ID")
if not API_HASH: missing_vars.append("API_HASH")
if not BOT_TOKEN: missing_vars.append("BOT_TOKEN")
if not STRING_SESSION: missing_vars.append("STRING_SESSION")

if missing_vars:
    error_msg = f"Environment variable tidak ditemukan: {', '.join(missing_vars)}"
    logger.error(error_msg)
    raise ValueError(error_msg)

# Konversi API_ID ke integer
try:
    API_ID = int(API_ID)
except ValueError:
    logger.error("API_ID harus berupa angka (integer).")
    raise

# --- DUA CLIENT: BOT (UNTUK KAMU) DAN USER (UNTUK AKSES CHANNEL) ---
bot_app = Client(
    "bot_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

user_app = Client(
    "user_session",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=STRING_SESSION,
    in_memory=True
)

# --- FUNGSI MENGURAI LINK TELEGRAM (SAMA SEPERTI SEBELUMNYA) ---
def parse_telegram_link(link):
    # Link privat: https://t.me/c/1234567890/123
    private_pattern = r"https?://t\.me/c/(\d+)/(\d+)"
    match = re.match(private_pattern, link)
    if match:
        chat_id_str = match.group(1)
        message_id = int(match.group(2))
        chat_id = int(f"-100{chat_id_str}")
        return chat_id, message_id

    # Link publik: https://t.me/username/456
    public_pattern = r"https?://t\.me/([^/]+)/(\d+)"
    match = re.match(public_pattern, link)
    if match:
        username = match.group(1)
        message_id = int(match.group(2))
        return username, message_id

    return None, None

# --- HANDLER PERINTAH /start ---
@bot_app.on_message(filters.command("start"))
async def start_command(client, message):
    await message.reply_text(
        "Halo! Kirimkan saya link pesan (public atau private) yang ingin Anda ambil kontennya.\n\n"
        "Contoh: `https://t.me/c/1234567890/123`"
    )

# --- HANDLER UNTUK MENERIMA LINK ---
@bot_app.on_message(filters.text & ~filters.command("start"))
async def handle_link(client, message):
    link = message.text.strip()
    try:
        # 1. Parse link
        chat_id, msg_id = parse_telegram_link(link)
        if chat_id is None or msg_id is None:
            return await message.reply_text("❌ Format link tidak dikenali.")

        # 2. Ambil pesan MENGGUNAKAN USER CLIENT (akun pribadimu)
        logger.info(f"Mengambil pesan dari chat_id={chat_id}, msg_id={msg_id}")
        msg = await user_app.get_messages(chat_id=chat_id, message_ids=msg_id)

        if not msg:
            return await message.reply_text("❌ Pesan tidak ditemukan. Pastikan link benar dan akunmu memiliki akses.")

        # 3. Status proses
        status_msg = await message.reply_text("⏳ Sedang memproses pesan...")

        # 4. Salin isi pesan ke chat pribadimu
        await msg.copy(
            chat_id=message.chat.id,
            caption=msg.caption if msg.caption else None,
            reply_to_message_id=message.id
        )

        # 5. Hapus status
        await status_msg.delete()
        logger.info(f"Berhasil mengirim konten dari {link}")

    except RPCError as e:
        # Error dari Telegram API (misal: channel tidak bisa diakses)
        logger.error(f"Telegram API Error: {e}")
        await message.reply_text(f"❌ Error Telegram: {e}")
    except Exception as e:
        logger.error(f"Unexpected Error: {e}")
        await message.reply_text(f"❌ Terjadi kesalahan: {e}")

# --- FUNGSI UTAMA UNTUK MENJALANKAN KEDUA CLIENT ---
async def main():
    try:
        # 1. Mulai user client (akun pribadi)
        logger.info("Memulai user client...")
        await user_app.start()
        logger.info("✅ User client berjalan.")

        # 2. Mulai bot client
        logger.info("Memulai bot client...")
        await bot_app.start()
        logger.info("✅ Bot client berjalan.")

        # 3. Info tambahan
        me = await bot_app.get_me()
        logger.info(f"🤖 Bot @{me.username} siap menerima perintah.")

        # 4. Tahan agar program tidak berhenti
        await idle()

    except RPCError as e:
        logger.error(f"Gagal start client (RPC Error): {e}")
    except Exception as e:
        logger.error(f"Gagal start client: {e}")
    finally:
        logger.info("Proses shutdown...")
        await user_app.stop()
        await bot_app.stop()

if __name__ == "__main__":
    asyncio.run(main())
