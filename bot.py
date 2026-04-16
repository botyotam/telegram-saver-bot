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
    UsernameNotOccupied, InviteHashExpired
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
STRING_SESSION = os.getenv("STRING_SESSION", "")  # 🆕 User Account Session

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

# Inisialisasi User Client (untuk akses channel private) - Jika ada string session
user_client = None
if STRING_SESSION:
    user_client = Client(
        "railway_user",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=STRING_SESSION,
        parse_mode=ParseMode.MARKDOWN
    )
    logger.info("✅ User Client (String Session) aktif!")
else:
    logger.warning("⚠️ String Session tidak di-set, hanya bisa forward dari channel yang bot bisa akses")

# Storage
user_data = {}
pending_downloads = {}  # Untuk track download yang sedang berjalan

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

async def get_message_from_link(chat_id, message_id):
    """
    Ambil pesan menggunakan User Client (kalau ada) atau Bot Client
    """
    # Prioritaskan User Client karena bisa akses lebih banyak channel
    if user_client and user_client.is_connected:
        try:
            return await user_client.get_messages(chat_id, message_id)
        except Exception as e:
            logger.warning(f"User client gagal: {e}, coba bot client...")
    
    # Fallback ke Bot Client
    return await bot.get_messages(chat_id, message_id)

async def download_with_client(message, file_path):
    """
    Download menggunakan client yang tepat
    """
    # Prioritaskan User Client
    if user_client and user_client.is_connected:
        try:
            return await user_client.download_media(message, file_name=file_path)
        except Exception as e:
            logger.warning(f"User client download gagal: {e}")
    
    # Fallback ke Bot
    return await bot.download_media(message, file_name=file_path)

@bot.on_message(filters.command("start"))
async def start_cmd(client, message: Message):
    user_id = message.from_user.id
    user_data[user_id] = {
        "downloads": 0,
        "threads": 0,
        "last_seen": datetime.now(),
        "status": "idle"
    }
    
    mode_text = "🟢 **Mode: User Account + Bot**" if STRING_SESSION else "🟡 **Mode: Bot Only**"
    
    text = f"""
👋 **Halo {message.from_user.first_name}!**

{mode_text}

🤖 **Media Downloader Bot**

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
• Bot tidak bisa baca pesan tanpa String Session

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

async def process_link_download(client, message: Message, chat_id, msg_id, is_private=True):
    """
    Proses download dari link
    """
    user_id = message.from_user.id
    user_data[user_id]["status"] = "processing"
    
    progress_msg = await message.reply_text("⏳ Mengambil pesan dari channel...")
    
    try:
        # Ambil pesan
        target_msg = await get_message_from_link(chat_id, msg_id)
        
        if not target_msg:
            await progress_msg.edit_text("❌ Pesan tidak ditemukan")
            return
        
        # Cek apakah ini thread/album (media_group_id)
        if target_msg.media_group_id:
            await process_thread(message, target_msg, user_id, progress_msg)
        else:
            # Single media
            await process_single_media(message, target_msg, user_id, progress_msg)
            
    except ChannelPrivate:
        await progress_msg.edit_text("""
❌ **Channel Private - Tidak Bisa Akses**

Solusi:
1. **Pakai String Session** (akun Anda harus join channel)
2. Atau add bot ke channel (kalau Anda admin)

💡 String Session = bot "login" sebagai akun Anda
""")
    except PeerIdInvalid:
        await progress_msg.edit_text("""
❌ **Bot Belum Kenal Channel**

**Solusi Wajib:** Pakai String Session!

Tanpa String Session, bot hanya bisa akses channel dimana bot di-add sebagai member.

