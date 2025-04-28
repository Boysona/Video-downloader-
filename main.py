import os
import logging
import uuid
import shutil
import telebot
import subprocess
from flask import Flask, request, abort

# Configure logging
logging.basicConfig(level=logging.INFO)

# Configuration
TOKEN = "7513880960:AAFt2TJowXrh3LJ63zafDuIF0Eybk-Wx9LQ"
REQUIRED_CHANNEL = "@guruubka_wasmada"
ADMIN_ID = 5978150981  # Your Telegram user ID

# Initialize bot and app
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Directories
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Track users
existing_users = set()
if os.path.exists('users.txt'):
    with open('users.txt', 'r') as f:
        existing_users = set(line.strip() for line in f)

# Admin state
admin_state = {}

# Check subscription
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
    bot.send_message(chat_id, "⚠️ Please join our channel to use the bot!", reply_markup=markup)

# Download video
def download_video(url):
    try:
        unique_id = str(uuid.uuid4())
        output_path = os.path.join(DOWNLOAD_DIR, f"{unique_id}.%(ext)s")
        command = ['yt-dlp', '--no-playlist', '-o', output_path, url]
        subprocess.run(command, check=True)
        # Find downloaded file
        for file in os.listdir(DOWNLOAD_DIR):
            if unique_id in file:
                return os.path.join(DOWNLOAD_DIR, file)
        return None
    except Exception as e:
        logging.error(f"Download error: {e}")
        return None

# Start handler
@bot.message_handler(commands=['start'])
def start_handler(message):
    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)

    user_id = str(message.from_user.id)
    if user_id not in existing_users:
        existing_users.add(user_id)
        with open('users.txt', 'a') as f:
            f.write(f"{user_id}\n")

    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name

    if message.from_user.id == ADMIN_ID:
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Send Ads (Broadcast)", "Total Users")
        bot.send_message(message.chat.id, "🔐 Welcome to Admin Panel", reply_markup=markup)
    else:
        welcome_text = f"👋 Salom {username}!\n\nSend me any video link (TikTok, YouTube, Instagram, & download !"
        bot.send_message(message.chat.id, welcome_text)

# Admin Panel Handlers
@bot.message_handler(func=lambda m: m.text == "Total Users" and m.from_user.id == ADMIN_ID)
def total_users(message):
    bot.send_message(message.chat.id, f"📈 Total users: {len(existing_users)}")

@bot.message_handler(func=lambda m: m.text == "Send Ads (Broadcast)" and m.from_user.id == ADMIN_ID)
def send_broadcast(message):
    admin_state[message.from_user.id] = 'awaiting_broadcast'
    bot.send_message(message.chat.id, "✏️ Send the broadcast message:")

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and admin_state.get(m.from_user.id) == 'awaiting_broadcast', content_types=['text', 'photo', 'video'])
def broadcast_message(message):
    admin_state[message.from_user.id] = None
    success = 0
    fail = 0
    for user_id in existing_users:
        try:
            bot.copy_message(user_id, message.chat.id, message.message_id)
            success += 1
        except Exception:
            fail += 1
    bot.send_message(message.chat.id, f"✅ Broadcast completed.\nSuccessful: {success}\nFailed: {fail}")

# Download Handler
@bot.message_handler(content_types=['text'])
def handle_url(message):
    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)

    url = message.text.strip()
    if url.startswith('http'):
        bot.send_message(message.chat.id, "⏳ Downloading your video, please wait...")
        file_path = download_video(url)
        if file_path:
            with open(file_path, 'rb') as video:
                bot.send_video(message.chat.id, video)
            os.remove(file_path)
        else:
            bot.send_message(message.chat.id, "❌ Failed to download the video. Please check the URL.")
    else:
        bot.send_message(message.chat.id, "⚠️ Please send a valid video URL!")

# Fallback Handler
@bot.message_handler(content_types=['photo', 'sticker', 'video', 'audio', 'voice', 'document'])
def fallback(message):
    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)
    bot.send_message(message.chat.id, "⚠️ Please send a valid video URL!")

# Webhook Endpoints
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
    webhook_url = "https://video-downloader-1pmv.onrender.com"  # Update this
    if webhook_url:
        bot.set_webhook(url=webhook_url)
        return f'Webhook set to: {webhook_url}', 200
    else:
        return 'No webhook URL provided.', 400

@app.route('/delete_webhook', methods=['GET', 'POST'])
def delete_webhook():
    bot.delete_webhook()
    return 'Webhook deleted.', 200

if __name__ == "__main__":
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    bot.delete_webhook()
    bot.set_webhook(url="https://video-downloader-1pmv.onrender.com")  # Update this
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8080)))
