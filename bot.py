import os
import re
from pyrogram import Client, filters
from pyrogram.types import Message

# --- AMBIL KREDENSIAL DARI ENVIRONMENT RAILWAY ---
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("API_ID, API_HASH, atau BOT_TOKEN belum diatur.")

app = Client(
    "my_saver_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# --- FUNGSI UNTUK MENGURAI LINK TELEGRAM ---
def parse_telegram_link(link):
    """
    Mengubah link Telegram menjadi chat_id dan message_id yang bisa dipahami Pyrogram.
    Contoh:
    - https://t.me/c/1234567890/123 -> chat_id = -1001234567890, message_id = 123
    - https://t.me/username/456 -> chat_id = "username", message_id = 456
    """
    # Pola untuk link private channel (c/...)
    private_pattern = r"https?://t\.me/c/(\d+)/(\d+)"
    match = re.match(private_pattern, link)
    if match:
        chat_id_str = match.group(1)
        message_id = int(match.group(2))
        # Untuk channel private, chat_id harus diawali dengan -100
        chat_id = int(f"-100{chat_id_str}")
        return chat_id, message_id

    # Pola untuk link public channel/group (@username)
    public_pattern = r"https?://t\.me/([^/]+)/(\d+)"
    match = re.match(public_pattern, link)
    if match:
        username = match.group(1)
        message_id = int(match.group(2))
        return username, message_id

    return None, None

# --- HANDLER PERINTAH /start ---
@app.on_message(filters.command("start"))
async def start_command(client, message):
    await message.reply_text(
        "Halo! Kirimkan saya link pesan (public atau private) yang ingin Anda ambil kontennya.\n\n"
        "Contoh: `https://t.me/c/1234567890/123`"
    )

# --- HANDLER UNTUK MENERIMA LINK ---
@app.on_message(filters.text & ~filters.command("start"))
async def handle_link(client, message):
    link = message.text.strip()
    try:
        # 1. Parse link dulu
        chat_id, msg_id = parse_telegram_link(link)
        if chat_id is None or msg_id is None:
            return await message.reply_text(
                "❌ Format link tidak dikenali.\n"
                "Gunakan link seperti: `https://t.me/c/1234567890/123` atau `https://t.me/username/456`"
            )

        # 2. Ambil pesan berdasarkan chat_id dan message_id
        msg = await client.get_messages(chat_id=chat_id, message_ids=msg_id)
        if not msg:
            return await message.reply_text("❌ Pesan tidak ditemukan. Pastikan link benar dan bot memiliki akses.")

        # 3. Kirim status
        status_msg = await message.reply_text("⏳ Sedang memproses pesan...")

        # 4. Salin isi pesan ke chat pribadi user
        await msg.copy(
            chat_id=message.chat.id,
            caption=msg.caption if msg.caption else None,
            reply_to_message_id=message.id
        )

        # 5. Hapus status
        await status_msg.delete()

    except Exception as e:
        await message.reply_text(f"❌ Terjadi kesalahan: {e}")

# --- JALANKAN BOT ---
if __name__ == "__main__":
    print("🤖 Bot sedang berjalan...")
    app.run()
