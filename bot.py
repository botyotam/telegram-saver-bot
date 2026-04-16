"""
Telegram Media Downloader Bot for Railway
Bypass content sharing restrictions
Support: Forward media + Channel links
"""

import os
import asyncio
import logging
import re
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, ChannelInvalid, ChannelPrivate, MessageIdInvalid
from pyrogram.enums import ParseMode

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment Variables
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not all([API_ID, API_HASH, BOT_TOKEN]):
    logger.error("❌ Environment variables belum di-set!")
    raise ValueError("API_ID, API_HASH, BOT_TOKEN wajib diisi")

# Inisialisasi Client
app = Client(
    "railway_media_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.MARKDOWN,
    no_updates=False
)

# Storage
user_data = {}

# Regex patterns untuk link
CHANNEL_LINK_PATTERN = re.compile(r'https?://t\.me/c/(\d+)/(\d+)')
PUBLIC_LINK_PATTERN = re.compile(r'https?://t\.me/(\w+)/(\d+)')

def get_status(user_id):
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
• Download dari **forward** atau **link**
• Support Thread/Album
• No database

⚠️ **Cara pakai:**
1. **Forward** media dari channel, atau
2. **Kirim link** (contoh: `https://t.me/c/123/1`)
3. Bot akan proses otomatis
4. Hasil bisa di-share bebas!

📊 **Status:** /status
"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ])
    await message.reply_text(text, reply_markup=keyboard)

@app.on_message(filters.command("status"))
async def status_cmd(client, message: Message):
    user_id = message.from_user.id
    data = get_status(user_id)
    
    await message.reply_text(f"""
📊 **Status Anda**
├ Downloads: {data['downloads']}
├ Threads: {data['threads']}
├ Status: {data['status']}
└ Last Active: {data['last_seen'].strftime('%H:%M:%S')}

💡 Forward media atau kirim link untuk memulai!
""")

@app.on_message(filters.command("help"))
async def help_cmd(client, message: Message):
    await message.reply_text("""
📖 **CARA PENGGUNAAN:**

**1. Via Forward (Rekomendasi):**
• Forward media dari channel ke bot
• Tunggu proses download & upload
• Media baru tanpa restriction

**2. Via Link:**
• Kirim link: `https://t.me/c/123456/3` (private)
• Atau: `https://t.me/channelname/5` (public)
• Bot akan ambil & upload ulang

**3. Thread/Album:**
• Forward album sekaligus
• Bot proses semua media

⚠️ **Catatan:**
• Bot harus bisa akses channel
• Untuk private channel, add bot dulu
• File max 2GB
""")

@app.on_callback_query()
async def callback_handler(client, callback_query):
    data = callback_query.data
    
    if data == "status":
        await callback_query.answer()
        await status_cmd(client, callback_query.message)
    elif data == "help":
        await callback_query.answer()
        await help_cmd(client, callback_query.message)

async def progress_callback(current, total, client, progress_msg):
    if total:
        percent = (current / total) * 100
        try:
            await progress_msg.edit_text(f"⏳ Downloading... {percent:.1f}%")
        except:
            pass

async def process_media(client, message, progress_msg, target_msg, user_id):
    """Proses media (dipakai oleh forward dan link)"""
    try:
        # Cek tipe media
        media_type = None
        if target_msg.photo: media_type = "photo"
        elif target_msg.video: media_type = "video"
        elif target_msg.document: media_type = "document"
        elif target_msg.audio: media_type = "audio"
        elif target_msg.voice: media_type = "voice"
        elif target_msg.video_note: media_type = "video_note"
        elif target_msg.animation: media_type = "animation"
        elif target_msg.sticker: media_type = "sticker"
        
        if not media_type:
            await progress_msg.edit_text("❌ Tidak ada media")
            return
        
        # Download
        await progress_msg.edit_text("⏳ Mendownload...")
        file_path = await client.download_media(
            target_msg,
            file_name=f"/tmp/dl_{user_id}_{target_msg.id}_",
            progress=progress_callback,
            progress_args=(client, progress_msg)
        )
        
        if not file_path:
            await progress_msg.edit_text("❌ Gagal download")
            return
        
        # Upload
        await progress_msg.edit_text("📤 Mengupload ulang...")
        
        caption = target_msg.caption or ""
        footer = f"\n\n📥 Unlocked via Bot | {datetime.now().strftime('%Y-%m-%d')}"
        new_caption = caption + footer if caption else footer.strip()
        
        # Send berdasarkan tipe
        if media_type == "photo":
            await client.send_photo(message.chat.id, file_path, caption=new_caption)
        elif media_type == "video":
            await client.send_video(message.chat.id, file_path, caption=new_caption, supports_streaming=True)
        elif media_type == "document":
            await client.send_document(message.chat.id, file_path, caption=new_caption)
        elif media_type == "audio":
            await client.send_audio(message.chat.id, file_path, caption=new_caption)
        elif media_type == "voice":
            await client.send_voice(message.chat.id, voice=file_path)
        elif media_type == "video_note":
            await client.send_video_note(message.chat.id, video_note=file_path)
        elif media_type == "animation":
            await client.send_animation(message.chat.id, animation=file_path, caption=new_caption)
        elif media_type == "sticker":
            await client.send_sticker(message.chat.id, sticker=file_path)
        
        # Cleanup
        try:
            os.remove(file_path)
        except:
            pass
        
        user_data[user_id]["downloads"] += 1
        user_data[user_id]["status"] = "idle"
        
        await progress_msg.edit_text("✅ **Berhasil!** Media sudah bisa di-share.")
        
    except Exception as e:
        logger.error(f"Process error: {e}")
        await progress_msg.edit_text(f"❌ Error: {str(e)}")
        user_data[user_id]["status"] = "error"

