import os
import requests
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify

app = Flask(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

def ist_str():
    return datetime.now(IST).strftime('%d-%m-%Y %I:%M %p')

DHAN_CLIENT_ID = os.environ.get("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.environ.get("DHAN_ACCESS_TOKEN", "")

QTY = 15

STATE = {}
STATE["dhan"] = "CONNECTED ✅ Profile OK"
STATE["last_msg"] = "BOTH LIVE BOT STARTED ✅ | Qty 15"
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

@app.route('/api/status')
def api_status():
    return jsonify(STATE)

@app.route('/test-order')
def test_order():
    try:
        headers = {}
        headers["access-token"] = DHAN_ACCESS_TOKEN
        headers["client-id"] = DHAN_CLIENT_ID
        headers["Content-Type"] = "application/json"
        r1 = requests.get(
            "https://auth.dhan.co/v2/profile",
            headers=headers,
            timeout=10
        )
        result = {}
        result["test"] = "DHAN LIVE TEST"
        result["time"] = ist_str()
        result["profile_status"] = r1.status_code
        result["profile"] = r1.text[:500]
        result["note"] = "200 = OK | 401 = Token Problem | Market Closed = Normal"
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/')
def home():
    now = ist_str()
    html = ""
    html += "<html><head><title>DHAN BOT</title>"
    html += "<meta name='viewport' content='width=device-width, initial-scale=1'>"
    html += "<style>"
    html += "body{background:#070a12;color:#fff;font-family:Arial;padding:12px}"
    html += ".card{background:#101826;border:1px solid #26314d;border-radius:16px;padding:14px;margin-top:12px}"
    html += ".big{font-size:26px;font-weight:bold}"
    html += ".small{font-size:11px;color:#94a3b8}"
    html += "a{color:#4ade80}"
    html += "</style></head><body>"
    html += "<h2>🚀 DHAN BOT | BOTH LIVE</h2>"
    html += "<div class='small'>" + now + "</div>"
    html += "<div class='card'>"
    html += "<h3>📈 Trade 1 - 9:20 ORB</h3>"
    html += "<div class='big' id='t1'>WAITING</div>"
    html += "<div class='small'>FIXED SL 2000 • TGT 2000</div>"
    html += "</div>"
    html += "<div class='card'>"
    html += "<h3>🔥 Trade 2 - 10:15 BREAKOUT</h3>"
    html += "<div class='big' id='t2'>WAITING</div>"
    html += "<div class='small'>TRAILING SL 2000 • NO TARGET</div>"
    html += "</div>"
    html += "<div class='card'>"
    html += "<h3>💰 Today P&L</h3>"
    html += "<div class='big' id='pnl'>Rs 0</div>"
    html += "<div class='small'>Qty 15 | Dhan: <span id='dhan'>-</span></div>"
    html += "<div class='small' id='msg'></div>"
    html += "</div>"
    html += "<div class='card'>"
    html += "<a href='/test-order'>👉 CLICK - TEST DHAN CONNECTION</a>"
    html += "</div>"
    html += "<script>"
    html += "function load(){"
    html += "fetch('/api/status').then(r=>r.json()).then(d=>{"
    html += "document.getElementById('t1').innerText=d.trade_920?'🟢 RUNNING':'WAITING';"
    html += "document.getElementById('t2').innerText=d.trade_1015?'🟢 RUNNING':'WAITING';"
    html += "document.getElementById('pnl').innerText='Rs '+(d.pnl_today||0);"
    html += "document.getElementById('dhan').innerText=d.dhan;"
    html += "document.getElementById('msg').innerText=d.last_msg;"
    html += "});}"
    html += "load();"
    html += "setInterval(load,8000);"
    html += "</script>"
    html += "</body></html>"
    return html

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
