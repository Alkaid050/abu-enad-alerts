import requests
import json
from datetime import datetime, timedelta
import pytz
import os
from dotenv import load_dotenv
import finnhub
import time
import csv
from typing import Dict, List, Optional, Set

# تحميل متغيرات البيئة من ملف .env
load_dotenv()

# 🔹 إعدادات API ومصادر البيانات
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_KEY_TWELVEDATA = os.getenv("API_KEY_TWELVEDATA")

# إعدادات القنوات
CHANNEL_GENERAL = os.getenv("CHANNEL_GENERAL", "@abu_enad_signals")
CHANNEL_MICROSCOPE = os.getenv("CHANNEL_MICROSCOPE", "@abu_enad_signals_2")

# إعدادات التداول
MIN_VOLUME_THRESHOLD = float(os.getenv("MIN_VOLUME_THRESHOLD", "50000"))
PRICE_CHANGE_THRESHOLD = float(os.getenv("PRICE_CHANGE_THRESHOLD", "2.0"))
VOLUME_INCREASE_THRESHOLD = float(os.getenv("VOLUME_INCREASE_THRESHOLD", "1.25"))
VOLUME_DECREASE_THRESHOLD = float(os.getenv("VOLUME_DECREASE_THRESHOLD", "0.85"))
ALERT_COOLDOWN_MINUTES = int(os.getenv("ALERT_COOLDOWN_MINUTES", "30"))

# إعدادات فلترة الأسهم
MAX_STOCK_PRICE = float(os.getenv("MAX_STOCK_PRICE", "10.0"))
MIN_NET_PROFIT_MARGIN = float(os.getenv("MIN_NET_PROFIT_MARGIN", "-5.0"))
MIN_CURRENT_RATIO = float(os.getenv("MIN_CURRENT_RATIO", "1.0"))

# متغيرات عامة لتتبع التنبيهات
last_alert_times: Dict[str, datetime] = {}
alert_log_file = "alerts_log.csv"

