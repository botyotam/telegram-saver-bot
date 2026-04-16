"""
Telegram Media Downloader Bot for Railway
Bypass content sharing restrictions
"""

import os
import asyncio
import logging
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment Variables dari Railway Variables
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Validasi ENV
if not all([API_ID, API_HASH, BOT_TOKEN]):
    logger.error("❌ Environment variables belum di-set!")
    raise ValueError("API_ID, API_HASH, BOT_TOKEN wajib diisi")

# Inisialisasi Client
app = Client(
    "railway_media_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode="markdown",
    no_updates=False  # Penting untuk Railway
)

# In-memory storage (no database)
user_data = {}

def get_status(user_id):
    """Get user status"""
    if user_id not in user_data:
        user_data[user_id] = {
            "downloads": 0,
            "threads": 0,
            "last_seen": datetime.now(),
            "status": "idle"
        }
    return user_data[user_id]

@app.on_message(filters.command("start"))
async def start_cmd(client, message: Message):
    """Start command"""
    user_id = message.from_user.id
    user_data[user_id] = {
        "downloads": 0,
        "threads": 0,
        "last_seen": datetime.now(),
        "status": "idle"
    }
    
    text = f"""
👋 **Halo {message.from_user.first_name}!**

🤖 **Media Downloader Bot**

✨ **Fitur:**
• Bypass restriction channel
• Download & re-upload
• Support Thread/Album
• No database

⚠️ **Cara pakai:**
1. Forward media dari channel terbatas
2. Bot akan proses otomatis
3. Hasil bisa di-share bebas!

📊 **Status Anda:** /status
"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ])
    await message.reply_text(text, reply_markup=keyboard)

@app.on_message(filters.command("status"))
async def status_cmd(client, message: Message):
    """Status command"""
    user_id = message.from_user.id
    data = get_status(user_id)
    
    await message.reply_text(f"""
📊 **Status Anda**
├ Downloads: {data['downloads']}
├ Threads: {data['threads']}
├ Status: {data['status']}
└ Last Active: {data['last_seen'].strftime('%H:%M:%S')}

💡 Forward media dari channel untuk memulai!
""")

@app.on_message(filters.command("help"))
async def help_cmd(client, message: Message):
    """Help command"""
    await message.reply_text("""
📖 **CARA PENGGUNAAN:**

**1. Single Media:**
• Forward 1 foto/video/file ke bot
• Tunggu proses download & upload
• Media baru tanpa restriction

**2. Thread/Album:**
• Forward album (multiple media) sekaligus
• Bot akan proses semua (max 10 item)
• Hasil dikirim sebagai media group

**3. Tips:**
• Bot harus bisa akses channel (public)
• Untuk private channel, add bot dulu
• File max 2GB (Telegram limit)

