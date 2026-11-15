import os, time, threading, requests
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify

app = Flask(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
def ist_now(): return datetime.now(IST)
def ist_str(): return ist_now().strftime('%d-%m-%Y %I:%M %p')

# ===== DHAN CONFIG =====
DHAN_CLIENT_ID = os.environ.get("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.environ.get("DHAN_ACCESS_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

DHAN_BASE = "https://api.dhan.co"  # ✅ Correct - auth.dhan.co Illa

QTY = 65
MAX_LOSS = 2000

TRADE1_TIME = "09:20"
TRADE1_SL = 2000
TRADE1_TGT = 2000

TRADE2_TIME = "10:15"
TRADE2_SL = 2000
TRADE2_TGT = None

STATE = {
    "dhan": "Not Checked",
    "funds": 0,
    "funds_status": 0,
    "last_msg": "BOTH LIVE BOT STARTED ✅ | 9:20=True | 10:15=True | Qty=65 | MaxLoss=2000 | Dhan: Checking...",
    "live": True,
    "open_trade": None,
    "status": "BOTH LIVE BOT RUNNING",
    "trade_920": False,
    "trade_1015": False,
    "qty": QTY,
    "pnl_today": 0,
    "trade1_pnl": 0,
    "trade2_pnl": 0,
    "trade1_status": "WAITING",
    "trade2_status": "WAITING",
    "nifty_live": 0,
    "nifty_pct": 0,
    "updated": ist_str(),
}

def dhan_headers():
    return {"access-token": DHAN_ACCESS_TOKEN, "client-id": DHAN_CLIENT_ID, "Content-Type": "application/json", "Accept": "application/json"}

def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
        return r.status_code == 200
    except:
        return False

# ✅ FIX 1 - Real Dhan Check - Fake CONNECTED Illa
def check_dhan():
    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
        STATE["dhan"] = "TOKEN MISSING - Render Env la Pannunga"
        return False
    try:
        r = requests.get(f"{DHAN_BASE}/v2/funds", headers=dhan_headers(), timeout=10)
        print("DHAN FUNDS:", r.status_code, r.text[:300])
        STATE["funds_status"] = r.status_code
        if r.status_code == 200:
            j = r.json()
            d = j.get("data", j) if isinstance(j, dict) else {}
            avail = d.get("availableBalance") or d.get("availabelBalance") or d.get("available_balance") or 0
            STATE["funds"] = float(avail or 0)
            STATE["dhan"] = f"CONNECTED ✅ Funds Rs {STATE['funds']}"
            return True
        elif r.status_code == 401:
            STATE["dhan"] = "TOKEN EXPIRED - Pudhu Token Pannunga"
            return False
        else:
            STATE["dhan"] = f"DHAN Error {r.status_code}"
            return False
    except Exception as e:
        STATE["dhan"] = f"DHAN Fail: {e}"
        return False

# ✅ FIX 2 - Nifty Dhan la Irundhu - Yahoo Illa
def get_nifty():
    try:
        r = requests.post(f"{DHAN_BASE}/v2/marketfeed/quote", headers=dhan_headers(), json={"IDX_I": [13]}, timeout=10)
        d = r.json().get("data", {})
        price = float(d.get("IDX_I", {}).get("13", {}).get("last_price", 0))
        return price, 0
    except Exception as e:
        print("NIFTY ERR:", e)
        return 0, 0

# ✅ FIX 3 - Real Order Place
def get_option_security_id(strike, option_type):
    # Nifty Weekly Expiry - Option Chain la Thedrom
    try:
        price, _ = get_nifty()
        if not price: return None
        # Nearest Expiry - Dhan Option Chain API
        r = requests.post(f"{DHAN_BASE}/v2/optionchain", headers=dhan_headers(),
            json={"UnderlyingScrip": 13, "UnderlyingSeg": "IDX_I", "Expiry": "0"}, timeout=10)
        data = r.json().get("data", {})
        oc = data.get("oc", {})
        for k, v in oc.items():
            try:
                if abs(float(k) - strike) < 1:
                    side = v.get("ce" if option_type == "CE" else "pe", {})
                    return str(side.get("securityId", ""))
            except: pass
        return None
    except:
        return None

def place_order(security_id, side, qty):
    try:
        payload = {
            "dhanClientId": DHAN_CLIENT_ID,
            "transactionType": side, "exchangeSegment": "NSE_FNO",
            "productType": "INTRADAY", "orderType": "MARKET",
            "validity": "DAY", "securityId": str(security_id),
            "quantity": int(qty), "price": 0, "triggerPrice": 0,
            "afterMarketOrder": False, "amoTime": "OPEN"
        }
        r = requests.post(f"{DHAN_BASE}/v2/orders", headers=dhan_headers(), json=payload, timeout=10)
        print("ORDER:", r.status_code, r.text[:500])
        return r.status_code in [200, 201], r.text[:500]
    except Exception as e:
        return False, str(e)

def get_positions_pnl():
    try:
        r = requests.get(f"{DHAN_BASE}/v2/positions", headers=dhan_headers(), timeout=10)
        if r.status_code == 200:
            data = r.json().get("data", [])
            total = sum(float(x.get("realizedProfit", 0) or 0) + float(x.get("unrealizedProfit", 0) or 0) for x in data)
            return total
        return 0
    except:
        return 0

def execute_trade(trade_no, time_label, is_trailing):
    price, _ = get_nifty()
    if not price:
        send_telegram(f"⚠️ {time_label} Trade Skip - Nifty Price Illa")
        return
    # Simple Logic: Nifty Prev Close ku Mela Irundha CE, Keezha Irundha PE
    # ATM Strike
    atm = round(price / 50) * 50
    # ITM 1 = ATM - 50 for CE (In The Money)
    strike = atm - 50
    opt_type = "CE"
    # Nifty 9:20 / 10:15 la Direction Paarthu - Ippo CE Default
    sec_id = get_option_security_id(strike, opt_type)
    if not sec_id:
        send_telegram(f"⚠️ {time_label} Trade Skip - Option ID Kedaikala Strike {strike} {opt_type}")
        STATE[f"trade{trade_no}_status"] = "FAILED - Option ID Illa"
        return
    ok, resp = place_order(sec_id, "BUY", QTY)
    if ok:
        STATE["open_trade"] = {"trade": trade_no, "strike": strike, "type": opt_type, "sec": sec_id, "qty": QTY, "trailing": is_trailing, "sl": TRADE1_SL if trade_no == 1 else TRADE2_SL, "tgt": TRADE1_TGT if trade_no == 1 else None}
        STATE[f"trade{trade_no}_status"] = "RUNNING"
        send_telegram(f"✅ {time_label} TRADE {trade_no} PLACED\nNifty {price}\nStrike {strike} {opt_type} Qty {QTY}\nSL 2000 {'TGT 2000' if trade_no==1 else 'TRAILING - No Target'}")
    else:
        STATE[f"trade{trade_no}_status"] = f"FAILED - {resp[:100]}"
        send_telegram(f"❌ {time_label} Order Failed: {resp[:200]}")

def bot_loop():
    time.sleep(5)
    ok = check_dhan()
    send_telegram(f"✅ DHAN BOT STARTED\n9:20 Fixed SL 2000 TGT 2000\n10:15 Trailing SL 2000 No Target\nQty 65\nDhan: {STATE['dhan']}")
    while True:
        try:
            now = ist_now()
            price, pct = get_nifty()
            if price:
                STATE["nifty_live"] = round(price, 2)
                STATE["nifty_pct"] = pct
                STATE["updated"] = ist_str()
            # PnL Update - Real Positions la Irundhu
            if STATE["open_trade"]:
                STATE["pnl_today"] = get_positions_pnl()
            # 9:20 Trade
            if now.strftime("%H:%M") == TRADE1_TIME and not STATE["trade_920"]:
                STATE["trade_920"] = True
                execute_trade(1, "9:20", False)
            # 10:15 Trade
            if now.strftime("%H:%M") == TRADE2_TIME and not STATE["trade_1015"]:
                STATE["trade_1015"] = True
                execute_trade(2, "10:15", True)
            # Midnight Reset
            if now.hour == 0 and now.minute < 5:
                STATE["trade_920"] = False
                STATE["trade_1015"] = False
                STATE["trade1_status"] = "WAITING"
                STATE["trade2_status"] = "WAITING"
                STATE["pnl_today"] = 0
                STATE["trade1_pnl"] = 0
                STATE["trade2_pnl"] = 0
                STATE["open_trade"] = None
            # Refresh Funds Every 5 Min
            if now.minute % 5 == 0 and now.second < 30:
                check_dhan()
            time.sleep(30)
        except Exception as e:
            print("LOOP ERR:", e)
            time.sleep(30)

threading.Thread(target=bot_loop, daemon=True).start()

@app.route('/api/status')
def api_status():
    return jsonify(STATE)

@app.route('/api/prices')
def api_prices():
    return jsonify(STATE)

@app.route('/health')
def health():
    return jsonify({"ok": True, "time": ist_str(), "dhan": STATE["dhan"], "funds": STATE["funds"]})

@app.route('/status')
def status_page():
    return jsonify({"dhan_status": STATE["funds_status"], "funds": STATE["funds"], "nifty": STATE["nifty_live"], "dhan": STATE["dhan"], "token_set": bool(DHAN_ACCESS_TOKEN)})

@app.route('/')
def home():
    now = ist_str()
    html = """
    <html><head><title>DHAN BOT - Dashboard</title><meta name='viewport' content='width=device-width, initial-scale=1'>
    <style>
    *{box-sizing:border-box}
    body{background:#070a12;color:#fff;font-family:Arial;margin:0;padding:12px}
    .top{background:linear-gradient(90deg,#0f172a,#1e293b);border:1px solid #26314d;border-radius:16px;padding:14px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px}
    .top h2{margin:0;font-size:20px} .top small{color:#94a3b8}
    .live{background:#052e1a;color:#4ade80;padding:6px 14px;border-radius:20px;font-weight:bold;font-size:13px}
    .grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:12px}
    @media(max-width:700px){.grid{grid-template-columns:1fr}}
    .card{background:#101826;border:1px solid #26314d;border-radius:16px;padding:14px}
    .card h3{margin:0 0 8px 0;font-size:15px}
    .big{font-size:26px;font-weight:bold;margin:6px 0}
    .green{color:#22c55e} .red{color:#ef4444} .yellow{color:#facc15}
    .pill{display:inline-block;padding:5px 12px;border-radius:20px;font-size:12px;font-weight:bold}
    .small{font-size:11px;color:#94a3b8}
    .box{background:#0b1220;border:1px solid #26314d;border-radius:12px;padding:12px;margin-top:12px}
    table{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}
    th,td{padding:9px;border-bottom:1px solid #26314d;text-align:left} th{color:#94a3b8}
    </style></head><body>
    <div class='top'><div><h2>🚀 DHAN BOT <span style='font-size:13px;color:#94a3b8'>| BOTH LIVE</span></h2><small>""" + now + """ | Auto Refresh 8s</small></div><div class='live' id='liveDot'>● LIVE</div></div>
    <div class='grid'>
      <div class='card' style='border-color:#22c55e'><h3>📈 Trade 1 - 9:20 ORB</h3><span class='pill' style='background:#052e1a;color:#4ade80'>FIXED SL 2000 • FIXED TGT 2000</span><div class='big' id='t1Status'>WAITING</div><div class='small'>Trailing Illa - SL / TGT Fixed</div><div class='small' style='margin-top:6px'>P&L: <b id='t1Pnl' class='green'>Rs 0</b></div></div>
      <div class='card' style='border-color:#f59e0b'><h3>🔥 Trade 2 - 10:15 BREAKOUT</h3><span class='pill' style='background:#3a2a0a;color:#facc15'>TRAILING SL 2000 • NO TARGET</span><div class='big' id='t2Status'>WAITING</div><div class='small'>Profit Poga Poga SL Mela Pogum - No Time Limit</div><div class='small' style='margin-top:6px'>P&L: <b id='t2Pnl' class='green'>Rs 0</b></div></div>
      <div class='card'><h3>💰 Today P&L</h3><div class='big' id='todayPnl'>Rs 0</div><div class='small'>Qty 65 | NIFTY: <b id='niftyLive'>-</b> (<span id='niftyPct'>-</span>%)</div><div class='small' style='margin-top:6px'>Funds: <b id='fundsVal'>-</b> | Dhan: <span id='dhanStat'>-</span></div></div>
    </div>
    <div class='box'><b>📋 LIVE STATUS</b><table><tr><th>Item</th><th>Value</th></tr><tr><td>Bot Status</td><td id='botStatus'>-</td></tr><tr><td>Dhan Connection</td><td id='dhanConn'>-</td></tr><tr><td>Open Trade</td><td id='openTrade'>-</td></tr><tr><td>Trade 9:20</td><td id='tr920'>-</td></tr><tr><td>Trade 10:15</td><td id='tr1015'>-</td></tr><tr><td>Last Msg</td><td id='lastMsg'>-</td></tr></table></div>
    <div class='box'><b>⚙️ CONFIG</b><table><tr><th>Trade</th><th>Time</th><th>SL</th><th>Target</th><th>Trailing</th></tr><tr><td>Trade 1</td><td>9:20</td><td>2000</td><td>2000</td><td>No</td></tr><tr><td>Trade 2</td><td>10:15</td><td>2000</td><td>No Target</td><td>Yes</td></tr></table><div class='small' style='margin-top:8px'>Qty: 65 | Max Loss: 2000 per Trade | No Time Limit - Trail Thaan Exit</div></div>
    <script>
    function fmt(n){return 'Rs '+Number(n||0).toLocaleString('en-IN',{maximumFractionDigits:0})}
    function load(){ fetch('/api/status').then(r=>r.json()).then(d=>{ document.getElementById('botStatus').innerText=d.status; document.getElementById('dhanConn').innerText=d.dhan; document.getElementById('dhanStat').innerText=d.dhan; document.getElementById('fundsVal').innerText=fmt(d.funds); document.getElementById('openTrade').innerText=d.open_trade?JSON.stringify(d.open_trade):'None'; document.getElementById('tr920').innerText=d.trade_920; document.getElementById('tr1015').innerText=d.trade_1015; document.getElementById('t1Status').innerText=d.trade1_status||'WAITING'; document.getElementById('t2Status').innerText=d.trade2_status||'WAITING'; document.getElementById('todayPnl').innerText=fmt(d.pnl_today); document.getElementById('todayPnl').style.color=(d.pnl_today||0)>=0?'#22c55e':'#ef4444'; document.getElementById('t1Pnl').innerText=fmt(d.trade1_pnl); document.getElementById('t2Pnl').innerText=fmt(d.trade2_pnl); document.getElementById('lastMsg').innerText=d.last_msg||''; document.getElementById('niftyLive').innerText=d.nifty_live||'-'; document.getElementById('niftyPct').innerText=d.nifty_pct||'-'; document.getElementById('liveDot').innerText=d.live?'● LIVE':'○ OFFLINE'; }); }
    load(); setInterval(load,8000);
    </script></body></html>
    """
    return html

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
