"""
Telegram Media Downloader Bot for Railway
Bypass content sharing restrictions using User Account + Bot
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
    MessageIdInvalid, PeerIdInvalid, PhotoExtInvalid,
    UsernameNotOccupied, InviteHashExpired, AuthKeyUnregistered
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
STRING_SESSION = os.getenv("STRING_SESSION", "")

if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("API_ID, API_HASH, BOT_TOKEN wajib diisi")

# Inisialisasi Bot (untuk interaksi user)
bot = Client(
    "railway_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.MARKDOWN,
    no_updates=False
)

# Inisialisasi User Client (untuk akses channel private)
user_client = None
if STRING_SESSION:
    user_client = Client(
        "railway_user",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=STRING_SESSION,
        parse_mode=ParseMode.MARKDOWN,
        no_updates=True  # Tidak perlu listen updates, hanya untuk download
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

@bot.on_message(filters.command("start"))
async def start_cmd(client, message: Message):
    user_id = message.from_user.id
    user_data[user_id] = {
        "downloads": 0,
        "threads": 0,
        "last_seen": datetime.now(),
        "status": "idle"
    }
    
    has_string = "✅ Aktif" if STRING_SESSION else "❌ Tidak aktif"
    
    text = f"""
👋 **Halo {message.from_user.first_name}!**

🤖 **Media Downloader Bot**

🔐 **String Session:** {has_string}

✨ **Fitur:**
• Bypass **NO FORWARD** restriction
• Download dari **link channel** (t.me/c/xxx)
• Ambil semua media dalam **thread/album**
• Re-upload tanpa restriction

⚠️ **Cara pakai:**
1. Copy link dari channel (t.me/c/... atau t.me/channel/...)
2. Kirim link ke bot
3. Bot akan download & upload ulang
4. Hasil bisa di-share bebas!

📊 **Status:** /status
"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ])
    await message.reply_text(text, reply_markup=keyboard)

@bot.on_message(filters.command("status"))
async def status_cmd(client, message: Message):
    user_id = message.from_user.id
    data = get_status(user_id)
    
    mode = "User+Bot" if STRING_SESSION else "Bot Only"
    
    await message.reply_text(f"""
📊 **Status Anda**
├ Mode: `{mode}`
├ Downloads: {data['downloads']}
├ Threads: {data['threads']}
├ Status: {data['status']}
└ Last Active: {data['last_seen'].strftime('%H:%M:%S')}

💡 Kirim link channel untuk download!
""")

@bot.on_message(filters.command("help"))
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

⚠️ **CATATAN PENTING:**
• Untuk channel private (t.me/c/...), **WAJIB** pakai String Session
• String Session = akun Telegram Anda (aman, hanya di server)

