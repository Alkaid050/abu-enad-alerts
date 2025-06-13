import requests
import json
from datetime import datetime
import pytz

# 🔐 TwelveData API
API_KEY = "248a6135d4cf4dd9aafa3417f115795e"
TELEGRAM_BOT_TOKEN = "7413413899:AAG_3UpCE8TbV0RST6c9189Sip2B3k0MbW8"
CHANNEL_1 = "@abu_enad_signals"
CHANNEL_2 = "@abu_enad_signals_2"

sent_signals = {}
peak_liquidity = {}

# 🔽 جلب بيانات السوق من TwelveData
def get_stock_data(symbol):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1min&outputsize=5&apikey={API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        try:
            return response.json().get("values", [])
        except:
            return []
    return []

# 🟡 إرسال رسالة تيليجرام
def send_telegram_message(channel, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": channel, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload)
    except:
        pass

# 🔄 حساب السعر المتوقع
def calculate_expected_price(price, liquidity_ratio):
    try:
        multiplier = 1 + (liquidity_ratio / 1000)
        return round(float(price) * multiplier, 2)
    except:
        return price

# 💰 حساب القيمة العادلة
def calculate_fair_value(expected_price):
    return round(expected_price * 1.1, 2)

# 🟦 سهم معين
def process_stock(symbol):
    data = get_stock_data(symbol)
    if len(data) < 3: return

    latest, prev = data[0], data[1]
    try:
        current_price = float(latest["close"])
        prev_price = float(prev["close"])
        volume = float(latest["volume"])
    except:
        return

    change_percent = ((current_price - prev_price) / prev_price) * 100
    timestamp = datetime.now(pytz.timezone("Asia/Riyadh")).strftime("%I:%M %p")

    if symbol not in sent_signals:
        sent_signals[symbol] = {"entry": False, "boost25": False, "exit15": False, "exit25": False}
        peak_liquidity[symbol] = volume

    # 🚨 دخول سيولة
    if not sent_signals[symbol]["entry"] and volume > 50000 and change_percent >= 2:
        expected_price = calculate_expected_price(current_price, volume / 1000)
        fair_value = calculate_fair_value(expected_price)
        message = f"🚨 <b>دخول سيولة</b>
📈 <b>{symbol}</b>
💰 السعر: <b>{current_price}</b>
🎯 المتوقع: <b>{expected_price}</b>
📊 العادلة: <b>{fair_value}</b>
⏰ {timestamp}"
        send_telegram_message(CHANNEL_1, message)
        sent_signals[symbol]["entry"] = True
        peak_liquidity[symbol] = volume

    # ✅ تعزيز دخول
    elif volume >= peak_liquidity[symbol] * 1.25 and not sent_signals[symbol]["boost25"]:
        expected_price = calculate_expected_price(current_price, volume / 1000)
        message = f"✅ <b>تعزيز دخول</b>
📈 <b>{symbol}</b>
💰 السعر: <b>{current_price}</b>
🎯 المتوقع: <b>{expected_price}</b>
⏰ {timestamp}"
        send_telegram_message(CHANNEL_2, message)
        sent_signals[symbol]["boost25"] = True
        peak_liquidity[symbol] = volume

    # ⚠️ خروج 15٪
    elif volume <= peak_liquidity[symbol] * 0.85 and not sent_signals[symbol]["exit15"]:
        message = f"⚠️ <b>تحذير خروج</b>
📉 <b>{symbol}</b>
💰 السعر: <b>{current_price}</b>
⏰ {timestamp}"
        send_telegram_message(CHANNEL_2, message)
        sent_signals[symbol]["exit15"] = True

    # ❌ خروج نهائي
    elif volume <= peak_liquidity[symbol] * 0.75 and not sent_signals[symbol]["exit25"]:
        expected_price = calculate_expected_price(current_price, -volume / 1000)
        message = f"❌ <b>خروج نهائي</b>
📉 <b>{symbol}</b>
💰 السعر: <b>{current_price}</b>
🔻 المتوقع بعد الخروج: <b>{expected_price}</b>
⏰ {timestamp}"
        send_telegram_message(CHANNEL_2, message)
        sent_signals[symbol]["exit25"] = True

# 📊 جلب كل رموز السوق الشرعية تحت 10 دولار
def fetch_symbols():
    return ["MLGO", "JFBR", "ZVSA", "SONM", "BCLI", "PCSA", "KNW", "ENTO", "BKYI", "BDRX", "HOLO", "TC"]

symbols = fetch_symbols()
for symbol in symbols:
    process_stock(symbol)
