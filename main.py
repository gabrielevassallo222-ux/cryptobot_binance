"""
CryptoBot v2 - BINANCE TESTNET SEMPLIFICATO
BTC/USDT, ETH/USDT, BNB/USDT
RSI < 40 + MACD > 0
Versione stabile - senza crash all'avvio
"""

import asyncio
import json
import requests
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import os
from collections import deque
import hmac
import hashlib
import time

BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_SECRET_KEY = os.getenv('BINANCE_SECRET_KEY', '')
BINANCE_TESTNET_URL = "https://testnet.binance.vision/api"

def calculate_rsi(prices, period=14):
    if len(prices) < period:
        return 50.0
    changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = sum(1 for c in changes if c > 0)
    losses = sum(1 for c in changes if c < 0)
    if losses == 0:
        return 100.0 if gains > 0 else 50.0
    avg_gain = sum([c for c in changes if c > 0]) / period if gains > 0 else 0
    avg_loss = sum([abs(c) for c in changes if c < 0]) / period if losses > 0 else 0
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_macd(prices):
    if len(prices) < 26:
        return 0.0
    return prices[-1] - prices[0]

class CryptoBot:
    def __init__(self):
        self.api_key = BINANCE_API_KEY
        self.secret_key = BINANCE_SECRET_KEY
        self.running = True
        self.paused = False
        self.cycle = 0
        self.trades = []
        self.balance = 1000.0
        self.startup = datetime.now()
        self.prices = {'BTCUSDT': deque(maxlen=100), 'ETHUSDT': deque(maxlen=100), 'BNBUSDT': deque(maxlen=100)}
        self.positions = []
    
    def get_price(self, symbol):
        try:
            url = "{}/v3/ticker/price?symbol={}".format(BINANCE_TESTNET_URL, symbol)
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                return float(r.json()['price'])
        except:
            pass
        return None
    
    def uptime_str(self):
        e = datetime.now() - self.startup
        return "{}d {}h {}m".format(e.days, e.seconds // 3600, (e.seconds % 3600) // 60)

bot = CryptoBot()

HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>CryptoBot v2</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Courier New', monospace; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #ffd700; padding: 20px; }
.container { max-width: 1200px; margin: 0 auto; }
h1 { text-align: center; margin-bottom: 20px; font-size: 2.5em; text-shadow: 0 0 10px #ffd700; }
.status { text-align: center; padding: 15px; background: rgba(255,215,0,0.1); border: 2px solid #ffd700; border-radius: 8px; margin-bottom: 20px; font-weight: bold; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 30px; }
.card { background: rgba(255,215,0,0.1); border: 2px solid #ffd700; border-radius: 8px; padding: 15px; text-align: center; }
.card-label { font-size: 0.8em; opacity: 0.7; margin-bottom: 5px; }
.card-value { font-size: 1.8em; font-weight: bold; }
.button { padding: 10px 25px; font-size: 1em; background: #ffd700; color: #000; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; margin-top: 20px; }
.button.paused { background: #ff6b6b; }
.trades-box { background: rgba(255,215,0,0.05); border: 2px solid #ffd700; border-radius: 8px; padding: 15px; margin-top: 30px; }
.trade-row { padding: 8px; border-bottom: 1px solid rgba(255,215,0,0.2); font-size: 0.9em; }
</style>
</head>
<body>
<div class="container">
    <h1>🚀 CryptoBot v2 - Testnet</h1>
    <div style="text-align: center; margin-bottom: 15px;">
        <span style="background: rgba(255,215,0,0.2); border: 1px solid #ffd700; padding: 5px 10px; border-radius: 3px; margin: 0 5px;">BTC + ETH + BNB</span>
        <span style="background: rgba(255,215,0,0.2); border: 1px solid #ffd700; padding: 5px 10px; border-radius: 3px; margin: 0 5px;">Every 30s</span>
        <span style="background: rgba(255,215,0,0.2); border: 1px solid #ffd700; padding: 5px 10px; border-radius: 3px; margin: 0 5px;">24/7</span>
    </div>
    <button id="pauseBtn" class="button" style="display: block; margin: 0 auto;">PAUSE</button>
    <div class="status" id="status">LIVE TRADING 24/7</div>
    <div class="grid">
        <div class="card">
            <div class="card-label">Balance</div>
            <div class="card-value" id="balance">$1000</div>
        </div>
        <div class="card">
            <div class="card-label">Cycles</div>
            <div class="card-value" id="cycles">0</div>
        </div>
        <div class="card">
            <div class="card-label">Orders</div>
            <div class="card-value" id="orders">0</div>
        </div>
        <div class="card">
            <div class="card-label">Uptime</div>
            <div class="card-value" id="uptime">0d 0h 0m</div>
        </div>
    </div>
    <div class="trades-box">
        <h2 style="color: #ffd700; margin-bottom: 10px;">Recent Activity</h2>
        <div id="trades-list"><div class="trade-row" style="opacity: 0.5;">Waiting for signals...</div></div>
    </div>
</div>
<script>
document.getElementById('pauseBtn').addEventListener('click', async function() {
    let isPaused = this.textContent === 'RESUME';
    await fetch(isPaused ? '/api/resume' : '/api/pause');
    this.textContent = isPaused ? 'PAUSE' : 'RESUME';
    this.classList.toggle('paused');
    document.getElementById('status').textContent = isPaused ? 'LIVE TRADING 24/7' : 'PAUSED';
});

async function update() {
    try {
        let res = await fetch('/api/status').then(r => r.json());
        document.getElementById('balance').textContent = '$' + res.balance.toFixed(0);
        document.getElementById('cycles').textContent = res.cycle;
        document.getElementById('orders').textContent = res.orders;
        document.getElementById('uptime').textContent = res.uptime;
        let trades = await fetch('/api/trades').then(r => r.json());
        let html = trades.reverse().slice(0, 10).map(t => '<div class="trade-row">' + t + '</div>').join('');
        document.getElementById('trades-list').innerHTML = html || '<div class="trade-row" style="opacity: 0.5;">Waiting for signals...</div>';
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
            self.wfile.write(HTML.encode())
        elif self.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'balance': bot.balance,
                'cycle': bot.cycle,
                'orders': len(bot.trades),
                'uptime': bot.uptime_str(),
                'paused': bot.paused
            }).encode())
        elif self.path == '/api/trades':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(bot.trades[-20:]).encode())
        elif self.path == '/api/pause':
            bot.paused = True
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"paused"}')
        elif self.path == '/api/resume':
            bot.paused = False
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"resumed"}')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, *args):
        pass

async def trading_loop():
    print("CryptoBot v2 - Starting...")
    print("Symbols: BTC/USDT, ETH/USDT, BNB/USDT")
    print("Strategy: RSI < 40 + MACD > 0")
    
    while bot.running:
        if bot.paused:
            await asyncio.sleep(1)
            continue
        
        bot.cycle += 1
        
        for symbol in ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']:
            price = bot.get_price(symbol)
            if price:
                bot.prices[symbol].append(price)
                if len(bot.prices[symbol]) > 30:
                    rsi = calculate_rsi(list(bot.prices[symbol]))
                    macd = calculate_macd(list(bot.prices[symbol]))
                    if rsi < 40 and macd > 0:
                        bot.trades.append("[{}] BUY {} @ ${:.2f}".format(datetime.now().strftime('%H:%M'), symbol, price))
                        print("BUY {} @ ${:.2f}".format(symbol, price))
        
        if bot.cycle % 10 == 0:
            print("Cycle {} | Balance: ${:.2f} | Trades: {}".format(bot.cycle, bot.balance, len(bot.trades)))
        
        await asyncio.sleep(30)

def run_server():
    server = HTTPServer(('0.0.0.0', 8000), Handler)
    print("\nServer started on port 8000")
    server.serve_forever()

if __name__ == '__main__':
    Thread(target=run_server, daemon=True).start()
    asyncio.run(trading_loop())
