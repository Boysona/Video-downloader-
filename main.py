import shutil
import telebot
import yt_dlp
import os
import uuid
from flask import Flask, request, abort
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import imageio_ffmpeg

# --- Configuration ---
BOT_TOKEN = "7513880960:AAH29znCI1-lsxQYG0R4NnBnV1qevAnhROw"
ADMIN_ID = 5978150981 # Replace with your actual admin ID
USER_FILE = "users.txt"
DOWNLOAD_DIR = "downloads"
WEBHOOK_URL = "https://video-downloader-0wo5.onrender.com" # Replace with your actual Render URL

# --- Bot Initialization ---
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

# Dictionary to store message_id of the "👀" icon for deletion
bot.icon_messages = {}
# Dictionary to store video info for callback queries
bot.video_info = {}

# --- Bot Description and Commands Setup ---
try:
    bot.set_my_description(
        "I'm a powerful media downloader bot! Send me links from platforms like TikTok, YouTube, Instagram, Pinterest, and Facebook. I'll download the media for you, including video descriptions and available subtitles. You can even download audio only from YouTube videos!",
        language_code='en'
    )
    bot.set_my_short_description(
        "Your ultimate bot for downloading media from popular platforms!",
        language_code='en'
    )
    commands = [
        telebot.types.BotCommand("/start", "👋 Get a welcome message and info"),
        telebot.types.BotCommand("/help", "❓ Get information on how to use the bot"),
        telebot.types.BotCommand("/admin", "👑 Access admin panel (for admins only)")
    ]
    bot.set_my_commands(commands)
except Exception as e:
    print(f"Error setting bot description or commands: {e}")

# --- Directory Setup ---
if os.path.exists(DOWNLOAD_DIR):
    shutil.rmtree(DOWNLOAD_DIR)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# --- User Management ---
def save_user(user_id):
    if not os.path.exists(USER_FILE):
        open(USER_FILE, "w").close()
    with open(USER_FILE, "r+") as f:
        ids = f.read().splitlines()
        if str(user_id) not in ids:
            f.write(f"{user_id}\n")

# --- Start Command Handler ---
@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = message.chat.id
    save_user(user_id)
    name = message.from_user.first_name
    welcome_text = (
        f"👋 Salam {name}, I'm your friendly media downloader bot!\n"
        "Send me a link from TikTok, YouTube, Instagram, Facebook, or other supported platforms, and I’ll download it for you.\n\n"
        "For more info, use /help."
    )
    bot.send_message(user_id, welcome_text)
    if user_id == ADMIN_ID:
        show_admin_panel(user_id)

# --- Help Command Handler ---
@bot.message_handler(commands=['help'])
def help_handler(message):
    user_id = message.chat.id
    help_text = (
        "Here are some instructions:\n"
        "🔗 Send me a supported media link (TikTok, YouTube, Instagram, Pinterest, Facebook, etc.), and I'll download the media for you.\n"
        "📝 For videos, I'll include the **video description** and **subtitles** (if available).\n"
        "🎵 For YouTube links, you'll have the option to download **audio only**.\n\n"
        "/start - Begin using the bot\n"
        "/help - Get help and instructions"
    )
    bot.send_message(user_id, help_text, parse_mode='Markdown')

# --- Admin Panel ---
@bot.message_handler(commands=['admin'])
def admin_command_handler(message):
    if message.chat.id == ADMIN_ID:
        show_admin_panel(message.chat.id)
    else:
        bot.send_message(message.chat.id, "You are not authorized to use this command.")

