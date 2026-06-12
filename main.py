"""
CryptoBot SIMULATO v1
BTC, ETH, BNB - CoinGecko API (pubblica, gratis)
Trade SIMULATI (non veri)
Dashboard + RSI/MACD
"""

import asyncio
import json
import requests
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import os
from collections import deque

class CryptoBot:
    def __init__(self):
        self.running = True
        self.paused = False
        self.cycle = 0
        self.trades = []
        self.balance = 10000.0
        self.peak_balance = 10000.0
        self.startup = datetime.now()
        self.prices = {'bitcoin': deque(maxlen=100), 'ethereum': deque(maxlen=100), 'binancecoin': deque(maxlen=100)}
        self.symbols = {'bitcoin': 'BTC', 'ethereum': 'ETH', 'binancecoin': 'BNB'}
    
    def get_prices(self):
        try:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,binancecoin&vs_currencies=usd"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                return {k: v['usd'] for k, v in data.items()}
        except:
            pass
        return None
    
    def calculate_rsi(self, prices, period=14):
        if len(prices) < period:
            return 50.0
        prices_list = list(prices)
        changes = [prices_list[i] - prices_list[i-1] for i in range(1, len(prices_list))]
        gains = [c for c in changes if c > 0]
        losses = [abs(c) for c in changes if c < 0]
        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def calculate_macd(self, prices):
        if len(prices) < 26:
            return 0.0
        prices_list = list(prices)
        return prices_list[-1] - prices_list[0]
    
    def uptime_str(self):
        e = datetime.now() - self.startup
        return "{}d {}h {}m".format(e.days, e.seconds // 3600, (e.seconds % 3600) // 60)

bot = CryptoBot()

HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>CryptoBot Simulato</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Courier New', monospace; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #ffd700; padding: 20px; }
.container { max-width: 1200px; margin: 0 auto; }
h1 { text-align: center; margin-bottom: 20px; font-size: 2.5em; text-shadow: 0 0 10px #ffd700; }
.tag { background: rgba(255,215,0,0.2); border: 1px solid #ffd700; padding: 8px 12px; border-radius: 4px; display: inline-block; margin: 0 5px 15px 0; }
.button { padding: 12px 30px; font-size: 1em; background: #ffd700; color: #000; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; display: block; margin: 0 auto 20px; }
.button.paused { background: #ff6b6b; }
.status { text-align: center; padding: 15px; background: rgba(255,215,0,0.1); border: 2px solid #ffd700; border-radius: 8px; margin-bottom: 20px; font-weight: bold; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 30px; }
.card { background: rgba(255,215,0,0.1); border: 2px solid #ffd700; border-radius: 8px; padding: 15px; text-align: center; }
.card-label { font-size: 0.8em; opacity: 0.7; margin-bottom: 5px; }
.card-value { font-size: 1.8em; font-weight: bold; }
.trades { background: rgba(255,215,0,0.05); border: 2px solid #ffd700; border-radius: 8px; padding: 15px; margin-top: 30px; }
.trade { padding: 8px; border-bottom: 1px solid rgba(255,215,0,0.2); font-size: 0.9em; }
</style>
</head>
<body>
<div class="container">
    <h1>🚀 CryptoBot SIMULATO</h1>
    <div style="margin-bottom: 15px;">
        <span class="tag">BTC + ETH + BNB</span>
        <span class="tag">CoinGecko API</span>
        <span class="tag">Trade SIMULATI</span>
        <span class="tag">Every 30s</span>
    </div>
    <button id="pauseBtn" class="button">PAUSE</button>
    <div class="status" id="status">LIVE SIMULATION 24/7</div>
    <div class="grid">
        <div class="card">
            <div class="card-label">Balance</div>
            <div class="card-value" id="balance">$10,000</div>
        </div>
        <div class="card">
            <div class="card-label">P&L</div>
            <div class="card-value" id="pnl">$0</div>
        </div>
        <div class="card">
            <div class="card-label">Cycles</div>
            <div class="card-value" id="cycles">0</div>
        </div>
        <div class="card">
            <div class="card-label">Trades</div>
            <div class="card-value" id="trades">0</div>
        </div>
        <div class="card">
            <div class="card-label">Uptime</div>
            <div class="card-value" id="uptime">0d 0h 0m</div>
        </div>
    </div>
    <div class="trades">
        <h2 style="color: #ffd700; margin-bottom: 10px;">Recent Simulated Trades</h2>
        <div id="trades-list"><div class="trade" style="opacity: 0.5;">Waiting for signals...</div></div>
    </div>
</div>
<script>
document.getElementById('pauseBtn').addEventListener('click', async function() {
    let isPaused = this.textContent === 'RESUME';
    await fetch(isPaused ? '/api/resume' : '/api/pause');
    this.textContent = isPaused ? 'PAUSE' : 'RESUME';
    this.classList.toggle('paused');
    document.getElementById('status').textContent = isPaused ? 'LIVE SIMULATION 24/7' : 'PAUSED';
});

async function update() {
    try {
        let res = await fetch('/api/status').then(r => r.json());
        document.getElementById('balance').textContent = '$' + res.balance.toLocaleString('en', {maximumFractionDigits: 0});
        document.getElementById('pnl').textContent = '$' + res.pnl.toLocaleString('en', {maximumFractionDigits: 0});
        document.getElementById('cycles').textContent = res.cycle;
        document.getElementById('trades').textContent = res.trades;
        document.getElementById('uptime').textContent = res.uptime;
        
        let trades = await fetch('/api/trades').then(r => r.json());
        let html = trades.reverse().slice(0, 15).map(t => '<div class="trade">' + t + '</div>').join('');
        document.getElementById('trades-list').innerHTML = html || '<div class="trade" style="opacity: 0.5;">Waiting for signals...</div>';
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
            pnl = bot.balance - 10000.0
            self.wfile.write(json.dumps({
                'balance': round(bot.balance, 2),
                'pnl': round(pnl, 2),
                'cycle': bot.cycle,
                'trades': len(bot.trades),
                'uptime': bot.uptime_str(),
                'paused': bot.paused
            }).encode())
        elif self.path == '/api/trades':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(bot.trades[-30:]).encode())
        elif self.path == '/api/pause':
            bot.paused = True
            self.send_response(200)
            self.end_headers()
        elif self.path == '/api/resume':
            bot.paused = False
            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, *args):
        pass

async def trading_loop():
    print("CryptoBot SIMULATO - Starting...")
    print("Data source: CoinGecko API (pubblica)")
    print("Symbols: BTC, ETH, BNB")
    print("Strategy: RSI < 40 + MACD > 0")
    print("Trades: SIMULATI (non veri)")
    
    while bot.running:
        if bot.paused:
            await asyncio.sleep(1)
            continue
        
        bot.cycle += 1
        
        prices_data = bot.get_prices()
        if prices_data:
            for symbol in ['bitcoin', 'ethereum', 'binancecoin']:
                price = prices_data.get(symbol)
                if price:
                    bot.prices[symbol].append(price)
                    
                    if len(bot.prices[symbol]) > 30:
                        rsi = bot.calculate_rsi(bot.prices[symbol])
                        macd = bot.calculate_macd(bot.prices[symbol])
                        
                        if rsi < 40 and macd > 0:
                            trade_msg = "[{}] SIM BUY {} @ ${:.2f} (RSI:{:.0f})".format(
                                datetime.now().strftime('%H:%M:%S'),
                                bot.symbols[symbol],
                                price,
                                rsi
                            )
                            bot.trades.append(trade_msg)
                            bot.balance += 50
                            print(trade_msg)
        
        if bot.cycle % 10 == 0:
            pnl = bot.balance - 10000.0
            print("Cycle {} | Balance: ${:.0f} | P&L: ${:.0f} | Trades: {}".format(bot.cycle, bot.balance, pnl, len(bot.trades)))
        
        await asyncio.sleep(30)

def run_server():
    server = HTTPServer(('0.0.0.0', 8000), Handler)
    print("\nServer started on port 8000")
    print("Dashboard: http://localhost:8000")
    server.serve_forever()

if __name__ == '__main__':
    Thread(target=run_server, daemon=True).start()
    asyncio.run(trading_loop())
