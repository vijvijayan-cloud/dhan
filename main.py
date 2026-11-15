import os, requests, threading, time
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
DHAN_AUTO_TRADE = os.environ.get("DHAN_AUTO_TRADE", "OFF")

IST = timezone(timedelta(hours=5, minutes=30))

def ist_str():
    return datetime.now(IST).strftime('%d-%m-%Y %I:%M %p')

def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
        return r.status_code == 200
    except:
        return False

CONFIG = {
    "NIFTY": {"emoji": "🟣", "step": 50, "lot": 65},
    "SENSEX": {"emoji": "🔵", "step": 100, "lot": 20},
    "CRUDEOILM": {"emoji": "⚫", "step": 50, "lot": 10},
    "GOLDM": {"emoji": "🟡", "step": 100, "lot": 10},
    "SILVERM": {"emoji": "⚪", "step": 500, "lot": 5},
}
ORDER = ["NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "SILVERM"]
SCRIPTS = {"NIFTY": "^NSEI", "SENSEX": "^BSESN", "CRUDEOILM": "CL=F", "GOLDM": "GC=F", "SILVERM": "SI=F"}

def get_usdinr():
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/USDINR=X?range=1d&interval=1m", headers={"User-Agent": "Mozilla/5.0"}, timeout=8).json()
        return r["chart"]["result"][0]["meta"]["regularMarketPrice"]
    except:
        return 88.50

def convert_price(name, raw, usdinr):
    if name == "CRUDEOILM":
        return raw * usdinr
    if name == "GOLDM":
        return (raw / 31.1035) * 10 * usdinr
    if name == "SILVERM":
        return (raw / 31.1035) * 1000 * usdinr
    return raw

def get_prices():
    usdinr = get_usdinr()
    out = {}
    for name in ORDER:
        sym = SCRIPTS[name]
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=15m"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8).json()
            res = r["chart"]["result"][0]
            meta = res["meta"]
            raw = meta.get("regularMarketPrice", 0)
            prev_raw = meta.get("previousClose", raw)
            price = convert_price(name, raw, usdinr)
            prev = convert_price(name, prev_raw, usdinr)
            chg = price - prev
            pct = chg / prev * 100 if prev else 0
            q = res["indicators"]["quote"][0]
            closes = [convert_price(name, c, usdinr) for c in q["close"] if c is not None]
            def ema(d, p):
                k = 2 / (p + 1)
                e = d[0]
                for v in d[1:]:
                    e = v * k + e * (1 - k)
                return e
            e9 = ema(closes, 9) if len(closes) > 9 else price
            e21 = ema(closes, 21) if len(closes) > 21 else price
            if e9 > e21 and price > e9:
                action = "BUY CE"
                trend = "UP"
            elif e9 < e21 and price < e9:
                action = "BUY PE"
                trend = "DOWN"
            else:
                action = "WAIT"
                trend = "WAIT"
            step = CONFIG[name]["step"]
            atm = round(price / step) * step
            if action == "BUY CE":
                strike = atm - step
                typ = "CE"
            elif action == "BUY PE":
                strike = atm + step
                typ = "PE"
            else:
                strike = atm
                typ = "CE"
            prem = round(abs(price - strike) * 0.3 + price * 0.005, 2)
            out[name] = {"name": name, "live": round(price, 2), "pct": round(pct, 2), "action": action, "trend": trend, "emoji": CONFIG[name]["emoji"], "strike": strike, "typ": typ, "prem": prem, "sl": round(prem * 0.60, 2), "tgt": round(prem * 1.80, 2), "lot": CONFIG[name]["lot"]}
        except:
            out[name] = {"name": name, "live": 0, "pct": 0, "action": "WAIT", "trend": "Loading", "emoji": CONFIG[name]["emoji"], "strike": 0, "typ": "CE", "prem": 0, "sl": 0, "tgt": 0, "lot": 0}
    return out

@app.route('/api/prices')
def api_prices():
    return jsonify(get_prices())

@app.route('/test_telegram')
def t():
    ok = send_telegram("Test OK! Auto Scalp Bot Ready!")
    return "Sent!" if ok else "Failed - Check Telegram Token"

@app.route('/')
def home():
    return f"""
    <html><head><title>Auto Scalp Bot</title><meta name='viewport' content='width=device-width, initial-scale=1'>
    <style>body{{background:#0e1117;color:white;font-family:Arial;padding:12px}} .card{{background:#131722;border-radius:12px;padding:12px;margin-top:10px;border:1px solid #222}}</style></head><body>
    <h2>AUTO SCALP BOT C</h2>
    <div>Time: {ist_str()} | Mode: {DHAN_AUTO_TRADE}</div>
    <div id='data'>Loading...</div>
    <script>
    function load(){{ fetch('/api/prices').then(r=>r.json()).then(d=>{{ let h=''; for(let k in d){{ let x=d[k]; h+='<div class=card><b>'+x.emoji+' '+x.name+' - Rs '+x.live+'</b> | '+x.pct+'% | '+x.trend+' | '+x.action+' '+x.strike+' '+x.typ+' | Entry '+x.prem+' | TGT '+x.tgt+' | SL '+x.sl+'</div>'; }} document.getElementById('data').innerHTML=h; }}); }}
    load(); setInterval(load,8000);
    </script></body></html>
    """

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
