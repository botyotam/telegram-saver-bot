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
from pyrogram.errors import (
    FloodWait, ChannelInvalid, ChannelPrivate, 
    MessageIdInvalid, PeerIdInvalid, PhotoExtInvalid
)
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

💡 Forward media dari channel untuk memulai!
""")

@app.on_message(filters.command("help"))
async def help_cmd(client, message: Message):
    await message.reply_text("""
📖 **CARA PENGGUNAAN:**

**1. Via Forward (REKOMENDASI - Paling Mudah):**
• Forward media dari channel ke bot
• Tunggu proses download & upload
• Media baru tanpa restriction

**2. Via Link:**
• Kirim link: `https://t.me/c/123456/3` (private)
• Atau: `https://t.me/channelname/5` (public)
• ⚠️ **Bot harus sudah join channel dulu!**

**3. Thread/Album:**
• Forward album sekaligus
• Bot proses semua media

⚠️ **Catatan Penting:**
• Untuk link private channel, **bot harus jadi member**
• Kalau belum, **forward saja** (lebih mudah)
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

async def process_and_upload(client, message, target_msg, user_id, progress_msg):
    """Download dan upload dengan fix PHOTO_EXT_INVALID"""
    try:
        # Cek tipe media
        media_type = None
        file_name = None
        
        if target_msg.photo:
            media_type = "photo"
            # FIX: Tentukan ekstensi yang benar untuk foto
            file_name = f"photo_{target_msg.id}.jpg"
        elif target_msg.video:
            media_type = "video"
            file_name = f"video_{target_msg.id}.mp4"
        elif target_msg.document:
            media_type = "document"
            # Gunakan nama file asli kalau ada
            doc = target_msg.document
            file_name = doc.file_name if doc.file_name else f"file_{target_msg.id}"
        elif target_msg.audio:
            media_type = "audio"
            file_name = f"audio_{target_msg.id}.mp3"
        elif target_msg.voice:
            media_type = "voice"
            file_name = f"voice_{target_msg.id}.ogg"
        elif target_msg.video_note:
            media_type = "video_note"
            file_name = f"video_note_{target_msg.id}.mp4"
        elif target_msg.animation:
            media_type = "animation"
            file_name = f"animation_{target_msg.id}.mp4"
        elif target_msg.sticker:
            media_type = "sticker"
            file_name = f"sticker_{target_msg.id}.webp"
        else:
            await progress_msg.edit_text("❌ Tipe media tidak didukung")
            return
        
        if not media_type:
            await progress_msg.edit_text("❌ Tidak ada media")
            return
        
        # Download ke path dengan ekstensi benar
        await progress_msg.edit_text("⏳ Mendownload...")
        
        # FIX: Pastikan folder /tmp ada
        os.makedirs("/tmp", exist_ok=True)
        
        file_path = f"/tmp/{file_name}"
        
        # Download dengan progress
        downloaded_path = await client.download_media(
            target_msg,
            file_name=file_path,
            progress=progress_callback,
            progress_args=(client, progress_msg)
        )
        
        if not downloaded_path or not os.path.exists(downloaded_path):
            await progress_msg.edit_text("❌ Gagal download file")
            return
        
        # FIX: Rename kalau ekstensi tidak sesuai untuk foto
        if media_type == "photo":
            # Pastikan ekstensi .jpg untuk foto
            if not downloaded_path.endswith(('.jpg', '.jpeg', '.png')):
                new_path = downloaded_path + ".jpg"
                os.rename(downloaded_path, new_path)
                downloaded_path = new_path
        
        # Upload ulang
        await progress_msg.edit_text("📤 Mengupload ulang...")
        
        caption = target_msg.caption or ""
        footer = f"\n\n📥 Unlocked via Bot | {datetime.now().strftime('%Y-%m-%d')}"
        new_caption = caption + footer if caption else footer.strip()
        
        # FIX: Kirim dengan cara yang berbeda untuk hindari PHOTO_EXT_INVALID
        try:
            if media_type == "photo":
                # FIX: Buka file sebagai binary dan kirim
                with open(downloaded_path, 'rb') as photo_file:
                    await client.send_photo(
                        message.chat.id,
                        photo=photo_file,
                        caption=new_caption
                    )
            elif media_type == "video":
                with open(downloaded_path, 'rb') as video_file:
                    await client.send_video(
                        message.chat.id,
                        video=video_file,
                        caption=new_caption,
                        supports_streaming=True
                    )
            elif media_type == "document":
                with open(downloaded_path, 'rb') as doc_file:
                    await client.send_document(
                        message.chat.id,
                        document=doc_file,
                        caption=new_caption
                    )
            elif media_type == "audio":
                with open(downloaded_path, 'rb') as audio_file:
                    await client.send_audio(
                        message.chat.id,
                        audio=audio_file,
                        caption=new_caption
                    )
            elif media_type == "voice":
                with open(downloaded_path, 'rb') as voice_file:
                    await client.send_voice(
                        message.chat.id,
                        voice=voice_file
                    )
            elif media_type == "video_note":
                with open(downloaded_path, 'rb') as vn_file:
                    await client.send_video_note(
                        message.chat.id,
                        video_note=vn_file
                    )
            elif media_type == "animation":
                with open(downloaded_path, 'rb') as anim_file:
                    await client.send_animation(
                        message.chat.id,
                        animation=anim_file,
                        caption=new_caption
                    )
            elif media_type == "sticker":
                with open(downloaded_path, 'rb') as sticker_file:
                    await client.send_sticker(
                        message.chat.id,
                        sticker=sticker_file
                    )
        except PhotoExtInvalid:
            # FIX: Kalau masih error, kirim sebagai document saja
            await progress_msg.edit_text("⚠️ Mengirim sebagai document...")
            with open(downloaded_path, 'rb') as doc_file:
                await client.send_document(
                    message.chat.id,
                    document=doc_file,
                    caption=new_caption + "\n\n_(Sent as document due to format issue)_"
                )
        
        # Cleanup
        try:
            if os.path.exists(downloaded_path):
                os.remove(downloaded_path)
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
        
        user_data[user_id]["downloads"] += 1
        user_data[user_id]["status"] = "idle"
        
        await progress_msg.edit_text("✅ **Berhasil!** Media sudah bisa di-share.")
        
    except Exception as e:
        logger.error(f"Process error: {e}")
        await progress_msg.edit_text(f"❌ Error: {str(e)}")
        user_data[user_id]["status"] = "error"

