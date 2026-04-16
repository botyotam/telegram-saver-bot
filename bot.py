import os
import re
import asyncio
from pyrogram import Client, filters, idle

# --- AMBIL KREDENSIAL DARI ENVIRONMENT RAILWAY ---
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
STRING_SESSION = os.environ.get("STRING_SESSION")

if not all([API_ID, API_HASH, BOT_TOKEN, STRING_SESSION]):
    raise ValueError("API_ID, API_HASH, BOT_TOKEN, atau STRING_SESSION belum diatur.")

# --- BOT CLIENT (untuk menerima perintah dan membalas kamu) ---
bot_app = Client(
    "bot_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# --- USER CLIENT (untuk mengakses channel privat atas nama akunmu) ---
user_app = Client(
    "user_session",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=STRING_SESSION,
    in_memory=True
)

# --- FUNGSI MENGURAI LINK TELEGRAM ---
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

# --- HANDLER /start ---
@bot_app.on_message(filters.command("start"))
async def start_command(client, message):
    await message.reply_text(
        "Halo! Kirimkan saya link pesan (public atau private) yang ingin Anda ambil kontennya.\n\n"
        "Contoh: `https://t.me/c/1234567890/123`"
    )

# --- HANDLER UNTUK LINK ---
@bot_app.on_message(filters.text & ~filters.command("start"))
async def handle_link(client, message):
    link = message.text.strip()
    try:
        # 1. Parse link
        chat_id, msg_id = parse_telegram_link(link)
        if chat_id is None or msg_id is None:
            return await message.reply_text("❌ Format link tidak dikenali.")

        # 2. GUNAKAN USER_APP untuk mengambil pesan dari channel privat
        msg = await user_app.get_messages(chat_id=chat_id, message_ids=msg_id)
        if not msg:
            return await message.reply_text("❌ Pesan tidak ditemukan. Pastikan link benar dan akunmu memiliki akses.")

        # 3. Kirim status proses
        status_msg = await message.reply_text("⏳ Sedang memproses pesan...")

        # 4. Salin isi pesan ke chat pribadimu (menggunakan BOT_APP)
        await msg.copy(
            chat_id=message.chat.id,
            caption=msg.caption if msg.caption else None,
            reply_to_message_id=message.id
        )

        # 5. Hapus status
        await status_msg.delete()

    except Exception as e:
        await message.reply_text(f"❌ Terjadi kesalahan: {e}")

# --- FUNGSI UTAMA MENJALANKAN KEDUA CLIENT ---
async def main():
    # Mulai kedua client secara asynchronous
    await user_app.start()
    await bot_app.start()
    print("✅ User client dan Bot client sudah berjalan.")

    # Tahan program agar tetap berjalan
    await idle()

    # Hentikan dengan bersih jika dihentikan
    await user_app.stop()
    await bot_app.stop()

if __name__ == "__main__":
    # Jalankan main() sekali saja
    asyncio.run(main())
