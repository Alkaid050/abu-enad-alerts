
import requests

# إعداد التوكن واسم القناة
TELEGRAM_BOT_TOKEN = "7413413899:AAG_3UpCE8TbV0RST6c9189Sip2B3k0MbW8"
CHANNEL_GENERAL = "@abu_enad_signals"

# دالة إرسال التنبيه
def send_alert(message: str, channel: str = CHANNEL_GENERAL):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": channel,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        print(f"✅ تم إرسال التنبيه بنجاح إلى {channel}")
    except requests.exceptions.RequestException as e:
        print(f"❌ فشل إرسال التنبيه: {e}")

# رموز اختبار وهمية
STOCKS = ["MLGO", "JFBR", "ZVSA", "SONM", "BCLI", "KNW", "TC", "BKYI", "BDRX", "PCSA"]

# تنفيذ تجربة إرسال تنبيه بسيط
for symbol in STOCKS:
    message = f"🚨 سهم <b>{symbol}</b> عليه دخول سيولة مبدئي ✅"
    send_alert(message)
