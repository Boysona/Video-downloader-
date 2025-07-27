import os
import requests
import telebot
from telebot import types
from flask import Flask, request
import yt_dlp
import re
from urllib.parse import urlparse
import uuid

# Initialize Flask app
app = Flask(__name__)

# Bot configuration
BOT_TOKEN = '8191487892:AAEdaDeZ2EwBLA90RrjU1nuR0nkfitpZo5o'
WEBHOOK_URL = 'https://video-downloader-aoqf.onrender.com' + '/' + BOT_TOKEN

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# Supported domains
SUPPORTED_DOMAINS = [
    'youtube.com', 'youtu.be',
    'instagram.com', 'instagr.am',
    'tiktok.com',
    'twitter.com', 'x.com',
    'facebook.com', 'fb.watch',
    'reddit.com',
    'pinterest.com', 'pin.it',
    'likee.video',
    'snapchat.com',
    'threads.net'
]

# ------------------------------
# Helper Functions
# ------------------------------

def is_supported_url(url):
    """Check if the URL is from a supported domain."""
    try:
        domain = urlparse(url).netloc.lower()
        return any(supported in domain for supported in SUPPORTED_DOMAINS)
    except:
        return False

def expand_short_url(url):
    """Expand shortened URLs to their final destination."""
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        return response.url
    except Exception as e:
        print(f"Error expanding URL: {e}")
        return url  # fallback to original if it fails

def extract_video_info(url):
    """Extract video information using yt-dlp."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'best',
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            return info
        except Exception as e:
            print(f"Error extracting video info: {e}")
            return None

def download_video(url):
    """Download video using yt-dlp."""
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'outtmpl': f'downloads/%(id)s.%(ext)s',
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return filename
        except Exception as e:
            print(f"Error downloading video: {e}")
            return None

def clean_filename(filename):
    """Clean the filename to remove special characters."""
    return re.sub(r'[^\w\-_. ]', '', filename)

def create_downloads_folder():
    """Create downloads folder if it doesn't exist."""
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

# ------------------------------
# Bot Handlers
# ------------------------------

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Send welcome message with instructions."""
    welcome_text = """
🌟 *Welcome to Video Downloader Bot* 🌟

Send me a link from:
- YouTube (videos & Shorts)
- Instagram (Posts/Reels/Stories)
- TikTok
- Twitter/X
- Facebook
- Reddit
- Pinterest
- Likee
- Snapchat
- Threads

I'll download the video for you!

📌 *Note*: Some private or age-restricted videos may not be downloadable.
"""
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message):
    """Handle incoming messages with URLs."""
    text = message.text

    # Expand short URLs (e.g. pin.it, youtube shorts)
    text = expand_short_url(text)

    if not is_supported_url(text):
        bot.reply_to(message, "❌ Unsupported URL. Please send a valid video link from supported platforms.")
        return

    # Send "processing" message
    processing_msg = bot.reply_to(message, "🔍 Processing your link, please wait...")

    try:
        # Extract video info
        video_info = extract_video_info(text)
        if not video_info:
            bot.edit_message_text("❌ Failed to get video information. The link might be invalid or private.", 
                                chat_id=message.chat.id, 
                                message_id=processing_msg.message_id)
            return

        # Send video details
        title = video_info.get('title', 'Untitled Video')
        duration = video_info.get('duration', 0)
        uploader = video_info.get('uploader', 'Unknown')

        details_text = f"""
📹 *Video Details*:
- Title: {title}
- Duration: {duration} seconds
- Uploader: {uploader}

⬇️ *Downloading video...* Please wait.
"""
        bot.edit_message_text(details_text, 
                            chat_id=message.chat.id, 
                            message_id=processing_msg.message_id,
                            parse_mode='Markdown')

        # Download the video
        create_downloads_folder()
        video_path = download_video(text)

        if not video_path or not os.path.exists(video_path):
            bot.edit_message_text("❌ Failed to download the video. Please try again later.", 
                                chat_id=message.chat.id, 
                                message_id=processing_msg.message_id)
            return

        # Send the video file
        with open(video_path, 'rb') as video_file:
            bot.send_video(message.chat.id, video_file, 
                          caption=f"🎥 *{title}* \n\n✅ Downloaded by @{bot.get_me().username}",
                          parse_mode='Markdown',
                          reply_to_message_id=message.message_id)

        # Delete processing message
        bot.delete_message(message.chat.id, processing_msg.message_id)

        # Clean up downloaded file
        try:
            os.remove(video_path)
        except:
            pass

    except Exception as e:
        print(f"Error handling message: {e}")
        bot.edit_message_text("❌ An error occurred while processing your request. Please try again later.", 
                             chat_id=message.chat.id, 
                             message_id=processing_msg.message_id)

# ------------------------------
# Flask Routes
# ------------------------------

@app.route('/')
def index():
    return "✅ Bot is running via webhook!", 200

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    try:
        json_str = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
    except Exception as e:
        print(f"Webhook Error: {e}")
        return f"Webhook Error: {e}", 500
    return '', 200

# ------------------------------
# Webhook Setup
# ------------------------------

if __name__ == "__main__":
    # Create downloads folder
    create_downloads_folder()

    # Set webhook
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print(f"✅ Webhook set to: {WEBHOOK_URL}")

    # Start Flask app
    app.run(host="0.0.0.0", port=8080)