🔐 **Setup String Session:**
1. Jalankan generator di Termux/PC
2. Dapatkan session string
3. Tambah ke Railway Variables
""")

@bot.on_callback_query()
async def callback_handler(client, callback_query):
    data = callback_query.data
    if data == "status":
        await callback_query.answer()
        await status_cmd(client, callback_query.message)
    elif data == "help":
        await callback_query.answer()
        await help_cmd(client, callback_query.message)

async def ensure_user_client():
    """Pastikan user client terhubung"""
    global user_client
    if not user_client:
        return None
    
    if not user_client.is_connected:
        try:
            await user_client.connect()
            logger.info("✅ User client reconnected")
        except Exception as e:
            logger.error(f"❌ Failed to connect user client: {e}")
            return None
    
    return user_client

async def get_message_from_link(chat_id, message_id):
    """
    Ambil pesan menggunakan User Client (kalau ada) atau Bot Client
    """
    # Coba dengan User Client dulu (lebih powerful)
    uc = await ensure_user_client()
    if uc:
        try:
            # FIX: Pastikan chat_id dalam format benar
            if isinstance(chat_id, str) and chat_id.startswith('-100'):
                # Sudah benar
                pass
            elif isinstance(chat_id, int) and chat_id > 0:
                # Convert ke format channel
                chat_id = f"-100{chat_id}"
            
            logger.info(f"Trying user client: {chat_id}, msg: {message_id}")
            msg = await uc.get_messages(chat_id, message_id)
            if msg:
                logger.info("✅ User client success")
                return msg
        except Exception as e:
            logger.warning(f"User client failed: {e}")
    
    # Fallback ke Bot Client
    try:
        logger.info(f"Trying bot client: {chat_id}, msg: {message_id}")
        msg = await bot.get_messages(chat_id, message_id)
        logger.info("✅ Bot client success")
        return msg
    except Exception as e:
        logger.error(f"Bot client also failed: {e}")
        raise

async def download_with_client(message, file_path):
    """
    Download menggunakan client yang tepat
    """
    # Prioritaskan User Client
    uc = await ensure_user_client()
    if uc:
        try:
            return await uc.download_media(message, file_name=file_path)
        except Exception as e:
            logger.warning(f"User client download failed: {e}")
    
    # Fallback ke Bot
    return await bot.download_media(message, file_name=file_path)

async def process_single_media(message: Message, target_msg: Message, user_id: int, progress_msg: Message):
    """Proses single media dengan fix PHOTO_EXT_INVALID"""
    try:
        # Cek tipe media
        media_type = None
        file_ext = None
        
        if target_msg.photo:
            media_type = "photo"
            file_ext = "jpg"  # FIX: Force jpg untuk foto
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
        
        # FIX: Gunakan nama file sementara tanpa ekstensi dulu
        temp_path = f"/tmp/dl_{user_id}_{target_msg.id}"
        
        downloaded = await download_with_client(target_msg, temp_path)
        
        if not downloaded or not os.path.exists(downloaded):
            await progress_msg.edit_text("❌ Gagal download file")
            return
        
        # FIX: Rename dengan ekstensi yang benar
        final_path = f"{temp_path}.{file_ext}"
        try:
            os.rename(downloaded, final_path)
            downloaded = final_path
        except:
            pass  # Kalau gagal rename, pakai nama asli
        
        # Upload
        await progress_msg.edit_text("📤 Mengupload ulang...")
        
        caption = target_msg.caption or ""
        footer = f"\n\n📥 Unlocked via Bot | {datetime.now().strftime('%Y-%m-%d')}"
        new_caption = caption + footer if caption else footer.strip()
        
        # FIX: Kirim dengan cara yang lebih aman
        try:
            if media_type == "photo":
                # FIX: Kirim sebagai document kalau foto gagal
                try:
                    await bot.send_photo(message.chat.id, photo=downloaded, caption=new_caption)
                except PhotoExtInvalid:
                    logger.warning("PhotoExtInvalid, sending as document instead")
                    await bot.send_document(message.chat.id, document=downloaded, caption=new_caption + "\n\n_(Sent as document)_")
            elif media_type == "video":
                await bot.send_video(message.chat.id, video=downloaded, caption=new_caption, supports_streaming=True)
            elif media_type == "document":
                await bot.send_document(message.chat.id, document=downloaded, caption=new_caption)
            elif media_type == "audio":
                await bot.send_audio(message.chat.id, audio=downloaded, caption=new_caption)
            elif media_type == "voice":
                await bot.send_voice(message.chat.id, voice=downloaded)
            elif media_type == "video_note":
                await bot.send_video_note(message.chat.id, video_note=downloaded)
            elif media_type == "animation":
                await bot.send_animation(message.chat.id, animation=downloaded, caption=new_caption)
            elif media_type == "sticker":
                await bot.send_sticker(message.chat.id, sticker=downloaded)
        except Exception as upload_error:
            # Last resort: kirim sebagai document
            logger.error(f"Upload error: {upload_error}, trying as document")
            try:
                await bot.send_document(message.chat.id, document=downloaded, caption=new_caption)
            except Exception as e:
                await progress_msg.edit_text(f"❌ Upload gagal: {str(e)}")
                return
        
        # Cleanup
        try:
            if os.path.exists(downloaded):
                os.remove(downloaded)
            # Cleanup file sementara kalau ada
            if os.path.exists(temp_path) and temp_path != downloaded:
                os.remove(temp_path)
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
        
        user_data[user_id]["downloads"] += 1
        user_data[user_id]["status"] = "idle"
        
        await progress_msg.edit_text("✅ **Berhasil!** Media sudah bisa di-share.")
        
    except Exception as e:
        logger.error(f"Single media error: {e}")
        await progress_msg.edit_text(f"❌ Error: {str(e)}")
        user_data[user_id]["status"] = "error"

async def process_thread(message: Message, first_msg: Message, user_id: int, progress_msg: Message):
    """Proses thread/album - ambil semua media dalam grup"""
    await progress_msg.edit_text("🧵 **Thread terdeteksi!** Mengambil semua media...")
    
    try:
        chat_id = first_msg.chat.id if first_msg.chat else first_msg.sender_chat.id
        media_group_id = first_msg.media_group_id
        
        # Get range pesan untuk cari thread
        start_id = max(1, first_msg.id - 20)
        end_id = first_msg.id + 20
        
        all_messages = await get_message_from_link(chat_id, list(range(start_id, end_id)))
        
        if not isinstance(all_messages, list):
            all_messages = [all_messages]
        
        # Filter yang sama media_group_id
        thread_messages = [m for m in all_messages if m and m.media_group_id == media_group_id]
        
        if not thread_messages:
            thread_messages = [first_msg]
        
        await progress_msg.edit_text(f"🧵 Thread: {len(thread_messages)} media ditemukan")
        
        # Download semua
        downloaded_files = []
        for idx, msg in enumerate(thread_messages, 1):
            await progress_msg.edit_text(f"⏳ Download {idx}/{len(thread_messages)}...")
            
            # Tentukan ekstensi
            if msg.photo:
                fname = f"thread_{msg.id}.jpg"
            elif msg.video:
                fname = f"thread_{msg.id}.mp4"
            else:
                fname = f"thread_{msg.id}.bin"
            
            fpath = f"/tmp/{fname}"
            downloaded = await download_with_client(msg, fpath)
            
            if downloaded and os.path.exists(downloaded):
                downloaded_files.append({
                    'path': downloaded,
                    'caption': msg.caption or "",
                    'type': 'photo' if msg.photo else 'video' if msg.video else 'doc'
                })
            
            await asyncio.sleep(0.3)
        
        # Upload semua
        await progress_msg.edit_text(f"📤 Uploading {len(downloaded_files)} media...")
        
        for idx, item in enumerate(downloaded_files, 1):
            cap = item['caption'] + f"\n\n📥 Thread {idx}/{len(downloaded_files)}"
            
            try:
                if item['type'] == 'photo':
                    await bot.send_photo(message.chat.id, photo=item['path'], caption=cap)
                elif item['type'] == 'video':
                    await bot.send_video(message.chat.id, video=item['path'], caption=cap)
                else:
                    await bot.send_document(message.chat.id, document=item['path'], caption=cap)
            except PhotoExtInvalid:
                # Fallback ke document
                await bot.send_document(message.chat.id, document=item['path'], caption=cap)
            
            # Cleanup
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
        await progress_msg.edit_text(f"❌ Error thread: {str(e)}")
        user_data[user_id]["status"] = "error"

@bot.on_message(filters.text & filters.private)
async def text_handler(client, message: Message):
    """Handle text - cek link"""
    text = message.text.strip()
    user_id = message.from_user.id
    
    # Cek link private channel (t.me/c/...)
    private_match = CHANNEL_LINK_PATTERN.match(text)
    if private_match:
        channel_id = int(private_match.group(1))
        msg_id = int(private_match.group(2))
        
        if not STRING_SESSION:
            await message.reply_text("""
