import requests, json
from datetime import datetime
import pytz

# إعدادات عامة
API_KEY = "248a6135d4cf4dd9aafa3417f115795e"
TELEGRAM_BOT_TOKEN = "7413413899:AAG_3UpCE8TbV0RST6c9189Sip2B3k0MbW8"
CHANNEL_1 = "@abu_enad_signals"       # قناة: رادار السيولة - أبو عناد
CHANNEL_2 = "@abu_enad_signals_2"     # قناة: صيد المجهر

sent_signals = {}
peak_liquidity = {}

def get_stock_data(symbol):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1min&outputsize=2&apikey={API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        return data.get("values", [])
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return []

def send_telegram_message(channel, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": channel, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Failed to send message: {e}")

def calculate_expected_price(price, liquidity_ratio):
    try:
        return round(float(price) * (1 + liquidity_ratio / 1000), 2)
    except:
        return price

def process_stock(symbol):
    data = get_stock_data(symbol)
    if len(data) < 2: return

    latest, previous = data[0], data[1]
    try:
        current_price = float(latest["close"])
        previous_price = float(previous["close"])
        volume = float(latest["volume"])
    except:
        return

    change = ((current_price - previous_price) / previous_price) * 100
    timestamp = datetime.now(pytz.timezone("Asia/Riyadh")).strftime("%I:%M %p")

    if symbol not in sent_signals:
        sent_signals[symbol] = {"entry": False, "boost25": False, "exit15": False, "exit25": False}
        peak_liquidity[symbol] = volume

    # دخول سيولة
    if not sent_signals[symbol]["entry"] and volume > 50000 and change >= 2:
        expected = calculate_expected_price(current_price, volume / 1000)
        fair_value = round(expected * 1.1, 2)
  message = f"\U0001F6A8 <b>دخول سيولة</b>\n\n📈 <b>{symbol}</b>\n💰 السعر الحالي: <b>{current_price}</b>\n⏰ {timestamp}"
        send_telegram_message(CHANNEL_1, msg)
        sent_signals[symbol]["entry"] = True
        peak_liquidity[symbol] = volume

    # تعزيز بعد ارتفاع 25% من أعلى سيولة
    elif sent_signals[symbol]["entry"] and not sent_signals[symbol]["boost25"]:
        if volume >= peak_liquidity[symbol] * 1.25:
            expected = calculate_expected_price(current_price, volume / 1000)
            msg = f"🟢 <b>تعزيز دخول</b>\n📈 <b>{symbol}</b>\n💰 السعر الحالي: <b>{current_price}</b>\n🎯 المتوقع: <b>{expected}</b>\n⏰ {timestamp}"
            send_telegram_message(CHANNEL_2, msg)
            sent_signals[symbol]["boost25"] = True
            peak_liquidity[symbol] = volume

    # خروج جزئي عند -15%
    elif volume <= peak_liquidity[symbol] * 0.85 and not sent_signals[symbol]["exit15"]:
        msg = f"⚠️ <b>تحذير خروج</b>\n📉 <b>{symbol}</b>\n💰 السعر الحالي: <b>{current_price}</b>\n⏰ {timestamp}"
        send_telegram_message(CHANNEL_2, msg)
        sent_signals[symbol]["exit15"] = True

    # خروج نهائي عند -25%
    elif volume <= peak_liquidity[symbol] * 0.75 and not sent_signals[symbol]["exit25"]:
        expected = calculate_expected_price(current_price, -volume / 1000)
        msg = f"❌ <b>خروج نهائي</b>\n📉 <b>{symbol}</b>\n💰 السعر الحالي: <b>{current_price}</b>\n🔻 المتوقع بعد الخروج: <b>{expected}</b>\n⏰ {timestamp}"
        send_telegram_message(CHANNEL_2, msg)
        sent_signals[symbol]["exit25"] = True

def fetch_symbols():
    # مؤقتًا: أسهم مختارة فقط حتى يتم استيراد السوق الكامل لاحقًا
    return ["MLGO", "JFBR", "ZVSA", "SONM", "BCLI"]

# تنفيذ على كل سهم
symbols = fetch_symbols()
print("✅ بدأ فحص السوق على الرموز المختارة...")
for symbol in symbols:
    process_stock(symbol)