🔧 Setup String Session di Railway Variables:
`STRING_SESSION=your_session_here`
""")
    except Exception as e:
        logger.error(f"Link error: {e}")
        await progress_msg.edit_text(f"❌ Error: {str(e)}")

async def process_single_media(message: Message, target_msg: Message, user_id: int, progress_msg: Message):
    """Proses single media"""
    try:
        # Cek tipe media
        media_type = None
        file_name = None
        
        if target_msg.photo:
            media_type = "photo"
            file_name = f"photo_{target_msg.id}.jpg"
        elif target_msg.video:
            media_type = "video"
            file_name = f"video_{target_msg.id}.mp4"
        elif target_msg.document:
            media_type = "document"
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
        
        # Download
        await progress_msg.edit_text("⏳ Mendownload...")
        os.makedirs("/tmp", exist_ok=True)
        file_path = f"/tmp/{file_name}"
        
        downloaded = await download_with_client(target_msg, file_path)
        
        if not downloaded or not os.path.exists(downloaded):
            await progress_msg.edit_text("❌ Gagal download")
            return
        
        # Upload
        await progress_msg.edit_text("📤 Mengupload ulang...")
        
        caption = target_msg.caption or ""
        footer = f"\n\n📥 Unlocked via Bot | {datetime.now().strftime('%Y-%m-%d')}"
        new_caption = caption + footer if caption else footer.strip()
        
        # Kirim dengan bot (bukan user client)
        if media_type == "photo":
            with open(downloaded, 'rb') as f:
                await bot.send_photo(message.chat.id, photo=f, caption=new_caption)
        elif media_type == "video":
            with open(downloaded, 'rb') as f:
                await bot.send_video(message.chat.id, video=f, caption=new_caption, supports_streaming=True)
        elif media_type == "document":
            with open(downloaded, 'rb') as f:
                await bot.send_document(message.chat.id, document=f, caption=new_caption)
        elif media_type == "audio":
            with open(downloaded, 'rb') as f:
                await bot.send_audio(message.chat.id, audio=f, caption=new_caption)
        elif media_type == "voice":
            with open(downloaded, 'rb') as f:
                await bot.send_voice(message.chat.id, voice=f)
        elif media_type == "video_note":
            with open(downloaded, 'rb') as f:
                await bot.send_video_note(message.chat.id, video_note=f)
        elif media_type == "animation":
            with open(downloaded, 'rb') as f:
                await bot.send_animation(message.chat.id, animation=f, caption=new_caption)
        elif media_type == "sticker":
            with open(downloaded, 'rb') as f:
                await bot.send_sticker(message.chat.id, sticker=f)
        
        # Cleanup
        try:
            os.remove(downloaded)
        except:
            pass
        
        user_data[user_id]["downloads"] += 1
        user_data[user_id]["status"] = "idle"
        
        await progress_msg.edit_text("✅ **Berhasil!** Media sudah bisa di-share.")
        
    except Exception as e:
        logger.error(f"Single media error: {e}")
        await progress_msg.edit_text(f"❌ Error: {str(e)}")
        user_data[user_id]["status"] = "error"

async def process_thread(message: Message, first_msg: Message, user_id: int, progress_msg: Message):
    """
    Proses thread/album - ambil semua media dalam grup
    """
    await progress_msg.edit_text("🧵 **Thread terdeteksi!** Mengambil semua media...")
    
    try:
        # Ambil semua pesan dalam media group
        chat_id = first_msg.chat.id if first_msg.chat else first_msg.sender_chat.id
        media_group_id = first_msg.media_group_id
        
        # Get messages sekitar (heuristic: ±10 dari msg_id)
        all_messages = await get_message_from_link(chat_id, list(range(first_msg.id - 10, first_msg.id + 10)))
        
        # Filter yang sama media_group_id
        thread_messages = [m for m in all_messages if m and m.media_group_id == media_group_id]
        
        if not thread_messages:
            thread_messages = [first_msg]  # Fallback ke pesan pertama saja
        
        await progress_msg.edit_text(f"🧵 Thread: {len(thread_messages)} media ditemukan")
        
        # Download semua
        downloaded_files = []
        for idx, msg in enumerate(thread_messages, 1):
            await progress_msg.edit_text(f"⏳ Download {idx}/{len(thread_messages)}...")
            
            # Tentukan nama file
            if msg.photo:
                fname = f"thread_{msg.id}.jpg"
            elif msg.video:
                fname = f"thread_{msg.id}.mp4"
            else:
                fname = f"thread_{msg.id}"
            
            fpath = f"/tmp/{fname}"
            downloaded = await download_with_client(msg, fpath)
            
            if downloaded:
                downloaded_files.append({
                    'path': downloaded,
                    'caption': msg.caption or "",
                    'type': 'photo' if msg.photo else 'video' if msg.video else 'doc'
                })
            
            await asyncio.sleep(0.5)  # Rate limit
        
        # Upload semua
        await progress_msg.edit_text(f"📤 Uploading {len(downloaded_files)} media...")
        
        for idx, item in enumerate(downloaded_files, 1):
            cap = item['caption'] + f"\n\n📥 Thread {idx}/{len(downloaded_files)}"
            
            with open(item['path'], 'rb') as f:
                if item['type'] == 'photo':
                    await bot.send_photo(message.chat.id, photo=f, caption=cap)
                elif item['type'] == 'video':
                    await bot.send_video(message.chat.id, video=f, caption=cap)
                else:
                    await bot.send_document(message.chat.id, document=f, caption=cap)
            
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

🔧 Tutorial lengkap: /help
""")
            return
        
        await process_link_download(client, message, f"-100{channel_id}", msg_id, is_private=True)
        return
    
    # Cek link public
    public_match = PUBLIC_LINK_PATTERN.match(text)
    if public_match:
        username = public_match.group(1)
        msg_id = int(public_match.group(2))
        
        # Skip bot commands
        if username.lower() in ['botfather', 'telegram', 'stickers', 'telegraph', 'tsave']:
            return
        
        await process_link_download(client, message, f"@{username}", msg_id, is_private=False)
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

async def main():
    """Main entry"""
    os.makedirs("/tmp", exist_ok=True)
    
    # Start user client kalau ada
    if user_client:
        await user_client.start()
        me = await user_client.get_me()
        logger.info(f"✅ User Client started: {me.first_name}")
    
    # Start bot
    await bot.start()
    logger.info("✅ Bot started!")
    
    # Keep running
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