def show_admin_panel(chat_id):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📊 Total Users", "📢 Send Ads (broadcast)")
    bot.send_message(chat_id, "Welcome to the Admin Panel", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📊 Total Users" and msg.chat.id == ADMIN_ID)
def total_users(msg):
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r") as f:
            count = len(f.readlines())
        bot.send_message(msg.chat.id, f"👥 Total users: {count}")
    else:
        bot.send_message(msg.chat.id, "No users yet.")

@bot.message_handler(func=lambda msg: msg.text == "📢 Send Ads (broadcast)" and msg.chat.id == ADMIN_ID)
def ask_broadcast(msg):
    bot.send_message(msg.chat.id, "Send your broadcast message (text, photo, video, etc.):")
    bot.register_next_step_handler(msg, broadcast_message)

def broadcast_message(message):
    if not os.path.exists(USER_FILE):
        bot.send_message(message.chat.id, "No users to broadcast to.")
        return
    with open(USER_FILE, "r") as f:
        user_ids = f.read().splitlines()
    sent = 0
    for uid in user_ids:
        try:
            uid = int(uid)
            if message.text:
                bot.send_message(uid, message.text)
            elif message.photo:
                bot.send_photo(uid, message.photo[-1].file_id, caption=message.caption or "")
            elif message.video:
                bot.send_video(uid, message.video.file_id, caption=message.caption or "")
            elif message.audio:
                bot.send_audio(uid, message.audio.file_id, caption=message.caption or "")
            elif message.voice:
                bot.send_voice(uid, message.voice.file_id)
            elif message.document:
                bot.send_document(uid, message.document.file_id, caption=message.caption or "")
            sent += 1
        except Exception as e:
            print(f"Error sending to {uid}: {e}")
    bot.send_message(message.chat.id, f"✅ Broadcast finished. Sent to {sent} users.")

# --- URL Validation ---
def is_supported_url(url):
    platforms = ['tiktok.com', 'youtube.com', 'youtu.be', 'pinterest.com', 'pin.it',
                 'instagram.com', 'snapchat.com', 'facebook.com', 'fb.watch', 'x.com', 'twitter.com']
    return any(p in url.lower() for p in platforms)

def is_youtube_url(url):
    return 'youtube.com' in url.lower() or 'youtu.be' in url.lower()

# --- Handle Incoming URLs ---
@bot.message_handler(func=lambda msg: msg.text and msg.text.startswith(('http://', 'https://')) and is_supported_url(msg.text))
def handle_url_message(msg):
    icon_msg = bot.send_message(msg.chat.id, "👀 Processing your link...")
    bot.icon_messages[msg.chat.id] = icon_msg.message_id

    if is_youtube_url(msg.text):
        handle_youtube_url(msg)
    else:
        handle_social_video(msg)

# --- YouTube Specific Handler ---
@bot.message_handler(func=lambda msg: is_youtube_url(msg.text))
def handle_youtube_url(msg):
    url = msg.text
    chat_id = msg.chat.id
    try:
        bot.send_chat_action(chat_id, 'typing')
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Video')
            description = info.get('description', '')
            formats = info.get('formats', [])

        markup = InlineKeyboardMarkup(row_width=2)
        video_resolutions = {
            f'{f["height"]}p': f['format_id']
            for f in formats if f.get('vcodec') != 'none' and f.get('height') <= 1080
        }
        audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
        
        # Add video quality options
        if video_resolutions:
            for res, fid in sorted(video_resolutions.items(), key=lambda x: int(x[0][:-1]), reverse=True):
                vid_id = str(uuid.uuid4())[:8]
                bot.video_info[vid_id] = {
                    'url': url,
                    'format_id': fid,
                    'type': 'video',
                    'description': description
                }
                markup.add(InlineKeyboardButton(f"Video {res}", callback_data=f'dl:{vid_id}'))
        
        # Add audio only option
        if audio_formats:
            # Prioritize m4a or webm audio if available
            audio_format_id = next((f['format_id'] for f in audio_formats if 'm4a' in f['ext'] or 'webm' in f['ext']), None)
            if not audio_format_id:
                # Fallback to the best audio format if specific ones not found
                audio_format_id = sorted(audio_formats, key=lambda x: x.get('tbr', 0), reverse=True)[0]['format_id']
            
            audio_id = str(uuid.uuid4())[:8]
            bot.video_info[audio_id] = {
                'url': url,
                'format_id': audio_format_id,
                'type': 'audio',
                'description': description
            }
            markup.add(InlineKeyboardButton("Download Audio Only 🎵", callback_data=f'dl:{audio_id}'))
        
        if not video_resolutions and not audio_formats:
            bot.send_message(chat_id, "No suitable video or audio formats found for this link.")
            cleanup_after_download(chat_id)
            return

        bot.send_message(chat_id, f"Choose download option for: **{title}**", reply_markup=markup, parse_mode='Markdown')

    except Exception as e:
        bot.send_message(chat_id, f"An error occurred while processing the YouTube link: {e}")
        cleanup_after_download(chat_id)

# --- Callback Query Handler for Downloads ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('dl:'))
def download_media(call):
    vid_uuid = call.data.split(":")[1]
    chat_id = call.message.chat.id
    
    if vid_uuid not in bot.video_info:
        bot.answer_callback_query(call.id, "Download link expired. Please send the URL again.")
        cleanup_after_download(chat_id)
        return

    data = bot.video_info.pop(vid_uuid) # Remove info after use
    url, fmt, media_type, description = data['url'], data['format_id'], data['type'], data.get('description', '')
    
    basename = str(uuid.uuid4())
    
    if media_type == 'video':
        output_path = os.path.join(DOWNLOAD_DIR, f"{basename}.mp4")
        ydl_opts = {
            'format': fmt,
            'outtmpl': output_path,
            'quiet': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en'],
            'convert_subtitles': 'srt',
            'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
            'postprocessors': [{
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }],
        }
    elif media_type == 'audio':
        output_path = os.path.join(DOWNLOAD_DIR, f"{basename}.mp3")
        ydl_opts = {
            'format': fmt,
            'outtmpl': output_path,
            'quiet': True,
            'extractaudio': True,
            'audioformat': 'mp3',
            'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }, {
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }],
        }
    else:
        bot.answer_callback_query(call.id, "Invalid media type.")
        cleanup_after_download(chat_id)
        return

    try:
        bot.answer_callback_query(call.id, "Starting download...")
        bot.send_chat_action(chat_id, 'upload_video' if media_type == 'video' else 'upload_audio')
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        caption_text = ""
        if description:
            caption_text = f"{description}\n\n"
        caption_text += "Powered by @Bot_makerrBot"

        if media_type == 'video':
            with open(output_path, 'rb') as f:
                bot.send_video(chat_id, f, caption=caption_text, reply_to_message_id=call.message.message_id)
            
            # Send subtitles if available
            subtitle_path = output_path.replace('.mp4', '.en.srt')
            if os.path.exists(subtitle_path):
                with open(subtitle_path, 'rb') as sub_file:
                    bot.send_document(chat_id, sub_file, caption="Subtitles for video")
        elif media_type == 'audio':
            with open(output_path, 'rb') as f:
                bot.send_audio(chat_id, f, caption=caption_text, reply_to_message_id=call.message.message_id)

    except Exception as e:
        bot.send_message(chat_id, f"Error during download: {e}")
    finally:
        cleanup_after_download(chat_id)

