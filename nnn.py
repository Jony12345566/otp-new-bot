import telebot
import sqlite3
import os
import time
import requests
import re
from telebot import types

# --- [ CONFIGURATION ] ---
API_TOKEN = '8177948502:AAFwuwk-wO9kkklZKDXxfUSvSh9EeYbeYLw' 
ADMIN_ID = 7128914520
OTP_GROUP_ID = -1002484729104 
GROUP_LINK = "https://t.me/otprcvrakib"

bot = telebot.TeleBot(API_TOKEN, threaded=True)

# --- [ DATABASE SETUP ] ---
def init_db():
    conn = sqlite3.connect('numbers.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS inventory 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, country TEXT, number TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS active_sessions 
                      (user_id INTEGER PRIMARY KEY, number TEXT)''')
    conn.commit()
    conn.close()

init_db()
pending_admin_files = {}
is_broadcasting = {} 
rename_state = {} 

# --- [ OTP FORWARDING LOGIC ] ---
@bot.message_handler(func=lambda message: message.chat.id == OTP_GROUP_ID)
def handle_otp_from_group(message):
    if not message.text: return
    otp_text = message.text
    phone_match = re.search(r'(\d{10,15})', otp_text)
    if phone_match:
        incoming_num = phone_match.group(1).strip()
        conn = sqlite3.connect('numbers.db'); cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM active_sessions WHERE number LIKE ?", (f'%{incoming_num}',))
        result = cursor.fetchone(); conn.close()
        if result:
            user_id = result[0]
            try: bot.send_message(user_id, f"🔔 **New OTP Received!**\n\n`{otp_text}`", parse_mode="Markdown")
            except: pass

# --- [ DELETE COUNTRY COMMAND (NEW) ] ---
@bot.message_handler(commands=['delete'])
def delete_country(message):
    if message.from_user.id == ADMIN_ID:
        try:
            parts = message.text.split()
            if len(parts) == 2:
                country_to_delete = parts[1].upper()
                conn = sqlite3.connect('numbers.db')
                cursor = conn.cursor()
                cursor.execute("DELETE FROM inventory WHERE country = ?", (country_to_delete,))
                conn.commit()
                count = cursor.rowcount
                conn.close()
                if count > 0:
                    bot.reply_to(message, f"🗑️ **{country_to_delete}** এর সব নাম্বার ({count} টি) রিমুভ করা হয়েছে।")
                else:
                    bot.reply_to(message, f"❌ এই নামে ( {country_to_delete} ) কোনো দেশ খুঁজে পাওয়া যায়নি।")
            else:
                bot.reply_to(message, "⚠️ সঠিক ফরম্যাট: `/delete USA`")
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {e}")

# --- [ START COMMAND ] ---
@bot.message_handler(commands=['start'])
def start(message):
    try:
        conn = sqlite3.connect('numbers.db'); cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.chat.id,))
        conn.commit(); conn.close()
        bot.send_message(message.chat.id, "✨ Welcome to Seven1tel Number Panel!", reply_markup=main_menu())
    except: pass

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("📱 Get Number"), types.KeyboardButton("🌍 Available Country"))
    return markup

# --- [ RENAME SYSTEM ] ---
@bot.message_handler(commands=['rename'])
def rename_start(message):
    if message.from_user.id == ADMIN_ID:
        conn = sqlite3.connect('numbers.db'); cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT country FROM inventory")
        countries = cursor.fetchall(); conn.close()
        if not countries: bot.reply_to(message, "❌ ডাটাবেজ খালি!"); return
        markup = types.InlineKeyboardMarkup()
        for c in countries: markup.add(types.InlineKeyboardButton(f"✏️ {c[0]}", callback_data=f"rn_{c[0]}"))
        bot.send_message(message.chat.id, "📍 দেশের নাম পরিবর্তন করতে সিলেক্ট করুন:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("rn_"))
def ask_new_name(call):
    if call.from_user.id == ADMIN_ID:
        old_name = call.data.replace("rn_", "")
        rename_state[ADMIN_ID] = old_name
        bot.edit_message_text(f"Selected: **{old_name}**\n📝 নতুন নাম লিখে পাঠান:", call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and ADMIN_ID in rename_state)
def process_rename(message):
    old_name = rename_state.pop(ADMIN_ID); new_name = message.text.strip().upper()
    conn = sqlite3.connect('numbers.db'); cursor = conn.cursor()
    cursor.execute("UPDATE inventory SET country = ? WHERE country = ?", (new_name, old_name))
    conn.commit(); conn.close()
    bot.reply_to(message, f"✅ আপডেট হয়েছে: {old_name} ➜ {new_name}")

# --- [ SEND SMS ] ---
@bot.message_handler(commands=['sendsms'])
def sendsms_command(message):
    if message.from_user.id == ADMIN_ID:
        is_broadcasting[ADMIN_ID] = True
        bot.reply_to(message, "📢 মেসেজ পাঠান (বাতিল করতে `/cancel`)।")

# --- [ FILE HANDLING & OTHERS ] ---
@bot.message_handler(content_types=['document'])
def handle_txt_file(message):
    if message.from_user.id == ADMIN_ID and not message.caption:
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        path = f"temp_{message.from_user.id}.txt"
        with open(path, 'wb') as f: f.write(downloaded)
        pending_admin_files[message.from_user.id] = path
        bot.reply_to(message, "📩 দেশের নাম লিখুন:")

@bot.message_handler(func=lambda message: message.from_user.id in pending_admin_files)
def capture_country_name(message):
    country = message.text.strip().upper(); path = pending_admin_files.pop(message.from_user.id)
    conn = sqlite3.connect('numbers.db'); cursor = conn.cursor(); added = 0
    with open(path, 'r') as f:
        for line in f:
            if line.strip(): cursor.execute("INSERT INTO inventory (country, number) VALUES (?, ?)", (country, line.strip())); added += 1
    conn.commit(); conn.close(); os.remove(path)
    bot.send_message(message.chat.id, f"✅ {added} টি নাম্বার {country} এ যুক্ত হয়েছে।")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    if message.text in ["📱 Get Number", "🌍 Available Country"]:
        show_countries(message.chat.id)

def show_countries(chat_id):
    conn = sqlite3.connect('numbers.db'); cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT country FROM inventory"); countries = cursor.fetchall(); conn.close()
    if not countries: bot.send_message(chat_id, "❌ স্টক খালি!"); return
    markup = types.InlineKeyboardMarkup()
    for c in countries: markup.add(types.InlineKeyboardButton(f"🌍 {c[0]}", callback_data=f"getnum_{c[0]}"))
    bot.send_message(chat_id, "📍 দেশ সিলেক্ট করুন:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("getnum_") or call.data == "get_country")
def handle_query(call):
    if call.data.startswith("getnum_"):
        country = call.data.split("_")[1]
        conn = sqlite3.connect('numbers.db'); cursor = conn.cursor()
        cursor.execute("SELECT id, number FROM inventory WHERE country = ? LIMIT 1", (country,))
        row = cursor.fetchone()
        if row:
            db_id, raw_num = row; num = str(raw_num).strip()
            if not num.startswith('+'): num = "+" + num
            cursor.execute("DELETE FROM inventory WHERE id = ?", (db_id,))
            cursor.execute("INSERT OR REPLACE INTO active_sessions (user_id, number) VALUES (?, ?)", (call.from_user.id, num))
            conn.commit()
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("🔄 Get Another", callback_data=f"getnum_{country}"), types.InlineKeyboardButton("🌍 Change Country", callback_data="get_country"), types.InlineKeyboardButton("🔔 OTP Group", url=GROUP_LINK))
            bot.edit_message_text(f"✅ **{country} Number:**\n`{num}`\n\n⌛ OTP এর জন্য অপেক্ষা করুন...", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        else: bot.send_message(call.message.chat.id, "❌ স্টক শেষ!")
        conn.close()

if __name__ == "__main__":
    print("🚀 Seven1tel Bot is Online.")
    while True:
        try: bot.polling(non_stop=True, interval=0, timeout=120)
        except: time.sleep(5)