⚠️ **String Session Belum Di-set!**

Untuk akses channel private (t.me/c/...), **WAJIB** pakai String Session.

**Cara setup:**
1. Generate String Session (via Termux/PC)
2. Tambah ke Railway Variables:
   `STRING_SESSION=your_session_string`

🔧 Tutorial: /help
""")
            return
        
        if user_id not in user_data:
            user_data[user_id] = {"downloads": 0, "threads": 0, "last_seen": datetime.now(), "status": "idle"}
        
        progress_msg = await message.reply_text("⏳ Mengambil pesan dari channel...")
        user_data[user_id]["status"] = "processing"
        
        try:
            # Format chat_id untuk private channel
            chat_id = f"-100{channel_id}"
            
            target_msg = await get_message_from_link(chat_id, msg_id)
            
            if not target_msg:
                await progress_msg.edit_text("❌ Pesan tidak ditemukan")
                return
            
            if not target_msg.media:
                await progress_msg.edit_text("❌ Pesan ini tidak berisi media")
                return
            
            # Cek apakah thread
            if target_msg.media_group_id:
                await process_thread(message, target_msg, user_id, progress_msg)
            else:
                await process_single_media(message, target_msg, user_id, progress_msg)
            
        except PeerIdInvalid:
            await progress_msg.edit_text("""
