#!/usr/bin/env python3
"""
بوت اكتشاف السيولة الفوري - إصدار مبسط
"""
import requests
import time
import logging
from datetime import datetime

# إعدادات البوت
TELEGRAM_TOKEN = "7413413899:AAG_3UpCE8TbV0RST6c9189Sip2B3k0MbW8"
CHANNEL_NAME = "@abu_enad_signals"
API_KEY = "248a6135d4cf4dd9aafa3417f115795e"  # TwelveData API

# معايير السيولة
MIN_VOLUME = 100000  # الحد الأدنى للحجم اليومي
MIN_PRICE = 1.00     # الحد الأدنى للسعر
MAX_PRICE = 10.00    # الحد الأقصى للسعر
PRICE_CHANGE = 2.0   # نسبة التغير المطلوبة %

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_active_stocks():
    """جلب الأسهم النشطة من TwelveData"""
    try:
        url = "https://api.twelvedata.com/stocks"
        params = {
            'country': 'United States',
            'exchange': 'NASDAQ,NYSE,AMEX',
            'apikey': API_KEY
        }
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        return [stock['symbol'] for stock in data.get('data', []) if '.' not in stock['symbol']]
    except Exception as e:
        logger.error(f"خطأ في جلب الأسهم: {e}")
        return []

def check_stock(symbol):
    """فحص السهم لاكتشاف السيولة"""
    try:
        url = "https://api.twelvedata.com/quote"
        params = {'symbol': symbol, 'apikey': API_KEY}

        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        price = float(data.get('price', 0))
        volume = float(data.get('volume', 0))
        change = float(data.get('percent_change', 0))

        # شروط التنبيه
        conditions = [
            MIN_PRICE <= price <= MAX_PRICE,
            volume >= MIN_VOLUME,
            abs(change) >= PRICE_CHANGE
        ]

        if all(conditions):
            return {
                'symbol': symbol,
                'price': price,
                'volume': volume,
                'change': change
            }
        return None

    except Exception as e:
        logger.error(f"خطأ في فحص {symbol}: {e}")
        return None

def send_alert(stock_data):
    """إرسال تنبيه للقناة"""
    try:
        emoji = "🚀" if stock_data['change'] > 0 else "🔻"
        message = (
            f"{emoji} <b>تنبيه سيولة</b> {emoji}

"
            f"🪙 <b>السهم:</b> {stock_data['symbol']}
"
            f"💰 <b>السعر:</b> ${stock_data['price']:.2f}
"
            f"📈 <b>التغير:</b> {stock_data['change']:.2f}%
"
            f"📊 <b>الحجم:</b> {stock_data['volume']:,.0f}

"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        params = {
            'chat_id': CHANNEL_NAME,
            'text': message,
            'parse_mode': 'HTML'
        }

        requests.post(url, json=params, timeout=10)
        logger.info(f"تم إرسال تنبيه لـ {stock_data['symbol']}")

    except Exception as e:
        logger.error(f"فشل إرسال التنبيه: {e}")

def main():
    """الدالة الرئيسية"""
    logger.info("تشغيل بوت اكتشاف السيولة...")
    checked_stocks = set()

    while True:
        try:
            stocks = get_active_stocks()
            logger.info(f"جاري فحص {len(stocks)} سهماً...")

            for symbol in stocks:
                if symbol not in checked_stocks:
                    stock_data = check_stock(symbol)
                    if stock_data:
                        send_alert(stock_data)
                        checked_stocks.add(symbol)
                    time.sleep(0.5)  # تجنب حظر API

            time.sleep(60)  # انتظار دقيقة بين كل مسح
            checked_stocks.clear()  # إعادة الفحص بعد فترة

        except KeyboardInterrupt:
            logger.info("إيقاف البوت...")
            break
        except Exception as e:
            logger.error(f"خطأ غير متوقع: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
