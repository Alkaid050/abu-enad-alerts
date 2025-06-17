#!/usr/bin/env python3
"""
بوت مراقبة السيولة المتكامل - النسخة المعدلة مع تصحيح الفلترة
"""

import requests
import time
import csv
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
import logging
from dataclasses import dataclass
import numpy as np
from collections import defaultdict

# إعداد نظام السجلات
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===== إعدادات API =====
FINNHUB_API_KEY = "d16sfh9r01qkv5jd2beg"
API_KEY_TWELVEDATA = "248a6135d4cf4dd9aafa3417f115795e"
TELEGRAM_BOT_TOKEN = "7413413899:AAG_3UpCE8TbV0RST6c9189Sip2B3k0MbW8"
CHANNEL_GENERAL = "@abu_enad_signals"
CHANNEL_MICROSCOPE = "@abu_enad_signals_2"
# ===== إعدادات التداول =====
MAX_STOCK_PRICE = 10.0
MIN_VOLUME_THRESHOLD = 50000
PRICE_CHANGE_THRESHOLD = 2.0
ALERT_COOLDOWN_MINUTES = 30

@dataclass
class StockData:
    symbol: str
    price: float
    volume: float
    change_percent: float
    market_cap: float = 0
    pe_ratio: float = 0

class EnhancedLiquidityBot:
    def __init__(self):
        self.tracked_stocks: Dict[str, Dict] = {}
        self.stock_peaks: Dict[str, float] = {}
        self.alerted_symbols: Set[str] = set()
        self.price_history: Dict[str, List[float]] = defaultdict(list)
        
        self.FORBIDDEN_STOCKS = {
            'MLGO', 'JFBR', 'BAC', 'JPM', 'WFC', 'C', 'GS', 'MS',
            'BUD', 'TAP', 'STZ', 'DEO', 'LVS', 'WYNN', 'MGM', 'CZR',
            'MO', 'PM', 'BTI'
        }
        
        self._init_csv_logs()

    def _init_csv_logs(self):
        """تهيئة ملف السجلات"""
        self.csv_file = 'enhanced_liquidity_logs.csv'
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Timestamp', 'Symbol', 'Price', 'Volume', 
                    'Change%', 'FairValue', 'AlertType', 'RSI',
                    'Support', 'Resistance'
                ])

    def fetch_market_data(self, symbol: str) -> Optional[StockData]:
        """جلب بيانات السوق مع فلترة محسنة"""
        try:
            # جلب البيانات من TwelveData
            url = "https://api.twelvedata.com/quote"
            params = {
                'symbol': symbol,
                'apikey': API_KEY_TWELVEDATA,
                'interval': '1min'
            }
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if not data.get('price'):
                return None

            price = float(data['price'])
            
            # الفلترة الأساسية
            if price > MAX_STOCK_PRICE:
                logger.debug(f"تم استبعاد {symbol} - السعر {price} > {MAX_STOCK_PRICE}")
                return None

            volume = float(data.get('volume', 0))
            if volume < MIN_VOLUME_THRESHOLD:
                logger.debug(f"تم استبعاد {symbol} - الحجم {volume} < {MIN_VOLUME_THRESHOLD}")
                return None

            return StockData(
                symbol=symbol,
                price=price,
                volume=volume,
                change_percent=float(data.get('percent_change', 0)),
                market_cap=float(data.get('market_cap', 0))
                
        except Exception as e:
            logger.error(f"خطأ في جلب بيانات {symbol}: {str(e)}")
            return None

    def scan_us_market(self) -> List[str]:
        """مسح السوق الأمريكي مع تحسينات"""
        try:
            logger.info("بدء مسح السوق الأمريكي...")
            url = "https://api.twelvedata.com/stocks"
            params = {
                'country': 'United States',
                'exchange': 'NASDAQ,NYSE,AMEX',
                'apikey': API_KEY_TWELVEDATA
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            valid_stocks = []
            for stock in data.get('data', []):
                symbol = stock.get('symbol', '')
                
                # شروط الفلترة الصارمة
                conditions = [
                    symbol not in self.FORBIDDEN_STOCKS,
                    stock.get('exchange') in ['NASDAQ', 'NYSE', 'AMEX'],
                    stock.get('currency') == 'USD',
                    stock.get('type') == 'Common Stock',
                    '.' not in symbol,
                    len(symbol) <= 5,
                    symbol.isalpha()
                ]
                
                if all(conditions):
                    valid_stocks.append(symbol)
            
            logger.info(f"تم العثور على {len(valid_stocks)} سهم مؤهل")
            return valid_stocks

        except Exception as e:
            logger.error(f"فشل مسح السوق: {str(e)}")
            return self._get_fallback_stocks()

    def analyze_stock(self, symbol: str):
        """تحليل متقدم للسهم"""
        stock_data = self.fetch_market_data(symbol)
        if not stock_data:
            return

        # تحليل السيولة
        liquidity_trend = self._calculate_liquidity_trend(symbol, stock_data.volume)
        
        # تحليل السعر
        price_trend = self._calculate_price_trend(symbol, stock_data.price)
        
        # حساب المؤشرات الفنية
        technicals = self._calculate_technical_indicators(symbol)
        
        # تحديد الإشارات
        signals = self._generate_signals(symbol, stock_data, liquidity_trend, price_trend, technicals)
        
        # معالجة الإشارات
        self._process_signals(symbol, stock_data, signals, technicals)

    def _process_signals(self, symbol: str, stock_data: StockData, signals: Dict, technicals: Dict):
        """معالجة إشارات التداول"""
        if signals.get('entry_signal'):
            message = self._generate_alert_message(
                symbol, stock_data, 'ENTRY', 
                technicals['fair_value'], 
                technicals['rsi'],
                technicals['support'],
                technicals['resistance']
            )
            self.send_alert(message, CHANNEL_GENERAL)
            self._log_trade(symbol, stock_data, 'ENTRY')
            
        elif signals.get('boost_signal'):
            message = self._generate_alert_message(
                symbol, stock_data, 'BOOST',
                technicals['fair_value'],
                technicals['rsi']
            )
            self.send_alert(message, CHANNEL_MICROSCOPE)
            self._log_trade(symbol, stock_data, 'BOOST')
            
        elif signals.get('exit_signal'):
            message = self._generate_alert_message(
                symbol, stock_data, 'EXIT',
                technicals['fair_value']
            )
            self.send_alert(message, CHANNEL_MICROSCOPE)
            self._log_trade(symbol, stock_data, 'EXIT')
            self._remove_from_tracking(symbol)

    def run_continuous_scan(self, interval: int = 60):
        """تشغيل المسح المستمر"""
        logger.info("بدء تشغيل البوت في وضع المراقبة المستمرة...")
        while True:
            try:
                start_time = time.time()
                
                stocks = self.scan_us_market()
                for symbol in stocks:
                    self.analyze_stock(symbol)
                    time.sleep(0.5)  # تجنب rate limiting
                
                elapsed = time.time() - start_time
                sleep_time = max(interval - elapsed, 5)
                logger.info(f"اكتمل المسح. الانتظار لـ {sleep_time:.1f} ثانية...")
                time.sleep(sleep_time)
                
            except KeyboardInterrupt:
                logger.info("إيقاف البوت بواسطة المستخدم...")
                break
            except Exception as e:
                logger.error(f"خطأ غير متوقع: {str(e)}")
                time.sleep(30)

if __name__ == "__main__":
    bot = EnhancedLiquidityBot()
    bot.run_continuous_scan()