⚠️ **Disclaimer:** Gunakan untuk konten legal!
""")

@app.on_callback_query()
async def callback_handler(client, callback_query):
    """Handle callbacks"""
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    if data == "status":
        await callback_query.answer()
        await status_cmd(client, callback_query.message)
    elif data == "help":
        await callback_query.answer()
        await help_cmd(client, callback_query.message)

async def download_with_progress(client, message, progress_msg):
    """Download media dengan progress"""
    try:
        # Download ke folder /tmp (Railway ephemeral storage)
        download_path = await client.download_media(
            message,
            file_name=f"/tmp/dl_{message.id}_",
            progress=progress_callback,
            progress_args=(client, progress_msg)
        )
        return download_path
    except Exception as e:
        logger.error(f"Download error: {e}")
        await progress_msg.edit_text(f"❌ Error download: {str(e)}")
        return None

async def progress_callback(current, total, client, progress_msg):
    """Progress callback"""
    if total:
        percent = (current / total) * 100
        try:
            await progress_msg.edit_text(f"⏳ Downloading... {percent:.1f}%")
        except:
            pass

@app.on_message(filters.forwarded | filters.media)
async def media_handler(client, message: Message):
    """Handle media - inti bypass"""
    user_id = message.from_user.id
    user_data[user_id]["status"] = "processing"
    user_data[user_id]["last_seen"] = datetime.now()
    
    # Progress message
    progress_msg = await message.reply_text("⏳ Memproses media...")
    
    try:
        # Cek tipe media
        media_type = None
        file_path = None
        
        if message.photo:
            media_type = "photo"
        elif message.video:
            media_type = "video"
        elif message.document:
            media_type = "document"
        elif message.audio:
            media_type = "audio"
        elif message.voice:
            media_type = "voice"
        elif message.video_note:
            media_type = "video_note"
        elif message.animation:
            media_type = "animation"
        elif message.sticker:
            media_type = "sticker"
        
        if not media_type:
            await progress_msg.edit_text("❌ Tidak ada media yang ditemukan")
            return
        
        # Download
        await progress_msg.edit_text("⏳ Mendownload...")
        file_path = await download_with_progress(client, message, progress_msg)
        
        if not file_path:
            return
        
        # Upload ulang (bypass restriction)
        await progress_msg.edit_text("📤 Mengupload ulang...")
        
        caption = message.caption or ""
        footer = f"\n\n📥 Unlocked via Bot | {datetime.now().strftime('%Y-%m-%d')}"
        new_caption = caption + footer if caption else footer.strip()
        
        # Send berdasarkan tipe
        if media_type == "photo":
            await client.send_photo(
                message.chat.id,
                photo=file_path,
                caption=new_caption
            )
        elif media_type == "video":
            await client.send_video(
                message.chat.id,
                video=file_path,
                caption=new_caption,
                supports_streaming=True
            )
        elif media_type == "document":
            await client.send_document(
                message.chat.id,
                document=file_path,
                caption=new_caption
            )
        elif media_type == "audio":
            await client.send_audio(
                message.chat.id,
                audio=file_path,
                caption=new_caption
            )
        elif media_type == "voice":
            await client.send_voice(
                message.chat.id,
                voice=file_path
            )
        elif media_type == "video_note":
            await client.send_video_note(
                message.chat.id,
                video_note=file_path
            )
        elif media_type == "animation":
            await client.send_animation(
                message.chat.id,
                animation=file_path,
                caption=new_caption
            )
        elif media_type == "sticker":
            await client.send_sticker(
                message.chat.id,
                sticker=file_path
            )
        
        # Update stats
        user_data[user_id]["downloads"] += 1
        user_data[user_id]["status"] = "idle"
        
        # Cleanup
        try:
            os.remove(file_path)
        except:
            pass
        
        await progress_msg.edit_text("✅ **Berhasil!** Media sudah bisa di-share.")
        
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await progress_msg.edit_text("⏳ Rate limit, mencoba lagi...")
    except Exception as e:
        logger.error(f"Error: {e}")
        await progress_msg.edit_text(f"❌ Error: {str(e)}")
        user_data[user_id]["status"] = "error"

# Thread handling sederhana
thread_buffer = {}

@app.on_message(filters.media & ~filters.forwarded)
async def thread_handler(client, message: Message):
    """Handle media group (thread/album)"""
    if message.media_group_id:
        group_id = message.media_group_id
        
        if group_id not in thread_buffer:
            thread_buffer[group_id] = []
            # Tunggu 2 detik untuk kumpulkan semua
            await asyncio.sleep(2)
        
        thread_buffer[group_id].append(message)
        
        # Proses jika ini pesan terakhir (heuristic)
        if len(thread_buffer[group_id]) >= 2:  # Minimal 2 untuk thread
            await process_thread(client, group_id)

async def process_thread(client, group_id):
    """Process thread media"""
    messages = thread_buffer.get(group_id, [])
    if not messages:
        return
    
    user_id = messages[0].from_user.id
    status_msg = await messages[0].reply_text(f"🧵 Thread: {len(messages)} items")
    
    success = 0
    for msg in messages:
        try:
            file_path = await client.download_media(msg, file_name=f"/tmp/thread_{msg.id}_")
            if file_path:
                caption = msg.caption or ""
                footer = f"\n📥 Thread {success+1}/{len(messages)}"
                
                if msg.photo:
                    await client.send_photo(msg.chat.id, file_path, caption=caption+footer)
                elif msg.video:
                    await client.send_video(msg.chat.id, file_path, caption=caption+footer)
                
                os.remove(file_path)
                success += 1
                await asyncio.sleep(0.5)  # Rate limit
        except Exception as e:
            logger.error(f"Thread error: {e}")
    
    user_data[user_id]["threads"] += 1
    await status_msg.edit_text(f"✅ Thread selesai: {success}/{len(messages)} berhasil")
    
    del thread_buffer[group_id]

@app.on_message(filters.text & filters.private)
async def text_handler(client, message: Message):
    """Handle text non-command"""
    if not message.text.startswith('/'):
        await message.reply_text("""
ℹ️ Kirimkan **media** atau **forward** dari channel terbatas.

📌 Command: /start | /status | /help
""")

def main():
    """Main"""
    logger.info("🚂 Starting Railway Bot...")
    app.run()

if __name__ == "__main__":
    main()
