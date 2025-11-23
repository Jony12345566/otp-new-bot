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
BOT_TOKEN  = os.environ.get("BOT_TOKEN")
CHAT_ID    = os.environ.get("CHAT_ID")
PHPSESSID  = os.environ.get("PHPSESSID")
PORT       = int(os.environ.get("PORT", 10000))  # Render default port

if not BOT_TOKEN or not CHAT_ID or not PHPSESSID:
    logging.error("BOT_TOKEN, CHAT_ID, or PHPSESSID not set in environment variables!")
    exit(1)

# ==============================
# Panel API URL & Headers
# ==============================
today = datetime.today().strftime('%Y-%m-%d')
api_url = (
        f"http://139.99.63.204/ints/agent/res/data_smscdr.php?"
        f"fdate1={today}%2000:00:00&fdate2={today}%2023:59:59&"
        f"iDisplayStart=0&iDisplayLength=50&sEcho=1"
    )
cookies = {'PHPSESSID': PHPSESSID}

headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Referer': 'http://139.99.63.204/ints/agent/smscdr',
    "X-Requested-With": "XMLHttpRequest",
}

# ==============================
# Dynamic Params (today's date)
# ==============================




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
    "249": "Sudan"
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
        r = requests.get(api_url, cookies=cookies, headers=headers, timeout=10)

        logging.info(f"Status Code: {r.status_code}")
        logging.info(f"Response Head: {r.text[:300]}")

        data = r.json()  # এখানে JSON parse করবে
    except Exception as e:
        logging.error(f"Error fetching data: {e}")
        return []

    otps = []
    if "aaData" in data:
        for row in reversed(data["aaData"]):
            time_str = row[0]
            number   = str(row[2])
            service  = row[3]
            full_msg = str(row[5])

            if full_msg.strip() == "0":
                continue

            patterns = [
                r'\b\d{4,6}\b',
                r'\d{3}\s?\d{3}',
                r'[A-Za-z0-9]{4,12}',
                r'\b\d{3}[-\s]?\d{3}\b'
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

