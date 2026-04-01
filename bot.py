import telebot
from telebot import types
import yt_dlp
import os
import re
import time
import sqlite3
from datetime import datetime

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = '8681585910:AAEvXnyGeP3UeskKi08OW46MUwbO3GUcG_o'  # Твой TikTok бот
ADMIN_ID = 5298604296
BOT_USERNAME = 'tt_saveeee_bot'
CHANNEL_ID = '-1001888094511'  # Твой музыкальный канал
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

def get_user_ref_stats(user_id):
    conn = sqlite3.connect('tiktok_bot.db')
    c = conn.cursor()
    c.execute("SELECT ref_code FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else None

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
    
    # Проверка подписки
    if not is_subscribed(uid):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_URL))
        markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
        bot.send_message(
            message.chat.id,
            "⚠️ *Доступ к боту закрыт!*\n\nПодпишись на канал, чтобы скачивать видео без водяного знака.",
            reply_markup=markup,
            parse_mode='Markdown'
        )
        return
    
    is_admin = (uid == ADMIN_ID)
    bot.send_message(
        message.chat.id,
        "📥 *TikTok Downloader готов!*\n\nОтправь ссылку на TikTok видео — скачаю без водяного знака.",
        reply_markup=main_menu(is_admin),
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda m: m.text == "📥 Скачать TikTok")
def download_button(message):
    uid = message.from_user.id
    
    if not is_subscribed(uid):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_URL))
        markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
        bot.send_message(message.chat.id, "⚠️ *Доступ закрыт!*", reply_markup=markup, parse_mode='Markdown')
        return
    
    bot.send_message(message.chat.id, "🔗 *Отправь ссылку на TikTok*\n\nПример: https://vm.tiktok.com/...", parse_mode='Markdown')
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
    
    if 'tiktok.com' not in url and 'vm.tiktok.com' not in url:
        bot.send_message(message.chat.id, "❌ *Это не ссылка TikTok!*", parse_mode='Markdown')
        return
    
    wait = bot.send_message(message.chat.id, "📥 *Скачиваю видео...*", parse_mode='Markdown')
    
    try:
        filename, title = download_tiktok(url)
        if not filename:
            raise Exception("Не удалось скачать")
        
        with open(filename, 'rb') as video:
            bot.send_video(
                message.chat.id,
                video,
                caption=f"🎬 *{title[:100]}*\n\n📥 Скачано с @{BOT_USERNAME}"
            )
        os.remove(filename)
        bot.delete_message(message.chat.id, wait.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ *Ошибка:* {e}", message.chat.id, wait.message_id, parse_mode='Markdown')

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
    help_text = f"""📥 *TikTok Downloader*

*Как пользоваться:*
1. Найди видео в TikTok
2. Нажми «Поделиться» → «Копировать ссылку»
3. Отправь ссылку в этот чат
4. Бот пришлёт видео *без водяного знака*

*Пример ссылки:*
https://vm.tiktok.com/...

*Команды:*
/start — начать
📥 Скачать TikTok — инструкция
❓ Помощь — это сообщение"""

    if is_admin:
        help_text += "\n\n🔗 *Рефералка* — создавай ссылки для рекламы"
    
    help_text += "\n\n@avgustc"
    
    bot.send_message(message.chat.id, help_text, reply_markup=main_menu(is_admin), parse_mode='Markdown')

# ========== ОБРАБОТКА ПРЯМЫХ ССЫЛОК ==========
@bot.message_handler(func=lambda m: 'tiktok.com' in m.text or 'vm.tiktok.com' in m.text)
def handle_tiktok_url(message):
    uid = message.from_user.id
    
    if not is_subscribed(uid):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_URL))
        markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
        bot.send_message(message.chat.id, "⚠️ *Доступ закрыт!*", reply_markup=markup, parse_mode='Markdown')
        return
    
    wait = bot.send_message(message.chat.id, "📥 *Скачиваю видео...*", parse_mode='Markdown')
    
    try:
        filename, title = download_tiktok(message.text)
        if not filename:
            raise Exception("Не удалось скачать")
        
        with open(filename, 'rb') as video:
            bot.send_video(
                message.chat.id,
                video,
                caption=f"🎬 *{title[:100]}*\n\n📥 Скачано с @{BOT_USERNAME}"
            )
        os.remove(filename)
        bot.delete_message(message.chat.id, wait.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ *Ошибка:* {e}", message.chat.id, wait.message_id, parse_mode='Markdown')

# ========== ПРОВЕРКА ПОДПИСКИ ==========
@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_callback(call):
    if is_subscribed(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Подписка подтверждена!")
        bot.edit_message_text(
            "🎉 Спасибо за подписку! Теперь ты можешь скачивать видео.",
            call.message.chat.id,
            call.message.message_id
        )
        uid = call.from_user.id
        is_admin = (uid == ADMIN_ID)
        bot.send_message(
            call.message.chat.id,
            "📥 *TikTok Downloader готов!*\n\nОтправь ссылку на TikTok видео.",
            reply_markup=main_menu(is_admin),
            parse_mode='Markdown'
        )
    else:
        bot.answer_callback_query(call.id, "❌ Вы ещё не подписаны!", show_alert=True)

# ========== РЕФЕРАЛЬНЫЕ КНОПКИ ==========
@bot.callback_query_handler(func=lambda call: call.data == "ref_create")
def create_ref(call):
    if call.from_user.id != ADMIN_ID:
        return
    msg = bot.send_message(call.message.chat.id, "📝 *Введи название для ссылки*\n\nНапример: `канал_петрова`", parse_mode='Markdown')
    bot.register_next_step_handler(msg, save_ref)

def save_ref(message):
    label = message.text.strip()
    code = f"ref_{int(time.time())}"
    add_ref_link(code, label)
    ref_link = f"https://t.me/{BOT_USERNAME}?start={code}"
    bot.send_message(message.chat.id, f"✅ *Ссылка создана!*\n\n🔗 `{ref_link}`\n📌 Метка: {label}", parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == "ref_list")
def list_refs(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    links = get_ref_links()
    if not links:
        bot.send_message(call.message.chat.id, "📭 *Нет созданных ссылок*", parse_mode='Markdown')
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for code, label, clicks, created in links:
        markup.add(types.InlineKeyboardButton(f"📊 {label} — {clicks} переходов", callback_data=f"ref_{code}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_ref"))
    
    bot.send_message(call.message.chat.id, "📊 *Список реферальных ссылок:*", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('ref_') and call.data != "ref_create" and call.data != "ref_list")
def show_ref_stats(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    code = call.data[4:]
    links = get_ref_links()
    for c, label, clicks, created in links:
        if c == code:
            ref_link = f"https://t.me/{BOT_USERNAME}?start={code}"
            text = f"📊 *Статистика ссылки*\n\n📌 Метка: {label}\n🔗 `{ref_link}`\n👥 Переходов: {clicks}\n📅 Создана: {created}"
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
    bot.answer_callback_query(call.id, "✅ Ссылка удалена!")
    bot.edit_message_text("🗑 Ссылка удалена", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_ref")
def back_to_ref(call):
    if call.from_user.id != ADMIN_ID:
        return
    bot.delete_message(call.message.chat.id, call.message.message_id)
    ref_cmd(call.message)

if __name__ == '__main__':
    print("📥 TikTok Downloader Bot запущен!")
    bot.infinity_polling()
