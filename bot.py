"""
Telegram Media Downloader Bot - Stabil Version
Menggunakan User Client saja (lebih powerful untuk akses channel)
"""

import os
import asyncio
import logging
import re
from datetime import datetime
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import (
    FloodWait, ChannelInvalid, ChannelPrivate, 
    MessageIdInvalid, PeerIdInvalid, PhotoExtInvalid,
    AuthKeyUnregistered
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
STRING_SESSION = os.getenv("STRING_SESSION", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")  # Optional, untuk bot commands

if not all([API_ID, API_HASH, STRING_SESSION]):
    raise ValueError("API_ID, API_HASH, STRING_SESSION wajib diisi!")

# Inisialisasi User Client (utama)
app = Client(
    "media_downloader",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=STRING_SESSION,
    parse_mode=ParseMode.MARKDOWN,
    no_updates=False  # Wajib False untuk receive updates
)

# Storage
user_data = {}

# Regex patterns
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
    
    me = await client.get_me()
    
    text = f"""
👋 **Halo {message.from_user.first_name}!**

🤖 **Media Downloader Bot**
👤 **Mode:** User Account (@{me.username})

✨ **Fitur:**
• Bypass **NO FORWARD** restriction
• Download dari **link channel** (t.me/c/xxx)
• Ambil semua media dalam **thread/album**
• Re-upload tanpa restriction

⚠️ **Cara pakai:**
1. Copy link dari channel (t.me/c/... atau t.me/channel/...)
2. Kirim link ke bot ini
3. Bot akan download & upload ulang
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
    me = await client.get_me()
    
    await message.reply_text(f"""
📊 **Status Anda**
├ Mode: `User Account (@{me.username})`
├ Downloads: {data['downloads']}
├ Threads: {data['threads']}
├ Status: {data['status']}
└ Last Active: {data['last_seen'].strftime('%H:%M:%S')}

💡 Kirim link channel untuk download!
""")

@app.on_message(filters.command("help"))
async def help_cmd(client, message: Message):
    await message.reply_text("""
📖 **CARA PENGGUNAAN:**

**1. Copy Link dari Channel:**
• Di channel dengan "No Forward", tap pesan
• Pilih **Copy Link** (bukan Forward)
• Contoh: `https://t.me/c/123456789/42`

**2. Kirim ke Bot:**
• Paste link ke bot ini
• Bot akan proses otomatis

**3. Hasil:**
• Media baru tanpa restriction
• Bisa di-share ke mana saja!

⚠️ **CATATAN:**
• Bot ini berjalan sebagai **User Account** (bukan Bot API)
• Bisa akses semua channel yang Anda join
• Lebih powerful dari Bot API biasa
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

async def download_media(client, message, file_path):
    """Download dengan retry"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return await client.download_media(message, file_name=file_path)
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            await asyncio.sleep(1)
    return None

async def upload_media(client, chat_id, file_path, caption, media_type):
    """Upload dengan fallback ke document"""
    try:
        if media_type == "photo":
            try:
                await client.send_photo(chat_id, photo=file_path, caption=caption)
            except PhotoExtInvalid:
                # Fallback ke document
                await client.send_document(chat_id, document=file_path, caption=caption + "\n\n_(Sent as document)_")
        elif media_type == "video":
            await client.send_video(chat_id, video=file_path, caption=caption, supports_streaming=True)
        elif media_type == "document":
            await client.send_document(chat_id, document=file_path, caption=caption)
        elif media_type == "audio":
            await client.send_audio(chat_id, audio=file_path, caption=caption)
        elif media_type == "voice":
            await client.send_voice(chat_id, voice=file_path)
        elif media_type == "video_note":
            await client.send_video_note(chat_id, video_note=file_path)
        elif media_type == "animation":
            await client.send_animation(chat_id, animation=file_path, caption=caption)
        elif media_type == "sticker":
            await client.send_sticker(chat_id, sticker=file_path)
    except Exception as e:
        # Last resort: kirim sebagai document
        logger.error(f"Upload error: {e}, trying as document")
        await client.send_document(chat_id, document=file_path, caption=caption)

async def process_single_media(client, message, target_msg, user_id, progress_msg):
    """Proses single media"""
    try:
        # Detect media type
        media_type = None
        file_ext = "bin"
        
        if target_msg.photo:
            media_type = "photo"
            file_ext = "jpg"
        elif target_msg.video:
            media_type = "video"
            file_ext = "mp4"
        elif target_msg.document:
            media_type = "document"
            doc = target_msg.document
            file_ext = doc.file_name.split('.')[-1] if doc.file_name and '.' in doc.file_name else "bin"
        elif target_msg.audio:
            media_type = "audio"
            file_ext = "mp3"
        elif target_msg.voice:
            media_type = "voice"
            file_ext = "ogg"
        elif target_msg.video_note:
            media_type = "video_note"
            file_ext = "mp4"
        elif target_msg.animation:
            media_type = "animation"
            file_ext = "mp4"
        elif target_msg.sticker:
            media_type = "sticker"
            file_ext = "webp"
        else:
            await progress_msg.edit_text("❌ Tipe media tidak didukung")
            return
        
        # Download
        await progress_msg.edit_text("⏳ Mendownload...")
        os.makedirs("/tmp", exist_ok=True)
        
        temp_path = f"/tmp/dl_{user_id}_{target_msg.id}"
        file_path = f"{temp_path}.{file_ext}"
        
        downloaded = await download_media(client, target_msg, temp_path)
        
        if not downloaded:
            await progress_msg.edit_text("❌ Gagal download")
            return
        
        # Rename kalau perlu
        if downloaded != file_path and os.path.exists(downloaded):
            try:
                os.rename(downloaded, file_path)
            except:
                file_path = downloaded
        
        # Upload
        await progress_msg.edit_text("📤 Mengupload ulang...")
        
        caption = target_msg.caption or ""
        footer = f"\n\n📥 Unlocked via Bot | {datetime.now().strftime('%Y-%m-%d')}"
        new_caption = caption + footer if caption else footer.strip()
        
        await upload_media(client, message.chat.id, file_path, new_caption, media_type)
        
        # Cleanup
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            if os.path.exists(downloaded) and downloaded != file_path:
                os.remove(downloaded)
        except:
            pass
        
        user_data[user_id]["downloads"] += 1
        user_data[user_id]["status"] = "idle"
        
        await progress_msg.edit_text("✅ **Berhasil!** Media sudah bisa di-share.")
        
    except Exception as e:
        logger.error(f"Process error: {e}")
        await progress_msg.edit_text(f"❌ Error: {str(e)}")
        user_data[user_id]["status"] = "error"

async def process_thread(client, message, first_msg, user_id, progress_msg):
    """Proses thread/album"""
    await progress_msg.edit_text("🧵 **Thread terdeteksi!** Mengambil semua media...")
    
    try:
        chat_id = first_msg.chat.id
        media_group_id = first_msg.media_group_id
        
        # Get messages around
        start_id = max(1, first_msg.id - 20)
        all_msgs = await client.get_messages(chat_id, list(range(start_id, first_msg.id + 20)))
        
        if not isinstance(all_msgs, list):
            all_msgs = [all_msgs]
        
        # Filter thread
        thread_msgs = [m for m in all_msgs if m and m.media_group_id == media_group_id]
        
        if not thread_msgs:
            thread_msgs = [first_msg]
        
        await progress_msg.edit_text(f"🧵 Thread: {len(thread_msgs)} media")
        
        # Download all
        downloaded_files = []
        for idx, msg in enumerate(thread_msgs, 1):
            await progress_msg.edit_text(f"⏳ Download {idx}/{len(thread_msgs)}...")
            
            ext = "jpg" if msg.photo else "mp4" if msg.video else "bin"
            fpath = f"/tmp/thread_{msg.id}.{ext}"
            
            temp = f"/tmp/thread_{msg.id}"
            dl = await download_media(client, msg, temp)
            
            if dl:
                if os.path.exists(dl):
                    try:
                        os.rename(dl, fpath)
                        dl = fpath
                    except:
                        fpath = dl
                
                downloaded_files.append({
                    'path': fpath,
                    'caption': msg.caption or "",
                    'type': 'photo' if msg.photo else 'video' if msg.video else 'doc'
                })
            
            await asyncio.sleep(0.3)
        
        # Upload all
        await progress_msg.edit_text(f"📤 Uploading {len(downloaded_files)} media...")
        
        for idx, item in enumerate(downloaded_files, 1):
            cap = item['caption'] + f"\n\n📥 Thread {idx}/{len(downloaded_files)}"
            
            try:
                if item['type'] == 'photo':
                    await client.send_photo(message.chat.id, photo=item['path'], caption=cap)
                elif item['type'] == 'video':
                    await client.send_video(message.chat.id, video=item['path'], caption=cap)
                else:
                    await client.send_document(message.chat.id, document=item['path'], caption=cap)
            except PhotoExtInvalid:
                await client.send_document(message.chat.id, document=item['path'], caption=cap)
            
            try:
                os.remove(item['path'])
            except:
                pass
            
            await asyncio.sleep(0.5)
        
        user_data[user_id]["threads"] += 1
        user_data[user_id]["downloads"] += len(downloaded_files)
        user_data[user_id]["status"] = "idle"
        
        await progress_msg.edit_text(f"✅ **Thread selesai!** {len(downloaded_files)} media berhasil")
        
    except Exception as e:
        logger.error(f"Thread error: {e}")
        await progress_msg.edit_text(f"❌ Error: {str(e)}")
        user_data[user_id]["status"] = "error"

@app.on_message(filters.text & filters.private)
async def text_handler(client, message: Message):
    """Handle text"""
    text = message.text.strip()
    user_id = message.from_user.id
    
    # Skip commands
    if text.startswith('/'):
        return
    
    # Check private link
    private_match = CHANNEL_LINK_PATTERN.match(text)
    if private_match:
        channel_id = int(private_match.group(1))
        msg_id = int(private_match.group(2))
        
        if user_id not in user_data:
            user_data[user_id] = {"downloads": 0, "threads": 0, "last_seen": datetime.now(), "status": "idle"}
        
        progress_msg = await message.reply_text("⏳ Mengambil pesan...")
        user_data[user_id]["status"] = "processing"
        
        try:
            chat_id = f"-100{channel_id}"
            logger.info(f"Getting message from {chat_id}, msg_id: {msg_id}")
            
            target_msg = await client.get_messages(chat_id, msg_id)
            
            if not target_msg:
                await progress_msg.edit_text("❌ Pesan tidak ditemukan")
                return
            
            if not target_msg.media:
                await progress_msg.edit_text("❌ Pesan tidak berisi media")
                return
            
            if target_msg.media_group_id:
                await process_thread(client, message, target_msg, user_id, progress_msg)
            else:
                await process_single_media(client, message, target_msg, user_id, progress_msg)
            
        except PeerIdInvalid:
            await progress_msg.edit_text("""
❌ **PEER_ID_INVALID**

Akun Anda belum join channel ini atau channel tidak ditemukan.

**Solusi:**
• Pastikan Anda sudah join channel di Telegram
• Coba buka link di browser/tele dulu
• Lalu coba lagi
""")
        except ChannelPrivate:
            await progress_msg.edit_text("""
❌ **Channel Private**

Anda belum join channel ini.

**Solusi:**
Join channel dulu, lalu coba lagi.
""")
        except Exception as e:
            logger.error(f"Error: {e}")
            await progress_msg.edit_text(f"❌ Error: {str(e)}")
        return
    
    # Check public link
    public_match = PUBLIC_LINK_PATTERN.match(text)
    if public_match:
        username = public_match.group(1)
        msg_id = int(public_match.group(2))
        
        if username.lower() in ['botfather', 'telegram', 'stickers']:
            return
        
        if user_id not in user_data:
            user_data[user_id] = {"downloads": 0, "threads": 0, "last_seen": datetime.now(), "status": "idle"}
        
        progress_msg = await message.reply_text("⏳ Mengambil dari link...")
        user_data[user_id]["status"] = "processing"
        
        try:
            chat_id = f"@{username}"
            target_msg = await client.get_messages(chat_id, msg_id)
            
            if not target_msg or not target_msg.media:
                await progress_msg.edit_text("❌ Tidak ada media")
                return
            
            if target_msg.media_group_id:
                await process_thread(client, message, target_msg, user_id, progress_msg)
            else:
                await process_single_media(client, message, target_msg, user_id, progress_msg)
            
        except Exception as e:
            await progress_msg.edit_text(f"❌ Error: {str(e)}")
        return
    
    # Not a link
    await message.reply_text("""
ℹ️ **Kirimkan link channel:**

• Private: `https://t.me/c/123456/1`
• Public: `https://t.me/channel/5`

📌 Command: /start | /status | /help
""")

async def main():
    """Main"""
    os.makedirs("/tmp", exist_ok=True)
    
    logger.info("🚀 Starting User Client...")
    await app.start()
    
    me = await app.get_me()
    logger.info(f"✅ Started as: {me.first_name} (@{me.username})")
    
    # Keep running
    await idle()
    
    await app.stop()

if __name__ == "__main__":
    app.run(main())
