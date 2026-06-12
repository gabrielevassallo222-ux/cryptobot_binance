import asyncio
import json
import requests
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import os

SYMBOL = 'BTCUSDT'
cycle = 0
balance = 1000.0
trades = []
start = datetime.now()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = '<html><body style="background:#1a1a2e;color:#ffd700;font-family:courier;padding:20px"><h1>CryptoBot v3</h1><p>Cycle: '+str(cycle)+'</p><p>Balance: $'+str(balance)+'</p><p>Trades: '+str(len(trades))+'</p></body></html>'
            self.wfile.write(html.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, *args):
        pass

def run_server():
    print("Starting server on port 8000...")
    server = HTTPServer(('0.0.0.0', 8000), Handler)
    server.serve_forever()

async def main():
    global cycle
    print("CryptoBot v3 ULTRA-SIMPLE started!")
    while True:
        cycle += 1
        print("Cycle:", cycle)
        await asyncio.sleep(30)

if __name__ == '__main__':
    Thread(target=run_server, daemon=True).start()
    asyncio.run(main())
