#!/usr/bin/env python3
"""
بوت مراقبة السيولة المتكامل - النسخة المصححة
يراقب السوق الأمريكي للأسهم الشرعية ≤ 10 دولار
"""

import requests
import time
import json
import csv
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
import numpy as np

# إعداد نظام السجلات
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class StockData:
    """بيانات السهم"""
    symbol: str
    price: float
    volume: float
    change_percent: float
    market_cap: float = 0
    pe_ratio: float = 0

class LiquidityBot:
    """بوت مراقبة السيولة المتكامل"""
    
    def __init__(self):
        # إعدادات API
        self.FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY', 'YOUR_FINNHUB_KEY')
        self.TWELVEDATA_API_KEY = os.getenv('TWELVEDATA_API_KEY', 'YOUR_TWELVEDATA_KEY')
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_TELEGRAM_TOKEN')
        
        # أسماء القنوات
        self.RADAR_CHANNEL = os.getenv('RADAR_CHANNEL', '@radar_liquidity_channel')
        self.MICROSCOPE_CHANNEL = os.getenv('MICROSCOPE_CHANNEL', '@microscope_channel')
        
        # إعدادات الفلترة
        self.MAX_PRICE = 10.0  # سعر أقصى 10 دولار
        self.MIN_VOLUME = 50000  # حجم تداول أدنى
        self.VOLUME_INCREASE_THRESHOLD = 2.0  # زيادة السيولة 2x
        self.ENHANCEMENT_THRESHOLD = 1.25  # تعزيز عند +25%
        self.EXIT_WARNING_THRESHOLD = 0.85  # تحذير عند -15%
        self.EXIT_FINAL_THRESHOLD = 0.75  # خروج نهائي عند -25%
        self.COOLDOWN_MINUTES = 30  # منع التكرار لمدة 30 دقيقة
        
        # بيانات التتبع
        self.tracked_stocks: Dict[str, Dict] = {}
        self.last_alerts: Dict[str, datetime] = {}
        self.stock_peaks: Dict[str, float] = {}
        
        # قائمة الأسهم المحرمة (للاستثناء)
        self.FORBIDDEN_STOCKS = {
            'MLGO', 'JFBR', 'BAC', 'JPM', 'WFC', 'C', 'GS', 'MS',  # بنوك
            'BUD', 'TAP', 'STZ', 'DEO',  # كحول
            'LVS', 'WYNN', 'MGM', 'CZR',  # قمار
            'MO', 'PM', 'BTI'  # تبغ
        }
        
        # إنشاء ملف CSV للسجلات
        self.csv_file = 'liquidity_alerts.csv'
        self._init_csv()
    
    def _init_csv(self):
        """إنشاء ملف CSV للسجلات"""
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'التاريخ', 'الوقت', 'الرمز', 'السعر', 'التغير%', 'الحجم',
                    'نوع التنبيه', 'القيمة العادلة', 'RSI', 'الدعم', 'المقاومة'
                ])
    
    def get_all_us_stocks(self) -> List[str]:
        """جلب جميع الأسهم الأمريكية من Finnhub"""
        try:
            url = f"https://finnhub.io/api/v1/stock/symbol?exchange=US&token={self.FINNHUB_API_KEY}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                stocks = response.json()
                symbols = [stock['symbol'] for stock in stocks 
                          if stock.get('type') == 'Common Stock' 
                          and '.' not in stock['symbol']  # استثناء الأسهم المعقدة
                          and len(stock['symbol']) <= 5]  # رموز قصيرة فقط
                
                logger.info(f"تم جلب {len(symbols)} سهم من السوق الأمريكي")
                return symbols[:500]  # أول 500 سهم لتجنب تجاوز حدود API
            else:
                logger.error(f"خطأ في جلب الأسهم: {response.status_code}")
                return self._get_fallback_stocks()
                
        except Exception as e:
            logger.error(f"خطأ في جلب الأسهم: {e}")
            return self._get_fallback_stocks()
    
    def _get_fallback_stocks(self) -> List[str]:
        """قائمة احتياطية من الأسهم الشرعية المعروفة"""
        return [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'AMD',
            'INTC', 'ORCL', 'CRM', 'ADBE', 'NFLX', 'PYPL', 'UBER', 'LYFT',
            'SNAP', 'TWTR', 'PINS', 'SQ', 'SHOP', 'ROKU', 'ZM', 'DOCU',
            'PLTR', 'SOFI', 'WISH', 'CLOV', 'SPCE', 'NIO', 'XPEV', 'LI',
            'SIRI', 'NOK', 'BB', 'AMC', 'GME', 'MVIS', 'SENS', 'CTRM'
        ]
    
    def get_stock_price_data(self, symbol: str) -> Optional[StockData]:
        """جلب بيانات السعر والحجم من TwelveData"""
        try:
            # جلب البيانات الحالية
            url = f"https://api.twelvedata.com/quote"
            params = {
                'symbol': symbol,
                'apikey': self.TWELVEDATA_API_KEY
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'price' in data:
                    return StockData(
                        symbol=symbol,
                        price=float(data['price']),
                        volume=float(data.get('volume', 0)),
                        change_percent=float(data.get('percent_change', 0)),
                        market_cap=float(data.get('market_cap', 0))
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"خطأ في جلب بيانات {symbol}: {e}")
            return None
    
    def get_financial_data(self, symbol: str) -> Dict:
        """جلب البيانات المالية من Finnhub"""
        try:
            # البيانات المالية الأساسية
            url = f"https://finnhub.io/api/v1/stock/metric"
            params = {
                'symbol': symbol,
                'metric': 'all',
                'token': self.FINNHUB_API_KEY
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                metrics = data.get('metric', {})
                
                return {
                    'cash': metrics.get('totalCashPerShareTTM', 0),
                    'debt': metrics.get('totalDebtToTotalCapitalTTM', 0),
                    'net_margin': metrics.get('netProfitMarginTTM', 0),
                    'current_ratio': metrics.get('currentRatioTTM', 0),
                    'pe_ratio': metrics.get('peBasicExclExtraTTM', 0),
                    'shares_outstanding': metrics.get('sharesOutstanding', 0)
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"خطأ في جلب البيانات المالية لـ {symbol}: {e}")
            return {}
    
    def calculate_fair_value(self, symbol: str, stock_data: StockData) -> Optional[float]:
        """حساب القيمة العادلة"""
        try:
            financial_data = self.get_financial_data(symbol)
            
            if not financial_data:
                return None
            
            # طريقة 1: القيمة الدفترية المعدلة
            cash = financial_data.get('cash', 0)
            debt_ratio = financial_data.get('debt', 0)
            shares = financial_data.get('shares_outstanding', 0)
            
            if shares > 0 and cash > 0:
                # القيمة العادلة = (النقد - نسبة الديون) / عدد الأسهم
                debt_amount = stock_data.market_cap * debt_ratio if debt_ratio else 0
                fair_value = (cash * shares - debt_amount) / shares
                return max(fair_value, 0.1)  # حد أدنى 0.1 دولار
            
            # طريقة 2: مضاعف P/E المعدل
            pe_ratio = financial_data.get('pe_ratio', 0)
            if pe_ratio > 0 and pe_ratio < 50:  # P/E معقول
                earnings_per_share = stock_data.price / pe_ratio
                fair_value = earnings_per_share * 15  # P/E مثالي = 15
                return fair_value
            
            return None
            
        except Exception as e:
            logger.error(f"خطأ في حساب القيمة العادلة لـ {symbol}: {e}")
            return None
    
    def calculate_rsi(self, symbol: str, period: int = 14) -> Optional[float]:
        """حساب مؤشر القوة النسبية RSI"""
        try:
            # جلب البيانات التاريخية
            url = f"https://api.twelvedata.com/time_series"
            params = {
                'symbol': symbol,
                'interval': '1day',
                'outputsize': period + 5,
                'apikey': self.TWELVEDATA_API_KEY
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                values = data.get('values', [])
                
                if len(values) >= period:
                    closes = [float(v['close']) for v in reversed(values)]
                    
                    # حساب RSI
                    deltas = np.diff(closes)
                    gains = np.where(deltas > 0, deltas, 0)
                    losses = np.where(deltas < 0, -deltas, 0)
                    
                    avg_gain = np.mean(gains[:period])
                    avg_loss = np.mean(losses[:period])
                    
                    if avg_loss == 0:
                        return 100
                    
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
                    
                    return round(rsi, 2)
            
            return None
            
        except Exception as e:
            logger.error(f"خطأ في حساب RSI لـ {symbol}: {e}")
            return None
    
    def calculate_support_resistance(self, symbol: str) -> Tuple[Optional[float], Optional[float]]:
        """حساب مستويات الدعم والمقاومة"""
        try:
            # جلب البيانات التاريخية
            url = f"https://api.twelvedata.com/time_series"
            params = {
                'symbol': symbol,
                'interval': '1day',
                'outputsize': 20,
                'apikey': self.TWELVEDATA_API_KEY
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                values = data.get('values', [])
                
                if len(values) >= 10:
                    highs = [float(v['high']) for v in values]
                    lows = [float(v['low']) for v in values]
                    
                    # حساب الدعم والمقاومة
                    resistance = round(max(highs), 2)
                    support = round(min(lows), 2)
                    
                    return support, resistance
            
            return None, None
            
        except Exception as e:
            logger.error(f"خطأ في حساب الدعم والمقاومة لـ {symbol}: {e}")
            return None, None
    
    def is_halal_stock(self, symbol: str, stock_data: StockData) -> bool:
        """فحص ما إذا كان السهم شرعي"""
        # استثناء الأسهم المحرمة
        if symbol in self.FORBIDDEN_STOCKS:
            return False
        
        # فحص البيانات المالية
        financial_data = self.get_financial_data(symbol)
        
        if financial_data:
            # الشرط 1: النقد أقل من الديون (للشركات الشرعية)
            cash = financial_data.get('cash', 0)
            debt_ratio = financial_data.get('debt', 0)
            
            # تصحيح المنطق: الشرعية تتطلب ديون قليلة
            if debt_ratio > 0.33:  # نسبة ديون أعلى من 33%
                return False
            
            # الشرط 2: هامش صافي الربح أكبر من -5%
            net_margin = financial_data.get('net_margin', 0)
            if net_margin < -5:
                return False
            
            # الشرط 3: نسبة السيولة أكبر من 1
            current_ratio = financial_data.get('current_ratio', 0)
            if current_ratio > 0 and current_ratio < 1:
                return False
        
        return True
    
    def check_liquidity_entry(self, symbol: str, stock_data: StockData) -> bool:
        """فحص دخول السيولة"""
        # فحص السعر ≤ 10 دولار
        if stock_data.price > self.MAX_PRICE:
            return False
        
        # فحص الحجم الأدنى
        if stock_data.volume < self.MIN_VOLUME:
            return False
        
        # فحص زيادة السيولة 2x
        if symbol in self.tracked_stocks:
            last_volume = self.tracked_stocks[symbol].get('volume', 0)
            if last_volume > 0:
                volume_ratio = stock_data.volume / last_volume
                return volume_ratio >= self.VOLUME_INCREASE_THRESHOLD
        
        # للأسهم الجديدة، قبول إذا كان الحجم عالي
        return stock_data.volume >= self.MIN_VOLUME * 2
    
    def check_enhancement_signal(self, symbol: str, stock_data: StockData) -> bool:
        """فحص إشارة التعزيز (+25%)"""
        if symbol not in self.tracked_stocks:
            return False
        
        entry_volume = self.tracked_stocks[symbol].get('entry_volume', 0)
        if entry_volume > 0:
            volume_ratio = stock_data.volume / entry_volume
            return volume_ratio >= self.ENHANCEMENT_THRESHOLD
        
        return False
    
    def check_exit_signals(self, symbol: str, stock_data: StockData) -> Optional[str]:
        """فحص إشارات الخروج"""
        if symbol not in self.stock_peaks:
            return None
        
        peak_volume = self.stock_peaks[symbol]
        current_ratio = stock_data.volume / peak_volume
        
        if current_ratio <= self.EXIT_FINAL_THRESHOLD:
            return "exit_final"  # خروج نهائي -25%
        elif current_ratio <= self.EXIT_WARNING_THRESHOLD:
            return "exit_warning"  # تحذير -15%
        
        return None
    
    def can_send_alert(self, symbol: str, alert_type: str) -> bool:
        """فحص إمكانية إرسال التنبيه (منع التكرار)"""
        key = f"{symbol}_{alert_type}"
        
        if key in self.last_alerts:
            time_diff = datetime.now() - self.last_alerts[key]
            if time_diff.total_seconds() < self.COOLDOWN_MINUTES * 60:
                return False
        
        return True
    
    def send_telegram_message(self, message: str, channel: str):
        """إرسال رسالة تليجرام"""
        try:
            url = f"https://api.telegram.org/bot{self.TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {
                'chat_id': channel,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"تم إرسال التنبيه إلى {channel}")
            else:
                logger.error(f"خطأ في إرسال التنبيه: {response.status_code}")
                
        except Exception as e:
            logger.error(f"خطأ في إرسال التنبيه: {e}")
    
    def format_alert_message(self, symbol: str, stock_data: StockData, alert_type: str, 
                           fair_value: Optional[float] = None, rsi: Optional[float] = None,
                           support: Optional[float] = None, resistance: Optional[float] = None) -> str:
        """تنسيق رسالة التنبيه"""
        
        if alert_type == "entry":
            emoji = "🚨"
            title = "تنبيه دخول سيولة"
        elif alert_type == "enhancement":
            emoji = "🚀"
            title = "تنبيه تعزيز"
        elif alert_type == "exit_warning":
            emoji = "⚠️"
            title = "تحذير خروج"
        else:  # exit_final
            emoji = "🔴"
            title = "خروج نهائي"
        
        message = f"{emoji} <b>{title}: {symbol}</b>\n\n"
        message += f"💰 السعر: ${stock_data.price:.2f}\n"
        message += f"📈 التغير: {stock_data.change_percent:+.2f}%\n"
        message += f"📊 الحجم: {stock_data.volume:,.0f}\n\n"
        
        # القيمة العادلة
        if fair_value:
            ratio = stock_data.price / fair_value
            if ratio < 0.9:
                value_status = f"🟢 مقوم بأقل من قيمته: {ratio:.2f}x"
            elif ratio > 1.1:
                value_status = f"🔴 مقوم بأعلى من قيمته: {ratio:.2f}x"
            else:
                value_status = f"🟡 مقوم بقيمته العادلة: {ratio:.2f}x"
            
            message += f"🎯 القيمة العادلة: ${fair_value:.2f}\n"
            message += f"{value_status}\n\n"
        
        # المؤشرات الفنية
        if rsi:
            if rsi < 30:
                rsi_status = f"🟢 ذروة بيع RSI: {rsi}"
            elif rsi > 70:
                rsi_status = f"🔴 ذروة شراء RSI: {rsi}"
            else:
                rsi_status = f"🟡 متوازن RSI: {rsi}"
            
            message += f"📈 المؤشرات الفنية:\n{rsi_status}\n\n"
        
        # الدعوم والمقاومات
        if support and resistance:
            message += f"🎯 الدعوم والمقاومات:\n"
            message += f"🟢 الدعم: ${support}\n"
            message += f"🔴 المقاومة: ${resistance}\n\n"
        
        message += f"⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}"
        
        return message
    
    def save_to_csv(self, symbol: str, stock_data: StockData, alert_type: str,
                   fair_value: Optional[float] = None, rsi: Optional[float] = None,
                   support: Optional[float] = None, resistance: Optional[float] = None):
        """حفظ التنبيه في ملف CSV"""
        try:
            with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().strftime('%Y-%m-%d'),
                    datetime.now().strftime('%H:%M:%S'),
                    symbol,
                    stock_data.price,
                    stock_data.change_percent,
                    stock_data.volume,
                    alert_type,
                    fair_value or '',
                    rsi or '',
                    support or '',
                    resistance or ''
                ])
        except Exception as e:
            logger.error(f"خطأ في حفظ البيانات: {e}")
    
    def process_stock(self, symbol: str):
        """معالجة سهم واحد"""
        try:
            # جلب بيانات السهم
            stock_data = self.get_stock_price_data(symbol)
            if not stock_data:
                return
            
            # فحص الشرعية
            if not self.is_halal_stock(symbol, stock_data):
                return
            
            # تحديث قمة السيولة
            if symbol not in self.stock_peaks or stock_data.volume > self.stock_peaks[symbol]:
                self.stock_peaks[symbol] = stock_data.volume
            
            # فحص إشارات الخروج أولاً
            exit_signal = self.check_exit_signals(symbol, stock_data)
            if exit_signal and self.can_send_alert(symbol, exit_signal):
                # حساب المؤشرات للخروج
                fair_value = self.calculate_fair_value(symbol, stock_data)
                rsi = self.calculate_rsi(symbol)
                support, resistance = self.calculate_support_resistance(symbol)
                
                # إرسال تنبيه الخروج
                message = self.format_alert_message(symbol, stock_data, exit_signal,
                                                  fair_value, rsi, support, resistance)
                self.send_telegram_message(message, self.MICROSCOPE_CHANNEL)
                
                # حفظ في CSV
                self.save_to_csv(symbol, stock_data, exit_signal, fair_value, rsi, support, resistance)
                
                # تحديث آخر تنبيه
                self.last_alerts[f"{symbol}_{exit_signal}"] = datetime.now()
                
                # إزالة من التتبع في حالة الخروج النهائي
                if exit_signal == "exit_final":
                    self.tracked_stocks.pop(symbol, None)
                
                return
            
            # فحص التعزيز
            if self.check_enhancement_signal(symbol, stock_data) and self.can_send_alert(symbol, "enhancement"):
                # حساب المؤشرات للتعزيز
                fair_value = self.calculate_fair_value(symbol, stock_data)
                rsi = self.calculate_rsi(symbol)
                support, resistance = self.calculate_support_resistance(symbol)
                
                # إرسال تنبيه التعزيز
                message = self.format_alert_message(symbol, stock_data, "enhancement",
                                                  fair_value, rsi, support, resistance)
                self.send_telegram_message(message, self.MICROSCOPE_CHANNEL)
                
                # حفظ في CSV
                self.save_to_csv(symbol, stock_data, "enhancement", fair_value, rsi, support, resistance)
                
                # تحديث آخر تنبيه
                self.last_alerts[f"{symbol}_enhancement"] = datetime.now()
                
                return
            
            # فحص دخول السيولة
            if self.check_liquidity_entry(symbol, stock_data) and self.can_send_alert(symbol, "entry"):
                # حساب المؤشرات للدخول
                fair_value = self.calculate_fair_value(symbol, stock_data)
                rsi = self.calculate_rsi(symbol)
                support, resistance = self.calculate_support_resistance(symbol)
                
                # إرسال تنبيه الدخول
                message = self.format_alert_message(symbol, stock_data, "entry",
                                                  fair_value, rsi, support, resistance)
                self.send_telegram_message(message, self.RADAR_CHANNEL)
                
                # حفظ في CSV
                self.save_to_csv(symbol, stock_data, "entry", fair_value, rsi, support, resistance)
                
                # إضافة للتتبع
                self.tracked_stocks[symbol] = {
                    'entry_volume': stock_data.volume,
                    'entry_price': stock_data.price,
                    'entry_time': datetime.now()
                }
                
                # تحديث آخر تنبيه
                self.last_alerts[f"{symbol}_entry"] = datetime.now()
            
            # تحديث بيانات التتبع
            if symbol in self.tracked_stocks:
                self.tracked_stocks[symbol]['last_volume'] = stock_data.volume
                self.tracked_stocks[symbol]['last_price'] = stock_data.price
                self.tracked_stocks[symbol]['last_update'] = datetime.now()
                
        except Exception as e:
            logger.error(f"خطأ في معالجة السهم {symbol}: {e}")
    
    def run_scan(self):
        """تشغيل مسح واحد للسوق"""
        logger.info("🔍 بدء مسح السوق...")
        
        # جلب جميع الأسهم
        all_stocks = self.get_all_us_stocks()
        
        processed_count = 0
        for symbol in all_stocks:
            try:
                self.process_stock(symbol)
                processed_count += 1
                
                # توقف قصير لتجنب تجاوز حدود API
                time.sleep(0.1)
                
                # طباعة التقدم كل 50 سهم
                if processed_count % 50 == 0:
                    logger.info(f"تم معالجة {processed_count} سهم...")
                    
            except Exception as e:
                logger.error(f"خطأ في معالجة {symbol}: {e}")
                continue
        
        logger.info(f"✅ انتهى المسح - تم معالجة {processed_count} سهم")
        logger.info(f"📊 الأسهم المتتبعة حالياً: {len(self.tracked_stocks)}")
    
    def run_continuous(self):
        """تشغيل البوت بشكل مستمر"""
        logger.info("🚀 بدء تشغيل بوت مراقبة السيولة...")
        
        while True:
            try:
                self.run_scan()
                
                # انتظار دقيقة واحدة قبل المسح التالي
                logger.info("⏳ انتظار دقيقة واحدة...")
                time.sleep(60)
                
            except KeyboardInterrupt:
                logger.info("🛑 تم إيقاف البوت بواسطة المستخدم")
                break
            except Exception as e:
                logger.error(f"خطأ في التشغيل المستمر: {e}")
                logger.info("⏳ انتظار 30 ثانية قبل المحاولة مرة أخرى...")
                time.sleep(30)

def main():
    """الدالة الرئيسية"""
    # تحميل متغيرات البيئة
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        logger.warning("مكتبة python-dotenv غير مثبتة - يرجى تثبيتها أو إضافة المتغيرات يدوياً")
    
    # إنشاء وتشغيل البوت
    bot = LiquidityBot()
    
    # فحص المفاتيح
    if bot.FINNHUB_API_KEY == 'YOUR_FINNHUB_KEY':
        logger.error("❌ يرجى إضافة مفتاح Finnhub في ملف .env")
        return
    
    if bot.TWELVEDATA_API_KEY == 'YOUR_TWELVEDATA_KEY':
        logger.error("❌ يرجى إضافة مفتاح TwelveData في ملف .env")
        return
    
    if bot.TELEGRAM_BOT_TOKEN == 'YOUR_TELEGRAM_TOKEN':
        logger.error("❌ يرجى إضافة توكن التليجرام في ملف .env")
        return
    
    # تشغيل البوت
    bot.run_continuous()

if __name__ == "__main__":
    main()

