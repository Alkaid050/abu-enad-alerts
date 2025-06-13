
import requests
import json
from datetime import datetime
import pytz

# 🔹 إعدادات API
API_KEY = "248a6135d4cf4dd9aafa3417f115795e"
SYMBOLS = ["MLGO", "JFBR", "ZVSA", "SONM", "BCLI"]
TELEGRAM_BOT_TOKEN = "7413413899:AAG_3UpCE8TbV0RST6c9189Sip2B3k0MbW8"
CHANNEL_1 = "@abu_enad_signals"
CHANNEL_2 = "@abu_enad_signals_2"

sent_signals = {}
peak_liquidity = {}

def get_stock_data(symbol):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1min&outputsize=5&apikey={API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        try:
            data = response.json()
            return data.get("values", [])
        except json.JSONDecodeError:
            print(f"❌ خطأ في قراءة JSON للسهم {symbol}")
            return []
    else:
        print(f"⚠️ خطأ في جلب البيانات ({response.status_code}) لسهم {symbol}")
        return []

def send_telegram_message(channel, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": channel, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            print(f"⚠️ فشل في إرسال الإشعار ({response.status_code})")
    except Exception as e:
        print(f"❌ خطأ أثناء إرسال إشعار تيليجرام: {e}")

def calculate_expected_price(latest_price, liquidity_ratio):
    try:
        multiplier = 1 + (liquidity_ratio / 1000)
        return round(float(latest_price) * multiplier, 2)
    except ValueError:
        return latest_price

def process_stock(symbol):
    data = get_stock_data(symbol)
    if len(data) < 3:
        return

    latest, prev = data[0], data[1]

    try:
        current_price = float(latest["close"])
        prev_price = float(prev["close"])
        volume = float(latest["volume"])
    except ValueError:
        print(f"⚠️ خطأ في استخراج بيانات {symbol}")
        return

    change_percent = ((current_price - prev_price) / prev_price) * 100
    now = datetime.now(pytz.timezone("Asia/Riyadh"))
    timestamp = now.strftime("%I:%M %p")

    if symbol not in sent_signals:
        sent_signals[symbol] = {"entry": False, "boost25": False, "exit15": False, "exit25": False}
        peak_liquidity[symbol] = volume

    if not sent_signals[symbol]["entry"] and volume > 50000 and change_percent >= 2:
        expected_price = calculate_expected_price(current_price, volume / 1000)
        fair_value = round(expected_price * 1.1, 2)
        message = f"🚨 <b>دخول سيولة</b>\n📈 <b>{symbol}</b>\n💰 السعر الحالي: <b>{current_price}</b>\n🎯 المتوقع: <b>{expected_price}</b>\n📊 القيمة العادلة: <b>{fair_value}</b>\n⏰ {timestamp}"
        send_telegram_message(CHANNEL_1, message)
        sent_signals[symbol]["entry"] = True
        peak_liquidity[symbol] = volume

    elif volume >= peak_liquidity[symbol] * 1.25 and not sent_signals[symbol]["boost25"]:
        expected_price = calculate_expected_price(current_price, volume / 1000)
        message = f"🟢 <b>تعزيز دخول</b>\n📈 <b>{symbol}</b>\n💰 السعر الحالي: <b>{current_price}</b>\n🎯 المتوقع: <b>{expected_price}</b>\n⏰ {timestamp}"
        send_telegram_message(CHANNEL_2, message)
        sent_signals[symbol]["boost25"] = True
        peak_liquidity[symbol] = volume

    elif volume <= peak_liquidity[symbol] * 0.85 and not sent_signals[symbol]["exit15"]:
        message = f"⚠️ <b>تحذير خروج</b>\n📉 <b>{symbol}</b>\n💰 السعر الحالي: <b>{current_price}</b>\n⏰ {timestamp}"
        send_telegram_message(CHANNEL_2, message)
        sent_signals[symbol]["exit15"] = True

    elif volume <= peak_liquidity[symbol] * 0.75 and not sent_signals[symbol]["exit25"]:
        expected_price = calculate_expected_price(current_price, -volume / 1000)
        message = f"❌ <b>خروج نهائي</b>\n📉 <b>{symbol}</b>\n💰 السعر الحالي: <b>{current_price}</b>\n🔻 المتوقع بعد الخروج: <b>{expected_price}</b>\n⏰ {timestamp}"
        send_telegram_message(CHANNEL_2, message)
        sent_signals[symbol]["exit25"] = True

for symbol in SYMBOLS:
    process_stock(symbol)
