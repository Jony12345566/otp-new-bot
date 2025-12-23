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
OTP_GROUP_ID = -1002484729104 # <--- Apnar Group ID boshan
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

# --- [ OTP FORWARDING LOGIC (ADVANCED ALL-MATCH) ] ---
@bot.message_handler(func=lambda message: message.chat.id == OTP_GROUP_ID)
def handle_otp_from_group(message):
    if not message.text: return
    
    otp_text = message.text
    # Message theke 3 ba tar beshi digit-er shob segment khuje ber kora
    found_segments = re.findall(r'\d{3,}', otp_text)
    
    if not found_segments: return

    conn = sqlite3.connect('numbers.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, number FROM active_sessions")
    all_sessions = cursor.fetchall()
    conn.close()

    best_match_user = None
    highest_match_score = 0

    for user_id, db_num in all_sessions:
        clean_db_num = re.sub(r'\D', '', db_num) # DB number theke + ba space bad deya
        current_match_score = 0
        
        for segment in found_segments:
            if segment in clean_db_num:
                current_match_score += len(segment) # Matching segments-er length score hishebe jog hobe
        
        if current_match_score > highest_match_score:
            highest_match_score = current_match_score
            best_match_user = user_id

    # Minimum 3 digit match korle forward korbe
    if best_match_user and highest_match_score >= 3:
        try:
            bot.send_message(best_match_user, f"🔔 **New OTP Received!**\n\n`{otp_text}`", parse_mode="Markdown")
        except: pass

# --- [ KEYBOARDS ] ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("📱 Get Number"), types.KeyboardButton("🌍 Available Country"))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    try:
        conn = sqlite3.connect('numbers.db'); cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.chat.id,))
        conn.commit(); conn.close()
        bot.send_message(message.chat.id, "✨ Welcome to Seven1tel Number Panel!", reply_markup=main_menu())
    except: pass

# --- [ ADMIN COMMAND: DELETE COUNTRY ] ---
@bot.message_handler(commands=['delete'])
def delete_country(message):
    if message.from_user.id == ADMIN_ID:
        try:
            parts = message.text.split()
            if len(parts) == 2:
                country_to_delete = parts[1].upper()
                conn = sqlite3.connect('numbers.db'); cursor = conn.cursor()
                cursor.execute("DELETE FROM inventory WHERE country = ?", (country_to_delete,))
                conn.commit(); count = cursor.rowcount; conn.close()
                if count > 0:
                    bot.reply_to(message, f"🗑️ **{country_to_delete}** er shob number ({count} ti) remove kora hoyeche.")
                else:
                    bot.reply_to(message, f"❌ '{country_to_delete}' naame kono desh khuje pawa jayni.")
            else:
                bot.reply_to(message, "⚠️ Format: `/delete USA`")
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {e}")

