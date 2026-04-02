import MetaTrader5 as mt5
import pandas as pd
import os
from dotenv import load_dotenv
from enhanced_strategy import EnhancedTradingStrategy
from datetime import datetime

def diagnostic_check():
    load_dotenv()
    
    # Connection details
    mt5_path = os.getenv("MT5_PATH")
    mt5_login = int(os.getenv("MT5_LOGIN"))
    mt5_pass = os.getenv("MT5_PASSWORD")
    mt5_server = os.getenv("MT5_SERVER")
    
    # Initialize MT5
    if not mt5.initialize(path=mt5_path, login=mt5_login, password=mt5_pass, server=mt5_server):
        print(f"❌ MT5 Initialization failed: {mt5.last_error()}")
        return

    print("✅ MT5 Connected Successfully")
    
    symbol = "XAUUSD"
    timeframe = "M5"
    strategy = EnhancedTradingStrategy(symbol, timeframe)
    
    # Fetch and calculate indicators
    analysis = strategy.analyze_timeframe(timeframe)
    
    if not analysis:
        print(f"❌ Failed to fetch data for {symbol}")
        mt5.shutdown()
        return

    print(f"\n--- Diagnostic for {symbol} ({timeframe}) ---")
    print(f"Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Current Price: {analysis.get('close'):.5f}")
    
    # Check RSI (14, Wilder's)
    rsi = analysis.get('rsi')
    print(f"RSI (14): {rsi:.2f} {'(OK)' if rsi else '(FAIL)'}")
    
    # Check EMAs (9, 21)
    ema9 = analysis.get('ema9')
    ema21 = analysis.get('ema21')
    print(f"EMA 9: {ema9:.5f}")
    print(f"EMA 21: {ema21:.5f}")
    print(f"EMA Trend: {'BULLISH' if ema9 > ema21 else 'BEARISH'}")
    
    # Check SuperTrend (10, 0.9)
    st_val = analysis.get('supertrend_value')
    st_dir = analysis.get('supertrend_direction')
    st_dir_text = "BULLISH" if st_dir == 1 else "BEARISH"
    print(f"SuperTrend (10, 0.9): {st_val:.5f} ({st_dir_text})")
    
    # Check Signal Logic
    signal = strategy.check_entry_conditions(analysis)
    print(f"\nFinal Entry Signal: {signal}")
    
    mt5.shutdown()

if __name__ == "__main__":
    diagnostic_check()
