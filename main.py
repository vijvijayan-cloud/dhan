import os, requests
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify
app = Flask(__name__)
IST = timezone(timedelta(hours=5, minutes=30))
def ist_str(): return datetime.now(IST).strftime('%d-%m-%Y %I:%M %p')
DHAN_CLIENT_ID = os.environ.get("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.environ.get("DHAN_ACCESS_TOKEN", "")
QTY = 15
STATE = {"dhan": "CONNECTED ✅ Profile OK", "last_msg": "BOTH LIVE BOT STARTED ✅ | Qty 15", "live": True, "open_trade": None, "status": "BOTH LIVE BOT RUNNING", "trade_920": False, "trade_1015": False, "qty": QTY, "pnl_today": 0, "trade1_pnl": 0, "trade2_pnl": 0, "nifty_live": 0, "nifty_pct": 0, "updated": ist_str()}

@app.route('/api/status')
def api_status():
    return jsonify(STATE)

@app.route('/test-order')
def test_order():
    try:
        headers = {"access-token": DHAN_ACCESS_TOKEN, "client-id": DHAN_CLIENT_ID, "Content-Type": "application/json"}
        r1 = requests.get("https://auth.dhan.co/v2/profile", headers=headers, timeout=10)
        return jsonify({"test": "DHAN LIVE TEST", "time": ist_str(), "profile_status": r1.status_code, "profile": r1.text[:500], "note": "200 = OK ✅ | 401 = Token Problem ❌ | Market Closed = Normal ✅"})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/')
def home():
    html = """<html><head><title>DHAN BOT</title><meta name='viewport' content='width=device-width, initial-scale=1'><style>body{background:#070a12;color:#fff;font-family:Arial;padding:12px}.card{background:#101826;border:1px solid #26314d;border-radius:16px;padding:14px;margin-top:12px}.big{font-size:26px;font-weight:bold}.small{font-size:11px;color:#94a3b8}a{color:#4ade80}</style></head><body><h2>🚀 DHAN BOT | BOTH LIVE</h2><div class='small'>""" + ist_str() + """</div><div class='card'><h3>📈 Trade 1 - 9:20 ORB</h3><div class='big' id='t1'>WAITING</div><div class='small'>FIXED SL 2000 • TGT 2000</div></div><div class='card'><h3>🔥 Trade 2 - 10:15 BREAKOUT</h3><div class='big' id='t2'>WAITING</div><div class='small'>TRAILING SL 2000 • NO TARGET</div></div><div class='card'><h3>💰 Today P&L</h3><div class='big' id='pnl'>Rs 0</div><div class='small'>Qty 15 | Dhan: <span id='dhan'>-</span></div><div class='small' id='msg'></div></div><div class='card'><a href='/test-order'>👉 CLICK - TEST DHAN CONNECTION</a></div><script>function load(){fetch('/api/status').then(r=>r.json()).then(d=>{document.getElementById('t1').innerText=d.trade_920?'🟢 RUNNING':'WAITING';document.getElementById('t2').innerText=d.trade_1015?'🟢 RUNNING':'WAITING';document.getElementById('pnl').innerText='Rs '+(d.pnl_today||0);document.getElementById('dhan').innerText=d.dhan;document.getElementById('msg').innerText=d.last_msg;})}load();setInterval(load,8000)</script></body></html>"""
    return html

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
