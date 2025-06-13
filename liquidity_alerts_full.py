
import requests
import json
from datetime import datetime
import pytz

# 🔹 إعدادات API ومصادر البيانات
API_KEY = "248a6135d4cf4dd9aafa3417f115795e"
TELEGRAM_BOT_TOKEN = "7413413899:AAG_3UpCE8TbV0RST6c9189Sip2B3k0MbW8"
CHANNEL_GENERAL = "@abu_enad_signals"
CHANNEL_MICROSCOPE = "@abu_enad_signals_2"

# 🔍 جلب قائمة الأسهم الأمريكية الشرعية تحت 10$
def get_valid_stocks():
    url = f"https://api.example.com/all_stocks?apikey={API_KEY}"
    response = requests.get(url)
    stocks = response.json()
    return [s['symbol'] for s in stocks if s['price'] < 10 and (s['is_halal'] or s['symbol'] in ["MLGO", "JFBR"])]

# 🔎 جلب بيانات السيولة لكل سهم
def get_stock_data(symbol):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1min&outputsize=5&apikey={API_KEY}"
    response = requests.get(url)
    return response.json().get("values", [])

# 📢 إرسال إشعارات إلى تيليجرام
def send_telegram_message(channel, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": channel, "text": message, "parse_mode": "HTML"}
    requests.post(url, data=payload)

# 🔥 تحليل السيولة وبناء إشارات التداول
def process_stock(symbol):
    data = get_stock_data(symbol)
    if len(data) < 3:
        return

    latest, prev = data[0], data[1]

    try:
        current_price = float(latest["close"])
        prev_price = float(prev["close"])
        current_volume = float(latest["volume"])
        prev_volume = float(prev["volume"])
    except ValueError:
        return

    change_percent = ((current_price - prev_price) / prev_price) * 100
    now = datetime.now(pytz.timezone("Asia/Riyadh"))
    timestamp = now.strftime("%I:%M %p")

    # دخول سيولة قوية
    if current_volume > 50000 and change_percent >= 2:
        message = f"🚨 <b>دخول سيولة</b>

📈 <b>{symbol}</b>
💰 السعر الحالي: <b>{current_price}</b>
⏰ {timestamp}"
        send_telegram_message(CHANNEL_GENERAL, message)

    # تعزيز عند زيادة السيولة 25% عن الذروة
    if current_volume >= prev_volume * 1.25:
        message = f"🟢 <b>تعزيز دخول</b>

📈 <b>{symbol}</b>
💰 السعر الحالي: <b>{current_price}</b>
⏰ {timestamp}"
        send_telegram_message(CHANNEL_MICROSCOPE, message)

    # خروج عند تراجع السيولة بنسبة 15% أو أكثر
    if current_volume <= prev_volume * 0.85:
        message = f"⚠️ <b>تحذير خروج</b>

📉 <b>{symbol}</b>
💰 السعر الحالي: <b>{current_price}</b>
⏰ {timestamp}"
        send_telegram_message(CHANNEL_MICROSCOPE, message)

# 🔄 تشغيل النظام لكل الأسهم الشرعية
valid_stocks = get_valid_stocks()
for symbol in valid_stocks:
    process_stock(symbol)
