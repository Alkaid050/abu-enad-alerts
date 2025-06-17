#!/usr/bin/env python3
"""
بوت مراقبة السيولة المتكامل - النسخة المحسنة مع TwelveData
يراقب السوق الأمريكي للأسهم الشرعية ≤ 10 دولار
"""

import requests
import time
import json
import csv
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
import logging
from dataclasses import dataclass
import numpy as np
from collections import defaultdict

# إعداد نظام السجلات
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ===== إعدادات API والقنوات =====
FINNHUB_API_KEY = "your_finnhub_api_key"  # استبدل بمفتاحك
API_KEY_TWELVEDATA = "your_twelvedata_api_key"  # استبدل بمفتاحك
TELEGRAM_BOT_TOKEN = "your_telegram_bot_token"  # استبدل بمفتاحك
CHANNEL_GENERAL = "@your_general_channel"  # استبدل بقناتك
CHANNEL_MICROSCOPE = "@your_microscope_channel"  # استبدل بقناتك

# ===== إعدادات التداول =====
MIN_VOLUME_THRESHOLD = 50000
PRICE_CHANGE_THRESHOLD = 2.0
VOLUME_INCREASE_THRESHOLD = 1.25
VOLUME_DECREASE_THRESHOLD = 0.85
ALERT_COOLDOWN_MINUTES = 30
MAX_STOCK_PRICE = 10.0
MIN_NET_PROFIT_MARGIN = -5.0
MIN_CURRENT_RATIO = 1.0

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
        # إعدادات الفلترة
        self.MAX_PRICE = MAX_STOCK_PRICE
        self.MIN_VOLUME = MIN_VOLUME_THRESHOLD
        self.VOLUME_INCREASE_THRESHOLD = VOLUME_INCREASE_THRESHOLD
        self.ENHANCEMENT_THRESHOLD = 1.25  # تعزيز عند +25%
        self.EXIT_WARNING_THRESHOLD = 0.85  # تحذير عند -15%
        self.EXIT_FINAL_THRESHOLD = 0.75  # خروج نهائي عند -25%
        self.COOLDOWN_MINUTES = ALERT_COOLDOWN_MINUTES
        
        # بيانات التتبع
        self.tracked_stocks: Dict[str, Dict] = {}
        self.last_alerts: Dict[str, datetime] = {}
        self.stock_peaks: Dict[str, float] = {}
        self.alerted_symbols: Set[str] = set()
        self.liquidity_history: Dict[str, List[float]] = defaultdict(list)
        self.price_history: Dict[str, List[float]] = defaultdict(list)
        
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
                    'نوع التنبيه', 'القيمة العادلة', 'RSI', 'الدعم', 'المقاومة',
                    'السعر المتوقع', 'السيولة القصوى', 'السيولة الحالية'
                ])
    
    def has_liquidity_inflow(self, symbol: str) -> bool:
        """التحقق من وجود دخول سيولة قوي"""
        if symbol not in self.liquidity_history or len(self.liquidity_history[symbol]) < 3:
            return False
        
        volumes = self.liquidity_history[symbol][-3:]
        return all(volumes[i] < volumes[i+1] for i in range(len(volumes)-1))
    
    def estimate_expected_price(self, symbol: str, current_liquidity: float, trend: float) -> float:
        """حساب السعر المتوقع بناءً على السيولة والزمن"""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 2:
            return 0.0
        
        prices = self.price_history[symbol]
        volumes = self.liquidity_history.get(symbol, [])
        min_len = min(len(prices), len(volumes))
        
        price_changes = []
        liquidity_changes = []
        
        for i in range(1, min_len):
            if volumes[i-1] > 0:
                price_change = (prices[i] - prices[i-1]) / prices[i-1]
                liquidity_change = (volumes[i] - volumes[i-1]) / volumes[i-1]
                price_changes.append(price_change)
                liquidity_changes.append(liquidity_change)
        
        if not price_changes:
            return 0.0
        
        avg_ratio = np.mean([p/l if l != 0 else 0 for p, l in zip(price_changes, liquidity_changes)])
        last_price = prices[-1]
        expected_change = avg_ratio * current_liquidity * trend
        return round(last_price * (1 + expected_change), 2)
    
    def get_fair_value_from_finnhub(self, symbol: str) -> Optional[float]:
        """حساب القيمة العادلة من Finnhub API"""
        try:
            url = f"https://finnhub.io/api/v1/stock/metric"
            params = {
                'symbol': symbol,
                'metric': 'priceFairValue',
                'token': FINNHUB_API_KEY
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json().get('metric', {}).get('priceFairValue', None)
            return None
        except Exception as e:
            logger.error(f"خطأ في جلب القيمة العادلة لـ {symbol}: {e}")
            return None
    
    def get_all_us_stocks_from_twelvedata(self) -> List[str]:
        """جلب جميع الأسهم الأمريكية من TwelveData"""
        try:
            logger.info("🔍 جلب جميع الأسهم من TwelveData...")
            url = "https://api.twelvedata.com/stocks"
            params = {'country': 'United States', 'apikey': API_KEY_TWELVEDATA}
            
            response = requests.get(url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    return [
                        stock['symbol'] for stock in data['data']
                        if (stock.get('exchange') in ['NASDAQ', 'NYSE', 'AMEX'] and
                            stock.get('symbol') and 
                            '.' not in stock['symbol'] and
                            len(stock['symbol']) <= 5 and
                            stock['symbol'].isalpha() and
                            stock['symbol'] not in self.FORBIDDEN_STOCKS)
                    ]
            return self._get_comprehensive_fallback_stocks()
        except Exception as e:
            logger.error(f"خطأ في جلب الأسهم: {e}")
            return self._get_comprehensive_fallback_stocks()
    
    def _get_comprehensive_fallback_stocks(self) -> List[str]:
        """قائمة شاملة من الأسهم الأمريكية (500+ سهم)"""
        logger.info("📋 استخدام القائمة الشاملة الاحتياطية...")
        return [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'AMD', 'INTC',
            'ORCL', 'CRM', 'ADBE', 'NFLX', 'PYPL', 'UBER', 'LYFT', 'SNAP', 'TWTR',
            'PINS', 'SQ', 'SHOP', 'ROKU', 'ZM', 'DOCU', 'PLTR', 'SOFI', 'WISH', 'CLOV',
            'SPCE', 'NIO', 'XPEV', 'LI', 'RIVN', 'LCID', 'FISV', 'CHPT', 'BLNK', 'PLUG',
            'FCEL', 'ENPH', 'SEDG', 'RUN', 'NOVA', 'SPWR', 'CSIQ', 'JKS', 'SOL', 'MAXN',
            'ARRY', 'SIRI', 'NOK', 'BB', 'T', 'VZ', 'TMUS', 'DISH', 'CMCSA', 'DIS',
            'NWSA', 'FOXA', 'PARA', 'WBD', 'FUBO', 'GSAT', 'IRDM', 'VSAT', 'GILT', 'HEAR',
            'AMC', 'GME', 'RBLX', 'TTWO', 'EA', 'ATVI', 'ZNGA', 'SKLZ', 'DKNG', 'PENN',
            'MRNA', 'PFE', 'JNJ', 'ABBV', 'TMO', 'UNH', 'CVS', 'AMGN', 'GILD', 'BIIB',
            'REGN', 'VRTX', 'ILMN', 'ISRG', 'DXCM', 'ZTS', 'IDXX', 'IQV', 'VEEV', 'TDOC',
            'ETSY', 'EBAY', 'BABA', 'JD', 'PDD', 'SE', 'MELI', 'CPNG', 'GRAB', 'DIDI',
            'WMT', 'TGT', 'COST', 'HD', 'LOW', 'TJX', 'ROST', 'DG', 'DLTR', 'BBY',
            'AAL', 'DAL', 'UAL', 'LUV', 'ALK', 'JBLU', 'SAVE', 'HA', 'SKYW', 'MESA',
            'ABNB', 'BKNG', 'EXPE', 'TRIP', 'MMYT', 'TCOM', 'HTHT', 'RCL', 'CCL', 'NCLH',
            'XOM', 'CVX', 'COP', 'EOG', 'SLB', 'HAL', 'BKR', 'OXY', 'DVN', 'FANG',
            'MRO', 'APA', 'HES', 'VLO', 'MPC', 'PSX', 'PBF', 'DK', 'CTRA', 'SM',
            'AMT', 'PLD', 'CCI', 'EQIX', 'DLR', 'SBAC', 'EXR', 'AVB', 'EQR', 'UDR',
            'CPT', 'ESS', 'MAA', 'AIV', 'BXP', 'VTR', 'WELL', 'PEAK', 'DOC', 'HR',
            'V', 'MA', 'AXP', 'COF', 'DFS', 'SYF', 'ALLY', 'LC', 'UPST', 'AFRM',
            'HOOD', 'COIN', 'MSTR', 'RIOT', 'MARA', 'HUT', 'BITF', 'CAN', 'HIVE', 'ARBK',
            'MVIS', 'SENS', 'CTRM', 'SNDL', 'NAKD', 'EXPR', 'KOSS', 'BBIG', 'PROG', 'ATER',
            'SPRT', 'GREE', 'IRNT', 'OPAD', 'TMC', 'BKKT', 'PHUN', 'DWAC', 'CFVI', 'BENF',
            'AI', 'PATH', 'SNOW', 'DDOG', 'CRWD', 'ZS', 'OKTA', 'PANW', 'FTNT', 'CYBR',
            'SPLK', 'NOW', 'WDAY', 'TEAM', 'ATLR', 'MDB', 'ESTC', 'ELASTIC', 'SUMO', 'FROG',
            'BNTX', 'NVAX', 'OCGN', 'INO', 'SRNE', 'VXRT', 'ATOS', 'CTXR', 'JAGX', 'OBSV',
            'BNGO', 'PACB', 'TWST', 'CRSP', 'EDIT', 'NTLA', 'BEAM', 'PRIME', 'VERV',
            'ICLN', 'PBW', 'QCLN', 'SMOG', 'ACES', 'FAN', 'GRID', 'RAYS', 'SUNW', 'OPTT',
            'WATT', 'AMRC', 'CLNE', 'BLDP', 'HYLN', 'WKHS', 'ARVL', 'KO', 'PEP', 'MDLZ',
            'GIS', 'K', 'CPB', 'CAG', 'SJM', 'HSY', 'MKC', 'CL', 'PG', 'UL', 'NSRGY',
            'EL', 'COTY', 'REV', 'IFF', 'FMC', 'CF', 'BA', 'CAT', 'DE', 'GE', 'HON',
            'MMM', 'LMT', 'RTX', 'NOC', 'GD', 'TXT', 'ITW', 'EMR', 'ETN', 'PH', 'CMI',
            'DOV', 'FLR', 'FORD', 'GM', 'STLA', 'HMC', 'TM', 'RACE', 'VWAGY', 'BMWYY',
            'BLK', 'SCHW', 'SPGI', 'MCO', 'ICE', 'CME', 'NDAQ', 'CBOE', 'MKTX', 'TW',
            'EVRG', 'CNP', 'AEP', 'SO'
        ]
    
    def get_stock_price_data(self, symbol: str) -> Optional[StockData]:
        """جلب بيانات السعر والحجم من TwelveData"""
        try:
            url = "https://api.twelvedata.com/quote"
            params = {'symbol': symbol, 'apikey': API_KEY_TWELVEDATA}
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'price' in data and data['price']:
                    return StockData(
                        symbol=symbol,
                        price=float(data['price']),
                        volume=float(data.get('volume', 0)),
                        change_percent=float(data.get('percent_change', 0)),
                        market_cap=float(data.get('market_cap', 0))
            return None
        except Exception as e:
            logger.error(f"خطأ في جلب بيانات {symbol}: {e}")
            return None
    
    def calculate_rsi(self, symbol: str, period: int = 14) -> Optional[float]:
        """حساب مؤشر القوة النسبية RSI"""
        try:
            url = "https://api.twelvedata.com/time_series"
            params = {
                'symbol': symbol,
                'interval': '1day',
                'outputsize': period + 5,
                'apikey': API_KEY_TWELVEDATA
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'values' in data and len(data['values']) >= period:
                    closes = [float(v['close']) for v in reversed(data['values'])]
                    deltas = np.diff(closes)
                    gains = np.where(deltas > 0, deltas, 0)
                    losses = np.where(deltas < 0, -deltas, 0)
                    
                    avg_gain = np.mean(gains[:period])
                    avg_loss = np.mean(losses[:period])
                    
                    if avg_loss == 0:
                        return 100
                    
                    rs = avg_gain / avg_loss
                    return round(100 - (100 / (1 + rs)), 2)
            return None
        except Exception as e:
            logger.error(f"خطأ في حساب RSI لـ {symbol}: {e}")
            return None
    
    def calculate_support_resistance(self, symbol: str) -> Tuple[Optional[float], Optional[float]]:
        """حساب مستويات الدعم والمقاومة"""
        try:
            url = "https://api.twelvedata.com/time_series"
            params = {
                'symbol': symbol,
                'interval': '1day',
                'outputsize': 20,
                'apikey': API_KEY_TWELVEDATA
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'values' in data and len(data['values']) >= 10:
                    highs = [float(v['high']) for v in data['values']]
                    lows = [float(v['low']) for v in data['values']]
                    return round(min(lows), 2), round(max(highs), 2)
            return None, None
        except Exception as e:
            logger.error(f"خطأ في حساب الدعم/المقاومة لـ {symbol}: {e}")
            return None, None
    
    def is_halal_stock(self, symbol: str, stock_data: StockData) -> bool:
        """فحص ما إذا كان السهم شرعي"""
        if symbol in self.FORBIDDEN_STOCKS:
            return False
        
        financial_data = self.get_financial_data(symbol)
        if financial_data:
            if financial_data.get('debt', 0) > 0.33:
                return False
            if financial_data.get('net_margin', 0) < MIN_NET_PROFIT_MARGIN:
                return False
            if financial_data.get('current_ratio', 0) > 0 and financial_data['current_ratio'] < MIN_CURRENT_RATIO:
                return False
        return True
    
    def get_financial_data(self, symbol: str) -> Dict:
        """جلب البيانات المالية من Finnhub أو TwelveData"""
        try:
            url = "https://api.twelvedata.com/statistics"
            params = {'symbol': symbol, 'apikey': API_KEY_TWELVEDATA}
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                stats = data.get('statistics', {})
                return {
                    'cash': stats.get('cash_per_share', 0),
                    'debt': stats.get('debt_to_equity', 0),
                    'net_margin': stats.get('profit_margin', 0),
                    'current_ratio': stats.get('current_ratio', 0),
                    'pe_ratio': stats.get('pe_ratio', 0),
                    'shares_outstanding': stats.get('shares_outstanding', 0)
                }
            return self._get_financial_data_from_finnhub(symbol)
        except Exception as e:
            logger.error(f"خطأ في جلب البيانات المالية لـ {symbol}: {e}")
            return {}
    
    def _get_financial_data_from_finnhub(self, symbol: str) -> Dict:
        """جلب البيانات المالية من Finnhub كاحتياط"""
        try:
            url = "https://finnhub.io/api/v1/stock/metric"
            params = {
                'symbol': symbol,
                'metric': 'all',
                'token': FINNHUB_API_KEY
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                metrics = response.json().get('metric', {})
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
            logger.error(f"خطأ في جلب البيانات من Finnhub لـ {symbol}: {e}")
            return {}
    
    def send_boost_alert(self, symbol: str, current_price: float):
        """إرسال تنبيه التعزيز"""
        message = f"🚀 تعزيز: {symbol}\nالسعر الحالي: {current_price:.2f}\n"
        message += f"📊 السيولة تجاوزت 25% من القمة السابقة"
        self.send_telegram_message(message, CHANNEL_MICROSCOPE)
    
    def send_exit_warning(self, symbol: str, current_price: float):
        """إرسال تحذير خروج"""
        message = f"⚠️ تحذير خروج: {symbol}\nالسعر الحالي: {current_price:.2f}\n"
        message += f"📉 انخفاض السيولة بنسبة 15% من القمة"
        self.send_telegram_message(message, CHANNEL_MICROSCOPE)
    
    def send_final_exit_alert(self, symbol: str, current_price: float):
        """إرسال تنبيه خروج نهائي"""
        message = f"🔴 خروج نهائي: {symbol}\nالسعر الحالي: {current_price:.2f}\n"
        message += f"📉 انخفاض السيولة بنسبة 25% من القمة"
        self.send_telegram_message(message, CHANNEL_MICROSCOPE)
        self.remove_from_tracking(symbol)
    
    def remove_from_tracking(self, symbol: str):
        """إزالة السهم من التتبع"""
        for d in [self.tracked_stocks, self.stock_peaks, self.liquidity_history, self.price_history]:
            d.pop(symbol, None)
        self.alerted_symbols.discard(symbol)
    
    def send_telegram_message(self, message: str, channel: str):
        """إرسال رسالة تليجرام"""
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {'chat_id': channel, 'text': message, 'parse_mode': 'HTML'}
            response = requests.post(url, data=data, timeout=10)
            if response.status_code != 200:
                logger.error(f"خطأ في إرسال التنبيه: {response.status_code}")
        except Exception as e:
            logger.error(f"خطأ في إرسال التنبيه: {e}")
    
    def process_stock(self, symbol: str):
        """معالجة سهم واحد"""
        try:
            # 1. جلب بيانات السهم
            stock_data = self.get_stock_price_data(symbol)
            if not stock_data:
                return
            
            # 2. فلترة السعر (≤ 10 دولار)
            if stock_data.price > self.MAX_PRICE:
                return
            
            # 3. فلترة الأسهم الشرعية (مع استثناء MLGO و JFBR)
            if not self.is_halal_stock(symbol, stock_data) and symbol not in ['MLGO', 'JFBR']:
                return
            
            # تحديث التاريخ السعري والسيولة
            self.price_history[symbol].append(stock_data.price)
            self.liquidity_history[symbol].append(stock_data.volume)
            
            # الحفاظ على حجم التاريخ محدودًا
            for history in [self.price_history, self.liquidity_history]:
                if len(history[symbol]) > 10:
                    history[symbol] = history[symbol][-10:]
            
            # 4. التحقق من وجود دخول سيولة قوي
            if not self.has_liquidity_inflow(symbol):
                return
            
            # 5. التأكد من ارتفاع السعر 2% بعد دخول السيولة
            if symbol in self.tracked_stocks:
                entry_price = self.tracked_stocks[symbol].get('entry_price', 0)
                if stock_data.price < entry_price * 1.02:
                    return
            
            # حساب المؤشرات
            fair_value = self.get_fair_value_from_finnhub(symbol)
            rsi = self.calculate_rsi(symbol)
            support, resistance = self.calculate_support_resistance(symbol)
            trend = 1.0 if stock_data.change_percent >= 0 else -1.0
            expected_price = self.estimate_expected_price(symbol, stock_data.volume, trend)
            
            # 6. منع تكرار التنبيهات
            if symbol in self.alerted_symbols:
                return
            
            # تحديث قمة السيولة
            if symbol not in self.stock_peaks or stock_data.volume > self.stock_peaks[symbol]:
                self.stock_peaks[symbol] = stock_data.volume
            
            # 7. تنبيهات التعزيز عند +25%
            if symbol in self.stock_peaks and stock_data.volume > self.stock_peaks[symbol] * 1.25:
                self.send_boost_alert(symbol, stock_data.price)
                self.alerted_symbols.add(symbol)
            
            # 8. تنبيهات الخروج عند انخفاض السيولة
            if symbol in self.stock_peaks:
                max_liquidity = self.stock_peaks[symbol]
                current_liquidity = stock_data.volume
                drop = (max_liquidity - current_liquidity) / max_liquidity
                
                if drop >= 0.15 and drop < 0.25:
                    self.send_exit_warning(symbol, stock_data.price)
                    self.alerted_symbols.add(symbol)
                elif drop >= 0.25:
                    self.send_final_exit_alert(symbol, stock_data.price)
                    return
            
            # 9. إرسال التنبيه الرئيسي
            alert_type = "دخول" if symbol not in self.tracked_stocks else "متابعة"
            message = (
                f"🚨 {symbol}\n💰 السعر: ${stock_data.price:.2f}\n"
                f"📈 المتوقع: ${expected_price:.2f}\n"
                f"🎯 العادلة: ${fair_value:.2f if fair_value else 'N/A'}\n"
                f"📣 النوع: {alert_type}\n"
                f"📊 الحجم: {stock_data.volume:,.0f}\n"
                f"📈 التغير: {stock_data.change_percent:+.2f}%\n"
                f"⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}"
            )
            
            channel = CHANNEL_GENERAL if alert_type == "دخول" else CHANNEL_MICROSCOPE
            self.send_telegram_message(message, channel)
            self.alerted_symbols.add(symbol)
            
            # 10. حفظ في CSV
            self.save_to_csv(
                symbol, stock_data, alert_type, 
                fair_value, rsi, support, resistance,
                expected_price, 
                self.stock_peaks.get(symbol, 0),
                stock_data.volume
            )
            
            # تحديث بيانات التتبع
            if symbol not in self.tracked_stocks:
                self.tracked_stocks[symbol] = {
                    'entry_price': stock_data.price,
                    'entry_volume': stock_data.volume,
                    'entry_time': datetime.now()
                }
            
        except Exception as e:
            logger.error(f"خطأ في معالجة {symbol}: {e}")
    
    def save_to_csv(self, symbol: str, stock_data: StockData, alert_type: str,
                   fair_value: Optional[float] = None, rsi: Optional[float] = None,
                   support: Optional[float] = None, resistance: Optional[float] = None,
                   expected_price: Optional[float] = None, max_liquidity: Optional[float] = None,
                   current_liquidity: Optional[float] = None):
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
                    resistance or '',
                    expected_price or '',
                    max_liquidity or '',
                    current_liquidity or ''
                ])
        except Exception as e:
            logger.error(f"خطأ في حفظ البيانات: {e}")
    
    def run_scan(self):
        """تشغيل مسح واحد للسوق"""
        logger.info("🔍 بدء مسح السوق...")
        all_stocks = self.get_all_us_stocks_from_twelvedata()
        
        if not all_stocks:
            logger.error("❌ لا توجد أسهم للمعالجة")
            return
        
        batch_size = 50
        processed_count = 0
        
        for i in range(0, len(all_stocks), batch_size):
            batch = all_stocks[i:i + batch_size]
            
            for symbol in batch:
                try:
                    self.process_stock(symbol)
                    processed_count += 1
                    time.sleep(0.5)
                except Exception as e:
                    logger.error(f"خطأ في معالجة {symbol}: {e}")
            
            logger.info(f"تم معالجة {processed_count}/{len(all_stocks)} سهم...")
            if i + batch_size < len(all_stocks):
                time.sleep(10)
        
        logger.info(f"✅ انتهى المسح - تم معالجة {processed_count} سهم")
        logger.info(f"📊 الأسهم المتتبعة حالياً: {len(self.tracked_stocks)}")
    
    def run_continuous(self):
        """تشغيل البوت بشكل مستمر"""
        logger.info("🚀 بدء تشغيل بوت مراقبة السيولة...")
        logger.info(f"📡 القناة الرئيسية: {CHANNEL_GENERAL}")
        logger.info(f"🔬 قناة المجهر: {CHANNEL_MICROSCOPE}")
        
        while True:
            try:
                self.run_scan()
                logger.info("⏳ انتظار دقيقة واحدة...")
                time.sleep(60)
            except KeyboardInterrupt:
                logger.info("🛑 تم إيقاف البوت بواسطة المستخدم")
                break
            except Exception as e:
                logger.error(f"خطأ في التشغيل: {e}")
                logger.info("⏳ انتظار 30 ثانية قبل إعادة المحاولة...")
                time.sleep(30)

def main():
    """الدالة الرئيسية"""
    print("🚀 بوت مراقبة السيولة - النسخة النهائية")
    print("=" * 60)
    print(f"📡 القناة الرئيسية: {CHANNEL_GENERAL}")
    print(f"🔬 قناة المجهر: {CHANNEL_MICROSCOPE}")
    print(f"💰 الحد الأقصى للسعر: ${MAX_STOCK_PRICE}")
    print(f"📊 الحد الأدنى للحجم: {MIN_VOLUME_THRESHOLD:,}")
    print("=" * 60)
    
    bot = LiquidityBot()
    bot.run_continuous()

if __name__ == "__main__":
    main()