# إنشاء ملف السجل إذا لم يكن موجوداً
def initialize_log_file():
    if not os.path.exists(alert_log_file):
        with open(alert_log_file, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([
                'التاريخ والوقت', 'الرمز', 'نوع التنبيه', 'السعر الحالي',
                'تغير السعر %', 'الحجم الحالي', 'الحجم السابق',
                'هامش صافي الربح', 'هامش الربح الإجمالي', 'نسبة التداول',
                'النقد المتوفر', 'إجمالي الديون', 'الإيرادات السنوية'
            ])

def log_alert(symbol: str, alert_type: str, price: float, change_percent: float,
              current_volume: float, prev_volume: float, fundamental_data: Dict):
    try:
        now = datetime.now(pytz.timezone("Asia/Riyadh"))
        with open(alert_log_file, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([
                now.strftime("%Y-%m-%d %H:%M:%S"),
                symbol,
                alert_type,
                price,
                f"{change_percent:.2f}",
                current_volume,
                prev_volume,
                fundamental_data.get('net_profit_margin', 'N/A'),
                fundamental_data.get('gross_profit_margin', 'N/A'),
                fundamental_data.get('current_ratio', 'N/A'),
                fundamental_data.get('cash_and_cash_equivalents', 'N/A'),
                fundamental_data.get('total_debt', 'N/A'),
                fundamental_data.get('total_revenue', 'N/A')
            ])
    except Exception as e:
        print(f"خطأ في حفظ السجل: {e}")

def should_send_alert(symbol: str, alert_type: str, current_volume: float, prev_volume: float) -> bool:
    now = datetime.now(pytz.timezone("Asia/Riyadh"))
    alert_key = f"{symbol}_{alert_type}"
    if alert_key in last_alert_times:
        time_diff = now - last_alert_times[alert_key]
        if time_diff.total_seconds() < (ALERT_COOLDOWN_MINUTES * 60):
            if prev_volume > 0:
                volume_change_ratio = current_volume / prev_volume
                if volume_change_ratio >= 2.0 or volume_change_ratio <= 0.5:
                    last_alert_times[alert_key] = now
                    return True
            return False
    last_alert_times[alert_key] = now
    return True

def get_valid_stocks() -> List[str]:
    return ["MLGO", "JFBR", "AAPL", "MSFT", "TSLA", "NVDA", "AMD", "INTC"]

def get_stock_data(symbol: str) -> List[Dict]:
    if not API_KEY_TWELVEDATA:
        print("مفتاح TwelveData API غير محدد.")
        return []
    try:
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1min&outputsize=5&apikey={API_KEY_TWELVEDATA}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("values", [])
    except Exception as e:
        print(f"خطأ للرمز {symbol}: {e}")
        return []

def get_fundamental_data(symbol: str) -> Dict:
    if not FINNHUB_API_KEY:
        print("مفتاح Finnhub غير محدد.")
        return {}
    finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)
    info = {}
    try:
        metrics = finnhub_client.company_basic_financials(symbol, 'all').get('metric', {})
        info['net_profit_margin'] = metrics.get('netMarginAnnual')
        info['gross_profit_margin'] = metrics.get('grossMarginAnnual')
        info['current_ratio'] = metrics.get('currentRatioAnnual')
        bs = finnhub_client.company_balance_sheet(symbol, 'annual')
        if bs and 'bs' in bs and bs['bs']:
            info['cash_and_cash_equivalents'] = bs['bs'][0].get('cashAndCashEquivalents')
            info['total_debt'] = bs['bs'][0].get('totalDebt')
        ic = finnhub_client.company_income_statement(symbol, 'annual')
        if ic and 'ic' in ic and ic['ic']:
            info['total_revenue'] = ic['ic'][0].get('revenue')
    except Exception as e:
        print(f"خطأ في جلب البيانات لـ {symbol}: {e}")
    return info

def passes_financial_filter(f: Dict) -> bool:
    if f.get('net_profit_margin', 0) < MIN_NET_PROFIT_MARGIN: return False
    if f.get('current_ratio', 0) < MIN_CURRENT_RATIO: return False
    if f.get('cash_and_cash_equivalents', 0) < f.get('total_debt', 0): return False
    if f.get('total_revenue', 0) <= 0: return False
    return True

def send_telegram_message(channel: str, message: str):
    if not TELEGRAM_BOT_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": channel, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"فشل إرسال تيليجرام: {e}")

def format_financial_data(f: Dict) -> str:
    text = "
📊 <b>البيانات المالية:</b>
"
    if f.get('total_revenue') is not None:
        revenue = f['total_revenue']
        text += f"💰 الإيرادات السنوية: ${revenue:,.0f}
" if revenue > 0 else f"❌ الإيرادات السنوية: ${revenue:,.0f}
"
    if f.get('net_profit_margin') is not None:
        margin = f['net_profit_margin']
        text += f"✅ هامش صافي الربح: {margin:.2f}%
" if margin > 0 else f"❌ هامش صافي الربح: {margin:.2f}%
"
    if f.get('gross_profit_margin') is not None:
        gpm = f['gross_profit_margin']
        text += f"✅ هامش الربح الإجمالي: {gpm:.2f}%
" if gpm > 0 else f"❌ هامش الربح الإجمالي: {gpm:.2f}%
"
    if f.get('cash_and_cash_equivalents') is not None:
        text += f"💵 النقد المتوفر: ${f['cash_and_cash_equivalents']:,.0f}
"
    if f.get('total_debt') is not None:
        text += f"💳 إجمالي الديون: ${f['total_debt']:,.0f}
"
    if f.get('current_ratio') is not None:
        ratio = f['current_ratio']
        text += f"✅ نسبة التداول: {ratio:.2f}
" if ratio >= 1.0 else f"⚠️ نسبة التداول: {ratio:.2f}
"
    return text

def process_stock(symbol: str):
    print(f"🔍 {symbol}")
    data = get_stock_data(symbol)
    if len(data) < 2: return
    try:
        current_price = float(data[0]["close"])
        prev_price = float(data[1]["close"])
        current_volume = float(data[0]["volume"])
        prev_volume = float(data[1]["volume"])
    except: return
    change_percent = ((current_price - prev_price) / prev_price) * 100 if prev_price else 0
    now = datetime.now(pytz.timezone("Asia/Riyadh"))
    timestamp = now.strftime("%I:%M %p")
    fundamentals = get_fundamental_data(symbol)
    msg = f"📈 <b>{symbol}</b>
💰 السعر الحالي: <b>${current_price:.2f}</b>
"
    msg += f"{'📈' if change_percent > 0 else '📉'} تغير السعر (دقيقة): {change_percent:+.2f}%
"
    msg += f"⏰ {timestamp}
📊 الحجم الحالي: {current_volume:,.0f}
"
    msg += format_financial_data(fundamentals)

    if (current_volume > MIN_VOLUME_THRESHOLD and change_percent >= PRICE_CHANGE_THRESHOLD and
        should_send_alert(symbol, "دخول_سيولة", current_volume, prev_volume)):
        send_telegram_message(CHANNEL_GENERAL, f"🚨 <b>دخول سيولة قوية</b>

{msg}")
        log_alert(symbol, "دخول سيولة قوية", current_price, change_percent, current_volume, prev_volume, fundamentals)

    if (prev_volume > 0 and current_volume >= prev_volume * VOLUME_INCREASE_THRESHOLD and
        should_send_alert(symbol, "تعزيز_دخول", current_volume, prev_volume)):
        send_telegram_message(CHANNEL_GENERAL, f"🟢 <b>تعزيز دخول</b>

{msg}")
        if passes_financial_filter(fundamentals):
            send_telegram_message(CHANNEL_MICROSCOPE, f"🔍 <b>صيد المجهر - تعزيز دخول</b>

{msg}
✅ <b>مرت بفلترة الجودة المالية</b>")
        log_alert(symbol, "تعزيز دخول", current_price, change_percent, current_volume, prev_volume, fundamentals)

    if (prev_volume > 0 and current_volume <= prev_volume * VOLUME_DECREASE_THRESHOLD and
        should_send_alert(symbol, "تحذير_خروج", current_volume, prev_volume)):
        send_telegram_message(CHANNEL_GENERAL, f"⚠️ <b>تحذير خروج</b>

{msg}")
        if passes_financial_filter(fundamentals):
            send_telegram_message(CHANNEL_MICROSCOPE, f"🔍 <b>صيد المجهر - تحذير خروج</b>

{msg}
✅ <b>مرت بفلترة الجودة المالية</b>")
        log_alert(symbol, "تحذير خروج", current_price, change_percent, current_volume, prev_volume, fundamentals)

def run_bot():
    print("🚀 بدء تشغيل البوت...")
    if not API_KEY_TWELVEDATA or not FINNHUB_API_KEY or not TELEGRAM_BOT_TOKEN: return
    initialize_log_file()
    while True:
        try:
            for symbol in get_valid_stocks():
                process_stock(symbol)
                time.sleep(1)
            time.sleep(60)
        except KeyboardInterrupt:
            print("🛑 تم إيقاف البوت.")
            break
        except Exception as e:
            print(f"⚠️ خطأ عام: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_bot()