@app.on_message(filters.forwarded | filters.media)
async def media_handler(client, message: Message):
    """Handle forward/media"""
    user_id = message.from_user.id
    
    if user_id not in user_data:
        user_data[user_id] = {"downloads": 0, "threads": 0, "last_seen": datetime.now(), "status": "idle"}
    
    user_data[user_id]["status"] = "processing"
    progress_msg = await message.reply_text("⏳ Memproses media...")
    
    await process_media(client, message, progress_msg, message, user_id)

@app.on_message(filters.text & filters.private)
async def text_handler(client, message: Message):
    """Handle text - cek link atau command"""
    text = message.text.strip()
    user_id = message.from_user.id
    
    # Cek link private channel
    private_match = CHANNEL_LINK_PATTERN.match(text)
    if private_match:
        channel_id = int(private_match.group(1))
        msg_id = int(private_match.group(2))
        
        if user_id not in user_data:
            user_data[user_id] = {"downloads": 0, "threads": 0, "last_seen": datetime.now(), "status": "idle"}
        
        progress_msg = await message.reply_text("⏳ Mengambil dari link channel...")
        user_data[user_id]["status"] = "fetching"
        
        try:
            # Format channel ID untuk private (-100 prefix)
            chat_id = f"-100{channel_id}"
            target_msg = await client.get_messages(chat_id, msg_id)
            
            if not target_msg or not target_msg.media:
                await progress_msg.edit_text("❌ Pesan tidak ditemukan atau tidak ada media")
                return
            
            await process_media(client, message, progress_msg, target_msg, user_id)
            
        except ChannelPrivate:
            await progress_msg.edit_text("""
❌ **Channel Private / Bot Tidak Punya Akses**

**Solusi:**
1. Add bot ke channel sebagai member/admin
2. Atau forward media langsung (bukan link)
""")
        except Exception as e:
            await progress_msg.edit_text(f"❌ Error: {str(e)}")
        return
    
    # Cek link public
    public_match = PUBLIC_LINK_PATTERN.match(text)
    if public_match:
        username = public_match.group(1)
        msg_id = int(public_match.group(2))
        
        if user_id not in user_data:
            user_data[user_id] = {"downloads": 0, "threads": 0, "last_seen": datetime.now(), "status": "idle"}
        
        progress_msg = await message.reply_text("⏳ Mengambil dari link...")
        user_data[user_id]["status"] = "fetching"
        
        try:
            chat_id = f"@{username}"
            target_msg = await client.get_messages(chat_id, msg_id)
            
            if not target_msg or not target_msg.media:
                await progress_msg.edit_text("❌ Pesan tidak ditemukan atau tidak ada media")
                return
            
            await process_media(client, message, progress_msg, target_msg, user_id)
            
        except Exception as e:
            await progress_msg.edit_text(f"❌ Error: {str(e)}")
        return
    
    # Bukan link, bukan command
    if not text.startswith('/'):
        await message.reply_text("""
ℹ️ **Kirimkan:**
• **Forward media** dari channel, atau  
• **Link channel** (contoh: `https://t.me/c/123456/3`)

📌 Command: /start | /status | /help
""")

def main():
    logger.info("🚂 Starting Railway Bot...")
    app.run()

if __name__ == "__main__":
    main()
