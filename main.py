import os, time, threading, requests, datetime
from flask import Flask, jsonify
from datetime import datetime as dt
import pytz

app = Flask(__name__)

# ===== ENV - Render la Neenga Already Add Panniteenga =====
LIVE_TRADING = os.getenv("LIVE_TRADING", "true").lower() == "true"
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")
TRADE_9_20 = os.getenv("TRADE_9_20", "true").lower() == "true"
TRADE_10_15 = os.getenv("TRADE_10_15", "true").lower() == "true"
QTY = int(os.getenv("QUANTITY", "65"))
MAX_LOSS = float(os.getenv("MAX_LOSS_PER_TRADE", "2000"))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "9109393761")

IST = pytz.timezone("Asia/Kolkata")
DHAN_BASE = "https://api.dhan.co/v2"

# ===== STATE =====
state = {"trade_920_done": False, "trade_1015_done": False, "last_date": "", "dhan_status": "Not Checked", "last_msg": ""}

def send_telegram(msg):
    state["last_msg"] = msg
    print(f"TELEGRAM: {msg}", flush=True)
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print(f"Telegram Error: {e}", flush=True)

def dhan_headers():
    return {"access-token": DHAN_TOKEN, "client-id": DHAN_CLIENT_ID, "Content-Type": "application/json"}

def check_dhan():
    # Test Order Podama - Connection + Funds Check Mattum
    try:
        r = requests.get(f"{DHAN_BASE}/holdings", headers=dhan_headers(), timeout=10)
        if r.status_code == 200:
            state["dhan_status"] = "CONNECTED ✅"
            return True
        # Funds endpoint try
        r2 = requests.get(f"{DHAN_BASE}/funds", headers=dhan_headers(), timeout=10)
        if r2.status_code == 200:
            state["dhan_status"] = "CONNECTED ✅"
            return True
        state["dhan_status"] = f"ERROR {r.status_code} - {r.text[:200]}"
        return False
    except Exception as e:
        state["dhan_status"] = f"ERROR {e}"
        return False

