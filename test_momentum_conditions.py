import MetaTrader5 as mt5
import os
from dotenv import load_dotenv

def test_breakout_pullback_conditions():
    """Test the breakout/pullback conditions to see if they're working"""
    
    # Load environment variables
    load_dotenv()
    
    # Initialize MT5
    mt5_path = os.getenv("MT5_PATH")
    mt5_login = int(os.getenv("MT5_LOGIN"))
    mt5_pass = os.getenv("MT5_PASSWORD")
    mt5_server = os.getenv("MT5_SERVER")
    
    if not mt5.initialize(path=mt5_path, login=mt5_login, password=mt5_pass, server=mt5_server):
        print(f"MT5 initialization failed: {mt5.last_error()}")
        return
    
    symbol = "XAUUSD"
    
    # Get current tick and candle data
    tick = mt5.symbol_info_tick(symbol)
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 3)
    
    if not tick or rates is None or len(rates) < 2:
        print("Failed to get market data")
        mt5.shutdown()
        return
    
    # Previous candle data (df.iloc[-2] equivalent)
    prev_candle = rates[-2]
    prev_open = prev_candle[1]   # open
    prev_high = prev_candle[2]   # high
    prev_low = prev_candle[3]    # low
    prev_close = prev_candle[4]  # close
    
    # Current candle data (for reference)
    current_candle = rates[-1]
    current_open = current_candle[1]
    current_close = current_candle[4]
    
    print("=" * 60)
    print("BREAKOUT/PULLBACK CONDITIONS TEST")
    print("=" * 60)
    print(f"Symbol: {symbol}")
    print(f"Current Tick - Bid: {tick.bid:.2f}, Ask: {tick.ask:.2f}")
    print(f"Previous Candle - Open: {prev_open:.2f}, High: {prev_high:.2f}, Low: {prev_low:.2f}, Close: {prev_close:.2f}")
    print()
    
    # Determine previous candle color
    if prev_close > prev_open:
        prev_candle_color = "GREEN"
    elif prev_close < prev_open:
        prev_candle_color = "RED"
    else:
        prev_candle_color = "DOJI"
    
    print(f"Previous Candle Color: {prev_candle_color}")
    print()
    
    if prev_candle_color == "GREEN":
        print("GREEN CANDLE CONDITIONS:")
        print("-" * 30)
        
        # BUY Breakout: tick.ask > prev_high
        buy_breakout = tick.ask > prev_high
        print(f"BUY Breakout: tick.ask ({tick.ask:.2f}) > prev_high ({prev_high:.2f}) = {buy_breakout}")
        
        # SELL Pullback: tick.bid <= prev_open OR tick.bid <= prev_low
        sell_pullback_open = tick.bid <= prev_open
        sell_pullback_low = tick.bid <= prev_low
        sell_pullback = sell_pullback_open or sell_pullback_low
        
        print(f"SELL Pullback to Open: tick.bid ({tick.bid:.2f}) <= prev_open ({prev_open:.2f}) = {sell_pullback_open}")
        print(f"SELL Pullback to Low: tick.bid ({tick.bid:.2f}) <= prev_low ({prev_low:.2f}) = {sell_pullback_low}")
        print(f"SELL Pullback (OR logic): {sell_pullback}")
        
    elif prev_candle_color == "RED":
        print("RED CANDLE CONDITIONS:")
        print("-" * 30)
        
        # SELL Breakout: tick.bid < prev_low
        sell_breakout = tick.bid < prev_low
        print(f"SELL Breakout: tick.bid ({tick.bid:.2f}) < prev_low ({prev_low:.2f}) = {sell_breakout}")
        
        # BUY Pullback: tick.ask >= prev_open OR tick.ask >= prev_high
        buy_pullback_open = tick.ask >= prev_open
        buy_pullback_high = tick.ask >= prev_high
        buy_pullback = buy_pullback_open or buy_pullback_high
        
        print(f"BUY Pullback to Open: tick.ask ({tick.ask:.2f}) >= prev_open ({prev_open:.2f}) = {buy_pullback_open}")
        print(f"BUY Pullback to High: tick.ask ({tick.ask:.2f}) >= prev_high ({prev_high:.2f}) = {buy_pullback_high}")
        print(f"BUY Pullback (OR logic): {buy_pullback}")
        
    else:
        print("DOJI CANDLE - No signals generated")
    
    print()
    print("SUMMARY:")
    print("-" * 30)
    
    if prev_candle_color == "GREEN":
        if tick.ask > prev_high:
            print("[SIGNAL] BUY Breakout condition is SATISFIED (price broke above previous high)")
        elif tick.bid <= prev_open or tick.bid <= prev_low:
            print("[SIGNAL] SELL Pullback condition is SATISFIED (price pulled back to previous levels)")
        else:
            print("[NO SIGNAL] No breakout/pullback conditions met")
    elif prev_candle_color == "RED":
        if tick.bid < prev_low:
            print("[SIGNAL] SELL Breakout condition is SATISFIED (price broke below previous low)")
        elif tick.ask >= prev_open or tick.ask >= prev_high:
            print("[SIGNAL] BUY Pullback condition is SATISFIED (price pulled back to previous levels)")
        else:
            print("[NO SIGNAL] No breakout/pullback conditions met")
    else:
        print("[NO SIGNAL] DOJI candle - conditions ignored")
    
    print()
    print("ANALYSIS:")
    print("-" * 30)
    
    # Show price distances
    print(f"Price distances from previous candle levels:")
    print(f"  Current ask vs prev_high: {tick.ask - prev_high:+.2f} points")
    print(f"  Current bid vs prev_low: {tick.bid - prev_low:+.2f} points")
    print(f"  Current ask vs prev_open: {tick.ask - prev_open:+.2f} points")
    print(f"  Current bid vs prev_open: {tick.bid - prev_open:+.2f} points")
    
    mt5.shutdown()

if __name__ == "__main__":
    test_breakout_pullback_conditions()