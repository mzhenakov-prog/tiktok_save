import telebot
from telebot import types
import yt_dlp
import os
import re
import time
import sqlite3
from datetime import datetime

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = '8681585910:AAEvXnyGeP3UeskKi08OW46MUwbO3GUcG_o'
ADMIN_ID = 5298604296
BOT_USERNAME = 'tt_saveeee_bot'
CHANNEL_ID = '-1001888094511'
CHANNEL_URL = 'https://t.me/lyubimkatt'

bot = telebot.TeleBot(BOT_TOKEN)

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect('tiktok_bot.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_seen TEXT,
                  ref_code TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ref_links
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  code TEXT UNIQUE,
                  label TEXT,
                  clicks INTEGER DEFAULT 0,
                  created_at TEXT)''')
    conn.commit()
    conn.close()

def add_user(user_id, username, ref_code=None):
    conn = sqlite3.connect('tiktok_bot.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_seen, ref_code) VALUES (?, ?, ?, ?)",
              (user_id, username, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ref_code))
    if ref_code:
        c.execute("UPDATE ref_links SET clicks = clicks + 1 WHERE code = ?", (ref_code,))
    conn.commit()
    conn.close()

def add_ref_link(code, label):
    conn = sqlite3.connect('tiktok_bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO ref_links (code, label, created_at) VALUES (?, ?, ?)",
              (code, label, datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()

def get_ref_links():
    conn = sqlite3.connect('tiktok_bot.db')
    rows = conn.execute("SELECT code, label, clicks, created_at FROM ref_links ORDER BY id DESC").fetchall()
    conn.close()
    return rows

def delete_ref_link(code):
    conn = sqlite3.connect('tiktok_bot.db')
    c = conn.cursor()
    c.execute("DELETE FROM ref_links WHERE code = ?", (code,))
    conn.commit()
    conn.close()

init_db()

# ========== ПРОВЕРКА ПОДПИСКИ ==========
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_ID, user_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return False

# ========== СКАЧИВАНИЕ TIKTOK ==========
def download_tiktok(url):
    opts = {
        'format': 'best',
        'outtmpl': '/tmp/tiktok_%(id)s.%(ext)s',
        'quiet': True,
        'ignoreerrors': True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return filename, info.get('title', 'TikTok')
    except Exception as e:
        print(f"Ошибка: {e}")
        return None, None

# ========== КНОПКИ ==========
def main_menu(is_admin=False):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📥 Скачать TikTok")
    if is_admin:
        markup.add("🔗 Рефералка")
    markup.add("❓ Помощь")
    return markup

def ref_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Создать ссылку", callback_data="ref_create"))
    markup.add(types.InlineKeyboardButton("📊 Мои ссылки", callback_data="ref_list"))
    return markup

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    uname = message.from_user.username or "unknown"
    
    args = message.text.split()
    ref_code = None
    if len(args) > 1:
        ref_code = args[1]
    
    add_user(uid, uname, ref_code)
    
    if not is_subscribed(uid):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_URL))
        markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
        bot.send_message(message.chat.id, "⚠️ *Доступ закрыт!*\n\nПодпишись на канал.", reply_markup=markup, parse_mode='Markdown')
        return
    
    is_admin = (uid == ADMIN_ID)
    bot.send_message(message.chat.id, "📥 *TikTok Downloader готов!*", reply_markup=main_menu(is_admin), parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📥 Скачать TikTok")
def download_button(message):
    uid = message.from_user.id
    if not is_subscribed(uid):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_URL))
        markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
        bot.send_message(message.chat.id, "⚠️ *Доступ закрыт!*", reply_markup=markup, parse_mode='Markdown')
        return
    
    bot.send_message(message.chat.id, "🔗 *Отправь ссылку на TikTok*", parse_mode='Markdown')
    bot.register_next_step_handler(message, process_tiktok)

def process_tiktok(message):
    uid = message.from_user.id
    if not is_subscribed(uid):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_URL))
        markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
        bot.send_message(message.chat.id, "⚠️ *Доступ закрыт!*", reply_markup=markup, parse_mode='Markdown')
        return
    
    url = message.text.strip()
    if 'tiktok.com' not in url:
        bot.send_message(message.chat.id, "❌ Это не ссылка TikTok!", parse_mode='Markdown')
        return
    
    wait = bot.send_message(message.chat.id, "📥 *Скачиваю...*", parse_mode='Markdown')
    try:
        filename, title = download_tiktok(url)
        if not filename:
            raise Exception("Не удалось скачать")
        with open(filename, 'rb') as f:
            bot.send_video(message.chat.id, f, caption=f"🎬 *{title[:100]}*\n\n📥 Скачано с @{BOT_USERNAME}")
        os.remove(filename)
        bot.delete_message(message.chat.id, wait.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка: {e}", message.chat.id, wait.message_id, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🔗 Рефералка")
def ref_cmd(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Только для создателя.")
        return
    bot.send_message(message.chat.id, "🔗 *Реферальная панель*", reply_markup=ref_menu(), parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "❓ Помощь")
def help_cmd(message):
    uid = message.from_user.id
    if not is_subscribed(uid):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_URL))
        markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
        bot.send_message(message.chat.id, "⚠️ *Доступ закрыт!*", reply_markup=markup, parse_mode='Markdown')
        return
    
    is_admin = (uid == ADMIN_ID)
    help_text = "📥 *TikTok Downloader*\n\n📥 Скачать TikTok — отправь ссылку\n❓ Помощь — это сообщение"
    if is_admin:
        help_text += "\n\n🔗 *Рефералка* — создавай ссылки"
    help_text += "\n\n@avgustc"
    bot.send_message(message.chat.id, help_text, reply_markup=main_menu(is_admin), parse_mode='Markdown')

@bot.message_handler(func=lambda m: 'tiktok.com' in m.text)
def handle_tiktok_url(message):
    uid = message.from_user.id
    if not is_subscribed(uid):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_URL))
        markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
        bot.send_message(message.chat.id, "⚠️ *Доступ закрыт!*", reply_markup=markup, parse_mode='Markdown')
        return
    
    wait = bot.send_message(message.chat.id, "📥 *Скачиваю...*", parse_mode='Markdown')
    try:
        filename, title = download_tiktok(message.text)
        if not filename:
            raise Exception("Не удалось скачать")
        with open(filename, 'rb') as f:
            bot.send_video(message.chat.id, f, caption=f"🎬 *{title[:100]}*\n\n📥 Скачано с @{BOT_USERNAME}")
        os.remove(filename)
        bot.delete_message(message.chat.id, wait.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка: {e}", message.chat.id, wait.message_id, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_callback(call):
    if is_subscribed(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Подписка подтверждена!")
        bot.edit_message_text("🎉 Спасибо!", call.message.chat.id, call.message.message_id)
        uid = call.from_user.id
        is_admin = (uid == ADMIN_ID)
        bot.send_message(call.message.chat.id, "📥 *TikTok Downloader готов!*", reply_markup=main_menu(is_admin), parse_mode='Markdown')
    else:
        bot.answer_callback_query(call.id, "❌ Вы ещё не подписаны!", show_alert=True)

# ========== РЕФЕРАЛЬНЫЕ КНОПКИ ==========
@bot.callback_query_handler(func=lambda call: call.data == "ref_create")
def create_ref(call):
    if call.from_user.id != ADMIN_ID:
        return
    msg = bot.send_message(call.message.chat.id, "📝 *Введи название для ссылки*", parse_mode='Markdown')
    bot.register_next_step_handler(msg, save_ref)

def save_ref(message):
    label = message.text.strip()
    code = f"ref_{int(time.time())}"
    add_ref_link(code, label)
    ref_link = f"https://t.me/{BOT_USERNAME}?start={code}"
    bot.send_message(message.chat.id, f"✅ *Ссылка создана!*\n\n🔗 `{ref_link}`\n📌 {label}", parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == "ref_list")
def list_refs(call):
    if call.from_user.id != ADMIN_ID:
        return
    links = get_ref_links()
    if not links:
        bot.send_message(call.message.chat.id, "📭 *Нет ссылок*", parse_mode='Markdown')
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for code, label, clicks, created in links:
        markup.add(types.InlineKeyboardButton(f"📊 {label} — {clicks}", callback_data=f"ref_{code}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_ref"))
    bot.send_message(call.message.chat.id, "📊 *Список ссылок:*", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('ref_') and call.data not in ["ref_create", "ref_list"])
def show_ref_stats(call):
    if call.from_user.id != ADMIN_ID:
        return
    code = call.data[4:]
    links = get_ref_links()
    for c, label, clicks, created in links:
        if c == code:
            ref_link = f"https://t.me/{BOT_USERNAME}?start={code}"
            text = f"📊 *Статистика*\n\n📌 {label}\n🔗 `{ref_link}`\n👥 {clicks}\n📅 {created}"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🗑 Удалить", callback_data=f"del_{code}"))
            markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="ref_list"))
            bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode='Markdown')
            bot.delete_message(call.message.chat.id, call.message.message_id)
            return

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def delete_ref(call):
    if call.from_user.id != ADMIN_ID:
        return
    code = call.data[4:]
    delete_ref_link(code)
    bot.answer_callback_query(call.id, "✅ Удалено!")
    bot.edit_message_text("🗑 Удалено", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_ref")
def back_to_ref(call):
    if call.from_user.id != ADMIN_ID:
        return
    bot.delete_message(call.message.chat.id, call.message.message_id)
    ref_cmd(call.message)

if __name__ == '__main__':
    print("📥 TikTok Bot запущен!")
    bot.infinity_polling()
