import os
import ccxt
import pandas as pd
import time
import requests

# ==========================================
# CONFIGURATION
# ==========================================
EXCHANGE_NAME = 'mexc'  # MEXC bypasses geo-blocks
TIMEFRAME = '1h'
VOL_SMA_LEN = 50
VOL_MULTIPLIER = 5.0
MA_LEN = 99

# TELEGRAM CREDENTIALS
TELEGRAM_BOT_TOKEN = '8664315850:AAHFWwfLOIXp2wpa6YUmbYF8K_dWypYH1FE'
TELEGRAM_CHAT_ID = '6281492105'

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
    print("Fetching markets...")
    markets = exchange.load_markets()
    symbols = [s for s in markets.keys() if s.endswith('/USDT') and markets[s]['active'] and markets[s]['spot']]
    print(f"Found {len(symbols)} active USDT pairs.")
    return symbols

def run_scanner():
    symbols = get_active_usdt_markets()
    print(f"\n--- Starting scan cycle at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
    
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
            pass # Ignore temporary network errors for individual coins
        
        # Rate limit protection
        time.sleep(0.1)
    
    print("\nScan cycle complete! GitHub Actions will run this again in 1 hour.")

if __name__ == "__main__":
    run_scanner()