# --- Generic Social Video Handler (TikTok, Instagram, etc.) ---
@bot.message_handler(func=lambda msg: is_supported_url(msg.text) and not is_youtube_url(msg.text))
def handle_social_video(msg):
    url = msg.text
    chat_id = msg.chat.id
    basename = str(uuid.uuid4())
    video_path = os.path.join(DOWNLOAD_DIR, f"{basename}.mp4")

    ydl_opts = {
        'format': 'best',
        'outtmpl': video_path,
        'quiet': True,
        'noplaylist': True,
        'merge_output_format': 'mp4',
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en'],
        'convert_subtitles': 'srt',
        'ignoreerrors': True,
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
        'postprocessors': [{
            'key': 'FFmpegMetadata',
            'add_metadata': True,
        }],
    }
    
    try:
        bot.send_chat_action(chat_id, 'upload_video')
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            description = info.get('description', '')
        
        if os.path.exists(video_path):
            caption_text = ""
            if description:
                caption_text = f"{description}\n\n"
            caption_text += "Powered by @Bot_makerrBot"

            with open(video_path, 'rb') as f:
                bot.send_video(chat_id, f, caption=caption_text)

            subtitle_path = video_path.replace('.mp4', '.en.srt')
            if os.path.exists(subtitle_path):
                with open(subtitle_path, 'rb') as sub:
                    bot.send_document(chat_id, sub, caption="Subtitles")
        else:
            bot.send_message(chat_id, "Sorry, I couldn't download the media from this link.")

    except Exception as e:
        bot.send_message(chat_id, f"An error occurred: {e}")
    finally:
        cleanup_after_download(chat_id)

# --- Cleanup Function ---
def cleanup_after_download(chat_id):
    # Delete the "👀" icon message
    if chat_id in bot.icon_messages:
        try:
            bot.delete_message(chat_id, bot.icon_messages[chat_id])
        except Exception as e:
            print(f"Error deleting icon message: {e}")
        finally:
            bot.icon_messages.pop(chat_id, None)
    
    # Clean up the downloads directory
    for file in os.listdir(DOWNLOAD_DIR):
        file_path = os.path.join(DOWNLOAD_DIR, file)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")

# --- Webhook Setup ---
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        abort(403)

@app.route('/set_webhook', methods=['GET', 'POST'])
def set_webhook():
    bot.set_webhook(url=WEBHOOK_URL)
    return f"Webhook set to {WEBHOOK_URL}", 200

@app.route('/delete_webhook', methods=['GET', 'POST'])
def delete_webhook():
    bot.delete_webhook()
    return "Webhook deleted", 200

if __name__ == "__main__":
    # Ensure webhook is set correctly on startup
    bot.delete_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
