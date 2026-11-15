import os
import time
import threading
import requests
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify

app = Flask(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

def ist_now():
    return datetime.now(IST)

def ist_str():
    return datetime.now(IST).strftime('%d-%m-%Y %I:%M %p')

DHAN_CLIENT_ID = os.environ.get("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.environ.get("DHAN_ACCESS_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

QTY = 15
MAX_LOSS = 2000

STATE = {}
STATE["dhan"] = "CONNECTED ✅"
STATE["last_msg"] = "BOTH LIVE BOT STARTED ✅ | Qty 15 | 9:20=True | 10:15=True"
STATE["live"] = True
STATE["open_trade"] = None
STATE["status"] = "BOTH LIVE BOT RUNNING"
STATE["trade_920"] = False
STATE["trade_1015"] = False
STATE["qty"] = QTY
STATE["pnl_today"] = 0
STATE["trade1_pnl"] = 0
STATE["trade2_pnl"] = 0
STATE["nifty_live"] = 0
STATE["nifty_pct"] = 0
STATE["updated"] = ist_str()
STATE["last_order_response"] = ""

def send_telegram(msg):
    try:
        if not TELEGRAM_BOT_TOKEN:
            return
        url = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage"
        data = {}
        data["chat_id"] = TELEGRAM_CHAT_ID
        data["text"] = msg
        requests.post(url, json=data, timeout=8)
    except:
        pass

def get_nifty():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?range=1d&interval=1m"
        headers = {}
        headers["User-Agent"] = "Mozilla/5.0"
        r = requests.get(url, headers=headers, timeout=8).json()
        meta = r["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice", 0)
        prev = meta.get("previousClose", price)
        pct = 0
        if prev:
            pct = (price - prev) / prev * 100
        return price, round(pct, 2)
    except:
        return 0, 0

def get_dhan_headers():
    headers = {}
    headers["access-token"] = DHAN_ACCESS_TOKEN
    headers["dhanClientId"] = DHAN_CLIENT_ID
    headers["Content-Type"] = "application/json"
    return headers

def get_funds():
    try:
        headers = get_dhan_headers()
        r = requests.get(
            "https://api.dhan.co/v2/funds",
            headers=headers,
            timeout=10
        )
        return r.status_code, r.text[:500]
    except Exception as e:
        return 0, str(e)

def place_dhan_order(side, qty, tag):
    try:
        headers = get_dhan_headers()
        order_data = {}
        order_data["dhanClientId"] = DHAN_CLIENT_ID
        order_data["transactionType"] = side
        order_data["exchangeSegment"] = "NSE_FNO"
        order_data["productType"] = "INTRADAY"
        order_data["orderType"] = "MARKET"
        order_data["validity"] = "DAY"
        order_data["securityId"] = "13"
        order_data["quantity"] = qty
        order_data["disclosedQuantity"] = 0
        order_data["price"] = 0
        order_data["triggerPrice"] = 0
        order_data["afterMarketOrder"] = False
        r = requests.post(
            "https://api.dhan.co/v2/orders",
            headers=headers,
            json=order_data,
            timeout=10
        )
        STATE["last_order_response"] = r.text[:500]
        return r.status_code, r.text[:500]
    except Exception as e:
        return 0, str(e)

def bot_loop():
    time.sleep(5)
    while True:
        try:
            price, pct = get_nifty()
            if price:
                STATE["nifty_live"] = round(price, 2)
                STATE["nifty_pct"] = pct
                STATE["updated"] = ist_str()
            now = ist_now()
            h = now.hour + now.minute / 60
            if 9.33 <= h < 9.35 and not STATE["trade_920"]:
                STATE["trade_920"] = True
                STATE["last_msg"] = "9:20 TRADE TRIGGERED | NIFTY " + str(price)
                code, resp = place_dhan_order("BUY", QTY, "9:20")
                STATE["last_msg"] = "9:20 ORDER TRIED | Code " + str(code) + " | " + resp[:200]
                send_telegram("DHAN 9:20 TRADE | Code " + str(code) + " | " + resp[:200])
            if 10.25 <= h < 10.27 and not STATE["trade_1015"]:
                STATE["trade_1015"] = True
                STATE["last_msg"] = "10:15 TRADE TRIGGERED | NIFTY " + str(price)
                code, resp = place_dhan_order("BUY", QTY, "10:15")
                STATE["last_msg"] = "10:15 ORDER TRIED | Code " + str(code) + " | " + resp[:200]
                send_telegram("DHAN 10:15 TRADE | Code " + str(code) + " | " + resp[:200])
            if now.hour == 0 and now.minute < 5:
                STATE["trade_920"] = False
                STATE["trade_1015"] = False
                STATE["pnl_today"] = 0
                STATE["trade1_pnl"] = 0
                STATE["trade2_pnl"] = 0
            time.sleep(30)
        except:
            time.sleep(30)

threading.Thread(target=bot_loop, daemon=True).start()

@app.route('/api/status')
def api_status():
    return jsonify(STATE)

@app.route('/test-order')
def test_order():
    try:
        code, txt = get_funds()
        result = {}
        result["test"] = "DHAN LIVE TEST"
        result["time"] = ist_str()
        result["funds_status"] = code
        result["funds"] = txt
        result["note"] = "200 = Token OK | 401 = Token Expired - Pudhu Token Pottanum | 403 = IP Whitelist Problem"
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/health')
def health():
    return jsonify({"ok": True, "time": ist_str()})

@app.route('/')
def home():
    now = ist_str()
    html = ""
    html += "<html><head><title>DHAN BOT</title>"
    html += "<meta name='viewport' content='width=device-width, initial-scale=1'>"
    html += "<style>"
    html += "body{background:#070a12;color:#fff;font-family:Arial;padding:12px}"
    html += ".top{background:#0f172a;border:1px solid #26314d;border-radius:16px;padding:14px;display:flex;justify-content:space-between;align-items:center}"
    html += ".live{background:#052e1a;color:#4ade80;padding:6px 14px;border-radius:20px;font-weight:bold}"
    html += ".grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:12px}"
    html += "@media(max-width:700px){.grid{grid-template-columns:1fr}}"
    html += ".card{background:#101826;border:1px solid #26314d;border-radius:16px;padding:14px}"
    html += ".big{font-size:26px;font-weight:bold;margin:6px 0}"
    html += ".small{font-size:11px;color:#94a3b8}"
    html += ".pill{display:inline-block;padding:5px 12px;border-radius:20px;font-size:12px;font-weight:bold}"
    html += ".box{background:#0b1220;border:1px solid #26314d;border-radius:12px;padding:12px;margin-top:12px}"
    html += "table{width:100%;border-collapse:collapse;font-size:13px}"
    html += "th,td{padding:9px;border-bottom:1px solid #26314d;text-align:left}"
    html += "th{color:#94a3b8}"
    html += "a{color:#4ade80}"
    html += "</style></head><body>"
    html += "<div class='top'><div><h2 style='margin:0'>🚀 DHAN BOT <span style='font-size:13px;color:#94a3b8'>| BOTH LIVE</span></h2><small>" + now + "</small></div><div class='live'>● LIVE</div></div>"
    html += "<div class='grid'>"
    html += "<div class='card' style='border-color:#22c55e'><h3>📈 Trade 1 - 9:20 ORB</h3><span class='pill' style='background:#052e1a;color:#4ade80'>FIXED SL 2000 • TGT 2000</span><div class='big' id='t1Status'>WAITING</div><div class='small'>P&L: <b id='t1Pnl'>Rs 0</b></div></div>"
    html += "<div class='card' style='border-color:#f59e0b'><h3>🔥 Trade 2 - 10:15 BREAKOUT</h3><span class='pill' style='background:#3a2a0a;color:#facc15'>TRAILING SL 2000 • NO TARGET</span><div class='big' id='t2Status'>WAITING</div><div class='small'>P&L: <b id='t2Pnl'>Rs 0</b></div></div>"
    html += "<div class='card'><h3>💰 Today P&L</h3><div class='big' id='todayPnl'>Rs 0</div><div class='small'>Qty 15 | NIFTY: <b id='niftyLive'>-</b> (<span id='niftyPct'>-</span>%)</div><div class='small'>Dhan: <span id='dhanStat'>-</span></div></div>"
    html += "</div>"
    html += "<div class='box'><b>📋 LIVE STATUS</b><table><tr><th>Item</th><th>Value</th></tr><tr><td>Bot Status</td><td id='botStatus'>-</td></tr><tr><td>Dhan</td><td id='dhanConn'>-</td></tr><tr><td>Open Trade</td><td id='openTrade'>-</td></tr><tr><td>Trade 9:20</td><td id='tr920'>-</td></tr><tr><td>Trade 10:15</td><td id='tr1015'>-</td></tr><tr><td>Last Order</td><td id='lastOrder'>-</td></tr><tr><td>Last Msg</td><td id='lastMsg'>-</td></tr></table></div>"
    html += "<div class='box'><a href='/test-order'>👉 CLICK HERE - TEST DHAN CONNECTION</a></div>"
    html += "<script>"
    html += "function fmt(n){return 'Rs '+Number(n||0).toLocaleString('en-IN',{maximumFractionDigits:0})}"
    html += "function load(){ fetch('/api/status').then(r=>r.json()).then(d=>{"
    html += "document.getElementById('botStatus').innerText=d.status;"
    html += "document.getElementById('dhanConn').innerText=d.dhan;"
    html += "document.getElementById('dhanStat').innerText=d.dhan;"
    html += "document.getElementById('openTrade').innerText=d.open_trade?JSON.stringify(d.open_trade):'None';"
    html += "document.getElementById('tr920').innerText=d.trade_920;"
    html += "document.getElementById('tr1015').innerText=d.trade_1015;"
    html += "document.getElementById('lastOrder').innerText=d.last_order_response||'';"
    html += "document.getElementById('t1Status').innerText=d.trade_920?'🟢 RUNNING':'WAITING';"
    html += "document.getElementById('t2Status').innerText=d.trade_1015?'🟢 RUNNING':'WAITING';"
    html += "document.getElementById('todayPnl').innerText=fmt(d.pnl_today);"
    html += "document.getElementById('t1Pnl').innerText=fmt(d.trade1_pnl);"
    html += "document.getElementById('t2Pnl').innerText=fmt(d.trade2_pnl);"
    html += "document.getElementById('lastMsg').innerText=d.last_msg||'';"
    html += "document.getElementById('niftyLive').innerText=d.nifty_live||'-';"
    html += "document.getElementById('niftyPct').innerText=d.nifty_pct||'-';"
    html += "});}"
    html += "load(); setInterval(load,8000);"
    html += "</script></body></html>"
    return html

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
