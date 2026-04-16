import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message

# --- AMBIL KREDENSIAL DARI ENVIRONMENT RAILWAY (NANTI) ---
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Pastikan semua kredensial sudah diisi
if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("API_ID, API_HASH, atau BOT_TOKEN belum diatur di environment variable.")

# Buat koneksi bot
app = Client(
    "my_saver_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True # Tidak menyimpan file .session di disk, karena Railway akan sering restart
)

# --- BAGIAN UTAMA BOT UNTUK MENGAMBIL KONTEN TERBATAS ---
@app.on_message(filters.command("start"))
async def start_command(client, message):
    """Balasan untuk perintah /start"""
    await message.reply_text(
        "Halo! Kirimkan saya link pesan (public atau private) yang ingin Anda ambil kontennya.\n\n"
        "Contoh: `https://t.me/c/1234567890/123`"
    )

@app.on_message(filters.text & ~filters.command("start"))
async def handle_link(client, message):
    """Menangani link yang dikirim user"""
    link = message.text.strip()
    try:
        # 1. Ambil data pesan dari link
        msg = await client.get_messages(link)
        if not msg:
            return await message.reply_text("❌ Pesan tidak ditemukan. Pastikan link benar dan bot punya akses.")
        
        # 2. Kirim status "memproses"
        status_msg = await message.reply_text("⏳ Sedang memproses pesan...")
        
        # 3. Pindahkan isi pesan (termasuk media) ke chat pribadi user
        await msg.copy(
            chat_id=message.chat.id,
            caption=msg.caption if msg.caption else None,
            reply_to_message_id=message.id # Balas pesan user
        )
        
        # 4. Hapus status "memproses" dan beri notifikasi sukses
        await status_msg.delete()
        # await message.reply_text("✅ Konten berhasil diambil!") # Bisa di-uncomment jika ingin
        
    except Exception as e:
        await message.reply_text(f"❌ Terjadi kesalahan: {e}")

# --- JALANKAN BOT ---
if __name__ == "__main__":
    print("🤖 Bot sedang berjalan...")
    app.run()
