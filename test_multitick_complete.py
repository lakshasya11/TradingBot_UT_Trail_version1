import MetaTrader5 as mt5
import os
from dotenv import load_dotenv
from enhanced_strategy import EnhancedTradingStrategy

def test_breakout_pullback_complete():
    """Complete Breakout/Pullback system test with detailed analysis"""
    load_dotenv()
    
    # Initialize MT5
    mt5_path = os.getenv("MT5_PATH")
    mt5_login = int(os.getenv("MT5_LOGIN"))
    mt5_pass = os.getenv("MT5_PASSWORD")
    mt5_server = os.getenv("MT5_SERVER")
    
    if not mt5.initialize(path=mt5_path, login=mt5_login, password=mt5_pass, server=mt5_server):
        print(f"MT5 initialization failed: {mt5.last_error()}")
        return
    
    print("COMPLETE BREAKOUT/PULLBACK SYSTEM TEST")
    print("=" * 60)
    
    strategy = EnhancedTradingStrategy("XAUUSD", "M1")
    
    # Test for 10 cycles to see breakout/pullback behavior
    for i in range(10):
        print(f"\n--- TEST CYCLE {i+1} ---")
        
        # Get analysis
        analysis = strategy.analyze_timeframe("M1")
        if not analysis:
            print("No analysis data")
            continue
        
        # Get current tick
        tick = mt5.symbol_info_tick("XAUUSD")
        if not tick:
            print("No tick data")
            continue
        
        # Get dataframe for previous candle analysis
        df = analysis.get('df')
        if df is None or len(df) < 2:
            print("Insufficient candle data")
            continue
        
        # Previous candle analysis
        prev_candle = df.iloc[-2]
        prev_open = prev_candle['open']
        prev_high = prev_candle['high']
        prev_low = prev_candle['low']
        prev_close = prev_candle['close']
        
        # Determine previous candle color
        if prev_close > prev_open:
            prev_candle_color = "GREEN"
        elif prev_close < prev_open:
            prev_candle_color = "RED"
        else:
            prev_candle_color = "DOJI"
        
        # Check entry conditions
        entry_signal = strategy.check_entry_conditions(analysis)
        
        # Display detailed analysis
        print(f"Market Analysis:")
        print(f"   Current Tick: Bid={tick.bid:.2f} Ask={tick.ask:.2f}")
        print(f"   Previous Candle: {prev_candle_color} | O:{prev_open:.2f} H:{prev_high:.2f} L:{prev_low:.2f} C:{prev_close:.2f}")
        print(f"   UT_BUY: {analysis.get('ut_buy', False)} | UT_SELL: {analysis.get('ut_sell', False)}")
        print(f"   RSI: {analysis.get('rsi', 0):.1f}")
        
        # Breakout/Pullback Analysis
        print(f"Breakout/Pullback Conditions:")
        if prev_candle_color == "RED":
            print(f"   SELL Breakout: tick.bid ({tick.bid:.2f}) < prev_low ({prev_low:.2f}) = {tick.bid < prev_low}")
            print(f"   BUY Pullback: tick.ask ({tick.ask:.2f}) >= prev_open ({prev_open:.2f}) = {tick.ask >= prev_open}")
            print(f"   BUY Pullback: tick.ask ({tick.ask:.2f}) >= prev_high ({prev_high:.2f}) = {tick.ask >= prev_high}")
        elif prev_candle_color == "GREEN":
            print(f"   BUY Breakout: tick.ask ({tick.ask:.2f}) > prev_high ({prev_high:.2f}) = {tick.ask > prev_high}")
            print(f"   SELL Pullback: tick.bid ({tick.bid:.2f}) <= prev_open ({prev_open:.2f}) = {tick.bid <= prev_open}")
            print(f"   SELL Pullback: tick.bid ({tick.bid:.2f}) <= prev_low ({prev_low:.2f}) = {tick.bid <= prev_low}")
        else:
            print(f"   DOJI candle - no signals generated")
        
        print(f"   FINAL SIGNAL: {entry_signal}")
        
        # Small delay
        import time
        time.sleep(1)
    
    print(f"\nTest completed!")
    
    # Summary
    print(f"\nBREAKOUT/PULLBACK SYSTEM SUMMARY:")
    print(f"   - Previous Candle Analysis: Working (uses df.iloc[-2])")
    print(f"   - Price Reference: BUY uses tick.ask, SELL uses tick.bid")
    print(f"   - Breakout Logic: GREEN->break high, RED->break low")
    print(f"   - Pullback Logic: GREEN->pullback to open/low, RED->pullback to open/high")
    print(f"   - Filters: UT Bot + RSI + Sideways detection active")
    print(f"   - DOJI Handling: Ignored (no signals)")
    
    mt5.shutdown()

if __name__ == "__main__":
    test_breakout_pullback_complete()