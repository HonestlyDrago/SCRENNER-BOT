import os
import ccxt
import pandas as pd
import time
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# ==========================================
# CONFIGURATION
# ==========================================
EXCHANGE_NAME = 'binance'
TIMEFRAME = '1h'
VOL_SMA_LEN = 50
VOL_MULTIPLIER = 5.0
MA_LEN = 99
SLEEP_MINUTES = 60  # Wait time between scans

# TELEGRAM CREDENTIALS
TELEGRAM_BOT_TOKEN = '8664315850:AAHFWwfLOIXp2wpa6YUmbYF8K_dWypYH1FE'
TELEGRAM_CHAT_ID = '6281492105'

# ==========================================
# DUMMY WEB SERVER (FOR CLOUD HOSTING)
# ==========================================
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot is running 24/7!")

def start_server():
    port = int(os.environ.get("PORT", 7860))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    print(f"\n🌐 Starting dummy web server on port {port}...")
    server.serve_forever()

# ==========================================
# BOT LOGIC
# ==========================================
exchange = getattr(ccxt, EXCHANGE_NAME)({
    'enableRateLimit': True,
})

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

def get_active_usdt_markets():
    print(f"\nFetching markets from {EXCHANGE_NAME.upper()}...")
    markets = exchange.load_markets()
    symbols = [s for s in markets.keys() if s.endswith('/USDT') and markets[s]['active'] and markets[s]['spot']]
    print(f"Found {len(symbols)} active USDT pairs.")
    return symbols

def run_scanner():
    while True:
        symbols = get_active_usdt_markets()
        print(f"\n--- Starting continuous scan cycle at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
        
        for symbol in symbols:
            try:
                ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=150)
                if len(ohlcv) < MA_LEN: continue
                
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['ma_99'] = df['close'].rolling(window=MA_LEN).mean()
                df['vol_sma_50'] = df['volume'].rolling(window=VOL_SMA_LEN).mean()
                
                current = df.iloc[-1]
                prev = df.iloc[-2]
                
                rvol_cond = current['volume'] > (current['vol_sma_50'] * VOL_MULTIPLIER)
                cross_up = (prev['close'] <= prev['ma_99']) and (current['close'] > current['ma_99'])
                trend_cond = cross_up or (current['close'] > current['ma_99'])
                
                if rvol_cond and trend_cond:
                    price = current['close']
                    msg = (
                        f"🚨 <b>VOLUME BREAKOUT ALERT!</b> 🚨\n\n"
                        f"🪙 <b>Coin:</b> {symbol}\n"
                        f"💵 <b>Price:</b> {price}\n"
                        f"📊 <b>Timeframe:</b> {TIMEFRAME}\n"
                        f"📈 <b>Volume Spike:</b> {current['volume']:.2f} (Avg: {current['vol_sma_50']:.2f})"
                    )
                    print(f"BREAKOUT: {symbol} at {price}!")
                    send_telegram_alert(msg)
                    
            except Exception:
                pass # Ignore temporary network errors
            
            time.sleep(0.1) # Rate limit protection
        
        print(f"\nScan cycle complete! Sleeping for {SLEEP_MINUTES} minutes before the next scan...")
        time.sleep(SLEEP_MINUTES * 60)

if __name__ == "__main__":
    print(f"===== Application Startup at {time.strftime('%Y-%m-%d %H:%M:%S')} =====")
    # Start the dummy web server in a background thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Run the continuous scanner
    run_scanner()
