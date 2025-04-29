import os
import re
import uuid
import shutil
import logging
import requests
import yt_dlp
import telebot
from flask import Flask, request, abort
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from faster_whisper import WhisperModel
from PIL import Image
from io import BytesIO
from datetime import datetime

# ——— CONFIG ———
TOKEN = "8136008912:AAHwM1ZBZ2WxgCnFpRA0MC_EIr9KcRQiF3c"
ADMIN_ID = 5978150981
REQUIRED_CHANNEL = "@qolka_ka"

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
FILE_SIZE_LIMIT = 20 * 1024 * 1024  # 20MB

# ——— Logging ———
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# ——— Bot & Flask ———
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ——— Whisper Model ———
model = WhisperModel(model_size_or_path="tiny", device="cpu", compute_type="int8")

# ——— User Tracking ———
users_file = 'users.txt'
existing_users = set()
if os.path.exists(users_file):
    with open(users_file, 'r') as f:
        existing_users = set(line.strip() for line in f)
total_files_processed = 0
total_processing_time = 0.0

admin_state = {}

# ——— Helpers ———
def check_subscription(user_id):
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ['member','administrator','creator']
    except:
        return False

def send_subscription_message(chat_id):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(
        text="Join Channel", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}"
    ))
    bot.send_message(chat_id, "⚠️ Fadlan ku biir channel-ka si aad u isticmaasho bot-kan.", reply_markup=markup)

def record_user(user_id):
    if str(user_id) not in existing_users:
        existing_users.add(str(user_id))
        with open(users_file,'a') as f: f.write(f"{user_id}\n")

