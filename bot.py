import telebot
from telebot import types
import subprocess
import sys
import os
import re

# ========== ОБНОВЛЯЕМ yt-dlp ==========
try:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"])
    print("✅ yt-dlp обновлён")
except:
    print("⚠️ Не удалось обновить yt-dlp")

import yt_dlp

# ========== НАСТРОЙКИ ==========
TG_TOKEN = '8681585910:AAEvXnyGeP3UeskKi08OW46MUwbO3GUcG_o'
CHANNEL_ID = '-1001888094511'
CHANNEL_URL = 'https://t.me/lyubimkatt'

bot = telebot.TeleBot(TG_TOKEN)

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📥 Скачать TikTok")
    markup.add("❓ Помощь")
    return markup

def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_ID, user_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return True

def download_tiktok(url):
    opts = {
        'format': 'best',
        'outtmpl': '/tmp/tiktok_%(id)s.%(ext)s',
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename, info.get('title', 'TikTok')

@bot.message_handler(commands=['start'])
def start(message):
    if not is_subscribed(message.from_user.id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_URL))
        markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
        bot.send_message(message.chat.id, "⚠️ *Доступ закрыт!*", reply_markup=markup, parse_mode='Markdown')
    else:
        bot.send_message(message.chat.id, "📥 *TikTok Downloader готов!*", reply_markup=main_menu(), parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == "📥 Скачать TikTok")
def download_button(message):
    if not is_subscribed(message.from_user.id):
        bot.send_message(message.chat.id, "⚠️ Сначала подпишись на канал!")
        return
    bot.send_message(message.chat.id, "🔗 *Отправь ссылку на TikTok*", parse_mode='Markdown')
    bot.register_next_step_handler(message, process_tiktok)

@bot.message_handler(func=lambda msg: msg.text == "❓ Помощь")
def help_button(message):
    bot.send_message(message.chat.id, "📥 Отправь ссылку на TikTok, я скачаю видео без водяного знака.", reply_markup=main_menu(), parse_mode='Markdown')

def process_tiktok(message):
    if not is_subscribed(message.from_user.id):
        bot.send_message(message.chat.id, "⚠️ Сначала подпишись на канал!")
        return
    
    url = message.text.strip()
    if 'tiktok.com' not in url:
        bot.send_message(message.chat.id, "❌ Это не ссылка TikTok!")
        return
    
    wait = bot.send_message(message.chat.id, "📥 *Скачиваю...*", parse_mode='Markdown')
    try:
        filename, title = download_tiktok(url)
        with open(filename, 'rb') as video:
            bot.send_video(message.chat.id, video, caption=f"🎬 *{title[:100]}*", parse_mode='Markdown')
        os.remove(filename)
        bot.delete_message(message.chat.id, wait.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка: {e}", message.chat.id, wait.message_id)

@bot.message_handler(func=lambda msg: 'tiktok.com' in msg.text)
def handle_tiktok_url(message):
    if not is_subscribed(message.from_user.id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_URL))
        markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
        bot.send_message(message.chat.id, "⚠️ *Доступ закрыт!*", reply_markup=markup, parse_mode='Markdown')
        return
    
    wait = bot.send_message(message.chat.id, "📥 *Скачиваю...*", parse_mode='Markdown')
    try:
        filename, title = download_tiktok(message.text)
        with open(filename, 'rb') as video:
            bot.send_video(message.chat.id, video, caption=f"🎬 *{title[:100]}*", parse_mode='Markdown')
        os.remove(filename)
        bot.delete_message(message.chat.id, wait.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка: {e}", message.chat.id, wait.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_callback(call):
    if is_subscribed(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Подписка подтверждена!")
        bot.edit_message_text("🎉 Спасибо!", call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "📥 *TikTok Downloader готов!*", reply_markup=main_menu(), parse_mode='Markdown')
    else:
        bot.answer_callback_query(call.id, "❌ Вы ещё не подписаны!", show_alert=True)

if __name__ == '__main__':
    print("📥 TikTok Downloader Bot запущен!")
    bot.polling(none_stop=True)
