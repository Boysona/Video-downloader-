import os
import re
import uuid
import shutil
import logging
import requests
import yt_dlp
import telebot
from flask import Flask, request, abort
from faster_whisper import WhisperModel
from datetime import datetime

# Configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TOKEN = "8136008912:AAHwM1ZBZ2WxgCnFpRA0MC_EIr9KcRQiF3c"
REQUIRED_CHANNEL = "@qolka_ka"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

ADMIN_ID = 5978150981
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

model = WhisperModel("tiny", device="cpu", compute_type="int8")

existing_users = set()
users_file = 'users.txt'
if os.path.exists(users_file):
    with open(users_file, 'r') as f:
        existing_users = set(line.strip() for line in f)

total_files_processed = 0
total_processing_time = 0.0
processing_start_time = None

FILE_SIZE_LIMIT = 20 * 1024 * 1024
URL_REGEX = r'(https?://[^\s]+)'
admin_state = {}

def check_subscription(user_id):
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.error(f"Subscription check error: {e}")
        return False

def send_subscription_message(chat_id):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(
        text="Ku Biir Channelka",
        url=f"https://t.me/{REQUIRED_CHANNEL[1:]}"
    ))
    bot.send_message(chat_id, "⚠️ Fadlan ku biir channelka si aad mar kale u isticmaashid botkaan!", reply_markup=markup)

def normalize_short_url(url: str) -> str:
    try:
        session = requests.Session()
        response = session.head(url, allow_redirects=True, timeout=10)
        return response.url
    except Exception as e:
        logging.warning(f"Redirect follow failed: {e}")
        return url

def transcribe(file_path: str) -> str | None:
    try:
        segments, _ = model.transcribe(file_path, beam_size=1)
        return " ".join(segment.text for segment in segments)
    except Exception as e:
        logging.error(f"Transcription error: {e}")
        return None

@bot.message_handler(func=lambda m: re.search(URL_REGEX, m.text or ""), content_types=['text'])
def handle_video_url(message):
    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)

    raw_url = re.search(URL_REGEX, message.text).group(1)
    url = normalize_short_url(raw_url)

    bot.send_chat_action(message.chat.id, 'upload_video')

    filename = None
    try:
        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                              '(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
            }
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
            except Exception as e:
                logging.error(f"Download failed: {e}")
                bot.send_message(message.chat.id, f"⚠️ Ma awoodo in aan soo dejiyo video-gaan. Khalad: {str(e)}")
                return

        transcription = transcribe(filename)

        with open(filename, 'rb') as vid:
            bot.send_video(message.chat.id, vid, supports_streaming=True)

        if transcription:
            if len(transcription) > 2000:
                with open('description.txt', 'w', encoding='utf-8') as f:
                    f.write(transcription)
                with open('description.txt', 'rb') as f:
                    bot.send_document(message.chat.id, f)
                os.remove('description.txt')
            else:
                bot.send_message(message.chat.id, f"📝\n\n{transcription}")
        else:
            bot.send_message(message.chat.id, "⚠️ Ma awoodo in aan soo saaro description-ka video-gaan.")

    except Exception as e:
        logging.error(f"General error: {e}")
        bot.send_message(message.chat.id, "⚠️ Khalad ayaa dhacay intii aan soo dejinayay ama falanqaynayay video-ga.")
    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)

# ... (kudar qaybaha kale sida /start, voice handlers, webhook, iwm)

if __name__ == "__main__":
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    bot.delete_webhook()
    bot.set_webhook(url="https://video-downloader-1pmv.onrender.com")
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8080)))
