#!/usr/bin/env python
"""
CryptoBot BINANCE TESTNET v2
BTC, ETH, BNB - Ordini VERI su Binance Testnet (soldi finti)
- Entry: RSI < 40 AND MACD > 0 -> BUY
- Exit: Take Profit +1% OR Stop Loss -1% -> SELL
Struttura semplice, threading (no asyncio) - NO CRASH
"""

import json
import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from collections import deque
import os

print("Starting CryptoBot Binance Testnet v2...")

API_KEY = os.environ.get("BINANCE_API_KEY", "")
SECRET_KEY = os.environ.get("BINANCE_SECRET_KEY", "")
BASE_URL = "https://testnet.binance.vision/api"

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
QTY = {"BTCUSDT": 0.001, "ETHUSDT": 0.01, "BNBUSDT": 0.1}

TAKE_PROFIT = 0.01   # +1%
STOP_LOSS = 0.01     # -1%
RSI_THRESHOLD = 40
MACD_THRESHOLD = 0

class Bot:
    def __init__(self):
        self.cycle = 0
        self.trades = []
        self.errors = []
        self.paused = False
        self.start = datetime.now()
        self.prices = {s: deque(maxlen=100) for s in SYMBOLS}
        self.connected = False
        self.balances = {}
        # open positions: symbol -> {"entry_price": float, "qty": float}
        self.positions = {}
        # ultimi valori RSI/MACD calcolati per ogni simbolo (per debug in dashboard)
        self.last_indicators = {}

bot = Bot()

# ---------------- BINANCE HELPERS ----------------

def public_get(path, params=None):
    try:
        url = BASE_URL + path
        r = requests.get(url, params=params, timeout=10)
        return r.json()
    except Exception as e:
        print("Public API error:", e)
        return None

def signed_request(method, path, params=None):
    if params is None:
        params = {}
    params["timestamp"] = int(time.time() * 1000)
    params["recvWindow"] = 10000
    query = urlencode(params)
    signature = hmac.new(SECRET_KEY.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()
    query += "&signature=" + signature
    url = BASE_URL + path + "?" + query
    headers = {"X-MBX-APIKEY": API_KEY}
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=10)
        else:
            r = requests.post(url, headers=headers, timeout=10)
        return r.json()
    except Exception as e:
        print("Signed API error:", e)
        return None

def get_account():
    return signed_request("GET", "/v3/account")

def get_price(symbol):
    data = public_get("/v3/ticker/price", {"symbol": symbol})
    if data and "price" in data:
        return float(data["price"])
    return None

def place_order(symbol, side):
    qty = QTY.get(symbol, 0.001)
    params = {
        "symbol": symbol,
        "side": side,
        "type": "MARKET",
        "quantity": qty
    }
    return signed_request("POST", "/v3/order", params)

# ---------------- INDICATORS ----------------

def calc_rsi(prices, period=14):
    if len(prices) < period:
        return 50.0
    plist = list(prices)
    changes = [plist[i] - plist[i-1] for i in range(1, len(plist))]
    gains = sum(c for c in changes if c > 0)
    losses = sum(abs(c) for c in changes if c < 0)
    if losses == 0:
        return 100.0 if gains > 0 else 50.0
    avg_g = gains / period
    avg_l = losses / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100 - (100 / (1 + rs))

def calc_macd(prices):
    if len(prices) < 26:
        return 0.0
    plist = list(prices)
    return plist[-1] - plist[0]

# ---------------- DASHBOARD ----------------

HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>CryptoBot Binance Testnet</title>
<style>
body { background: #1a1a2e; color: #ffd700; font-family: courier; padding: 20px; }
h1 { text-align: center; text-shadow: 0 0 10px #ffd700; }
.grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin: 20px 0; }
.card { background: rgba(255,215,0,0.1); border: 2px solid #ffd700; padding: 10px; text-align: center; border-radius: 5px; }
.card-val { font-size: 1.4em; font-weight: bold; }
button { background: #ffd700; color: #000; border: none; padding: 10px 30px; cursor: pointer; font-weight: bold; display: block; margin: 20px auto; border-radius: 5px; }
button.paused { background: #ff6b6b; }
.status { text-align: center; padding: 15px; background: rgba(255,215,0,0.1); border: 2px solid #ffd700; margin: 20px 0; }
.status.error { border-color: #ff6b6b; color: #ff6b6b; }
.trades { background: rgba(255,215,0,0.05); border: 2px solid #ffd700; padding: 15px; margin-top: 20px; max-height: 350px; overflow-y: auto; }
.trade { padding: 5px; border-bottom: 1px solid rgba(255,215,0,0.2); font-size: 0.9em; }
.positions { background: rgba(255,215,0,0.05); border: 2px solid #ffd700; padding: 15px; margin-top: 20px; }
</style>
</head>
<body>
<h1>CryptoBot BINANCE TESTNET v2</h1>
<div style="text-align: center; margin: 20px;">
<span style="background: rgba(255,215,0,0.2); padding: 5px 10px; border-radius: 3px; margin: 0 5px;">BTC+ETH+BNB</span>
<span style="background: rgba(255,215,0,0.2); padding: 5px 10px; border-radius: 3px; margin: 0 5px;">Binance Testnet</span>
<span style="background: rgba(255,215,0,0.2); padding: 5px 10px; border-radius: 3px; margin: 0 5px;">RSI&lt;40 + MACD&gt;0</span>
<span style="background: rgba(255,215,0,0.2); padding: 5px 10px; border-radius: 3px; margin: 0 5px;">TP +1% / SL -1%</span>
</div>
<button id="pauseBtn" onclick="togglePause()">PAUSE</button>
<div class="status" id="status">CARICAMENTO...</div>
<div class="grid" id="balances"></div>
<div class="grid">
<div class="card"><div style="font-size: 0.8em;">Cycles</div><div class="card-val" id="cyc">0</div></div>
<div class="card"><div style="font-size: 0.8em;">Orders</div><div class="card-val" id="trds">0</div></div>
<div class="card"><div style="font-size: 0.8em;">Open Positions</div><div class="card-val" id="pos">0</div></div>
<div class="card"><div style="font-size: 0.8em;">Uptime</div><div class="card-val" id="uptime">0h</div></div>
</div>
<div class="positions">
<h3 style="color: #ffd700; margin-bottom: 10px;">Open Positions</h3>
<div id="positions-list"><div class="trade" style="opacity: 0.5;">None</div></div>
</div>
<div class="positions">
<h3 style="color: #ffd700; margin-bottom: 10px;">Indicatori Live (debug)</h3>
<div id="indicators-list"><div class="trade" style="opacity: 0.5;">Calculating...</div></div>
</div>
<div class="trades">
<h3 style="color: #ffd700; margin-bottom: 10px;">Recent Activity</h3>
<div id="trades-list"><div class="trade" style="opacity: 0.5;">Waiting...</div></div>
</div>
<script>
function togglePause() {
    let btn = document.getElementById('pauseBtn');
    let isPaused = btn.textContent === 'RESUME';
    fetch(isPaused ? '/pause' : '/resume');
    btn.textContent = isPaused ? 'PAUSE' : 'RESUME';
    btn.classList.toggle('paused');
}

async function update() {
    try {
        let s = await fetch('/status').then(r => r.json());
        document.getElementById('cyc').textContent = s.cycle;
        document.getElementById('trds').textContent = s.orders;
        document.getElementById('pos').textContent = s.open_positions;
        document.getElementById('uptime').textContent = s.uptime;

        let statusEl = document.getElementById('status');
        if (s.connected) {
            statusEl.textContent = s.paused ? 'PAUSED' : 'CONNESSO A BINANCE TESTNET - LIVE';
            statusEl.classList.remove('error');
        } else {
            statusEl.textContent = 'NON CONNESSO: ' + (s.last_error || 'verifica le API keys');
            statusEl.classList.add('error');
        }

        let balHtml = '';
        for (const [asset, amount] of Object.entries(s.balances)) {
            balHtml += '<div class="card"><div style="font-size:0.8em;">' + asset + '</div><div class="card-val">' + amount + '</div></div>';
        }
        document.getElementById('balances').innerHTML = balHtml;

        let posHtml = '';
        for (const [symbol, p] of Object.entries(s.positions)) {
            posHtml += '<div class="trade">' + symbol + ': qty ' + p.qty + ' @ entry $' + p.entry_price + '</div>';
        }
        document.getElementById('positions-list').innerHTML = posHtml || '<div class="trade" style="opacity: 0.5;">None</div>';

        let indHtml = '';
        for (const [symbol, ind] of Object.entries(s.indicators)) {
            let ok = (ind.rsi < 40 && ind.macd > 0);
            indHtml += '<div class="trade">' + symbol + ': price $' + ind.price.toFixed(2) + ' | RSI ' + ind.rsi + ' | MACD ' + ind.macd + (ok ? ' -> SEGNALE OK' : '') + '</div>';
        }
        document.getElementById('indicators-list').innerHTML = indHtml || '<div class="trade" style="opacity: 0.5;">Calculating...</div>';

        let trades = await fetch('/trades').then(r => r.json());
        let html = trades.slice().reverse().slice(0, 20).map(x => '<div class="trade">' + x + '</div>').join('');
        document.getElementById('trades-list').innerHTML = html || '<div class="trade" style="opacity: 0.5;">Waiting...</div>';
    } catch(e) {}
}

update();
setInterval(update, 3000);
</script>
</body>
</html>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode())
        elif self.path == '/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            elapsed = datetime.now() - bot.start
            hours = elapsed.seconds // 3600
            last_error = bot.errors[-1] if bot.errors else None
            positions_out = {}
            for sym, p in bot.positions.items():
                positions_out[sym] = {"qty": p["qty"], "entry_price": round(p["entry_price"], 2)}
            data = json.dumps({
                'cycle': bot.cycle,
                'orders': len(bot.trades),
                'open_positions': len(bot.positions),
                'positions': positions_out,
                'indicators': bot.last_indicators,
                'uptime': f"{elapsed.days}d {hours}h",
                'paused': bot.paused,
                'connected': bot.connected,
                'balances': bot.balances,
                'last_error': last_error
            })
            self.wfile.write(data.encode())
        elif self.path == '/trades':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(bot.trades[-30:]).encode())
        elif self.path == '/pause':
            bot.paused = True
            self.send_response(200)
            self.end_headers()
        elif self.path == '/resume':
            bot.paused = False
            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass

def run_server():
    print("Server starting on port 8000...")
    server = HTTPServer(('0.0.0.0', 8000), Handler)
    server.serve_forever()

# ---------------- TRADING LOOP ----------------

def update_balances():
    acc = get_account()
    if acc and "balances" in acc:
        bot.connected = True
        result = {}
        for b in acc["balances"]:
            free = float(b["free"])
            if free > 0 and b["asset"] in ("USDT", "BTC", "ETH", "BNB"):
                result[b["asset"]] = round(free, 6)
        bot.balances = result
    else:
        bot.connected = False
        err = "Risposta Binance: " + str(acc)
        bot.errors.append(err)
        print(err)

def trading_loop():
    print("Trading loop started")
    print("API_KEY configurata:", "SI" if API_KEY else "NO")
    print("SECRET_KEY configurata:", "SI" if SECRET_KEY else "NO")
    print(f"Strategia: RSI < {RSI_THRESHOLD} + MACD > {MACD_THRESHOLD} | TP +{TAKE_PROFIT*100:.0f}% | SL -{STOP_LOSS*100:.0f}%")

    # Primo check connessione (non blocca il server, gia' partito)
    update_balances()

    while True:
        if not bot.paused:
            bot.cycle += 1

            # Ogni 10 cicli ricontrolla saldo
            if bot.cycle % 10 == 1:
                update_balances()

            for symbol in SYMBOLS:
                price = get_price(symbol)
                if not price:
                    continue

                bot.prices[symbol].append(price)

                # ---- Gestione posizione APERTA: controlla TP/SL ----
                if symbol in bot.positions:
                    pos = bot.positions[symbol]
                    entry = pos["entry_price"]
                    change = (price - entry) / entry

                    if change >= TAKE_PROFIT or change <= -STOP_LOSS:
                        res = place_order(symbol, "SELL")
                        if res and "orderId" in res:
                            reason = "TAKE PROFIT" if change >= TAKE_PROFIT else "STOP LOSS"
                            msg = f"[{datetime.now().strftime('%H:%M:%S')}] SELL {symbol} @ ${price:.2f} ({reason} {change*100:.2f}%) - OK"
                            bot.trades.append(msg)
                            print(msg)
                            del bot.positions[symbol]
                            update_balances()
                        else:
                            err_msg = f"[{datetime.now().strftime('%H:%M:%S')}] SELL {symbol} FALLITO: {res}"
                            bot.trades.append(err_msg)
                            bot.errors.append(err_msg)
                            print(err_msg)

                    # se ha posizione aperta, non valutare nuovo BUY su questo symbol
                    continue

                # ---- Nessuna posizione: valuta BUY ----
                if len(bot.prices[symbol]) > 30:
                    rsi = calc_rsi(bot.prices[symbol])
                    macd = calc_macd(bot.prices[symbol])

                    # LOG DIAGNOSTICO: stampa sempre i valori per capire perche' non scatta
                    print(f"[DEBUG] {symbol} price={price:.2f} RSI={rsi:.2f} MACD={macd:.4f} (serve RSI<{RSI_THRESHOLD} e MACD>{MACD_THRESHOLD})")
                    bot.last_indicators[symbol] = {"rsi": round(rsi, 2), "macd": round(macd, 4), "price": price}

                    if rsi < RSI_THRESHOLD and macd > MACD_THRESHOLD:
                        res = place_order(symbol, "BUY")
                        if res and "orderId" in res:
                            msg = f"[{datetime.now().strftime('%H:%M:%S')}] BUY {symbol} @ ${price:.2f} (RSI:{rsi:.0f}) - OK"
                            bot.trades.append(msg)
                            print(msg)
                            bot.positions[symbol] = {"entry_price": price, "qty": QTY.get(symbol, 0.001)}
                            update_balances()
                        else:
                            err_msg = f"[{datetime.now().strftime('%H:%M:%S')}] BUY {symbol} FALLITO: {res}"
                            bot.trades.append(err_msg)
                            bot.errors.append(err_msg)
                            print(err_msg)

            if bot.cycle % 10 == 0:
                print(f"Cycle {bot.cycle} | Connected: {bot.connected} | Orders: {len(bot.trades)} | Open: {len(bot.positions)}")

        time.sleep(30)

if __name__ == '__main__':
    print("CryptoBot Binance Testnet v2 - Avvio")
    t1 = Thread(target=run_server, daemon=True)
    t2 = Thread(target=trading_loop, daemon=True)
    t1.start()
    t2.start()
    print("Bot in esecuzione...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutdown")
