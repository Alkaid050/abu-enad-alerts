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
FINNHUB_API_KEY = "248a6135d4cf4dd9aafa3417f115795e"
API_KEY_TWELVEDATA = "248a6135d4cf4dd9aafa3417f115795e"
TELEGRAM_BOT_TOKEN = "7413413899:AAG_3UpCE8TbV0RST6c9189Sip2B3k0MbW8"
CHANNEL_GENERAL = "@abu_enad_signals"
CHANNEL_MICROSCOPE = "@abu_enad_signals_2"

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
    symbol: str
    price: float
    volume: float
    change_percent: float
    market_cap: float = 0
    pe_ratio: float = 0

class LiquidityBot:
    def __init__(self):
        self.MAX_PRICE = MAX_STOCK_PRICE
        self.MIN_VOLUME = MIN_VOLUME_THRESHOLD
        self.VOLUME_INCREASE_THRESHOLD = VOLUME_INCREASE_THRESHOLD
        self.ENHANCEMENT_THRESHOLD = 1.25
        self.EXIT_WARNING_THRESHOLD = 0.85
        self.EXIT_FINAL_THRESHOLD = 0.75
        self.COOLDOWN_MINUTES = ALERT_COOLDOWN_MINUTES

        self.tracked_stocks: Dict[str, Dict] = {}
        self.last_alerts: Dict[str, datetime] = {}
        self.stock_peaks: Dict[str, float] = {}
        self.alerted_symbols: Set[str] = set()
        self.liquidity_history: Dict[str, List[float]] = defaultdict(list)
        self.price_history: Dict[str, List[float]] = defaultdict(list)

        self.FORBIDDEN_STOCKS = {
            'BAC', 'JPM', 'WFC', 'C', 'GS', 'MS',
            'BUD', 'TAP', 'STZ', 'DEO',
            'LVS', 'WYNN', 'MGM', 'CZR',
            'MO', 'PM', 'BTI'
        }

        self.csv_file = 'liquidity_alerts.csv'
        self._init_csv()

    def _init_csv(self):
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'التاريخ', 'الوقت', 'الرمز', 'السعر', 'التغير%', 'الحجم',
                    'نوع التنبيه', 'القيمة العادلة', 'RSI', 'الدعم', 'المقاومة',
                    'السعر المتوقع', 'السيولة القصوى', 'السيولة الحالية'
                ])

    def get_all_us_stocks_from_twelvedata(self) -> List[str]:
        try:
            logger.info("🔍 جاري جلب الأسهم من TwelveData...")
            url = "https://api.twelvedata.com/stocks"
            params = {
                'country': 'United States',
                'exchange': 'NASDAQ,NYSE,AMEX',
                'apikey': API_KEY_TWELVEDATA,
                'format': 'JSON',
                'page': 1
            }

            all_stocks = []
            while True:
                response = requests.get(url, params=params, timeout=30)
                if response.status_code != 200:
                    logger.error(f"❌ فشل الاتصال: {response.status_code}")
                    break

                data = response.json()
                stocks = data.get('data', [])
                if not stocks:
                    break

                for stock in stocks:
                    symbol = stock.get("symbol", "")
                    exchange = stock.get("exchange", "")
                    if (
                        exchange in ['NASDAQ', 'NYSE', 'AMEX']
                        and symbol
                        and '.' not in symbol
                        and len(symbol) <= 5
                        and symbol.isalpha()
                        and symbol not in self.FORBIDDEN_STOCKS
                    ):
                        all_stocks.append(symbol)

                if len(stocks) < 100:
                    break

                params['page'] += 1
                time.sleep(1)

            logger.info(f"✅ تم جلب {len(all_stocks)} رمز من السوق الأمريكي.")
            return all_stocks

        except Exception as e:
            logger.error(f"⚠️ استثناء أثناء جلب الأسهم: {e}")
            return []

    def run_scan(self):
        logger.info("🚦 بدء مسح السوق بالكامل...")
        all_stocks = self.get_all_us_stocks_from_twelvedata()
        if not all_stocks:
            logger.warning("❌ لا توجد أسهم للمعالجة.")
            return

        batch_size = 50
        total = len(all_stocks)

        for i in range(0, total, batch_size):
            batch = all_stocks[i:i + batch_size]
            for symbol in batch:
                try:
                    self.process_stock(symbol)
                    time.sleep(0.4)
                except Exception as e:
                    logger.error(f"⚠️ خطأ في {symbol}: {e}")
            logger.info(f"📦 معالجة {i + len(batch)} / {total}")
            time.sleep(8)

        logger.info("✅ تم الانتهاء من المسح الكامل.")
