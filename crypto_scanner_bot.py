import os
import certifi
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
os.environ['CURL_CA_BUNDLE'] = certifi.where()
os.environ['SSL_CERT_FILE'] = certifi.where()

import ccxt
import pandas as pd
import time
import requests
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==========================================
# DUMMY SERVER FOR RENDER (Keeps the Free Tier happy)
# ==========================================
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    print(f"🌐 Starting dummy web server on port {port}...")
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()

# ==========================================
# CONFIGURATION
# ==========================================
EXCHANGE_NAME = 'binance'  # e.g., 'binance', 'bybit', 'kucoin'
TIMEFRAME = '1h'           # Chart timeframe (e.g., '15m', '1h', '4h')
VOL_SMA_LEN = 50           # Volume Moving Average Length
VOL_MULTIPLIER = 5.0       # How many times larger the volume needs to be
MA_LEN = 99                # Price Moving Average Length

# ⚠️ ENTER YOUR TELEGRAM BOT CREDENTIALS HERE
TELEGRAM_BOT_TOKEN = '8664315850:AAHFWwfLOIXp2wpa6YUmbYF8K_dWypYH1FE'
TELEGRAM_CHAT_ID = '6281492105'

# ==========================================
# INITIALIZE EXCHANGE
# ==========================================
# enableRateLimit is crucial to avoid getting banned by the exchange
exchange = getattr(ccxt, EXCHANGE_NAME)({
    'enableRateLimit': True,
})

def send_telegram_alert(message):
    """Sends a message to your Telegram app."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID, 
        'text': message, 
        'parse_mode': 'HTML'
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

def get_active_usdt_markets():
    """Fetches all active USDT trading pairs on the exchange."""
    print("Fetching markets...")
    markets = exchange.load_markets()
    # Filter for active spot markets paired with USDT
    symbols = [
        s for s in markets.keys() 
        if s.endswith('/USDT') and markets[s]['active'] and markets[s]['spot']
    ]
    print(f"Found {len(symbols)} active USDT pairs to scan.")
    return symbols

def run_scanner():
    symbols = get_active_usdt_markets()
    
    # Keep track of alerts to avoid spamming the same coin in the same hour
    alerted_candles = set()

    print("Starting the crypto market scanner...")
    send_telegram_alert("🤖 <b>Bot Status: ONLINE</b>\n\nThe Crypto Volume Scanner has successfully connected to the exchange and is now scanning the markets for breakouts!")
    
    while True:
        print(f"\n--- Starting new scan cycle at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
        
        for symbol in symbols:
            try:
                # Fetch recent historical data (limit to 150 to ensure we have enough data for MA 99)
                ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=150)
                
                # Skip newly listed coins that don't have enough data
                if len(ohlcv) < MA_LEN:
                    continue
                    
                # Convert data to a pandas DataFrame
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                
                # Calculate indicators using standard pandas
                df['ma_99'] = df['close'].rolling(window=MA_LEN).mean()
                df['vol_sma_50'] = df['volume'].rolling(window=VOL_SMA_LEN).mean()
                
                # Get the current (live) candle and the previous closed candle
                current = df.iloc[-1]
                prev = df.iloc[-2]
                
                # ----------------------------------------
                # CONDITION LOGIC
                # ----------------------------------------
                # 1. RVOL Condition
                rvol_cond = current['volume'] > (current['vol_sma_50'] * VOL_MULTIPLIER)
                
                # 2. Trend Condition (Crossover OR already above)
                cross_up = (prev['close'] <= prev['ma_99']) and (current['close'] > current['ma_99'])
                trend_cond = cross_up or (current['close'] > current['ma_99'])
                
                # ----------------------------------------
                # ALERT TRIGGER
                # ----------------------------------------
                if rvol_cond and trend_cond:
                    # Create a unique key for this specific candle so we only alert once per candle per coin
                    alert_key = f"{symbol}_{current['timestamp']}"
                    
                    if alert_key not in alerted_candles:
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
                        
                        # Add to alerted list
                        alerted_candles.add(alert_key)
                        
            except Exception as e:
                pass # Suppress errors for individual coins (e.g. temporary connection issues)
            
            # Built-in rate limiting sleep (prevent API bans)
            time.sleep(0.1)
            
        print("Scan cycle complete. Resting for 3 minutes...")
        
        # Prevent memory leaks by clearing alerts that are older than our timeframe
        if len(alerted_candles) > 1000:
            alerted_candles.clear()
            
        # Wait before scanning the market again
        time.sleep(180)

if __name__ == "__main__":
    run_scanner()