❌ **PEER_ID_INVALID**

Bot/User belum join channel ini.

**Solusi:**
1. Pastikan akun Anda (yang punya String Session) sudah join channel
2. Atau add bot ke channel sebagai member
""")
        except ChannelPrivate:
            await progress_msg.edit_text("""
❌ **Channel Private**

Akun Anda belum join channel ini.

**Solusi:**
Join channel dulu di Telegram, lalu coba lagi.
""")
        except AuthKeyUnregistered:
            await progress_msg.edit_text("""
❌ **String Session Invalid**

Session key tidak terdaftar atau expired.

**Solusi:**
1. Generate String Session baru
2. Update di Railway Variables
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
        
        # Skip bot commands
        if username.lower() in ['botfather', 'telegram', 'stickers', 'telegraph']:
            return
        
        if user_id not in user_data:
            user_data[user_id] = {"downloads": 0, "threads": 0, "last_seen": datetime.now(), "status": "idle"}
        
        progress_msg = await message.reply_text("⏳ Mengambil dari link...")
        user_data[user_id]["status"] = "processing"
        
        try:
            chat_id = f"@{username}"
            target_msg = await get_message_from_link(chat_id, msg_id)
            
            if not target_msg or not target_msg.media:
                await progress_msg.edit_text("❌ Pesan tidak ditemukan atau tidak ada media")
                return
            
            if target_msg.media_group_id:
                await process_thread(message, target_msg, user_id, progress_msg)
            else:
                await process_single_media(message, target_msg, user_id, progress_msg)
            
        except Exception as e:
            await progress_msg.edit_text(f"❌ Error: {str(e)}")
        return
    
    # Bukan link
    if not text.startswith('/'):
        await message.reply_text("""
ℹ️ **Kirimkan link channel:**

• Private: `https://t.me/c/123456/1`
• Public: `https://t.me/channel/5`

💡 Copy link dari pesan (bukan forward)

📌 Command: /start | /status | /help
""")

async def keep_alive():
    """Keep user client alive dengan ping periodik"""
    while True:
        try:
            if user_client and user_client.is_connected:
                # Ping dengan get_me
                me = await user_client.get_me()
                logger.info(f"💓 Keep alive: {me.first_name}")
            await asyncio.sleep(60)  # Ping tiap 60 detik
        except Exception as e:
            logger.warning(f"Keep alive error: {e}")
            await asyncio.sleep(30)

async def main():
    """Main entry"""
    os.makedirs("/tmp", exist_ok=True)
    
    # Start user client kalau ada
    if user_client:
        try:
            await user_client.start()
            me = await user_client.get_me()
            logger.info(f"✅ User Client started: {me.first_name} (@{me.username})")
            
            # Start keep alive task
            asyncio.create_task(keep_alive())
        except Exception as e:
            logger.error(f"❌ User client failed to start: {e}")
            logger.warning("⚠️ Continuing with bot only mode")
    
    # Start bot
    await bot.start()
    logger.info("✅ Bot started!")
    
    # Keep running
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
