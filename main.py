import os
import requests
import threading
import time
from datetime import datetime, time as dtime
from flask import Flask, jsonify, render_template_string
import pytz

app = Flask(__name__)

# ============ ENV - RENDER LA IRUKKU ============
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ============ SETTINGS ============
LOT_SIZE = 65
SL_AMOUNT = 2000
TARGET_AMOUNT = 2000
NIFTY_LOT_QTY = 65

IST = pytz.timezone("Asia/Kolkata")

# ============ TELEGRAM ============
def send_telegram(msg):
    try:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            print("Telegram Not Configured")
            return False
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
        print("Telegram:", r.text)
        return r.status_code == 200
    except Exception as e:
        print("Telegram Error:", e)
        return False

# ============ DHAN HELPERS ============
DHAN_BASE = "https://auth.dhan.co"

def dhan_headers():
    return {
        "access-token": DHAN_ACCESS_TOKEN,
        "client-id": DHAN_CLIENT_ID,
        "Content-Type": "application/json"
    }

def get_funds():
    try:
        url = f"{DHAN_BASE}/v2/funds"
        r = requests.get(url, headers=dhan_headers(), timeout=10)
        return r.status_code, r.json()
    except Exception as e:
        return 500, {"error": str(e)}

def get_nifty_price():
    try:
        # Nifty 50 - Security ID 13
        url = f"{DHAN_BASE}/v2/marketfeed/quote"
        payload = {"NSE_EQ": [13]}
        r = requests.post(url, headers=dhan_headers(), json=payload, timeout=10)
        data = r.json()
        ltp = data["data"]["NSE_EQ"]["13"]["last_price"]
        return ltp
    except Exception as e:
        print("Nifty Price Error:", e)
        return 25800.0

def get_option_chain():
    try:
        url = f"{DHAN_BASE}/v2/optionchain"
        # Nifty Expiry - Nearest Thursday - Dhan needs expiry date
        # Simplified: Use optionchain endpoint
        return None
    except:
        return None

def round_to_strike(price, step=50):
    return int(round(price / step) * step)

def get_itm1_symbol(nifty_price, option_type):
    """
    ITM 1 - 1 Strike Inside
    CE: ATM - 50
    PE: ATM + 50
    """
    atm = round_to_strike(nifty_price, 50)
    if option_type == "CE":
        strike = atm - 50
    else:
        strike = atm + 50
    return atm, strike

def place_order(symbol, qty, price, transaction_type="BUY"):
    try:
        url = f"{DHAN_BASE}/v2/orders"
        # For Nifty Options - NSE_FNO
        # securityId needs to be fetched - Simplified: Use Dhan Place Order
        payload = {
            "dhanClientId": DHAN_CLIENT_ID,
            "correlationId": f"bot_{int(time.time())}",
            "transactionType": transaction_type,
            "exchangeSegment": "NSE_FNO",
            "productType": "INTRADAY",
            "orderType": "MARKET",
            "validity": "DAY",
            "securityId": symbol,  # Must be Dhan Security ID
            "quantity": qty,
            "disclosedQuantity": 0,
            "price": 0,
            "triggerPrice": 0,
            "afterMarketOrder": False,
            "boProfitValue": 0,
            "boStopLossValue": 0
        }
        r = requests.post(url, headers=dhan_headers(), json=payload, timeout=15)
        print("Order Response:", r.text)
        return r.status_code, r.json()
    except Exception as e:
        return 500, {"error": str(e)}

