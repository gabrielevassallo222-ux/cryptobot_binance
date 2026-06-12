"""
CryptoBot v1 - BINANCE TESTNET
Trada su BTC/USDT, ETH/USDT, BNB/USDT
Strategia: RSI < 40 + MACD > 0 (2 SEGNALI)
Stop Loss: -1% | Take Profit: +1%
Trade ogni 30 secondi - 24/7
Railway Version con PAUSE Button
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

BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_SECRET_KEY = os.getenv('BINANCE_SECRET_KEY')
BINANCE_TESTNET_URL = "https://testnet.binance.vision/api"

def calculate_rsi(prices, period=14):
    if len(prices) < period:
        return 50.0
    changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [c for c in changes if c > 0]
    losses = [abs(c) for c in changes if c < 0]
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_macd(prices, fast=12, slow=26):
    if len(prices) < slow:
        return 0.0, 0.0
    ema_fast = prices[-1]
    for i in range(1, min(len(prices), fast)):
        ema_fast = ema_fast * (2/(fast+1)) + prices[-(i+1)] * (1 - 2/(fast+1))
    ema_slow = prices[-1]
    for i in range(1, min(len(prices), slow)):
        ema_slow = ema_slow * (2/(slow+1)) + prices[-(i+1)] * (1 - 2/(slow+1))
    return ema_fast - ema_slow, ema_fast

def calculate_sma(prices, period=20):
    if len(prices) < period:
        return prices[-1]
    return sum(prices[-period:]) / period

class CryptoPosition:
    def __init__(self, symbol, qty, side, entry_price, entry_time):
        self.symbol = symbol
        self.qty = qty
        self.side = side
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.stop_loss = entry_price * 0.99 if side == 'buy' else entry_price * 1.01
        self.take_profit = entry_price * 1.01 if side == 'buy' else entry_price * 0.99
        self.current_price = entry_price
        self.closed = False
        self.close_reason = None
        self.pnl = 0.0
    
    def update_price(self, current_price):
        self.current_price = current_price
        if self.side == 'buy':
            self.pnl = (current_price - self.entry_price) * self.qty
            if current_price <= self.stop_loss:
                self.closed = True
                self.close_reason = "STOP LOSS (-1%)"
                return 'stop_loss'
            if current_price >= self.take_profit:
                self.closed = True
                self.close_reason = "TAKE PROFIT (+1%)"
                return 'take_profit'
        return None

class CryptoTradingBot:
    def __init__(self):
        self.api_key = BINANCE_API_KEY
        self.secret_key = BINANCE_SECRET_KEY
        self.base_url = BINANCE_TESTNET_URL
        self.running = True
        self.paused = False
        self.cycle = 0
        self.trades_placed = []
        self.initial_capital = 1000.0
        self.current_balance = 1000.0
        self.peak_balance = 1000.0
        self.startup_time = datetime.now()
        self.price_history = {
            'BTCUSDT': deque(maxlen=100),
            'ETHUSDT': deque(maxlen=100),
            'BNBUSDT': deque(maxlen=100)
        }
        self.open_positions = []
        self.drawdown_threshold = -10.0
    
    def get_headers(self):
        return {
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/json"
        }
    
    def get_server_time(self):
        try:
            url = "{}/v3/time".format(self.base_url)
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return int(response.json()['serverTime'])
        except:
            pass
        return int(time.time() * 1000)
    
    def create_signature(self, query_string):
        return hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def get_account(self):
        try:
            timestamp = self.get_server_time()
            query_string = "timestamp={}".format(timestamp)
            signature = self.create_signature(query_string)
            
            url = "{}/v3/account?{}&signature={}".format(self.base_url, query_string, signature)
            response = requests.get(url, headers=self.get_headers(), timeout=10)
            if response.status_code == 200:
                account = response.json()
                self.current_balance = float(account.get('totalWalletBalance', self.current_balance))
                if self.current_balance > self.peak_balance:
                    self.peak_balance = self.current_balance
                return account
        except:
            pass
        return None
    
    def get_last_price(self, symbol):
        try:
            url = "{}/v3/ticker/price?symbol={}".format(self.base_url, symbol)
            response = requests.get(url, headers=self.get_headers(), timeout=10)
            if response.status_code == 200:
                return float(response.json()['price'])
        except:
            pass
        return None
    
    def get_klines(self, symbol, interval='1m', limit=100):
        try:
            url = "{}/v3/klines?symbol={}&interval={}&limit={}".format(self.base_url, symbol, interval, limit)
            response = requests.get(url, headers=self.get_headers(), timeout=10)
            if response.status_code == 200:
                klines = response.json()
                return [float(k[4]) for k in klines]
        except:
            pass
        return []
    
    def place_order(self, symbol, quantity, side):
        try:
            timestamp = self.get_server_time()
            query_string = "symbol={}&side={}&type=MARKET&quantity={}&timestamp={}".format(symbol, side.upper(), quantity, timestamp)
            signature = self.create_signature(query_string)
            
            url = "{}/v3/order?{}&signature={}".format(self.base_url, query_string, signature)
            response = requests.post(url, headers=self.get_headers(), timeout=10)
            if response.status_code == 200:
                order = response.json()
                avg_price = float(order.get('cummulativeQuoteQty', 0)) / float(order.get('executedQty', 1)) if float(order.get('executedQty', 0)) > 0 else 0
                
                if avg_price > 0:
                    position = CryptoPosition(symbol, quantity, side, avg_price, datetime.now())
                    self.open_positions.append(position)
                    self.trades_placed.append({'symbol': symbol, 'qty': quantity, 'side': side, 'price': avg_price, 'time': datetime.now().strftime('%H:%M:%S'), 'reason': 'Entry'})
                    return avg_price
        except:
            pass
        return None
    
    def close_position(self, position):
        try:
            close_side = 'SELL' if position.side == 'BUY' else 'BUY'
            entry_price = self.place_order(position.symbol, position.qty, close_side)
            if entry_price:
                position.close_price = entry_price
                position.closed = True
                self.trades_placed.append({'symbol': position.symbol, 'qty': position.qty, 'side': close_side, 'price': entry_price, 'time': datetime.now().strftime('%H:%M:%S'), 'reason': position.close_reason, 'pnl': position.pnl})
                return True
        except:
            pass
        return False
    
    def update_positions(self):
        for symbol in ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']:
            klines = self.get_klines(symbol)
            if klines:
                self.price_history[symbol].extend(klines[-5:])
        
        closed_count = 0
        for position in self.open_positions:
            if not position.closed:
                price = self.get_last_price(position.symbol)
                if price:
                    exit_type = position.update_price(price)
                    if exit_type:
                        self.close_position(position)
                        closed_count += 1
        return closed_count
    
    def calculate_indicators(self, symbol):
        if len(self.price_history[symbol]) < 20:
            return None, None, None
        prices = list(self.price_history[symbol])
        rsi = calculate_rsi(prices)
        macd, _ = calculate_macd(prices)
        sma = calculate_sma(prices)
        return rsi, macd, sma
    
    def should_buy(self, symbol):
        rsi, macd, sma = self.calculate_indicators(symbol)
        if rsi is None:
            return False
        return rsi < 40 and macd > 0
    
    def calculate_drawdown(self):
        if self.peak_balance == 0:
            return 0.0
        return ((self.current_balance - self.peak_balance) / self.peak_balance) * 100
    
    def calculate_pnl_dollars(self):
        return self.current_balance - self.initial_capital
    
    def get_uptime(self):
        elapsed = datetime.now() - self.startup_time
        return "{}d {}h {}m".format(elapsed.days, elapsed.seconds // 3600, (elapsed.seconds % 3600) // 60)

bot = CryptoTradingBot()

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>CryptoBot v1 - Binance Testnet</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Courier New', monospace; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #00ff88; padding: 20px; }
.container { max-width: 1400px; margin: 0 auto; }
h1 { text-align: center; margin-bottom: 20px; font-size: 2.5em; text-shadow: 0 0 10px #ffd700; color: #ffd700; }
.status { text-align: center; padding: 15px; background: rgba(255,215,0,0.1); border: 2px solid #ffd700; border-radius: 8px; margin-bottom: 20px; font-weight: bold; color: #ffd700; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
.card { background: rgba(255,215,0,0.1); border: 2px solid #ffd700; border-radius: 8px; padding: 20px; text-align: center; }
.card-label { font-size: 0.8em; opacity: 0.7; text-transform: uppercase; margin-bottom: 10px; color: #ffd700; }
.card-value { font-size: 2em; font-weight: bold; }
.positive { color: #00ff88; }
.negative { color: #ff6b6b; }
.trades-box { background: rgba(255,215,0,0.05); border: 2px solid #ffd700; border-radius: 8px; padding: 20px; margin-top: 30px; }
.trade { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr 1fr; gap: 10px; padding: 10px; border-bottom: 1px solid rgba(255,215,0,0.2); font-size: 0.85em; }
.tag { background: rgba(255,215,0,0.2); border: 2px solid #ffd700; padding: 8px 12px; border-radius: 4px; display: inline-block; color: #ffd700; font-weight: bold; margin: 0 10px 20px 0; }
.pause-btn { padding: 12px 30px; font-size: 1.1em; background: #ffd700; color: #000; border: 2px solid #ffd700; border-radius: 5px; cursor: pointer; font-weight: bold; text-transform: uppercase; transition: all 0.3s; }
.pause-btn:hover { opacity: 0.8; }
.pause-btn.paused { background: #ff6b6b; border-color: #ff6b6b; }
</style>
</head>
<body>
<div class="container">
    <h1>🚀 CryptoBot v1 - Binance Testnet</h1>
    <div style="margin-bottom: 20px;">
        <span class="tag">BTC + ETH + BNB</span>
        <span class="tag">Trade ogni 30 sec</span>
        <span class="tag">RSI < 40 + MACD > 0</span>
    </div>
    <div style="text-align: center; margin-bottom: 20px;">
        <button id="pauseBtn" class="pause-btn">PAUSE</button>
    </div>
    <div class="status" id="status">LIVE TRADING - CRYPTO 24/7</div>
    <div class="grid">
        <div class="card">
            <div class="card-label">Balance (USDT)</div>
            <div class="card-value" id="balance">$0.00</div>
        </div>
        <div class="card">
            <div class="card-label">P&L</div>
            <div class="card-value" id="pnl">$0.00</div>
        </div>
        <div class="card">
            <div class="card-label">Open Positions</div>
            <div class="card-value" id="open_count">0</div>
        </div>
        <div class="card">
            <div class="card-label">Total Orders</div>
            <div class="card-value" id="orders">0</div>
        </div>
        <div class="card">
            <div class="card-label">Cycles</div>
            <div class="card-value" id="cycle">0</div>
        </div>
        <div class="card">
            <div class="card-label">Uptime</div>
            <div class="card-value positive" id="uptime">0d 0h 0m</div>
        </div>
    </div>
    <div class="trades-box">
        <h2 style="color: #ffd700;">Recent Trades (Last 15)</h2>
        <div class="trade" style="font-weight: bold; border-bottom: 2px solid #ffd700; color: #ffd700;">
            <div>SYMBOL</div><div>SIDE</div><div>PRICE</div><div>REASON</div><div>TIME</div>
        </div>
        <div id="trades-list"></div>
    </div>
</div>
<script>
document.getElementById('pauseBtn').addEventListener('click', async function() {
    let isPaused = this.textContent === 'RESUME';
    let endpoint = isPaused ? '/api/resume' : '/api/pause';
    await fetch(endpoint);
    this.textContent = isPaused ? 'PAUSE' : 'RESUME';
    this.classList.toggle('paused');
    document.getElementById('status').textContent = isPaused ? 'LIVE TRADING - CRYPTO 24/7' : 'PAUSED - NO NEW TRADES';
});

async function update() {
    let res = await fetch('/api/status').then(r => r.json());
    document.getElementById('balance').textContent = '$' + res.balance.toFixed(2);
    document.getElementById('pnl').textContent = '$' + res.pnl_dollars.toFixed(2);
    document.getElementById('open_count').textContent = res.open_count;
    document.getElementById('orders').textContent = res.orders_count;
    document.getElementById('cycle').textContent = res.cycle;
    document.getElementById('uptime').textContent = res.uptime;
    let trades = await fetch('/api/trades').then(r => r.json());
    let html = trades.reverse().slice(0, 15).map(t => '<div class="trade"><div>' + t.symbol + '</div><div>' + t.side + '</div><div>$' + t.price.toFixed(2) + '</div><div>' + (t.reason || 'Trade') + '</div><div>' + t.time + '</div></div>').join('');
    document.getElementById('trades-list').innerHTML = html || '<div style="text-align:center;opacity:0.5;padding:20px;">No orders yet</div>';
}
update();
setInterval(update, 1000);
</script>
</body>
</html>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode('utf-8'))
        elif self.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            pnl_dollars = bot.calculate_pnl_dollars()
            open_pnl = sum(p.pnl for p in bot.open_positions if not p.closed)
            open_count = len([p for p in bot.open_positions if not p.closed])
            data = {
                'balance': round(bot.current_balance, 2),
                'pnl_dollars': round(pnl_dollars, 2),
                'open_pnl': round(open_pnl, 2),
                'open_count': open_count,
                'orders_count': len(bot.trades_placed),
                'cycle': bot.cycle,
                'uptime': bot.get_uptime(),
                'paused': bot.paused
            }
            self.wfile.write(json.dumps(data).encode())
        elif self.path == '/api/trades':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(bot.trades_placed).encode())
        elif self.path == '/api/pause':
            bot.paused = True
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'paused'}).encode())
        elif self.path == '/api/resume':
            bot.paused = False
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'resumed'}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, *args):
        pass

async def trading_loop():
    print("\n" + "="*70)
    print("CRYPTOBOT v1 - BINANCE TESTNET")
    print("="*70)
    print("\nStrategy: RSI < 40 + MACD > 0 (2 SIGNALS)")
    print("Symbols: BTC/USDT, ETH/USDT, BNB/USDT")
    print("Trade every 30 seconds - 24/7")
    print("Stop Loss: -1% | Take Profit: +1%\n")
    
    while bot.running:
        if bot.paused:
            await asyncio.sleep(1)
            continue
        
        bot.cycle += 1
        bot.get_account()
        closed = bot.update_positions()
        if closed > 0:
            print("Cycle {}: Closed {} positions".format(bot.cycle, closed))
        
        for symbol in ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']:
            has_open = any(p.symbol == symbol and not p.closed for p in bot.open_positions)
            if not has_open and bot.should_buy(symbol):
                try:
                    qty = 0.001
                    entry_price = bot.place_order(symbol, qty, 'BUY')
                    if entry_price:
                        rsi, macd, sma = bot.calculate_indicators(symbol)
                        print("Cycle {}: BUY {} @ ${:.2f} (RSI: {:.1f}, MACD: {:.3f})".format(bot.cycle, symbol, entry_price, rsi, macd))
                except:
                    pass
        
        if bot.cycle % 4 == 0:
            pnl = bot.calculate_pnl_dollars()
            open_count = len([p for p in bot.open_positions if not p.closed])
            print("Cycle {} | Balance: ${:.2f} | P&L: ${:.2f} | Open: {} | Orders: {}".format(bot.cycle, bot.current_balance, pnl, open_count, len(bot.trades_placed)))
        
        await asyncio.sleep(30)

def run_server():
    server = HTTPServer(('0.0.0.0', 8000), Handler)
    print('\n' + '='*70)
    print('CRYPTOBOT v1 ONLINE ON RAILWAY - BINANCE TESTNET')
    print('='*70 + '\n')
    server.serve_forever()

if __name__ == '__main__':
    Thread(target=run_server, daemon=True).start()
    asyncio.run(trading_loop())
