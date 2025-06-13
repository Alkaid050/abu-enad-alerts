"import requests
import json
from datetime import datetime
import pytz

API_KEY = "248a6135d4cf4dd9aafa3417f115795e"
SYMBOLS = ["MLGO", "JFBR", "ZVSA", "SONM", "BCLI"]  # يمكنك تعديل الرموز هنا
TELEGRAM_BOT_TOKEN = "7413413899:AAG_3UpCE8TbV0RST6c9189Sip2B3k0MbW8"
CHANNEL_1 = "@abu_enad_signals"  # قناة رادار السيولة
CHANNEL_2 = "@abu_enad_signals_2"  # قناة صيد المجهر

sent_signals = {}
peak_liquidity = {}

def get_stock_data(symbol):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1min&outputsize=5&apikey={API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if "values" in data:
            return data["values"]
    return []

def send_telegram_message(channel, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": channel,
        "text": message,
        "parse_mode": "HTML"
    }
    requests.post(url, data=payload)

def calculate_expected_price(latest_price, liquidity_ratio):
    try:
        multiplier = 1 + (liquidity_ratio / 1000)
        return round(float(latest_price) * multiplier, 2)
    except:
        return latest_price

def process_stock(symbol):
    data = get_stock_data(symbol)
    if len(data) < 3:
        return

    latest = data[0]
    prev = data[1]

    try:
        current_price = float(latest["close"])
        prev_price = float(prev["close"])
        volume = float(latest["volume"])
    except:
        return

    change_percent = ((current_price - prev_price) / prev_price) * 100

    now = datetime.now(pytz.timezone("Asia/Riyadh"))
    timestamp = now.strftime("%I:%M %p")

    if symbol not in sent_signals:
        sent_signals[symbol] = {"entry": False, "boost25": False, "exit15": False, "exit25": False}
        peak_liquidity[symbol] = volume

    # دخول سيولة
    if not sent_signals[symbol]["entry"] and volume > 50000 and change_percent >= 2:
        expected_price = calculate_expected_price(current_price, volume / 1000)
        fair_value = round(expected_price * 1.1, 2)

        message = f"🚨 <b>دخول سيولة</b>"

📈 <b>{symbol}</b>
💰 السعر الحالي: <b>{current_price}</b>
🎯 المتوقع: <b>{expected_price}</b>
📊 القيمة العادلة: <b>{fair_value}</b>
⏰ {timestamp}"
        send_telegram_message(CHANNEL_1, message)

        sent_signals[symbol]["entry"] = True
        peak_liquidity[symbol] = volume
        return

    # تعزيز عند زيادة 25%
    if sent_signals[symbol]["entry"] and not sent_signals[symbol]["boost25"]:
        if volume >= peak_liquidity[symbol] * 1.25:
            expected_price = calculate_expected_price(current_price, volume / 1000)
            message = f"🚀 <b>تعزيز سيولة</b>

📈 <b>{symbol}</b>
💰 السعر الحالي: <b>{current_price}</b>
🎯 المتوقع بعد التعزيز: <b>{expected_price}</b>
⏰ {timestamp}"
            send_telegram_message(CHANNEL_2, message)

            sent_signals[symbol]["boost25"] = True
            peak_liquidity[symbol] = volume
            return

    # خروج سيولة عند تراجع 15%
    if sent_signals[symbol]["entry"] and not sent_signals[symbol]["exit15"]:
        if volume <= peak_liquidity[symbol] * 0.85:
            message = f"⚠️ <b>خروج سيولة جزئي</b>

📉 <b>{symbol}</b>
💰 السعر الحالي: <b>{current_price}</b>
⏰ {timestamp}"
            send_telegram_message(CHANNEL_2, message)
            sent_signals[symbol]["exit15"] = True
            return

    # خروج نهائي عند 25%
    if sent_signals[symbol]["entry"] and not sent_signals[symbol]["exit25"]:
        if volume <= peak_liquidity[symbol] * 0.75:
            expected_price = calculate_expected_price(current_price, -volume / 1000)
            message = f"🚪 <b>خروج سيولة</b>

📉 <b>{symbol}</b>
💰 السعر الحالي: <b>{current_price}</b>
🔻 المتوقع بعد الخروج: <b>{expected_price}</b>
⏰ {timestamp}"
            send_telegram_message(CHANNEL_2, message)
            sent_signals[symbol]["exit25"] = True
            return

# التنفيذ
for symbol in SYMBOLS:
    process_stock(symbol)
