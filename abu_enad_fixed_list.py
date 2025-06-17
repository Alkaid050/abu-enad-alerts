
#!/usr/bin/env python3

import requests
import time
import csv
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from collections import defaultdict

# إعداد نظام التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# مفاتيح API
TWELVEDATA_API_KEY = "248a6135d4cf4dd9aafa3417f115795e"
FINNHUB_API_KEY = "d16sfh9r01qkv5jd2be0d16sfh9r01qkv5jd2beg"
TELEGRAM_TOKEN = "7413413899:AAG_3UpCE8TbV0RST6c9189Sip2B3k0MbW8"
CHANNEL_GENERAL = "@abu_enad_signals"
CHANNEL_MICROSCOPE = "@abu_enad_signals_2"

MAX_STOCK_PRICE = 10.0
MIN_VOLUME = 50000

@dataclass
class Stock:
    symbol: str
    price: float
    volume: float
    change: float

class SimpleLiquidityBot:
    def __init__(self):
        self.tracked_stocks = {}
        self.alert_history = set()

    def fetch_stock_data(self, symbol: str) -> Optional[Stock]:
        try:
            endpoint = "https://api.twelvedata.com/quote"
            params = {
                'symbol': symbol,
                'apikey': TWELVEDATA_API_KEY,
                'interval': '15min'
            }

            response = requests.get(endpoint, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()

            if not data.get('price') or not data.get('volume'):
                return None

            price = float(data['price'])
            volume = float(data['volume'])

            if price > MAX_STOCK_PRICE or volume < MIN_VOLUME:
                return None

            return Stock(
                symbol=symbol,
                price=price,
                volume=volume,
                change=float(data.get('percent_change', 0))
            )

        except Exception as e:
            logger.error(f"خطأ في {symbol}: {str(e)}")
            return None

    def scan_market(self) -> List[str]:
        logger.info("🔍 استخدام قائمة ثابتة من الرموز...")
        return [
            "MLGO", "JFBR", "KNW", "TC", "SONM", "ZVSA",
            "BDRX", "PCSA", "ENTO", "BKYI", "GMBL", "CRKN",
            "TIVC", "SINT", "PHGE", "ADTX"
        ]

    def run(self):
        while True:
            symbols = self.scan_market()
            for symbol in symbols:
                stock = self.fetch_stock_data(symbol)
                if stock:
                    logger.info(f"✅ {symbol} | Price: {stock.price} | Volume: {stock.volume} | Change%: {stock.change}")
                time.sleep(1)

if __name__ == "__main__":
    bot = SimpleLiquidityBot()
    bot.run()