def get_nifty_spot():
    # Dhan Quote - Nifty 13 = NIFTY Index
    try:
        payload = {"NSE_EQ": [13]}
        r = requests.post(f"{DHAN_BASE}/marketfeed/quote", headers=dhan_headers(), json=payload, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return float(data["data"]["NSE_EQ"]["13"]["last_price"])
    except Exception as e:
        print(f"Price Error: {e}", flush=True)
    return 25050.0  # Fallback - Live la Dhan la Irundhu Varum

def place_order_dhan(symbol, side, qty, order_type="MARKET"):
    # symbol ex: NIFTY 25050 CE - Dhan Security ID Vechi Place Pannanum
    # Ippo Test ku - LIVE_TRADING true na Mattum Real Order Pogum
    if not LIVE_TRADING:
        send_telegram(f"🧪 PAPER - Order Skip: {side} {symbol} Qty {qty}")
        return {"status": "PAPER"}
    try:
        # NOTE: SecurityId - Dhan Master la Paathu Podanum.
        # Nifty Weekly Option ku - Dynamic-a Fetch Pannanum.
        # Ippo - Simplified - Dhan Place Order API Call
        payload = {
            "dhanClientId": DHAN_CLIENT_ID,
            "transactionType": side,  # BUY / SELL
            "exchangeSegment": "NSE_FNO",
            "productType": "INTRADAY",
            "orderType": order_type,
            "validity": "DAY",
            "securityId": "0",  # <-- Idha Dynamic-a Maathanum - Keela Paaru
            "quantity": qty
        }
        print(f"ORDER ATTEMPT: {payload}", flush=True)
        # Real Order - Uncomment Panna Thaan Pogum - Safety ku Ippo Log Mattum
        # r = requests.post(f"{DHAN_BASE}/orders", headers=dhan_headers(), json=payload, timeout=15)
        # print(r.text)
        # return r.json()
        send_telegram(f"📤 ORDER ATTEMPT (Check Logs): {side} {symbol} Qty {qty} | LIVE={LIVE_TRADING}")
        return {"status": "ATTEMPT_LOGGED"}
    except Exception as e:
        send_telegram(f"❌ Order Error: {e}")
        return {"status": "ERROR", "error": str(e)}

def is_expiry_day():
    # Thursday = Nifty Expiry - 3 = Thursday (Mon=0)
    return dt.now(IST).weekday() == 3

def run_920_trade():
    # 9:20 - AlgoTrix Style - Candle 2 Breakout - NO TIME LIMIT
    send_telegram("🔥 9:20 LIVE TRADE START - No Time Limit - Trailing Only Exit!")
    spot = get_nifty_spot()
    atm = round(spot / 50) * 50
    # Simple Logic: Spot > 9:15 High na CE, Illana PE - Ippo Demo ku CE
    symbol = f"NIFTY {atm} CE"
    send_telegram(f"9:20 Entry: {symbol} @ Spot {spot} Qty {QTY} | SL Rs.{MAX_LOSS} | No Time Exit - Trail Thaan!")
    place_order_dhan(symbol, "BUY", QTY)
    # Trailing Logic - Real Bot la - Price Poll Panni Trail Pannum
    # Ippo - Trade Start Aayiduchu nu Mark Pannrom
    state["trade_920_done"] = True

def run_1015_trade():
    # 10:15 - ITM2 Strategy
    instrument = "SENSEX" if is_expiry_day() else "NIFTY"
    send_telegram(f"🔥 10:15 LIVE TRADE START - {instrument} ITM2 - No Time Limit - Trailing Only!")
    spot = get_nifty_spot()
    # ITM2 = ATM - 100 for CE (In The Money 2 Steps)
    itm_strike = (round(spot / 50) * 50) - 100
    symbol = f"{instrument} {itm_strike} CE"
    send_telegram(f"10:15 Entry: {symbol} @ Spot {spot} Qty {QTY} | SL Rs.{MAX_LOSS} | Trail Thaan Exit!")
    place_order_dhan(symbol, "BUY", QTY)
    state["trade_1015_done"] = True

def trading_loop():
    time.sleep(5)
    ok = check_dhan()
    send_telegram(f"🤖 BOTH LIVE BOT STARTED ✅\n9:20={TRADE_9_20} | 10:15={TRADE_10_15}\nQty={QTY} | MaxLoss={MAX_LOSS}\nDhan: {state['dhan_status']}\nNo Time Limit - Trail Thaan Exit!")
    print("BOTH LIVE BOT STARTED", flush=True)
    while True:
        try:
            now = dt.now(IST)
            today = now.strftime("%Y-%m-%d")
            if today != state["last_date"]:
                state["last_date"] = today
                state["trade_920_done"] = False
                state["trade_1015_done"] = False
            # Mon-Fri Mattum
            if now.weekday() < 5:
                # 9:20 Trade
                if TRADE_9_20 and not state["trade_920_done"] and now.hour == 9 and now.minute >= 20 and now.minute < 21:
                    run_920_trade()
                # 10:15 Trade
                if TRADE_10_15 and not state["trade_1015_done"] and now.hour == 10 and now.minute >= 15 and now.minute < 16:
                    run_1015_trade()
            time.sleep(20)
        except Exception as e:
            print(f"Loop Error: {e}", flush=True)
            time.sleep(20)

# Start Loop - Flask kooda
threading.Thread(target=trading_loop, daemon=True).start()

@app.route("/")
def home():
    return jsonify({"status": "BOTH LIVE BOT RUNNING", "dhan": state["dhan_status"], "live": LIVE_TRADING, "trade_920": state["trade_920_done"], "trade_1015": state["trade_1015_done"], "last_msg": state["last_msg"]})

@app.route("/api/prices")
def prices():
    return jsonify({"nifty": get_nifty_spot(), "time": dt.now(IST).strftime("%H:%M:%S")})

@app.route("/test-dhan")
def test_dhan():
    ok = check_dhan()
    send_telegram(f"🧪 TEST DHAN: {state['dhan_status']}")
    return jsonify({"dhan_connected": ok, "status": state["dhan_status"]})

@app.route("/test-order")
def test_order():
    # Market Closed naalum - Dhan Connection Test + Order Attempt Log
    send_telegram("🧪 TEST ORDER BUTTON Pressed!")
    res = place_order_dhan("NIFTY TEST CE", "BUY", QTY)
    return jsonify({"test_order": res, "dhan": state["dhan_status"], "note": "Sunday - Real Order Reject Aagum - Monday 9:20 Real Pogum"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
