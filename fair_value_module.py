
import requests
import os

# بيانات البيئة
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

def get_fair_value(symbol):
    url = f"https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={FINNHUB_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        cash = data.get("cash", 0)
        debt = data.get("debt", 0)
        shares_outstanding = data.get("shareOutstanding", 1)
        fair_value = round((cash - debt) / shares_outstanding, 2)
        return fair_value
    return None

# مثال على الاستخدام داخل تنبيه
symbol = "JFBR"
fair_value = get_fair_value(symbol)
if fair_value:
    print(f"🟡 القيمة العادلة لسهم {symbol}: {fair_value} دولار")
else:
    print(f"⚠️ لم يتم العثور على بيانات القيمة العادلة لسهم {symbol}")