# --- [ ADMIN COMMAND: RENAME COUNTRY ] ---
@bot.message_handler(commands=['rename'])
def rename_start(message):
    if message.from_user.id == ADMIN_ID:
        conn = sqlite3.connect('numbers.db'); cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT country FROM inventory"); countries = cursor.fetchall(); conn.close()
        if not countries: bot.reply_to(message, "❌ Database khali!"); return
        markup = types.InlineKeyboardMarkup()
        for c in countries:
            markup.add(types.InlineKeyboardButton(f"✏️ {c[0]}", callback_data=f"rn_{c[0]}"))
        bot.send_message(message.chat.id, "📍 Select Country to rename:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("rn_"))
def ask_new_name(call):
    if call.from_user.id == ADMIN_ID:
        old_name = call.data.replace("rn_", "")
        rename_state[ADMIN_ID] = old_name
        bot.edit_message_text(f"Selected: **{old_name}**\n📝 Notun naam likhe pathan:", call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and ADMIN_ID in rename_state)
def process_rename(message):
    old_name = rename_state.pop(ADMIN_ID); new_name = message.text.strip().upper()
    conn = sqlite3.connect('numbers.db'); cursor = conn.cursor()
    cursor.execute("UPDATE inventory SET country = ? WHERE country = ?", (new_name, old_name))
    conn.commit(); conn.close()
    bot.reply_to(message, f"✅ Updated: {old_name} ➜ {new_name}")

# --- [ BROADCAST SMS ] ---
@bot.message_handler(commands=['sendsms'])
def sendsms_command(message):
    if message.from_user.id == ADMIN_ID:
        is_broadcasting[ADMIN_ID] = True
        bot.reply_to(message, "📢 Message pathan (cancel korte `/cancel` likhun)।")

@bot.message_handler(func=lambda message: is_broadcasting.get(ADMIN_ID) and message.text == "/cancel")
def cancel_send(message):
    is_broadcasting[ADMIN_ID] = False
    bot.reply_to(message, "❌ Broadcast cancelled.")

@bot.message_handler(func=lambda message: is_broadcasting.get(ADMIN_ID), content_types=['text', 'photo', 'video', 'animation', 'document'])
def start_sending(message):
    if message.from_user.id == ADMIN_ID:
        is_broadcasting[ADMIN_ID] = False
        bot.reply_to(message, "⏳ Sending to all users...")
        conn = sqlite3.connect('numbers.db'); cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users"); all_users = cursor.fetchall(); conn.close()
        success = 0; failed = 0
        for user in all_users:
            try:
                bot.copy_message(user[0], message.chat.id, message.message_id)
                success += 1; time.sleep(0.05) 
            except: failed += 1
        bot.send_message(ADMIN_ID, f"📢 **Broadcast Result:**\n✅ Success: {success}\n❌ Failed: {failed}")

# --- [ ADMIN: ADD FILE ] ---
@bot.message_handler(content_types=['document'])
def handle_txt_file(message):
    if message.from_user.id == ADMIN_ID and not message.caption:
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        path = f"temp_{message.from_user.id}.txt"
        with open(path, 'wb') as f: f.write(downloaded)
        pending_admin_files[message.from_user.id] = path
        bot.reply_to(message, "📩 Desher naam likhun:")

@bot.message_handler(func=lambda message: message.from_user.id in pending_admin_files)
def capture_country_name(message):
    country = message.text.strip().upper(); path = pending_admin_files.pop(message.from_user.id)
    conn = sqlite3.connect('numbers.db'); cursor = conn.cursor(); added = 0
    with open(path, 'r') as f:
        for line in f:
            if line.strip(): cursor.execute("INSERT INTO inventory (country, number) VALUES (?, ?)", (country, line.strip())); added += 1
    conn.commit(); conn.close(); os.remove(path)
    bot.send_message(message.chat.id, f"✅ {added} numbers added to {country}.")

# --- [ USER INTERFACE & BUTTONS ] ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    if message.text in ["📱 Get Number", "🌍 Available Country"]:
        show_countries(message)

def show_countries(message_or_call):
    chat_id = message_or_call.chat.id if hasattr(message_or_call, 'chat') else message_or_call.message.chat.id
    conn = sqlite3.connect('numbers.db'); cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT country FROM inventory"); countries = cursor.fetchall(); conn.close()
    if not countries:
        bot.send_message(chat_id, "❌ Stock is empty!"); return
    markup = types.InlineKeyboardMarkup()
    for c in countries: markup.add(types.InlineKeyboardButton(f"🌍 {c[0]}", callback_data=f"getnum_{c[0]}"))
    
    if hasattr(message_or_call, 'message'):
        bot.edit_message_text("📍 Select Country:", chat_id, message_or_call.message.message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, "📍 Select Country:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    bot.answer_callback_query(call.id)
    if call.data == "get_country":
        show_countries(call)
    elif call.data.startswith("getnum_"):
        country = call.data.split("_")[1]
        conn = sqlite3.connect('numbers.db'); cursor = conn.cursor()
        cursor.execute("SELECT id, number FROM inventory WHERE country = ? LIMIT 1", (country,))
        row = cursor.fetchone()
        if row:
            db_id, raw_num = row; num = str(raw_num).strip()
            if not num.startswith('+'): num = "+" + num
            cursor.execute("DELETE FROM inventory WHERE id = ?", (db_id,))
            # OTP Forwarding-er jonno session update
            cursor.execute("INSERT OR REPLACE INTO active_sessions (user_id, number) VALUES (?, ?)", (call.from_user.id, num))
            conn.commit()
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("🔄 Get Another", callback_data=f"getnum_{country}"), types.InlineKeyboardButton("🌍 Change Country", callback_data="get_country"), types.InlineKeyboardButton("🔔 OTP Group", url=GROUP_LINK))
            bot.edit_message_text(f"✅ **{country} Number Assigned:**\n`{num}`\n\n⌛ OTP ashle ekhane auto forward hobe...", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        else: bot.send_message(call.message.chat.id, f"❌ {country} stock empty!")
        conn.close()
    elif call.data.startswith("rn_"):
        ask_new_name(call)

# --- [ POLLING ] ---
if __name__ == "__main__":
    print("🚀 Seven1tel Final Bot Online!")
    while True:
        try: bot.polling(non_stop=True, interval=0, timeout=120)
        except: time.sleep(5)
