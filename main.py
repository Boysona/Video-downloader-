import shutil
import telebot
import yt_dlp
import os
import uuid
from flask import Flask, request, abort
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import imageio_ffmpeg  # Isticmaalka imageio-ffmpeg
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "7513880960:AAFt2TJowXrh3LJ63zafDuIF0Eybk-Wx9LQ")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "5978150981"))  # Ensure ADMIN_ID is an integer
USER_FILE = "users.txt"
DOWNLOAD_DIR = "downloads"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://video-downloader-0wo5.onrender.com")

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

# Dictionary to store icon message_id for link reactions
bot.icon_messages = {}

# Set bot description, short description, and commands
try:
    bot.set_my_description(
        "I'm your advanced media downloader bot! Send me links from various platforms like TikTok, YouTube, Instagram, Pinterest, and Facebook, and I'll download the media for you, including video descriptions and subtitles where available. I also support audio-only downloads for YouTube videos.",
        language_code='en'
    )
    bot.set_my_short_description(
        "Your ultimate bot for downloading media from popular platforms!",
        language_code='en'
    )
    commands = [
        telebot.types.BotCommand("/start", "👋 Get a welcome message and info"),
        telebot.types.BotCommand("/help", "❓ Get information on how to use the bot"),
        telebot.types.BotCommand("/settings", "⚙️ Customize your bot experience")
    ]
    bot.set_my_commands(commands)
    logger.info("Bot description, short description, and commands set successfully.")
except Exception as e:
    logger.error(f"Error setting bot description or commands: {e}")

# Clean up and create downloads directory
if os.path.exists(DOWNLOAD_DIR):
    shutil.rmtree(DOWNLOAD_DIR)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
logger.info(f"Initialized {DOWNLOAD_DIR} directory.")

def save_user(user_id):
    """Saves a user ID to the user file if not already present."""
    try:
        if not os.path.exists(USER_FILE):
            open(USER_FILE, "w").close()
        with open(USER_FILE, "r+") as f:
            ids = f.read().splitlines()
            if str(user_id) not in ids:
                f.write(f"{user_id}\n")
                logger.info(f"User {user_id} saved.")
    except IOError as e:
        logger.error(f"Error saving user {user_id}: {e}")

@bot.message_handler(commands=['start'])
def start_handler(message):
    """Handles the /start command, sends a welcome message, and shows admin panel if applicable."""
    user_id = message.chat.id
    save_user(user_id)
    name = message.from_user.first_name if message.from_user.first_name else "there"
    welcome_text = (
        f"👋 Salam {name}, I'm your friendly media downloader bot!\n"
        "Send me a link from TikTok, YouTube, Instagram, Facebook, or other supported platforms, and I’ll download it for you.\n\n"
        "✨ **New Features:**\n"
        "- **YouTube Audio-Only Downloads**: Get just the audio from YouTube videos!\n"
        "- **Settings Menu**: Customize your preferences with /settings.\n\n"
        "For more info, use /help."
    )
    bot.send_message(user_id, welcome_text)
    if user_id == ADMIN_ID:
        show_admin_panel(user_id)

@bot.message_handler(commands=['help'])
def help_handler(message):
    """Handles the /help command, providing instructions on bot usage."""
    user_id = message.chat.id
    help_text = (
        "Here are some instructions:\n"
        "• `/start` - Get a welcome message and info\n"
        "• `/help` - Get help and instructions\n"
        "• `/settings` - Customize your bot experience (e.g., download preferences)\n\n"
        "Just send me a supported media link (TikTok, YouTube, Instagram, Pinterest, Facebook, X/Twitter, etc.), and I'll download the media (including video descriptions and subtitles where available). For YouTube links, I'll offer video quality and audio-only options."
    )
    bot.send_message(user_id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['settings'])
def settings_handler(message):
    """Handles the /settings command to display user preferences."""
    user_id = message.chat.id
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("Toggle YouTube Audio-Only", callback_data="toggle_youtube_audio_only"))
    # Add more settings here as needed in the future
    bot.send_message(user_id, "⚙️ **Bot Settings**\n\nChoose an option to manage your preferences:", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == "toggle_youtube_audio_only")
