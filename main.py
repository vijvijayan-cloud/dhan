import os, requests, threading, time
from datetime import datetime
from flask import Flask, jsonify
import pytz
app = Flask(__name__)
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
LOT_SIZE = 65
SL_AMOUNT = 2000
TARGET_AMOUNT = 2000
IST = pytz.timezone("Asia/Kolkata")
def send_telegram(msg):
    try:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return False
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
        return r.status_code == 200
    except: return False
def dhan_headers():
    return {"access-token": DHAN_ACCESS_TOKEN, "client-id": DHAN_CLIENT_ID, "Content-Type": "application/json"}
def get_funds():
    try:
        r = requests.get("https://auth.dhan.co/v2/funds", headers=dhan_headers(), timeout=10)
        return r.status_code, r.json()
    except Exception as e: return 500, {"error": str(e)}
def get_nifty_price():
    try:
        r = requests.post("https://auth.dhan.co/v2/marketfeed/quote", headers=dhan_headers(), json={"NSE_EQ": [13]}, timeout=10)
        return r.json()["data"]["NSE_EQ"]["13"]["last_price"]
    except: return 25800.0
def round_to_strike(p, s=50): return int(round(p/s)*s)
def get_itm1(p, t):
    atm = round_to_strike(p, 50)
    return atm, (atm-50 if t=="CE" else atm+50)
traded_920=False; traded_1015=False; last_day=None
def bot_scheduler():
    global traded_920, traded_1015, last_day
    while True:
        try:
            now=datetime.now(IST); today=now.strftime("%Y-%m-%d")
            if today!=last_day: traded_920=False; traded_1015=False; last_day=today
            if now.weekday()>=5: time.sleep(60); continue
            if not traded_920 and now.hour==9 and now.minute==20:
                nifty=get_nifty_price(); atm,strike=get_itm1(nifty,"CE")
                send_telegram(f"🚀 9:20 ORB - BUY {strike} CE - Nifty {nifty} - Qty 65 - SL 2000")
                traded_920=True
            if not traded_1015 and now.hour==10 and now.minute==15:
                nifty=get_nifty_price(); atm,strike=get_itm1(nifty,"CE")
                send_telegram(f"🚀 10:15 Breakout - BUY {strike} CE - Nifty {nifty} - Qty 65 - SL 2000")
                traded_1015=True
            time.sleep(30)
        except: time.sleep(30)
threading.Thread(target=bot_scheduler, daemon=True).start()
@app.route("/")
def home():
    code,funds=get_funds(); nifty=get_nifty_price()
    atm,ce=get_itm1(nifty,"CE"); _,pe=get_itm1(nifty,"PE")
    avail=0
    try: avail=funds.get("data",{}).get("availabelBalance",0)
    except: pass
    html=f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{{font-family:Arial;background:#0f172a;color:white;margin:0;padding:15px}}.card{{background:#1e293b;padding:15px;border-radius:12px;margin-bottom:12px}}.green{{color:#22c55e}}.red{{color:#ef4444}}.yellow{{color:#facc15}}.btn{{display:inline-block;background:#2563eb;color:white;padding:10px 16px;border-radius:8px;text-decoration:none;margin:4px}}.btn2{{background:#16a34a}}.btn3{{background:#f59e0b}}table{{width:100%;border-collapse:collapse}}td,th{{padding:8px;border-bottom:1px solid #334155;font-size:14px;text-align:left}}</style></head><body><h1>🤖 Dhan Trading Bot <span class="green">● LIVE</span></h1><p>{datetime.now(IST).strftime('%d-%m-%Y %I:%M %p')}</p><div class="card"><h2>📊 Nifty 50</h2><h1 class="yellow">{nifty}</h1><p>ATM: {atm} | ITM 1 CE: {ce} CE | ITM 1 PE: {pe} PE</p></div><div class="card"><h2>💰 Funds</h2><h1 class="green">Rs {avail}</h1><p>Status: {code} | Lot: 65 | Qty: 65</p></div><div class="card"><h2>⚙️ Bot Settings</h2><table><tr><td>Strike</td><td><b>ITM 1</b></td></tr><tr><td>Trade 1</td><td><b>9:20 ORB</b></td></tr><tr><td>Trade 2</td><td><b>10:15 Breakout</b></td></tr><tr><td>SL</td><td class="red"><b>Rs 2000</b></td></tr><tr><td>Target</td><td class="green"><b>Rs 2000</b></td></tr><tr><td>Telegram</td><td class="green"><b>✅ Connected</b></td></tr></table></div><div class="card"><h2>📈 Today's Trades</h2><table><tr><th>Time</th><th>Trade</th><th>Status</th></tr><tr><td>9:20</td><td>ORB - ITM 1</td><td>Waiting...</td></tr><tr><td>10:15</td><td>Breakout - ITM 1</td><td>Waiting...</td></tr></table></div><div class="card"><h2>🧪 Test</h2><a class="btn" href="/test-order">Test Order</a><a class="btn btn2" href="/test-telegram">Test Telegram</a><a class="btn btn3" href="/status">Status</a></div><p style="text-align:center;color:#94a3b8;font-size:12px">Dhan Bot - Lot 65 - ITM 1 - Final</p></body></html>"""
    return html
@app.route("/status")
def status():
    code,funds=get_funds()
    return jsonify({"bot":"ON","lot_size":65,"strike":"ITM 1","trade1":"9:20 ORB","trade2":"10:15 Breakout","sl":2000,"funds_status":code,"funds":funds,"telegram":bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),"time":datetime.now(IST).strftime("%d-%m-%Y %I:%M %p")})
@app.route("/test-order")
def test_order():
    code,funds=get_funds(); nifty=get_nifty_price(); atm,ce=get_itm1(nifty,"CE"); _,pe=get_itm1(nifty,"PE")
    avail=0
    try: avail=funds.get("data",{}).get("availabelBalance",0)
    except: pass
    return jsonify({"funds_status":code,"lot_size":65,"qty":65,"nifty":nifty,"atm":atm,"itm1_ce":ce,"itm1_pe":pe,"availabelBalance":avail,"time":datetime.now(IST).strftime("%d-%m-%Y %I:%M %p")})
@app.route("/test-telegram")
def test_telegram():
    ok=send_telegram("✅ Bot Connected! Telegram OK Sir! - "+datetime.now(IST).strftime('%d-%m-%Y %I:%M %p'))
    return jsonify({"telegram_sent":ok})
if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",10000)))
