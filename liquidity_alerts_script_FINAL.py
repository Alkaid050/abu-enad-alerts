
import requests
import time
from datetime import datetime
import random

# بيانات البوت والقنوات
TOKEN = "توكن البوت"
CHANNEL_GENERAL = "@اسم_قناة_رادار"
CHANNEL_MICROSCOPE = "@اسم_قناة_صيد_المجهر"

# إعدادات التنبيه
ENTRY_PERCENT = 2
BOOST_STEP = 0.25
EXIT_WARNING = 0.15
EXIT_FINAL = 0.25

WATCHLIST = ["MLGO", "HOLO", "ZVSA", "TC", "SONM", "BCLI"]

sent_signals = {}
peak_liquidity = {}

def send_alert(channel, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": channel, "text": text, "parse_mode": "HTML"}
    requests.post(url, data=payload)

def fetch_data(symbol):
    # مثال وهمي للبيانات
    current_price = round(random.uniform(0.5, 9.9), 2)
    volume = random.randint(10000, 100000)
    return current_price, volume

while True:
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for symbol in WATCHLIST:
        current_price, volume = fetch_data(symbol)

        if symbol not in sent_signals:
            sent_signals[symbol] = {
                "entry": False,
                "boost25": False,
                "exit15": False,
                "exit25": False
            }

        signal = sent_signals[symbol]
        prev_price = peak_liquidity.get(symbol, current_price)
        change_percent = ((current_price - prev_price) / prev_price) * 100

        if volume > 50000 and change_percent >= ENTRY_PERCENT and not signal["entry"]:
            expected_price = round(current_price * 1.1, 2)
            fair_value = round(expected_price * 1.1, 2)

            message = f"🚨 <b>دخول سيولة</b>\n\n📊 <b>{symbol}</b>\n💰 السعر الحالي: <b>{current_price}</b>\n📈 السعر المتوقع: <b>{expected_price}</b>\n📉 القيمة العادلة: <b>{fair_value}</b>\n🕓 {timestamp}"
            send_alert(CHANNEL_GENERAL, message)

            signal["entry"] = True
            peak_liquidity[symbol] = volume

        elif signal["entry"]:
            boost_threshold = peak_liquidity[symbol] * (1 + BOOST_STEP)
            exit_warn_threshold = peak_liquidity[symbol] * (1 - EXIT_WARNING)
            exit_final_threshold = peak_liquidity[symbol] * (1 - EXIT_FINAL)

            if volume >= boost_threshold and not signal["boost25"]:
                send_alert(CHANNEL_MICROSCOPE, f"🔁 <b>تعزيز سيولة</b>\n\n📊 <b>{symbol}</b>\n💧 حجم السيولة: <b>{volume}</b>\n🕓 {timestamp}")
                signal["boost25"] = True

            elif volume <= exit_warn_threshold and not signal["exit15"]:
                send_alert(CHANNEL_MICROSCOPE, f"⚠️ <b>تحذير خروج</b>\n\n📊 <b>{symbol}</b>\n🔻 السيولة تقلصت: <b>{volume}</b>\n🕓 {timestamp}")
                signal["exit15"] = True

            elif volume <= exit_final_threshold and not signal["exit25"]:
                send_alert(CHANNEL_MICROSCOPE, f"❌ <b>خروج نهائي</b>\n\n📊 <b>{symbol}</b>\n📉 انهيار السيولة: <b>{volume}</b>\n🕓 {timestamp}")
                sent_signals[symbol] = {
                    "entry": False,
                    "boost25": False,
                    "exit15": False,
                    "exit25": False
                }

    time.sleep(60)
