import os
import re
import uuid
import shutil
import logging
import requests
import telebot
import yt_dlp
from flask import Flask, request, abort
from faster_whisper import WhisperModel
from datetime import datetime
from PIL import Image
from io import BytesIO

# Configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Bot Configuration
TOKEN = "8136008912:AAHwM1ZBZ2WxgCnFpRA0MC_EIr9KcRQiF3c"
REQUIRED_CHANNEL = "@qolka_ka"
ADMIN_ID = 5978150981
BALOW_LINK = "https://www.tiktok.com/@zack3d2?_t=ZN-8vxFGTfLsQg&_r=1"
DOWNLOAD_DIR = "downloads"
FILE_SIZE_LIMIT = 20 * 1024 * 1024

# Initialize components
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Whisper Model
model = WhisperModel(
    model_size_or_path="tiny",
    device="cpu",
    compute_type="int8"
)

# User Tracking
existing_users = set()
users_file = 'users.txt'
if os.path.exists(users_file):
    with open(users_file, 'r') as f:
        existing_users = set(line.strip() for line in f)

# Processing Statistics
total_files_processed = 0
total_processing_time = 0.0
processing_start_time = None
admin_state = {}

# Helper Functions
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
        text="Join Channel",
        url=f"https://t.me/{REQUIRED_CHANNEL[1:]}"
    ))
    bot.send_message(chat_id, "⚠️ Please join our channel to continue!", reply_markup=markup)

def is_supported_url(url):
    platforms = ['tiktok.com', 'youtube.com', 'pinterest.com', 'pin.it', 'youtu.be',
                 'instagram.com', 'snapchat.com', 'facebook.com', 'x.com', 'twitter.com']
    return any(p in url.lower() for p in platforms)

def is_youtube_url(url):
    return 'youtube.com' in url.lower() or 'youtu.be' in url.lower()

def get_balow_button():
    keyboard = InlineKeyboardMarkup()
    button = InlineKeyboardButton(text="Get Content", url=BALOW_LINK)
    keyboard.add(button)
    return keyboard

# Handlers
@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = str(message.from_user.id)
    if user_id not in existing_users:
        existing_users.add(user_id)
        with open(users_file, 'a') as f:
            f.write(f"{user_id}\n")

    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)

    username = message.from_user.first_name or "there"
    text = f"""👋 Hello {username}!

📥 Send me:
- Media files (voice/audio/video) for transcription
- Social media links (TikTok, YouTube, etc.) for download

I'll process them and send back the results!"""
    
    if message.from_user.id == ADMIN_ID:
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Send Broadcast", "Total Users", "/status")
        bot.send_message(message.chat.id, text, reply_markup=markup)
    else:
        bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['status'])
def status_handler(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    total_users = len(existing_users)
    status_text = f"""📊 Bot Statistics
Users: {total_users}
Files Processed: {total_files_processed}
Total Processing Time: {total_processing_time:.2f}s
"""
    bot.send_message(message.chat.id, status_text)

# Media Processing Handlers
@bot.message_handler(content_types=['voice', 'audio', 'video', 'video_note'])
def handle_media(message):
    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)

    file_size = (message.voice or message.audio or message.video or message.video_note).file_size
    if file_size > FILE_SIZE_LIMIT:
        return bot.send_message(message.chat.id, "⚠️ File too large! Max 20MB.")

    process_media_file(message)

def process_media_file(message):
    try:
        file_info = bot.get_file(message.voice or message.audio or message.video or message.video_note.file_id)
        file_path = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.ogg")
        
        bot.send_chat_action(message.chat.id, 'typing')
        downloaded_file = bot.download_file(file_info.file_path)
        with open(file_path, 'wb') as f:
            f.write(downloaded_file)

        global processing_start_time
        processing_start_time = datetime.now()
        transcription = transcribe(file_path)
        
        global total_files_processed, total_processing_time
        total_files_processed += 1
        total_processing_time += (datetime.now() - processing_start_time).total_seconds()

        if transcription:
            send_transcription_result(message, transcription)
        else:
            bot.send_message(message.chat.id, "⚠️ Transcription failed.")
            
    except Exception as e:
        logging.error(f"Media processing error: {e}")
        bot.send_message(message.chat.id, "⚠️ Processing error.")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

def send_transcription_result(message, text):
    if len(text) > 2000:
        with open('transcription.txt', 'w') as f:
            f.write(text)
        with open('transcription.txt', 'rb') as f:
            bot.send_document(message.chat.id, f)
        os.remove('transcription.txt')
    else:
        bot.reply_to(message, text)

# URL Processing Handlers
@bot.message_handler(func=lambda msg: is_supported_url(msg.text))
def handle_url(message):
    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)

    if is_youtube_url(message.text):
        process_youtube_url(message)
    else:
        process_social_media_url(message)

def process_youtube_url(message):
    try:
        ydl_opts = {'quiet': True, 'extract_flat': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(message.text, download=False)
        
        formats = {f['format_id']: f['height'] for f in info['formats'] 
                   if f.get('height') and f['vcodec'] != 'none'}
        
        markup = InlineKeyboardMarkup()
        for fid, height in sorted(formats.items(), key=lambda x: x[1]):
            markup.add(InlineKeyboardButton(f"{height}p", callback_data=f"yt:{fid}"))
        
        bot.send_message(message.chat.id, "Select quality:", reply_markup=markup)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Error: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('yt:'))
def handle_yt_quality(call):
    try:
        format_id = call.data.split(':')[1]
        url = call.message.reply_to_message.text
        
        bot.send_chat_action(call.message.chat.id, 'upload_video')
        with yt_dlp.YoutubeDL({'format': format_id}) as ydl:
            file_path = ydl.prepare_filename(ydl.extract_info(url, download=False))
            ydl.download([url])
            
        with open(file_path, 'rb') as f:
            bot.send_video(call.message.chat.id, f)
            
    except Exception as e:
        bot.send_message(call.message.chat.id, f"⚠️ Download error: {str(e)}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

def process_social_media_url(message):
    try:
        with yt_dlp.YoutubeDL({'format': 'best'}) as ydl:
            file_path = ydl.prepare_filename(ydl.extract_info(message.text, download=False))
            ydl.download([message.text])
            
        with open(file_path, 'rb') as f:
            bot.send_video(message.chat.id, f)
            
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Error: {str(e)}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# Webhook Setup
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
        return '', 200
    abort(403)

if __name__ == "__main__":
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    bot.remove_webhook()
    bot.set_webhook(url="https://video-downloader-1pmv.onrender.com")
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8080)))
