import telebot
import sqlite3
import os
import time
import requests
import re # OTP matching-er jonno
from telebot import types

# --- [ CONFIGURATION ] ---
API_TOKEN = '8177948502:AAFwuwk-wO9kkklZKDXxfUSvSh9EeYbeYLw' 
ADMIN_ID = 7128914520
OTP_GROUP_ID = -1002574417604 # <--- Rose bot theke pawa ID ekhane boshan
GROUP_LINK = "https://t.me/otprcvrakib"

bot = telebot.TeleBot(API_TOKEN, threaded=True)

# --- [ DATABASE SETUP ] ---
def init_db():
    conn = sqlite3.connect('numbers.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS inventory 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, country TEXT, number TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''')
    # OTP session track korar jonno notun table
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
    # Message theke number khuje ber kora (Regex)
    phone_match = re.search(r'(\d{10,15})', otp_text)
    
    if phone_match:
        incoming_num = phone_match.group(1).strip()
        
        conn = sqlite3.connect('numbers.db')
        cursor = conn.cursor()
        # Session table-e milie dekha jeta kon user-er kache ache
        cursor.execute("SELECT user_id FROM active_sessions WHERE number LIKE ?", (f'%{incoming_num}',))
        result = cursor.fetchone()
        conn.close()

        if result:
            user_id = result[0]
            try:
                bot.send_message(user_id, f"🔔 **New OTP Received!**\n\n`{otp_text}`", parse_mode="Markdown")
            except: pass

# --- [ KEYBOARDS ] ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("📱 Get Number"), types.KeyboardButton("🌍 Available Country"))
    return markup

# --- [ START COMMAND ] ---
@bot.message_handler(commands=['start'])
def start(message):
    try:
        conn = sqlite3.connect('numbers.db')
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.chat.id,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✨ Welcome to Seven1tel Number Panel!", reply_markup=main_menu())
    except: pass

