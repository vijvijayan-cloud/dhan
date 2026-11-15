import os, time, threading, requests, csv, io
from flask import Flask, jsonify
from datetime import datetime as dt
from zoneinfo import ZoneInfo

app = Flask(__name__)

# ===== ENV =====
LIVE_TRADING = os.getenv("LIVE_TRADING", "true").lower() == "true"
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")
TRADE_9_20 = os.getenv("TRADE_9_20", "true").lower() == "true"
TRADE_10_15 = os.getenv("TRADE_10_15", "true").lower() == "true"
QTY = int(os.getenv("QUANTITY", "65"))
MAX_LOSS = float(os.getenv("MAX_LOSS_PER_TRADE", "2000"))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "9109393761")

IST = ZoneInfo("Asia/Kolkata")
DHAN_BASE = "https://api.dhan.co/v2"

state = {"trade_920_done": False, "trade_1015_done": False, "last_date": "", "dhan_status": "Not Checked", "last_msg": "", "open_trade": None, "half_booked": None}

# ===== TELEGRAM =====
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

# ===== DHAN CHECK =====
def check_dhan():
    try:
        r = requests.get(f"{DHAN_BASE}/funds", headers=dhan_headers(), timeout=10)
        if r.status_code == 200:
            state["dhan_status"] = "CONNECTED ✅ Funds OK"
            return True
        r2 = requests.get(f"{DHAN_BASE}/profile", headers=dhan_headers(), timeout=10)
        if r2.status_code == 200:
            state["dhan_status"] = "CONNECTED ✅ Profile OK"
            return True
        if r.status_code in [500, 400] and ("DH-1111" in r.text or "No holdings" in r.text or "HOLDING" in r.text):
            state["dhan_status"] = "CONNECTED ✅ Token OK - Holdings Empty (Normal)"
            return True
        state["dhan_status"] = f"ERROR {r.status_code} - {r.text[:200]}"
        return False
    except Exception as e:
        state["dhan_status"] = f"ERROR {e}"
        return False

