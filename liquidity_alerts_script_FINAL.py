
import requests
import time

# 🟩 إعدادات عامة
TOKEN = "7413413899:AAG_3UpCE8TbV0RST6c9189Sip2B3k0MbW8"
CHANNEL_GENERAL = "@abu_enad_signals"
CHANNEL_MICROSCOPE = "@abu_enad_signals_2"

WATCHLIST = ["MLGO", "HOLO", "ZVSA", "JFBR", "TC", "SONM", "BCLI", "BKYI", "BDRX", "PCSA"]
ENTRY_PERCENT = 2
BOOST_STEP = 0.25
EXIT_WARN = 0.15
EXIT_FINAL = 0.25

data_map = {}

# 🟦 إرسال رسالة لتليجرام
def send_alert(channel, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": channel, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload)
    except:
        pass

# 🟨 محاكاة بيانات الأسعار والسيولة (تُستبدل لاحقًا بـ API حقيقية)
def fetch_mock_data(symbol):
    import random
    price = round(random.uniform(0.5, 9.9), 2)
    liquidity = random.randint(1000, 10000)
    return price, liquidity

# 🟥 معالجة سهم معين
def process_stock(symbol):
    price, liquidity = fetch_mock_data(symbol)
    current = data_map.get(symbol, {})

    # أول دخول
    if "entry_price" not in current:
        if random.random() < 0.3:
            current["entry_price"] = price
            current["entry_liquidity"] = liquidity
            current["last_boost"] = liquidity
            data_map[symbol] = current
            send_alert(CHANNEL_GENERAL, f"🚨 *دخول سيولة*
السهم: `{symbol}`
السعر: ${price}")
            return

    # تعزيز
    if "entry_price" in current:
        boost_threshold = current["last_boost"] * (1 + BOOST_STEP)
        if liquidity >= boost_threshold:
            current["last_boost"] = liquidity
            data_map[symbol] = current
            send_alert(CHANNEL_MICROSCOPE, f"🟢 *تعزيز دخول*
`{symbol}` السيولة ارتفعت 📈
السعر: ${price}")

        # خروج تحذيري
        exit_threshold = current["entry_liquidity"] * (1 - EXIT_WARN)
        if liquidity <= exit_threshold and not current.get("warned"):
            current["warned"] = True
            send_alert(CHANNEL_MICROSCOPE, f"⚠️ *تحذير خروج*
`{symbol}` السيولة تقلصت
السعر الحالي: ${price}")

        # خروج نهائي
        exit_final = current["entry_liquidity"] * (1 - EXIT_FINAL)
        if liquidity <= exit_final:
            send_alert(CHANNEL_MICROSCOPE, f"❌ *خروج سيولة*
تم الخروج من `{symbol}`
السعر الحالي: ${price}")
            data_map.pop(symbol)

# 🟦 تشغيل رئيسي
def run():
    while True:
        for symbol in WATCHLIST:
            process_stock(symbol)
        time.sleep(60)

if __name__ == "__main__":
    run()
