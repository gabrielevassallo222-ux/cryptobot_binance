#!/usr/bin/env python
"""
CryptoBot SIMULATO - Threading Simple (no asyncio)
CoinGecko API pubblica - BTC, ETH, BNB
Trade simulati per testing
"""

import json
import requests
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from collections import deque

print("Starting CryptoBot...")

class Bot:
    def __init__(self):
        self.cycle = 0
        self.trades = []
        self.balance = 10000.0
        self.paused = False
        self.start = datetime.now()
        self.prices = {
            'bitcoin': deque(maxlen=100),
            'ethereum': deque(maxlen=100),
            'binancecoin': deque(maxlen=100)
        }

bot = Bot()

def get_prices():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,binancecoin&vs_currencies=usd"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            return {k: v['usd'] for k, v in data.items()}
    except Exception as e:
        print("Error getting prices:", e)
    return None

def calc_rsi(prices, period=14):
    if len(prices) < period:
        return 50.0
    plist = list(prices)
    changes = [plist[i] - plist[i-1] for i in range(1, len(plist))]
    gains = sum(1 for c in changes if c > 0)
    losses = sum(1 for c in changes if c < 0)
    if losses == 0:
        return 100.0 if gains > 0 else 50.0
    avg_g = sum(c for c in changes if c > 0) / period if gains > 0 else 0
    avg_l = sum(abs(c) for c in changes if c < 0) / period if losses > 0 else 0
    if avg_l == 0:
        return 100.0 if avg_g > 0 else 50.0
    return 100 - (100 / (1 + (avg_g / avg_l)))

def calc_macd(prices):
    if len(prices) < 26:
        return 0.0
    plist = list(prices)
    return plist[-1] - plist[0]

HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>CryptoBot</title>
<style>
body { background: #1a1a2e; color: #ffd700; font-family: courier; padding: 20px; }
h1 { text-align: center; text-shadow: 0 0 10px #ffd700; }
.grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin: 20px 0; }
.card { background: rgba(255,215,0,0.1); border: 2px solid #ffd700; padding: 10px; text-align: center; border-radius: 5px; }
.card-val { font-size: 1.5em; font-weight: bold; }
button { background: #ffd700; color: #000; border: none; padding: 10px 30px; cursor: pointer; font-weight: bold; display: block; margin: 20px auto; border-radius: 5px; }
button.paused { background: #ff6b6b; }
.status { text-align: center; padding: 15px; background: rgba(255,215,0,0.1); border: 2px solid #ffd700; margin: 20px 0; }
.trades { background: rgba(255,215,0,0.05); border: 2px solid #ffd700; padding: 15px; margin-top: 20px; max-height: 400px; overflow-y: auto; }
.trade { padding: 5px; border-bottom: 1px solid rgba(255,215,0,0.2); font-size: 0.9em; }
</style>
</head>
<body>
<h1>CryptoBot SIMULATO</h1>
<div style="text-align: center; margin: 20px;">
<span style="background: rgba(255,215,0,0.2); padding: 5px 10px; border-radius: 3px; margin: 0 5px;">BTC+ETH+BNB</span>
<span style="background: rgba(255,215,0,0.2); padding: 5px 10px; border-radius: 3px; margin: 0 5px;">CoinGecko API</span>
<span style="background: rgba(255,215,0,0.2); padding: 5px 10px; border-radius: 3px; margin: 0 5px;">SIMULATO</span>
</div>
<button id="pauseBtn" onclick="togglePause()">PAUSE</button>
<div class="status" id="status">LIVE SIMULATION</div>
<div class="grid">
<div class="card"><div style="font-size: 0.8em;">Balance</div><div class="card-val" id="bal">$10,000</div></div>
<div class="card"><div style="font-size: 0.8em;">P&L</div><div class="card-val" id="pnl">$0</div></div>
<div class="card"><div style="font-size: 0.8em;">Cycles</div><div class="card-val" id="cyc">0</div></div>
<div class="card"><div style="font-size: 0.8em;">Trades</div><div class="card-val" id="trds">0</div></div>
<div class="card"><div style="font-size: 0.8em;">Uptime</div><div class="card-val" id="uptime">0h</div></div>
</div>
<div class="trades">
<h3 style="color: #ffd700; margin-bottom: 10px;">Recent Trades</h3>
<div id="trades-list"><div class="trade" style="opacity: 0.5;">Waiting...</div></div>
</div>
<script>
function togglePause() {
    let btn = document.getElementById('pauseBtn');
    let isPaused = btn.textContent === 'RESUME';
    fetch(isPaused ? '/pause' : '/resume');
    btn.textContent = isPaused ? 'PAUSE' : 'RESUME';
    btn.classList.toggle('paused');
    document.getElementById('status').textContent = isPaused ? 'LIVE SIMULATION' : 'PAUSED';
}

async function update() {
    try {
        let s = await fetch('/status').then(r => r.json());
        document.getElementById('bal').textContent = '$' + s.b.toLocaleString();
        document.getElementById('pnl').textContent = '$' + s.p.toLocaleString();
        document.getElementById('cyc').textContent = s.c;
        document.getElementById('trds').textContent = s.t;
        document.getElementById('uptime').textContent = s.u;
        let trades = await fetch('/trades').then(r => r.json());
        let html = trades.reverse().slice(0, 20).map(x => '<div class="trade">' + x + '</div>').join('');
        document.getElementById('trades-list').innerHTML = html || '<div class="trade" style="opacity: 0.5;">Waiting...</div>';
    } catch(e) {}
}

update();
setInterval(update, 2000);
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
            pnl = bot.balance - 10000
            data = json.dumps({
                'b': int(bot.balance),
                'p': int(pnl),
                'c': bot.cycle,
                't': len(bot.trades),
                'u': f"{elapsed.days}d {hours}h"
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

def trading_loop():
    print("Trading loop started")
    while True:
        if not bot.paused:
            bot.cycle += 1
            prices = get_prices()
            if prices:
                for symbol in ['bitcoin', 'ethereum', 'binancecoin']:
                    price = prices.get(symbol)
                    if price:
                        bot.prices[symbol].append(price)
                        if len(bot.prices[symbol]) > 30:
                            rsi = calc_rsi(bot.prices[symbol])
                            macd = calc_macd(bot.prices[symbol])
                            if rsi < 40 and macd > 0:
                                names = {'bitcoin': 'BTC', 'ethereum': 'ETH', 'binancecoin': 'BNB'}
                                msg = f"[{datetime.now().strftime('%H:%M:%S')}] SIM BUY {names[symbol]} @ ${price:.0f}"
                                bot.trades.append(msg)
                                bot.balance += 50
                                print(msg)
            if bot.cycle % 10 == 0:
                print(f"Cycle {bot.cycle} | Balance: ${bot.balance:.0f} | Trades: {len(bot.trades)}")
        time.sleep(30)

if __name__ == '__main__':
    print("CryptoBot SIMULATO v3 - NO ASYNCIO")
    t1 = Thread(target=run_server, daemon=True)
    t2 = Thread(target=trading_loop, daemon=True)
    t1.start()
    t2.start()
    print("Bot running...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutdown")