def format_timedelta(sec):
    h=int(sec//3600); m=int((sec%3600)//60)
    return f"{h}h {m}m"

def transcribe(path):
    try:
        segments,_ = model.transcribe(path, beam_size=1)
        return " ".join(s.text for s in segments)
    except Exception as e:
        logging.error("Transcription error: %s", e)
        return None

def is_supported_url(url):
    platforms = ['tiktok.com','youtube.com','pinterest.com','pin.it','youtu.be',
                 'instagram.com','snapchat.com','facebook.com','x.com','twitter.com']
    return any(p in url.lower() for p in platforms)

def is_youtube_url(url):
    return 'youtube.com' in url.lower() or 'youtu.be' in url.lower()

# ——— Handlers ———
@bot.message_handler(commands=['start'])
def start(m):
    record_user(m.from_user.id)
    if not check_subscription(m.from_user.id):
        return send_subscription_message(m.chat.id)
    if m.from_user.id == ADMIN_ID:
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Send Broadcast","Total Users","/status")
        bot.send_message(m.chat.id, "🔧 Admin Panel", reply_markup=markup)
    else:
        name = m.from_user.username or m.from_user.first_name
        bot.send_message(m.chat.id, f"👋 Salaam {name}!\n• U dir voice/video/audio si aan u qoraal u badalo.\n• Ama u dir link video social media si aan u soo dejiyo.")

@bot.message_handler(commands=['status'])
def status(m):
    total=len(existing_users)
    bot.send_message(m.chat.id,
        f"📊 Stats:\n• Total users: {total}\n• Files processed: {total_files_processed}\n• Time spent: {format_timedelta(total_processing_time)}")

@bot.message_handler(func=lambda m: m.text=="Total Users" and m.from_user.id==ADMIN_ID)
def total_u(m):
    bot.send_message(m.chat.id, f"Total users: {len(existing_users)}")

@bot.message_handler(func=lambda m: m.text=="Send Broadcast" and m.from_user.id==ADMIN_ID)
def ask_broadcast(m):
    admin_state[m.from_user.id]='awaiting_broadcast'
    bot.send_message(m.chat.id, "Fadlan qor farriinta broadcast-ka:")

@bot.message_handler(func=lambda m: m.from_user.id==ADMIN_ID and admin_state.get(m.from_user.id)=='awaiting_broadcast',
                     content_types=['text','photo','video','audio','document'])
def do_broadcast(m):
    admin_state[m.from_user.id]=None
    success=fail=0
    for uid in existing_users:
        try:
            bot.copy_message(uid, m.chat.id, m.message_id)
            success+=1
        except:
            fail+=1
    bot.send_message(m.chat.id,f"Broadcast done. ✅ {success}\n❌ {fail}")

@bot.message_handler(content_types=['voice','audio','video','video_note'])
def handle_media(m):
    if not check_subscription(m.from_user.id):
        return send_subscription_message(m.chat.id)
    f = m.voice or m.audio or m.video or m.video_note
    if f.file_size>FILE_SIZE_LIMIT:
        return bot.send_message(m.chat.id,"⚠️ File ka way weyn yahay 20MB.")
    info=bot.get_file(f.file_id)
    path=os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.ogg")
    bot.download_file(info.file_path, open(path,'wb').write)
    bot.send_chat_action(m.chat.id,'typing')
    global total_files_processed, total_processing_time
    start=datetime.now()
    txt=transcribe(path)
    dur=(datetime.now()-start).total_seconds()
    total_files_processed+=1; total_processing_time+=dur
    if txt:
        if len(txt)>2000:
            with open('out.txt','w',encoding='utf-8') as ff: ff.write(txt)
            bot.send_document(m.chat.id, open('out.txt','rb'))
            os.remove('out.txt')
        else:
            bot.reply_to(m, txt)
    else:
        bot.send_message(m.chat.id,"⚠️ Ma awoodo in aan qoraal ka sameeyo.")
    os.remove(path)

@bot.message_handler(func=lambda m: m.text and is_youtube_url(m.text))
def yt_info(m):
    url=m.text; bot.send_chat_action(m.chat.id,'typing')
    try:
        ydl_opts={'quiet':True,'no_warnings':True,'extract_flat':True,'skip_download':True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info=ydl.extract_info(url, False)
        title,thumb,formats = info.get('title'), info.get('thumbnail'), info.get('formats',[])
        res_map={}
        for f in formats:
            if f.get('vcodec')!='none' and f.get('acodec')!='none' and f.get('height'):
                h=f['height']
                if h<=1080: res_map[f"{h}p"]=f['format_id']
        if not res_map:
            return bot.send_message(m.chat.id,"Ma jiro format video la heli karo.")
        markup=InlineKeyboardMarkup(row_width=3)
        for res in sorted(res_map, key=lambda x:int(x[:-1])):
            fmt=res_map[res]
            vid=str(uuid.uuid4())[:8]
            bot.video_info = getattr(bot,'video_info',{})
            bot.video_info[vid]={'url':url,'format_id':fmt}
            markup.add(InlineKeyboardButton(res,callback_data=f"dl:{vid}"))
        if thumb:
            resp=requests.get(thumb); bio=BytesIO(resp.content)
            bot.send_photo(m.chat.id, bio, caption=title, reply_markup=markup)
        else:
            bot.send_message(m.chat.id,f"Dooro quality: {title}", reply_markup=markup)
    except Exception as e:
        bot.send_message(m.chat.id,f"Error: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith('dl:'))
def dl_cb(c):
    vid=c.data.split(':',1)[1]
    info=getattr(bot,'video_info',{}).get(vid)
    if not info:
        return bot.answer_callback_query(c.id,"Waayow waqti ayaa dhaaftay, isku day mar kale.")
    bot.answer_callback_query(c.id,"Downloading...")
    out=os.path.join(DOWNLOAD_DIR,f"{uuid.uuid4()}.mp4")
    ydl_opts={'format':info['format_id'],'outtmpl':out,'quiet':True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([info['url']])
    bot.send_chat_action(c.message.chat.id,'upload_video')
    bot.send_video(c.message.chat.id, open(out,'rb'))
    os.remove(out)

@bot.message_handler(func=lambda m: m.text and is_supported_url(m.text))
def other_social(m):
    try:
        bot.send_chat_action(m.chat.id,'record_video')
        out=os.path.join(DOWNLOAD_DIR,f"{uuid.uuid4()}.mp4")
        ydl_opts={'format':'bestvideo+bestaudio','merge_output_format':'mp4','outtmpl':out,'quiet':True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([m.text])
        bot.send_video(m.chat.id, open(out,'rb'))
        os.remove(out)
    except Exception as e:
        bot.send_message(m.chat.id,f"Error: {e}")

@bot.message_handler(func=lambda m: True, content_types=['text','photo','sticker','document'])
def fallback(m):
    if not check_subscription(m.from_user.id):
        return send_subscription_message(m.chat.id)
    bot.send_message(m.chat.id,"⚠️ Fadlan u dir voice/video/audio ama link social media.")

# ——— Webhook routes ———
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
    webhook_url = "https://video-downloader-1pmv.onrender.com"
    bot.set_webhook(url=webhook_url)
    return f'Webhook set to: {webhook_url}', 200

@app.route('/delete_webhook', methods=['GET', 'POST'])
def del_webhook():
    bot.delete_webhook()
    return "Webhook deleted", 200

if __name__ == "__main__":
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    bot.delete_webhook()
    bot.set_webhook(url="https://video-downloader-1pmv.onrender.com")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
