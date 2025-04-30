
import os
import re
import uuid
import shutil
import logging
import requests
import telebot
import yt_dlp
from flask import Flask, request, abort
from PIL import Image
from io import BytesIO
from faster_whisper import WhisperModel
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ---- Bot Setup ----
TOKEN = "8136008912:AAHwM1ZBZ2WxgCnFpRA0MC_EIr9KcRQiF3c"  # Hal token un isticmaal
REQUIRED_CHANNEL = "@qolka_ka"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
ADMIN_ID = 5978150981

# ---- Directories ----
DOWNLOAD_DIR = "downloads"
if os.path.exists(DOWNLOAD_DIR):
    shutil.rmtree(DOWNLOAD_DIR)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ---- Whisper Model ----
model = WhisperModel("tiny", device="cpu", compute_type="int8")

# ---- Users Tracking ----
existing_users = set()
users_file = 'users.txt'
if os.path.exists(users_file):
    with open(users_file, 'r') as f:
        existing_users = set(line.strip() for line in f)

# ---- Misc ----
total_files_processed = 0
total_processing_time = 0.0
processing_start_time = None
FILE_SIZE_LIMIT = 20 * 1024 * 1024
BALOW_LINK = "https://www.tiktok.com/@zack3d2?_t=ZN-8vMGXY3EkEw&_r=1"
admin_state = {}

# ---- Utility Functions ----
def check_subscription(user_id):
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def send_subscription_message(chat_id):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Join the Channel", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}"))
    bot.send_message(chat_id, "⚠️ Please join the channel to continue!", reply_markup=markup)

def format_timedelta(seconds):
    h, m = int(seconds // 3600), int((seconds % 3600) // 60)
    return f"{h}h {m}m"

def get_balow_button():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text="Summarize | Get", url=BALOW_LINK))
    return keyboard

def is_supported_url(url):
    return any(p in url.lower() for p in [
        'tiktok.com', 'youtube.com', 'pinterest.com', 'pin.it',
        'instagram.com', 'snapchat.com', 'facebook.com', 'x.com', 'twitter.com'
    ])

def is_youtube_url(url):
    return 'youtube.com' in url or 'youtu.be' in url

def transcribe(file_path):
    try:
        segments, _ = model.transcribe(file_path, beam_size=1)
        return " ".join(seg.text for seg in segments)
    except Exception as e:
        return None

# ---- Command Handlers ----
@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = str(message.from_user.id)
    if user_id not in existing_users:
        existing_users.add(user_id)
        with open(users_file, 'a') as f:
            f.write(f"{user_id}\n")

    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)

    if message.from_user.id == ADMIN_ID:
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Send Broadcast", "Total Users", "/status")
        bot.send_message(message.chat.id, "Admin Panel", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, 
            "👋 Send me voice/video/audio to transcribe OR a TikTok/YouTube/social link to download.")

@bot.message_handler(commands=['status'])
def status_handler(message):
    bot.send_message(message.chat.id, f"📊 Files processed: {total_files_processed}\n⏱ Time: {format_timedelta(total_processing_time)}")

@bot.message_handler(func=lambda m: m.text == "Total Users" and m.from_user.id == ADMIN_ID)
def total_users(message):
    bot.send_message(message.chat.id, f"Total users: {len(existing_users)}")

@bot.message_handler(func=lambda m: m.text == "Send Broadcast" and m.from_user.id == ADMIN_ID)
def send_broadcast(message):
    admin_state[message.from_user.id] = 'awaiting_broadcast'
    bot.send_message(message.chat.id, "Send the message to broadcast:")

@bot.message_handler(func=lambda m: admin_state.get(m.from_user.id) == 'awaiting_broadcast',
                     content_types=['text', 'photo', 'video', 'audio', 'document'])
def broadcast(message):
    admin_state[message.from_user.id] = None
    for uid in existing_users:
        try:
            bot.copy_message(uid, message.chat.id, message.message_id)
        except: pass
    bot.send_message(message.chat.id, "Broadcast done.")

# ---- File Transcription Handler ----
@bot.message_handler(content_types=['voice', 'audio', 'video', 'video_note'])
def handle_transcription(message):
    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)

    file_size = (message.voice or message.audio or message.video or message.video_note).file_size
    if file_size > FILE_SIZE_LIMIT:
        return bot.send_message(message.chat.id, "⚠️ File too large (max 20MB)")

    file_id = (message.voice or message.audio or message.video or message.video_note).file_id
    file_info = bot.get_file(file_id)
    file_path = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.ogg")
    downloaded_file = bot.download_file(file_info.file_path)
    with open(file_path, 'wb') as f:
        f.write(downloaded_file)

    global total_files_processed, total_processing_time
    start = datetime.now()
    transcript = transcribe(file_path)
    total_files_processed += 1
    total_processing_time += (datetime.now() - start).total_seconds()

    if transcript:
        bot.send_message(message.chat.id, transcript[:4096])
    else:
        bot.send_message(message.chat.id, "⚠️ Couldn't transcribe the audio.")
    os.remove(file_path)

# ---- Social Media & YouTube Handler ----
@bot.message_handler(func=lambda msg: is_youtube_url(msg.text))
def handle_youtube(msg):
    url = msg.text
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title')
            formats = {f"{f['height']}p": f['format_id'] for f in info['formats']
                       if f.get('height') and f.get('vcodec') != 'none'}

        markup = InlineKeyboardMarkup()
        for res, fmt in formats.items():
            vid = str(uuid.uuid4())[:8]
            bot.video_info = getattr(bot, 'video_info', {})
            bot.video_info[vid] = {'url': url, 'format_id': fmt}
            markup.add(InlineKeyboardButton(res, callback_data=f'dl:{vid}'))

        bot.send_message(msg.chat.id, f"Choose quality for: {title}", reply_markup=markup)
    except Exception as e:
        bot.send_message(msg.chat.id, f"Error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("dl:"))
def download_video(call):
    vid = call.data.split(":")[1]
    data = bot.video_info.get(vid)
    output = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp4")
    with yt_dlp.YoutubeDL({'format': data['format_id'], 'outtmpl': output, 'quiet': True}) as ydl:
        ydl.download([data['url']])
    with open(output, 'rb') as v:
        bot.send_video(call.message.chat.id, v)
    os.remove(output)

@bot.message_handler(func=lambda msg: is_supported_url(msg.text) and not is_youtube_url(msg.text))
def handle_social(msg):
    url = msg.text
    output = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp4")
    with yt_dlp.YoutubeDL({'format': 'best', 'outtmpl': output, 'quiet': True}) as ydl:
        ydl.download([url])
    with open(output, 'rb') as v:
        bot.send_video(msg.chat.id, v)
    os.remove(output)

@bot.message_handler(func=lambda m: True, content_types=['text'])
def fallback(message):
    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)
    bot.send_message(message.chat.id, "Send voice/audio/video OR social media link.")

# ---- Webhook Routes ----
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        abort(403)

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    webhook_url = "https://YOUR-WEBHOOK-URL"  # BADAL
    bot.set_webhook(url=webhook_url)
    return 'Webhook set'

@app.route('/delete_webhook', methods=['GET'])
def delete_webhook():
    bot.delete_webhook()
    return 'Webhook deleted'

if __name__ == '__main__':
    bot.delete_webhook()
    bot.set_webhook(url="https://video-downloader-1pmv.onrender.com")  # BADAL
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8080)))
