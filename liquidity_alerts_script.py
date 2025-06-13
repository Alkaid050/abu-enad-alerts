
import requests
import time

API_KEY = "248a6135d4cf4dd9aafa3417f115795e"
SYMBOLS = ["AAPL", "MSFT", "GOOG"]  # عدل الرموز حسب الأسهم المطلوبة
INTERVAL = "1min"

def fetch_data(symbol):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={INTERVAL}&apikey={API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        if "values" in data:
            latest = data["values"][0]
            print(f"[{symbol}] Open: {latest['open']}, Close: {latest['close']}, Volume: {latest['volume']}")
        else:
            print(f"[{symbol}] Error: {data.get('message', 'No data')}")
    except Exception as e:
        print(f"[{symbol}] Exception: {str(e)}")

def main():
    for symbol in SYMBOLS:
        fetch_data(symbol)
    print("-" * 40)

if __name__ == "__main__":
    while True:
        main()
        time.sleep(60)
