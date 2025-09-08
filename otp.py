import requests
import time
import re
import os
import logging
from flask import Flask
import threading
from datetime import datetime, date

# ==============================
# Logging Setup
# ==============================
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ==============================
# Environment Variables
# ==============================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID   = os.environ.get("CHAT_ID")
PHPSESSID  = os.environ.get("PHPSESSID")
PORT = int(os.environ.get("PORT", 10000))  # Render default port

if not BOT_TOKEN or not CHAT_ID or not PHPSESSID:
    logging.error("BOT_TOKEN, CHAT_ID, or PHPSESSID not set in environment variables!")
    exit(1)

# ==============================
# Panel API URL & Headers
# ==============================
url = "http://94.23.120.156/ints/client/res/data_smscdr.php"
cookies = {'PHPSESSID': PHPSESSID}

headers = {
    'Host': '94.23.120.156',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Referer': 'http://94.23.120.156/ints/client/SMSDashboard',
    # 'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.9,bn;q=0.8',
    # 'Cookie': 'PHPSESSID=hu4kqabdf7kb11ugi7kjgmujn8',
}


# ==============================
# Dynamic Params (today's date)
# ==============================
today = datetime.today().strftime('%Y-%m-%d')

params = {
    "fdate1": f"{today} 00:00:00",  # Set today's date as the start date
    "fdate2": f"{today} 23:59:59",  # Set today's date as the end date
    "sEcho": "1",
    "iColumns": "9",
    "sColumns": ",,,,,,,,",
    "iDisplayStart": "0",
    "iDisplayLength": "25",
    "mDataProp_0": "0",
    "bSearchable_0": "true",
    "bSortable_0": "true",
    "mDataProp_1": "1",
    "bSearchable_1": "true",
    "bSortable_1": "true",
    "mDataProp_2": "2",
    "bSearchable_2": "true",
    "bSortable_2": "true",
    "mDataProp_3": "3",
    "bSearchable_3": "true",
    "bSortable_3": "true",
    "mDataProp_4": "4",
    "bSearchable_4": "true",
    "bSortable_4": "true",
    "mDataProp_5": "5",
    "bSearchable_5": "true",
    "bSortable_5": "true",
    "mDataProp_6": "6",
    "bSearchable_6": "true",
    "bSortable_6": "true",
    "mDataProp_7": "7",
    "bSearchable_7": "true",
    "bSortable_7": "true",
    "mDataProp_8": "8",
    "bSearchable_8": "true",
    "bSortable_8": "false",
    "sSearch": "",
    "bRegex": "false",
    "iSortCol_0": "0",
    "sSortDir_0": "desc",
    "iSortingCols": "1"
}

# ==============================
# Country Code Map
# ==============================
COUNTRY_CODES = {
    "1":   "USA 🇺🇸",
    "7":   "Russia 🇷🇺",
    "20":  "Egypt 🇪🇬",
    "212": "Morocco 🇲🇦",
    "213": "Algeria 🇩🇿",
    "216": "Tunisia 🇹🇳",
    "218": "Libya 🇱🇾",
    "880": "Bangladesh 🇧🇩",
    "91":  "India 🇮🇳",
    "92":  "Pakistan 🇵🇰",
    "963": "Syria 🇸🇾",
    "964": "Iraq 🇮🇶",
    "970": "Palestine 🇵🇸",
    "971": "UAE 🇦🇪",
    "972": "Israel 🇮🇱",
    "973": "Bahrain 🇧🇭",
    "974": "Qatar 🇶🇦",
    "966": "Saudi Arabia 🇸🇦",
}

def detect_country(number):
    for code, country in sorted(COUNTRY_CODES.items(), key=lambda x: -len(x[0])):
        if str(number).startswith(code):
            return country
    return "Unknown 🌍"

# ==============================
# Telegram Sender
# ==============================
def send_to_telegram(message):
    url_api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }
    try:
        requests.post(url_api, json=payload, timeout=10)
        logging.info("Message sent to Telegram")
    except Exception as e:
        logging.error(f"Telegram send error: {e}")

# ==============================
# Fetch OTPs
# ==============================
def fetch_otps():
    try:
        r = requests.get(url, params=params, cookies=cookies, headers=headers, timeout=10)
        data = r.json()
    except Exception as e:
        logging.error(f"Error fetching data: {e}")
        return []

    otps = []
    if "aaData" in data:
        for row in reversed(data["aaData"]):
            time_str = row[0]
            number   = str(row[2])
            service  = row[3]
            full_msg = str(row[4])

            if full_msg.strip() == "0":
                continue

            patterns = [
                r'\b\d{4,6}\b',
                r'\d{3}\s?\d{3}',
                r'[A-Za-z0-9]{4,12}',
                r'[\w-]{4,12}'
            ]

            otp_code = "N/A"
            for pattern in patterns:
                match = re.search(pattern, full_msg)
                if match:
                    otp_code = match.group()
                    break

            country = detect_country(number)

            msg = (
                f"🔥 <b>{service} {country} RECEIVED!</b> ✨\n\n"
                f"<b>⏰ Time:</b> {time_str}\n"
                f"<b>🌍 Country:</b> {country}\n"
                f"<b>⚙️ Service:</b> {service}\n"
                f"<b>☎️ Number:</b> {number[:6]}***{number[-3:]}\n"
                f"<b>🔑 OTP:</b> <code>{otp_code}</code>\n"
                f"<b>📩 Full Message:</b>\n<pre>{full_msg}</pre>"
            )
            otps.append(msg)
    return otps

# ==============================
# Main OTP Loop
# ==============================
def otp_loop():
    last_seen = set()
    current_day = date.today()

    logging.info("OTP bot started")

    while True:
        try:
            # প্রতিদিন নতুন দিনে reset হবে
            if date.today() != current_day:
                last_seen.clear()
                current_day = date.today()
                logging.info("New day detected, last_seen reset ✅")

            otps = fetch_otps()
            for otp in otps:
                if otp not in last_seen:
                    send_to_telegram(otp)
                    last_seen.add(otp)
        except Exception as e:
            logging.error(f"Main loop error: {e}")

        time.sleep(5)

# ==============================
# Flask App for Render Ping
# ==============================
app = Flask(__name__)

@app.route("/")
def home():
    return "OTP Bot is alive!"

# ==============================
# Run Flask & Bot Threaded
# ==============================
if __name__ == "__main__":
    threading.Thread(target=otp_loop).start()
    app.run(host="0.0.0.0", port=PORT)