def toggle_youtube_audio_only_setting(call):
    """Toggles the YouTube audio-only download preference for the user."""
    user_id = call.message.chat.id
    # This is a placeholder. In a real application, you'd store this preference in a database.
    # For now, let's just simulate a toggle and inform the user.
    # You might use a simple dict in memory for demonstration, but it won't persist across restarts.
    bot.user_settings = getattr(bot, 'user_settings', {})
    current_state = bot.user_settings.get(user_id, {}).get('youtube_audio_only', False)
    new_state = not current_state
    
    if user_id not in bot.user_settings:
        bot.user_settings[user_id] = {}
    bot.user_settings[user_id]['youtube_audio_only'] = new_state
    
    status_text = "Enabled" if new_state else "Disabled"
    bot.answer_callback_query(call.id, f"YouTube Audio-Only downloads: {status_text}")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"⚙️ **Bot Settings**\n\nYouTube Audio-Only downloads are now: **{status_text}**.\n\nChoose an option to manage your preferences:",
        reply_markup=call.message.reply_markup,
        parse_mode='Markdown'
    )
    logger.info(f"User {user_id} toggled YouTube audio-only to {new_state}.")

def show_admin_panel(chat_id):
    """Displays the admin panel with options for bot management."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("📊 Total Users"), KeyboardButton("📢 Send Ads (broadcast)"))
    markup.add(KeyboardButton("❌ Hide Admin Panel"))
    bot.send_message(chat_id, "🔑 **Welcome to Admin Panel**", reply_markup=markup, parse_mode='Markdown')
    logger.info(f"Admin panel shown to {chat_id}.")

@bot.message_handler(func=lambda msg: msg.text == "📊 Total Users" and msg.chat.id == ADMIN_ID)
def total_users(msg):
    """Responds with the total number of registered users."""
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r") as f:
            count = len(f.readlines())
        bot.send_message(msg.chat.id, f"👥 Total users: **{count}**", parse_mode='Markdown')
        logger.info(f"Admin {msg.chat.id} checked total users: {count}.")
    else:
        bot.send_message(msg.chat.id, "No users yet.")

@bot.message_handler(func=lambda msg: msg.text == "📢 Send Ads (broadcast)" and msg.chat.id == ADMIN_ID)
def ask_broadcast(msg):
    """Prompts the admin to send a broadcast message."""
    bot.send_message(msg.chat.id, "✍️ Send your broadcast message (text, photo, video, etc.):")
    bot.register_next_step_handler(msg, broadcast_message)
    logger.info(f"Admin {msg.chat.id} initiated broadcast.")

def broadcast_message(message):
    """Sends a broadcast message to all registered users."""
    if not os.path.exists(USER_FILE):
        bot.send_message(message.chat.id, "No users to broadcast to.")
        return
    with open(USER_FILE, "r") as f:
        user_ids = f.read().splitlines()
    sent = 0
    failed = 0
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
        except telebot.apihelper.ApiTelegramException as e:
            logger.warning(f"Failed to send broadcast to user {uid}: {e}")
            failed += 1
            # Handle specific errors like "Bot was blocked by the user"
            if "bot was blocked by the user" in str(e).lower():
                logger.info(f"User {uid} blocked the bot. Removing from user list.")
                # Optional: Remove user from USER_FILE if they blocked the bot
                # This requires rewriting the file or maintaining a dynamic list.
                pass
        except Exception as e:
            logger.error(f"Error sending broadcast to {uid}: {e}")
            failed += 1
    bot.send_message(message.chat.id, f"✅ Broadcast finished. Sent to **{sent}** users. Failed for **{failed}** users.", parse_mode='Markdown')
    logger.info(f"Broadcast sent to {sent} users, failed for {failed} users.")

@bot.message_handler(func=lambda msg: msg.text == "❌ Hide Admin Panel" and msg.chat.id == ADMIN_ID)
def hide_admin_panel(msg):
    """Hides the admin panel keyboard."""
    bot.send_message(msg.chat.id, "Admin panel hidden.", reply_markup=telebot.types.ReplyKeyboardRemove())
    logger.info(f"Admin panel hidden for {msg.chat.id}.")

def is_supported_url(url):
    """Checks if the given URL is from a supported platform."""
    # Updated to include more precise YouTube domains and X/Twitter
    platforms = ['tiktok.com', 'youtube.com', 'youtu.be', 'pinterest.com', 'pin.it',
                 'instagram.com', 'snapchat.com', 'facebook.com', 'fb.watch', 'x.com', 'twitter.com']
    return any(p in url.lower() for p in platforms)

def is_youtube_url(url):
    """Checks if the given URL is a YouTube URL."""
    return 'youtube.com' in url.lower() or 'youtu.be' in url.lower()

@bot.message_handler(func=lambda msg: is_supported_url(msg.text))
def react_and_process_url(msg):
    """Reacts with an emoji and then processes the URL for download."""
    user_id = msg.chat.id
    try:
        icon_msg = bot.send_message(user_id, "👀 Processing your link...")
        bot.icon_messages[user_id] = icon_msg.message_id
        
        if is_youtube_url(msg.text):
            handle_youtube_url(msg)
        else:
            handle_social_video(msg)
    except Exception as e:
        logger.error(f"Error in react_and_process_url for user {user_id}: {e}")
        bot.send_message(user_id, "An unexpected error occurred while processing your link. Please try again later.")
        # Clean up icon message if an error occurs early
        if user_id in bot.icon_messages:
            bot.delete_message(user_id, bot.icon_messages[user_id])
            bot.icon_messages.pop(user_id, None)

@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_unsupported_messages(message):
    """Handles unsupported text messages by guiding the user."""
    user_id = message.chat.id
    if not is_supported_url(message.text) and not message.text.startswith('/'):
        bot.send_message(user_id, "Hmm, I don't recognize that. Please send me a valid link from a supported platform (like YouTube, TikTok, Instagram, Facebook, X/Twitter, or Pinterest).")
        logger.info(f"User {user_id} sent an unsupported message: {message.text}")

def handle_youtube_url(msg):
    """Processes a YouTube URL to offer download options."""
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
            title = info.get('title', 'YouTube Video')
            description = info.get('description', '')
            formats = info.get('formats', [])

        resolutions = {f'{f["height"]}p': f['format_id']
                       for f in formats if f.get('vcodec') != 'none' and f.get('height') <= 1080 and f.get('ext') == 'mp4'} # Filter for mp4

        audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and f.get('ext') == 'm4a']
        best_audio_format = None
        if audio_formats:
            # Sort by filesize or bitrate to get the "best" audio
            best_audio_format = max(audio_formats, key=lambda x: x.get('filesize', 0) or x.get('abr', 0), default=None)

        markup = InlineKeyboardMarkup(row_width=3)
        for res, fid in sorted(resolutions.items(), key=lambda x: int(x[0][:-1]), reverse=True): # Sort descending
            vid_id = str(uuid.uuid4())[:8]
            bot.video_info = getattr(bot, 'video_info', {})
            bot.video_info[vid_id] = {
                'url': url,
                'format_id': fid,
                'description': description,
                'type': 'video'
            }
            markup.add(InlineKeyboardButton(res, callback_data=f'dl:{vid_id}'))

        # Add audio-only option if available and settings allow
        user_settings = getattr(bot, 'user_settings', {}).get(chat_id, {})
        if best_audio_format and user_settings.get('youtube_audio_only', True): # Default to true for now
            audio_id = str(uuid.uuid4())[:8]
            bot.video_info[audio_id] = {
                'url': url,
                'format_id': best_audio_format['format_id'],
                'description': description,
                'type': 'audio'
            }
            markup.add(InlineKeyboardButton("🎵 Audio Only", callback_data=f'dl:{audio_id}'))

        if not resolutions and not best_audio_format:
            bot.send_message(chat_id, "No suitable video or audio formats found for this YouTube link.")
            cleanup_icon_message(chat_id)
            return

        bot.send_message(chat_id, f"🎬 **{title}**\n\nChoose your download option:", reply_markup=markup, parse_mode='Markdown')
        logger.info(f"YouTube options sent to user {chat_id} for URL: {url}")

    except Exception as e:
        logger.error(f"Error handling YouTube URL {url} for user {chat_id}: {e}", exc_info=True)
        bot.send_message(chat_id, f"Error processing YouTube link. Please ensure it's a valid YouTube video. Error: {e}")
        cleanup_icon_message(chat_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('dl:'))
def download_youtube_media(call):
    """Initiates download for YouTube video or audio based on user selection."""
    vid = call.data.split(":")[1]
    chat_id = call.message.chat.id
    
    bot.answer_callback_query(call.id, "Starting download...")
    
    if not hasattr(bot, 'video_info') or vid not in bot.video_info:
        bot.send_message(chat_id, "Download link expired or invalid. Please send the link again.")
        cleanup_icon_message(chat_id)
        return

    data = bot.video_info.pop(vid)  # Use pop to remove it after use
    url, fmt, description, media_type = data['url'], data['format_id'], data.get('description', ''), data['type']
    
    basename = str(uuid.uuid4())
    
    try:
        if media_type == 'video':
            file_path = os.path.join(DOWNLOAD_DIR, f"{basename}.mp4")
            ydl_opts = {
                'format': fmt,
                'outtmpl': file_path,
                'quiet': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en'],
                'convert_subtitles': 'srt',
                'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
                'noplaylist': True,
                'merge_output_format': 'mp4',
            }
            message_type_action = 'upload_video'
            send_method = bot.send_video
        elif media_type == 'audio':
            file_path = os.path.join(DOWNLOAD_DIR, f"{basename}.m4a")
            ydl_opts = {
                'format': fmt,
                'outtmpl': file_path,
                'quiet': True,
                'extractaudio': True,
                'audioformat': 'm4a',
                'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
                'noplaylist': True,
            }
            message_type_action = 'upload_audio'
            send_method = bot.send_audio
        else:
            bot.send_message(chat_id, "Unsupported media type selected.")
            cleanup_download_dir()
            cleanup_icon_message(chat_id)
            return

        bot.send_chat_action(chat_id, message_type_action)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        final_caption = f"{description}\n\nDownloaded by @Bot_makerrBot" if description else "Downloaded by @Bot_makerrBot"
        
        with open(file_path, 'rb') as f:
            if media_type == 'video':
                send_method(chat_id, f, caption=final_caption, reply_to_message_id=call.message.message_id, timeout=600)
            elif media_type == 'audio':
                send_method(chat_id, f, caption=final_caption, reply_to_message_id=call.message.message_id, timeout=600)

        if media_type == 'video':
            subtitle_path = file_path.replace('.mp4', '.en.srt')
            if os.path.exists(subtitle_path):
                with open(subtitle_path, 'rb') as sub_file:
                    bot.send_document(chat_id, sub_file, caption="Subtitles", reply_to_message_id=call.message.message_id)
                os.remove(subtitle_path) # Clean up subtitle file

        logger.info(f"Successfully downloaded and sent {media_type} to user {chat_id} from URL: {url}")

    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Telegram API error during download for user {chat_id}: {e}", exc_info=True)
        if "file_size_limit_exceeded" in str(e):
            bot.send_message(chat_id, "The file is too large to send via Telegram. Please try a lower quality if available.")
        else:
            bot.send_message(chat_id, f"A Telegram error occurred during download. Please try again. Error: {e}")
    except Exception as e:
        logger.error(f"Error during download for user {chat_id}: {e}", exc_info=True)
        bot.send_message(chat_id, f"An error occurred during download. Please try again. Error: {e}")
    finally:
        cleanup_download_dir()
        cleanup_icon_message(chat_id)
        # Delete the quality selection message
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception as e:
            logger.warning(f"Could not delete quality selection message for {chat_id}: {e}")

def handle_social_video(msg):
    """Handles download for non-YouTube social media videos."""
    url = msg.text
    chat_id = msg.chat.id
    try:
        bot.send_chat_action(chat_id, 'upload_video')
        path, sub_path, description = download_video_any(url)
        if path:
            final_caption = f"{description}\n\nDownloaded by @Bot_makerrBot" if description else "Downloaded by @Bot_makerrBot"

            with open(path, 'rb') as f:
                bot.send_video(chat_id, f, caption=final_caption, reply_to_message_id=msg.message_id, timeout=600)

            if sub_path and os.path.exists(sub_path):
                with open(sub_path, 'rb') as sub:
                    bot.send_document(chat_id, sub, caption="Subtitles", reply_to_message_id=msg.message_id)
                os.remove(sub_path) # Clean up subtitle file
            logger.info(f"Successfully downloaded and sent social video to user {chat_id} from URL: {url}")
        else:
            bot.send_message(chat_id, "An error occurred during download or no media was found for this link.")
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Telegram API error during social video download for user {chat_id}: {e}", exc_info=True)
        if "file_size_limit_exceeded" in str(e):
            bot.send_message(chat_id, "The file is too large to send via Telegram.")
        else:
            bot.send_message(chat_id, f"A Telegram error occurred during download. Error: {e}")
    except Exception as e:
        logger.error(f"Error during social video download for user {chat_id}: {e}", exc_info=True)
        bot.send_message(chat_id, f"An error occurred during download. Please try again. Error: {e}")
    finally:
        cleanup_download_dir()
        cleanup_icon_message(chat_id)

def download_video_any(url):
    """Downloads a video from any supported platform."""
    basename = str(uuid.uuid4())
    video_path = os.path.join(DOWNLOAD_DIR, f"{basename}.mp4")
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', # Prioritize mp4 for compatibility
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
        'retries': 3, # Add retries for robustness
        'fragment_retries': 3,
        'logger': logger, # Pass the logger for yt-dlp to use
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            description = info.get('description', '')
        subtitle_path = video_path.replace('.mp4', '.en.srt')
        return video_path, subtitle_path if os.path.exists(subtitle_path) else None, description
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp download error for {url}: {e}")
        return None, None, ""
    except Exception as e:
        logger.error(f"General download error for {url}: {e}", exc_info=True)
        return None, None, ""

def cleanup_download_dir():
    """Cleans up the download directory."""
    for file in os.listdir(DOWNLOAD_DIR):
        file_path = os.path.join(DOWNLOAD_DIR, file)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Error cleaning up file {file_path}: {e}")
    logger.info("Download directory cleaned up.")

def cleanup_icon_message(chat_id):
    """Deletes the initial 'processing' icon message."""
    if chat_id in bot.icon_messages:
        try:
            bot.delete_message(chat_id, bot.icon_messages[chat_id])
            bot.icon_messages.pop(chat_id, None)
            logger.info(f"Icon message deleted for chat ID: {chat_id}")
        except telebot.apihelper.ApiTelegramException as e:
            logger.warning(f"Could not delete icon message for {chat_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error deleting icon message for {chat_id}: {e}")

@app.route('/', methods=['POST'])
def webhook():
    """Handles incoming webhook updates from Telegram."""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        abort(403)

@app.route('/set_webhook', methods=['GET', 'POST'])
def set_webhook_route():
    """Route to manually set the Telegram webhook."""
    try:
        bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook set to {WEBHOOK_URL}")
        return f"Webhook set to {WEBHOOK_URL}", 200
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return f"Error setting webhook: {e}", 500

@app.route('/delete_webhook', methods=['GET', 'POST'])
def delete_webhook_route():
    """Route to manually delete the Telegram webhook."""
    try:
        bot.delete_webhook()
        logger.info("Webhook deleted.")
        return "Webhook deleted", 200
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")
        return f"Error deleting webhook: {e}", 500

if __name__ == "__main__":
    logger.info("Starting bot application...")
    # It's good practice to ensure webhook is set correctly on startup
    try:
        bot.delete_webhook() # Ensure previous webhook is cleared
        bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Initial webhook setup complete to {WEBHOOK_URL}")
    except Exception as e:
        logger.error(f"Failed to set webhook on startup: {e}")
    
    # Use environment variable for port
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
    logger.info(f"Flask app running on port {port}")

