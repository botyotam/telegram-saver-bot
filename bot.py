import os
import re
from pyrogram import Client, filters

# --- AMBIL SEMUA KREDENSIAL DARI ENVIRONMENT RAILWAY ---
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
STRING_SESSION = os.environ.get("STRING_SESSION")  # <-- baru

if not all([API_ID, API_HASH, BOT_TOKEN, STRING_SESSION]):
    raise ValueError("API_ID, API_HASH, BOT_TOKEN, atau STRING_SESSION belum diatur.")

# --- BOT CLIENT (untuk menerima perintah dan membalas) ---
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
    session_string=STRING_SESSION,  # langsung pakai string, tanpa file
    in_memory=True
)

# --- FUNGSI PARSE LINK (sama seperti sebelumnya) ---
def parse_telegram_link(link):
    private_pattern = r"https?://t\.me/c/(\d+)/(\d+)"
    match = re.match(private_pattern, link)
    if match:
        chat_id_str = match.group(1)
        message_id = int(match.group(2))
        chat_id = int(f"-100{chat_id_str}")
        return chat_id, message_id

    public_pattern = r"https?://t\.me/([^/]+)/(\d+)"
    match = re.match(public_pattern, link)
    if match:
        username = match.group(1)
        message_id = int(match.group(2))
        return username, message_id

    return None, None

# --- HANDLER /start untuk bot ---
@bot_app.on_message(filters.command("start"))
async def start_command(client, message):
    await message.reply_text(
        "Halo! Kirimkan saya link pesan (public atau private) yang ingin Anda ambil kontennya.\n\n"
        "Contoh: `https://t.me/c/1234567890/123`"
    )

# --- HANDLER UNTUK LINK, MENGGUNAKAN USER_APP UNTUK GET_MESSAGES ---
@bot_app.on_message(filters.text & ~filters.command("start"))
async def handle_link(client, message):
    link = message.text.strip()
    try:
        chat_id, msg_id = parse_telegram_link(link)
        if chat_id is None or msg_id is None:
            return await message.reply_text("❌ Format link tidak dikenali.")

        # GUNAKAN USER_APP (akunmu) untuk mengambil pesan
        msg = await user_app.get_messages(chat_id=chat_id, message_ids=msg_id)
        if not msg:
            return await message.reply_text("❌ Pesan tidak ditemukan. Pastikan link benar dan akunmu memiliki akses.")

        status_msg = await message.reply_text("⏳ Sedang memproses pesan...")

        # Salin isi pesan menggunakan BOT_APP agar sampai ke chat pribadimu
        await msg.copy(
            chat_id=message.chat.id,
            caption=msg.caption if msg.caption else None,
            reply_to_message_id=message.id
        )

        await status_msg.delete()

    except Exception as e:
        await message.reply_text(f"❌ Terjadi kesalahan: {e}")

# --- JALANKAN KEDUA CLIENT BERSAMAAN ---
if __name__ == "__main__":
    import asyncio
    async def main():
        await user_app.start()
        print("👤 User client started.")
        await bot_app.run()  # bot_app.run() akan menjalankan bot hingga dihentikan

    asyncio.run(main())