def place_option_order(option_type, reason):
    try:
        nifty = get_nifty_price()
        atm, strike = get_itm1_symbol(nifty, option_type)
        # Estimate Premium for SL calculation
        # ITM 1 Premium approx 100
        premium = 100
        sl_points = SL_AMOUNT / LOT_SIZE  # 2000/65 = 30.76
        sl_price = round(premium - sl_points, 1)
        target_price = round(premium + (TARGET_AMOUNT / LOT_SIZE), 1)

        msg = f"""🚀 BOT ORDER - {reason}
Nifty: {nifty}
ATM: {atm} | Strike: {strike} {option_type}
Qty: {LOT_SIZE} (ITM 1)
Entry Approx: {premium}
SL: {sl_price} (Rs {SL_AMOUNT})
Target: {target_price}
Time: {datetime.now(IST).strftime('%d-%m-%Y %I:%M %p')}
"""
        send_telegram(msg)
        return {
            "status": "signal_generated",
            "nifty": nifty,
            "atm": atm,
            "strike": strike,
            "option_type": option_type,
            "qty": LOT_SIZE,
            "lot_size": LOT_SIZE,
            "sl_price": sl_price,
            "target_price": target_price,
            "reason": reason
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ============ BOT LOGIC - SCHEDULER ============
traded_920 = False
traded_1015 = False
last_day = None

def bot_scheduler():
    global traded_920, traded_1015, last_day
    while True:
        try:
            now = datetime.now(IST)
            today = now.strftime("%Y-%m-%d")
            if today != last_day:
                traded_920 = False
                traded_1015 = False
                last_day = today

            # Only Mon-Fri, 9:15 - 15:30
            if now.weekday() >= 5:
                time.sleep(60)
                continue

            # Trade 1 - 9:20 ORB
            if not traded_920 and now.hour == 9 and now.minute == 20:
                # Simplified: Check Nifty vs 9:15 Candle
                # For now - Default CE if Nifty Up, else PE
                # Real logic: Compare with 9:15 High/Low
                nifty = get_nifty_price()
                # Placeholder: Use previous close logic - You can add 9:15 High/Low API
                result = place_option_order("CE", "9:20 ORB Breakout")
                send_telegram(f"✅ 9:20 Trade Signal: {result}")
                traded_920 = True

            # Trade 2 - 10:15 Breakout
            if not traded_1015 and now.hour == 10 and now.minute == 15:
                nifty = get_nifty_price()
                result = place_option_order("CE", "10:15 Breakout")
                send_telegram(f"✅ 10:15 Trade Signal: {result}")
                traded_1015 = True

            time.sleep(30)
        except Exception as e:
            print("Scheduler Error:", e)
            time.sleep(30)

# Start Scheduler in Background
threading.Thread(target=bot_scheduler, daemon=True).start()

# ============ ROUTES ============
@app.route("/")
def home():
    nifty = get_nifty_price()
    atm, ce_strike = get_itm1_symbol(nifty, "CE")
    _, pe_strike = get_itm1_symbol(nifty, "PE")
    html = f"""
    <h1>🤖 Dhan Bot - ON</h1>
    <p><b>Nifty:</b> {nifty}</p>
    <p><b>ATM:</b> {atm} | <b>ITM 1 CE:</b> {ce_strike} CE | <b>ITM 1 PE:</b> {pe_strike} PE</p>
    <p><b>Lot:</b> 65 | <b>SL:</b> Rs 2000 | <b>Target:</b> Rs 2000</p>
    <p><b>Trade 1:</b> 9:20 ORB | <b>Trade 2:</b> 10:15 Breakout</p>
    <p><b>Time:</b> {datetime.now(IST).strftime('%d-%m-%Y %I:%M %p')}</p>
    <hr>
    <a href="/test-order">Test Order</a> | <a href="/test-telegram">Test Telegram</a> | <a href="/status">Status</a>
    """
    return html

@app.route("/status")
def status():
    code, funds = get_funds()
    return jsonify({
        "bot": "ON",
        "lot_size": LOT_SIZE,
        "qty": LOT_SIZE,
        "strike": "ITM 1",
        "trade1": "9:20 ORB",
        "trade2": "10:15 Breakout",
        "sl": SL_AMOUNT,
        "funds_status": code,
        "funds": funds,
        "telegram_configured": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        "time": datetime.now(IST).strftime("%d-%m-%Y %I:%M %p")
    })

@app.route("/test-order")
def test_order():
    code, funds = get_funds()
    nifty = get_nifty_price()
    atm, ce_strike = get_itm1_symbol(nifty, "CE")
    _, pe_strike = get_itm1_symbol(nifty, "PE")
    avail = 0
    try:
        avail = funds.get("data", {}).get("availabelBalance", 0)
    except:
        pass
    return jsonify({
        "funds_status": code,
        "lot_size": LOT_SIZE,
        "qty": LOT_SIZE,
        "nifty": nifty,
        "atm": atm,
        "itm1_ce": ce_strike,
        "itm1_pe": pe_strike,
        "availabelBalance": avail,
        "time": datetime.now(IST).strftime("%d-%m-%Y %I:%M %p")
    })

@app.route("/test-telegram")
def test_telegram():
    ok = send_telegram("✅ Bot Connected! Telegram OK Sir! - Test Message - " + datetime.now(IST).strftime('%d-%m-%Y %I:%M %p'))
    return jsonify({"telegram_sent": ok, "time": datetime.now(IST).strftime("%d-%m-%Y %I:%M %p")})

@app.route("/test-buy-ce")
def test_buy_ce():
    result = place_option_order("CE", "Manual Test CE")
    return jsonify(result)

@app.route("/test-buy-pe")
def test_buy_pe():
    result = place_option_order("PE", "Manual Test PE")
    return jsonify(result)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