# --- [ INTERACTIVE RENAME SYSTEM ] ---
@bot.message_handler(commands=['rename'])
def rename_start(message):
    if message.from_user.id == ADMIN_ID:
        conn = sqlite3.connect('numbers.db'); cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT country FROM inventory")
        countries = cursor.fetchall(); conn.close()
        if not countries:
            bot.reply_to(message, "❌ Database-e kono country nei!"); return
        markup = types.InlineKeyboardMarkup()
        for c in countries:
            markup.add(types.InlineKeyboardButton(f"✏️ {c[0]}", callback_data=f"rn_{c[0]}"))
        bot.send_message(message.chat.id, "📍 Kon desher naam change korte chan? Select korun:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("rn_"))
def ask_new_name(call):
    if call.from_user.id == ADMIN_ID:
        old_name = call.data.replace("rn_", "")
        rename_state[ADMIN_ID] = old_name
        bot.edit_message_text(f"Selected: **{old_name}**\n\n📝 Ekhon ei desher **Notun Naam** likhe pathan:", 
                             call.message.chat.id, call.message.message_id, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and ADMIN_ID in rename_state)
def process_rename(message):
    old_name = rename_state.pop(ADMIN_ID)
    new_name = message.text.strip().upper()
    try:
        conn = sqlite3.connect('numbers.db'); cursor = conn.cursor()
        cursor.execute("UPDATE inventory SET country = ? WHERE country = ?", (new_name, old_name))
        conn.commit(); conn.close()
        bot.reply_to(message, f"✅ Done! '{old_name}' to '{new_name}' updated.")
    except: pass

# --- [ SEND SMS / BROADCAST SYSTEM ] ---
@bot.message_handler(commands=['sendsms'])
def sendsms_command(message):
    if message.from_user.id == ADMIN_ID:
        is_broadcasting[ADMIN_ID] = True
        bot.reply_to(message, "📢 **Send SMS Mode Active**\nApni ja likhben shob user pabe. Cancel korte `/cancel` likhun.")

@bot.message_handler(func=lambda message: is_broadcasting.get(ADMIN_ID) and message.text == "/cancel")
def cancel_send(message):
    is_broadcasting[ADMIN_ID] = False
    bot.reply_to(message, "❌ Message sending cancelled.")

@bot.message_handler(func=lambda message: is_broadcasting.get(ADMIN_ID), content_types=['text', 'photo', 'video', 'animation', 'document'])
def start_sending(message):
    if message.from_user.id == ADMIN_ID:
        is_broadcasting[ADMIN_ID] = False
        bot.reply_to(message, "⏳ Shobai ke pathano shuru hoyeche...")
        conn = sqlite3.connect('numbers.db'); cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users"); all_users = cursor.fetchall(); conn.close()
        success = 0; failed = 0
        for user in all_users:
            try:
                bot.copy_message(user[0], message.chat.id, message.message_id)
                success += 1; time.sleep(0.05) 
            except: failed += 1
        bot.send_message(ADMIN_ID, f"📢 **SMS Results:**\n✅ Success: {success}\n❌ Failed: {failed}")

# --- [ ADMIN: FILE ADDING ] ---
@bot.message_handler(content_types=['document'])
def handle_txt_file(message):
    if message.from_user.id == ADMIN_ID:
        if not message.caption:
            try:
                file_info = bot.get_file(message.document.file_id)
                downloaded_file = bot.download_file(file_info.file_path)
                temp_path = f"temp_{message.from_user.id}.txt"
                with open(temp_path, 'wb') as f: f.write(downloaded_file)
                pending_admin_files[message.from_user.id] = temp_path
                bot.reply_to(message, "📩 File peyechi! Ekhon Country Name likhun:")
            except: pass

@bot.message_handler(func=lambda message: message.from_user.id in pending_admin_files)
def capture_country_name(message):
    country = message.text.strip().upper()
    file_path = pending_admin_files.pop(message.from_user.id)
    try:
        conn = sqlite3.connect('numbers.db'); cursor = conn.cursor()
        added = 0
        with open(file_path, 'r') as f:
            for line in f:
                if line.strip():
                    cursor.execute("INSERT INTO inventory (country, number) VALUES (?, ?)", (country, line.strip())); added += 1
        conn.commit(); conn.close(); os.remove(file_path)
        bot.send_message(message.chat.id, f"✅ Done! {added} numbers added to {country}.")
    except: pass

# --- [ HANDLING TEXT BUTTONS ] ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    if message.text in ["📱 Get Number", "🌍 Available Country"]:
        show_countries(message.chat.id)

def show_countries(chat_id):
    try:
        conn = sqlite3.connect('numbers.db'); cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT country FROM inventory")
        countries = cursor.fetchall(); conn.close()
        if not countries:
            bot.send_message(chat_id, "❌ No numbers available."); return
        markup = types.InlineKeyboardMarkup()
        for c in countries:
            markup.add(types.InlineKeyboardButton(f"🌍 {c[0]}", callback_data=f"getnum_{c[0]}"))
        bot.send_message(chat_id, "📍 Select Country:", reply_markup=markup)
    except: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("getnum_") or call.data == "get_country")
def handle_query(call):
    try:
        bot.answer_callback_query(call.id) 
        conn = sqlite3.connect('numbers.db'); cursor = conn.cursor()
        if call.data == "get_country":
            show_countries(call.message.chat.id)
        elif call.data.startswith("getnum_"):
            country = call.data.split("_")[1]
            cursor.execute("SELECT id, number FROM inventory WHERE country = ? LIMIT 1", (country,))
            row = cursor.fetchone()
            if row:
                db_id, raw_num = row
                
                # --- AUTO '+' ADD LOGIC ---
                num = str(raw_num).strip()
                if not num.startswith('+'):
                    num = "+" + num
                # --------------------------

                cursor.execute("DELETE FROM inventory WHERE id = ?", (db_id,))
                # OTP Forwarding-er jonno session table-e data save kora
                cursor.execute("INSERT OR REPLACE INTO active_sessions (user_id, number) VALUES (?, ?)", (call.from_user.id, num))
                conn.commit()

                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    types.InlineKeyboardButton("🔄 Get Another Number", callback_data=f"getnum_{country}"),
                    types.InlineKeyboardButton("🌍 Change Country", callback_data="get_country"),
                    types.InlineKeyboardButton("🔔 OTP View / OTP Group", url=GROUP_LINK)
                )
                text = f"✅ **{country} Number Assigned:**\n`{num}`\n\n⌛ OTP ashle auto ekhane paben. Opekkha korun..."
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
            else:
                bot.send_message(call.message.chat.id, f"❌ {country} is out of stock!")
        conn.close()
    except: pass

if __name__ == "__main__":
    print("🚀 Seven1tel Bot Online. OTP Forwarding active.")
    while True:
        try:
            bot.polling(non_stop=True, interval=0, timeout=120)
        except:
            time.sleep(5)