@app.on_message(filters.forwarded | filters.media)
async def media_handler(client, message: Message):
    """Handle forward/media - CARA PALING MUDAH & AMAN"""
    user_id = message.from_user.id
    
    if user_id not in user_data:
        user_data[user_id] = {"downloads": 0, "threads": 0, "last_seen": datetime.now(), "status": "idle"}
    
    user_data[user_id]["status"] = "processing"
    progress_msg = await message.reply_text("⏳ Memproses media...")
    
    # Langsung proses pesan yang diforward (sudah punya akses)
    await process_and_upload(client, message, message, user_id, progress_msg)

@app.on_message(filters.text & filters.private)
async def text_handler(client, message: Message):
    """Handle text - cek link atau command"""
    text = message.text.strip()
    user_id = message.from_user.id
    
    # Cek link private channel (t.me/c/...)
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
            
            # FIX: Coba ambil info channel dulu untuk "meet the peer"
            try:
                chat = await client.get_chat(chat_id)
                logger.info(f"Found chat: {chat.title}")
            except Exception as e:
                logger.warning(f"Cannot get chat info: {e}")
            
            target_msg = await client.get_messages(chat_id, msg_id)
            
            if not target_msg:
                await progress_msg.edit_text("❌ Pesan tidak ditemukan")
                return
            
            if not target_msg.media:
                await progress_msg.edit_text("❌ Pesan ini tidak berisi media")
                return
            
            await process_and_upload(client, message, target_msg, user_id, progress_msg)
            
        except PeerIdInvalid:
            await progress_msg.edit_text("""
❌ **PEER_ID_INVALID - Bot Belum Kenal Channel Ini**

**Solusi:**
1️⃣ **Forward media saja** (lebih mudah, tidak perlu setup)
2️⃣ Atau add bot ke channel sebagai member, lalu coba lagi

💡 **Saran:** Gunakan cara **Forward** saja, lebih simpel!
""")
        except ChannelPrivate:
            await progress_msg.edit_text("""
❌ **Channel Private - Bot Tidak Punya Akses**

**Solusi:**
1️⃣ **Forward media langsung** ke bot (REKOMENDASI)
2️⃣ Atau add bot ke channel sebagai admin/member

💡 **Saran:** Forward saja, tidak perlu repot add bot!
""")
        except Exception as e:
            logger.error(f"Link error: {e}")
            await progress_msg.edit_text(f"❌ Error: {str(e)}")
        return
    
    # Cek link public
    public_match = PUBLIC_LINK_PATTERN.match(text)
    if public_match:
        username = public_match.group(1)
        msg_id = int(public_match.group(2))
        
        # Skip kalau ini command bot (t.me/botname/start)
        if username.lower() in ['botfather', 'telegram', 'stickers', 'telegraph']:
            return
        
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
            
            await process_and_upload(client, message, target_msg, user_id, progress_msg)
            
        except Exception as e:
            await progress_msg.edit_text(f"❌ Error: {str(e)}")
        return
    
    # Bukan link, bukan command
    if not text.startswith('/'):
        await message.reply_text("""
ℹ️ **Kirimkan:**
• **Forward media** dari channel (PALING MUDAH), atau  
• **Link channel** (contoh: `https://t.me/c/123456/3`)

📌 Command: /start | /status | /help

💡 **Tips:** Forward lebih mudah dan tidak perlu setup!
""")

def main():
    logger.info("🚂 Starting Railway Bot...")
    # Buat folder downloads kalau belum ada
    os.makedirs("/tmp", exist_ok=True)
    app.run()

if __name__ == "__main__":
    main()