# ===== NIFTY SPOT =====
def get_nifty_spot():
    try:
        payload = {"NSE_EQ": [13]}
        r = requests.post(f"{DHAN_BASE}/marketfeed/quote", headers=dhan_headers(), json=payload, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return float(data["data"]["NSE_EQ"]["13"]["last_price"])
    except Exception as e:
        print(f"Price Error: {e}", flush=True)
    return 25050.0

def get_option_ltp(security_id):
    try:
        payload = {"NSE_FNO": [int(security_id)]}
        r = requests.post(f"{DHAN_BASE}/marketfeed/quote", headers=dhan_headers(), json=payload, timeout=10)
        if r.status_code == 200:
            d = r.json()["data"]["NSE_FNO"][str(security_id)]
            return float(d["last_price"])
    except Exception as e:
        print(f"LTP Error: {e}", flush=True)
    return 0

# ===== SECURITY ID FINDER =====
def get_security_id(symbol_name, strike, option_type):
    try:
        r = requests.get("https://images.dhan.co/api-data/api-scrip-master.csv", timeout=20)
        if r.status_code != 200:
            return None
        reader = csv.DictReader(io.StringIO(r.text))
        for row in reader:
            try:
                vals = " ".join([str(v) for v in row.values()])
                if symbol_name in vals and str(strike) in vals and option_type in vals and "NSE" in vals:
                    for k, v in row.items():
                        if "SECURITY_ID" in k.upper() or "SMST" in k.upper():
                            return str(v)
            except:
                continue
    except Exception as e:
        print(f"SecurityID Error: {e}", flush=True)
    return None

# ===== PLACE ORDER - REAL DHAN =====
def place_order_dhan(security_id, side, qty, tag=""):
    if not LIVE_TRADING:
        send_telegram(f"🧪 PAPER - Skip: {side} SecId {security_id} Qty {qty}")
        return {"status": "PAPER"}
    if not security_id:
        send_telegram(f"❌ Order Fail - SecurityId Kedaikala - {tag}")
        return {"status": "NO_SECURITY_ID"}
    try:
        payload = {
            "dhanClientId": DHAN_CLIENT_ID,
            "transactionType": side,
            "exchangeSegment": "NSE_FNO",
            "productType": "INTRADAY",
            "orderType": "MARKET",
            "validity": "DAY",
            "securityId": str(security_id),
            "quantity": int(qty),
            "price": 0,
            "triggerPrice": 0,
            "afterMarketOrder": False,
            "boProfitValue": 0,
            "boStopLossValue": 0,
            "drvExpiryDate": None,
            "drvOptionType": None,
            "drvStrikePrice": None
        }
        print(f"ORDER: {payload}", flush=True)
        r = requests.post(f"{DHAN_BASE}/orders", headers=dhan_headers(), json=payload, timeout=15)
        print(f"ORDER RESP: {r.status_code} {r.text[:500]}", flush=True)
        if r.status_code in [200, 201]:
            send_telegram(f"✅ ORDER SUCCESS {tag}\nSecId: {security_id} Qty: {qty}\nResp: {r.text[:200]}")
            return r.json()
        else:
            # DH-905 = IP Problem - Ippo Clear-a Sollrom
            if "DH-905" in r.text or "Invalid IP" in r.text:
                send_telegram(f"❌ DH-905 Invalid IP - {tag}\nDhan la Static IP Delete Pannunga / Render IP Add Pannunga!\nRender IP Paakka: /my-ip Open Pannunga!")
            else:
                send_telegram(f"⚠️ ORDER REJECTED {tag}\nReason: {r.text[:300]}\nMarket Closed na Normal Thaan!")
            return {"status": "REJECTED", "resp": r.text}
    except Exception as e:
        send_telegram(f"❌ Order Error {tag}: {e}")
        return {"status": "ERROR", "error": str(e)}

# ===== TRAILING MONITOR - NO TIME LIMIT =====
def monitor_trailing(order_info, entry_price, tag):
    highest = entry_price
    sl_price = entry_price - (MAX_LOSS / QTY)
    send_telegram(f"👀 {tag} Trailing Started\nEntry: {entry_price} | SL: {round(sl_price,1)} | No Time Limit!")
    while True:
        try:
            time.sleep(20)
            ltp = get_option_ltp(order_info.get("security_id", 0))
            if ltp == 0:
                continue
            if ltp > highest:
                highest = ltp
                new_sl = highest - (MAX_LOSS / QTY * 0.5)
                if new_sl > sl_price:
                    sl_price = new_sl
                    send_telegram(f"🔒 {tag} Trail Up! High: {highest} New SL: {round(sl_price,1)} LTP: {ltp}")
            if ltp <= sl_price:
                send_telegram(f"🛑 {tag} SL HIT! Exit @ {ltp} | High Was {highest} | Loss/Profit Locked!")
                place_order_dhan(order_info.get("security_id"), "SELL", QTY, tag + " EXIT")
                state["open_trade"] = None
                break
            if ltp >= entry_price * 2 and state.get("half_booked") != tag:
                state["half_booked"] = tag
                send_telegram(f"💰 {tag} 2x Profit! LTP {ltp} - Trail Continue Pannrom!")
        except Exception as e:
            print(f"Monitor Error: {e}", flush=True)
            time.sleep(20)

def is_expiry_day():
    return dt.now(IST).weekday() == 3

# ===== TRADE 1 - 9:20 =====
def run_920_trade():
    send_telegram("🔥 9:20 LIVE TRADE START - No Time Limit - Trailing Only Exit!")
    spot = get_nifty_spot()
    atm = round(spot / 50) * 50
    symbol = f"NIFTY {atm} CE"
    sec_id = get_security_id("NIFTY", atm, "CE")
    send_telegram(f"9:20 Entry: {symbol} @ Spot {spot} Qty {QTY}\nSecId: {sec_id} | SL Rs.{MAX_LOSS} | Trail Thaan Exit!")
    res = place_order_dhan(sec_id, "BUY", QTY, "9:20 TRADE")
    state["trade_920_done"] = True
    if res.get("status") not in ["NO_SECURITY_ID", "ERROR", "REJECTED"]:
        state["open_trade"] = {"security_id": sec_id, "tag": "9:20"}
        entry = get_option_ltp(sec_id) if sec_id else 100
        if entry > 0:
            threading.Thread(target=monitor_trailing, args=({"security_id": sec_id}, entry, "9:20"), daemon=True).start()

# ===== TRADE 2 - 10:15 ITM2 =====
def run_1015_trade():
    instrument = "SENSEX" if is_expiry_day() else "NIFTY"
    send_telegram(f"🔥 10:15 LIVE TRADE START - {instrument} ITM2 - No Time Limit - Trailing Only!")
    spot = get_nifty_spot()
    itm_strike = (round(spot / 50) * 50) - 100
    symbol = f"{instrument} {itm_strike} CE"
    sec_id = get_security_id(instrument, itm_strike, "CE")
    send_telegram(f"10:15 Entry: {symbol} @ Spot {spot} Qty {QTY}\nSecId: {sec_id} | SL Rs.{MAX_LOSS} | Trail Thaan Exit!")
    res = place_order_dhan(sec_id, "BUY", QTY, "10:15 TRADE")
    state["trade_1015_done"] = True
    if res.get("status") not in ["NO_SECURITY_ID", "ERROR", "REJECTED"]:
        entry = get_option_ltp(sec_id) if sec_id else 100
        if entry > 0:
            threading.Thread(target=monitor_trailing, args=({"security_id": sec_id}, entry, "10:15"), daemon=True).start()

# ===== MAIN LOOP =====
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
                state["half_booked"] = None
            if now.weekday() < 5:
                if TRADE_9_20 and not state["trade_920_done"] and now.hour == 9 and now.minute >= 20 and now.minute < 21:
                    run_920_trade()
                if TRADE_10_15 and not state["trade_1015_done"] and now.hour == 10 and now.minute >= 15 and now.minute < 16:
                    run_1015_trade()
            time.sleep(20)
        except Exception as e:
            print(f"Loop Error: {e}", flush=True)
            time.sleep(20)

threading.Thread(target=trading_loop, daemon=True).start()

@app.route("/")
def home():
    return jsonify({"status": "BOTH LIVE BOT RUNNING", "dhan": state["dhan_status"], "live": LIVE_TRADING, "trade_920": state["trade_920_done"], "trade_1015": state["trade_1015_done"], "last_msg": state["last_msg"], "open_trade": state["open_trade"]})

@app.route("/api/prices")
def prices():
    return jsonify({"nifty": get_nifty_spot(), "time": dt.now(IST).strftime("%H:%M:%S")})

@app.route("/my-ip")
def my_ip():
    try:
        ip = requests.get("https://api.ipify.org", timeout=10).text
    except:
        ip = "unknown"
    return jsonify({"render_outbound_ip": ip, "copy_this_ip": ip, "note": "Idha Dhan Static IP la Add Pannunga, 0.0.0.0 Delete Pannunga"})

@app.route("/test-dhan")
def test_dhan():
    ok = check_dhan()
    send_telegram(f"🧪 TEST DHAN: {state['dhan_status']}")
    return jsonify({"dhan_connected": ok, "status": state["dhan_status"]})

@app.route("/test-order")
def test_order():
    send_telegram("🧪 TEST ORDER BUTTON Pressed!")
    spot = get_nifty_spot()
    atm = round(spot / 50) * 50
    sec_id = get_security_id("NIFTY", atm, "CE")
    res = place_order_dhan(sec_id, "BUY", QTY, "TEST ORDER")
    return jsonify({"test_order": res, "dhan": state["dhan_status"], "sec_id": sec_id, "note": "Sunday - Real Order Reject Aagum - Monday 9:20 Real Pogum - DH-905 Vandha IP Fix Pannanum"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
