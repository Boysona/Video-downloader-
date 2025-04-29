import os
import uuid
import telebot
import yt_dlp
import requests
from flask import Flask, request
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from PIL import Image
from io import BytesIO

# ========== SETTINGS ==========
BOT_TOKEN = "8136008912:AAHwM1ZBZ2WxgCnFpRA0MC_EIr9KcRQiF3c"
REQUIRED_CHANNEL = "@qolka_ka"
ADMIN_ID = 5978150981
WEBHOOK_URL = "https://video-downloader-1pmv.onrender.com"  # <--Update this!
PORT = int(os.environ.get('PORT', 5000))
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
user_db = set()

# ========== HELPERS ==========
def is_supported_url(url):
    platforms = ['tiktok.com', 'youtube.com', 'pinterest.com', 'pin.it', 'youtu.be',
                 'instagram.com', 'snapchat.com', 'facebook.com', 'x.com', 'twitter.com']
    return any(p in url.lower() for p in platforms)

def check_subscription(user_id):
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ['member', 'creator', 'administrator']
    except:
        return False

def get_join_channel_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Join Channel", url=f"https://t.me/{REQUIRED_CHANNEL.strip('@')}"))
    return markup

# ========== HANDLERS ==========
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_db.add(message.from_user.id)
    if not check_subscription(message.from_user.id):
        bot.send_message(message.chat.id, "Fadlan ku biir kanaalka si aad u isticmaasho bot-kan.", reply_markup=get_join_channel_markup())
        return
    bot.send_message(message.chat.id, "Salam! Isii link muuqaal ah si aan kuu soo dejiyo.")

@bot.message_handler(commands=['broadcast'])
def handle_broadcast(message):
    if message.from_user.id != ADMIN_ID:
        return
    msg = message.text.split(" ", 1)
    if len(msg) < 2:
        bot.send_message(message.chat.id, "Isticmaal: /broadcast fariin")
        return
    for uid in user_db:
        try:
            bot.send_message(uid, msg[1])
        except:
            continue
    bot.send_message(message.chat.id, "Fariinta waa la diray.")

@bot.message_handler(commands=['users'])
def handle_users(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(message.chat.id, f"Tirada users: {len(user_db)}")

@bot.message_handler(func=lambda msg: is_supported_url(msg.text))
def handle_video_url(msg):
    if not check_subscription(msg.from_user.id):
        bot.send_message(msg.chat.id, "Fadlan marka hore ku biir kanaalka.", reply_markup=get_join_channel_markup())
        return

    url = msg.text
    try:
        bot.send_chat_action(msg.chat.id, 'typing')
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'outtmpl': os.path.join(DOWNLOAD_DIR, f"%(title)s.%(ext)s"),
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info)

        bot.send_chat_action(msg.chat.id, 'upload_video')
        with open(video_path, 'rb') as f:
            bot.send_video(msg.chat.id, f, caption="Muuqaalkaga waa kan.")
        os.remove(video_path)

    except Exception as e:
        bot.send_message(msg.chat.id, f"Error: {str(e)}")

# ========== WEBHOOK SETUP ==========
@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def index():
    return "Bot is running."

if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=PORT)
