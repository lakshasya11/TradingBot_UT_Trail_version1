import MetaTrader5 as mt5
import os
from dotenv import load_dotenv
from enhanced_strategy import EnhancedTradingStrategy

def test_entry_conditions():
    """Test breakout/pullback entry conditions to debug why trades aren't executing"""
    
    load_dotenv()
    
    # MT5 Connection
    mt5_path = os.getenv("MT5_PATH")
    mt5_login = int(os.getenv("MT5_LOGIN"))
    mt5_pass = os.getenv("MT5_PASSWORD")
    mt5_server = os.getenv("MT5_SERVER")
    
    if not mt5.initialize(path=mt5_path, login=mt5_login, password=mt5_pass, server=mt5_server):
        print(f"MT5 initialization failed: {mt5.last_error()}")
        return
    
    symbol = "XAUUSD"
    strategy = EnhancedTradingStrategy(symbol, "M1")
    
    print("=== DEBUGGING BREAKOUT/PULLBACK ENTRY CONDITIONS ===")
    
    # Get current analysis
    analysis = strategy.analyze_timeframe("M1")
    
    if analysis:
        print(f"\nCURRENT ANALYSIS:")
        print(f"RSI: {analysis.get('rsi', 0):.2f}")
        print(f"UT_BUY: {analysis.get('ut_buy', False)}")
        print(f"UT_SELL: {analysis.get('ut_sell', False)}")
        print(f"Close Price: {analysis.get('close', 0):.5f}")
        print(f"Trail Stop: {analysis.get('trail_stop', 0):.5f}")
        print(f"ATR: {analysis.get('atr', 0):.5f}")
        
        # Get current tick
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            print("❌ Failed to get tick data")
            return
        
        print(f"Current Tick: Bid={tick.bid:.2f}, Ask={tick.ask:.2f}")
        
        # Get dataframe for previous candle analysis
        df = analysis.get('df')
        if df is None or len(df) < 2:
            print("❌ Insufficient candle data")
            return
        
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
        
        print(f"\nPREVIOUS CANDLE ANALYSIS:")
        print(f"Color: {prev_candle_color}")
        print(f"Open: {prev_open:.2f}, High: {prev_high:.2f}, Low: {prev_low:.2f}, Close: {prev_close:.2f}")
        
        # Test entry conditions
        signal = strategy.check_entry_conditions(analysis)
        print(f"\nSIGNAL RESULT: {signal}")
        
        # Manual condition check
        rsi = analysis.get('rsi', 50)
        ut_buy = analysis.get('ut_buy', False)
        ut_sell = analysis.get('ut_sell', False)
        
        print(f"\nBREAKOUT/PULLBACK CONDITION CHECK:")
        
        if prev_candle_color == "GREEN":
            print(f"GREEN Candle Conditions:")
            # BUY Breakout
            buy_breakout = tick.ask > prev_high
            print(f"  - BUY Breakout: tick.ask ({tick.ask:.2f}) > prev_high ({prev_high:.2f}) = {buy_breakout} {'✅' if buy_breakout else '❌'}")
            print(f"  - UT_BUY: {ut_buy} {'✅' if ut_buy else '❌'}")
            print(f"  - RSI > 30: {rsi:.1f} > 30 = {rsi > 30} {'✅' if rsi > 30 else '❌'}")
            buy_signal = ut_buy and rsi > 30 and buy_breakout
            print(f"  - BUY SIGNAL: {buy_signal} {'🚀' if buy_signal else '❌'}")
            
            # SELL Pullback
            sell_pullback = tick.bid <= prev_open or tick.bid <= prev_low
            print(f"  - SELL Pullback: tick.bid ({tick.bid:.2f}) <= prev_open ({prev_open:.2f}) OR prev_low ({prev_low:.2f}) = {sell_pullback} {'✅' if sell_pullback else '❌'}")
            print(f"  - UT_SELL: {ut_sell} {'✅' if ut_sell else '❌'}")
            print(f"  - RSI < 70: {rsi:.1f} < 70 = {rsi < 70} {'✅' if rsi < 70 else '❌'}")
            sell_signal = ut_sell and rsi < 70 and sell_pullback
            print(f"  - SELL SIGNAL: {sell_signal} {'🚀' if sell_signal else '❌'}")
            
        elif prev_candle_color == "RED":
            print(f"RED Candle Conditions:")
            # SELL Breakout
            sell_breakout = tick.bid < prev_low
            print(f"  - SELL Breakout: tick.bid ({tick.bid:.2f}) < prev_low ({prev_low:.2f}) = {sell_breakout} {'✅' if sell_breakout else '❌'}")
            print(f"  - UT_SELL: {ut_sell} {'✅' if ut_sell else '❌'}")
            print(f"  - RSI < 70: {rsi:.1f} < 70 = {rsi < 70} {'✅' if rsi < 70 else '❌'}")
            sell_signal = ut_sell and rsi < 70 and sell_breakout
            print(f"  - SELL SIGNAL: {sell_signal} {'🚀' if sell_signal else '❌'}")
            
            # BUY Pullback
            buy_pullback = tick.ask >= prev_open or tick.ask >= prev_high
            print(f"  - BUY Pullback: tick.ask ({tick.ask:.2f}) >= prev_open ({prev_open:.2f}) OR prev_high ({prev_high:.2f}) = {buy_pullback} {'✅' if buy_pullback else '❌'}")
            print(f"  - UT_BUY: {ut_buy} {'✅' if ut_buy else '❌'}")
            print(f"  - RSI > 30: {rsi:.1f} > 30 = {rsi > 30} {'✅' if rsi > 30 else '❌'}")
            buy_signal = ut_buy and rsi > 30 and buy_pullback
            print(f"  - BUY SIGNAL: {buy_signal} {'🚀' if buy_signal else '❌'}")
            
        else:
            print(f"DOJI Candle - No signals generated")
        
        # Check existing positions
        positions = mt5.positions_get(symbol=symbol)
        print(f"\nEXISTING POSITIONS: {len(positions) if positions else 0}")
        
        if signal != "NONE" and not positions:
            print(f"\n>> TRADE SHOULD EXECUTE: {signal}")
        elif signal != "NONE" and positions:
            print(f"\n>> SIGNAL PRESENT BUT POSITION EXISTS: {signal}")
        elif signal == "SIDEWAYS":
            print(f"\n>> MARKET IS SIDEWAYS - TRADES BLOCKED")
        else:
            print(f"\n>> NO TRADE SIGNAL - WAITING FOR CONDITIONS")
            
    else:
        print("❌ Failed to get analysis data")
    
    mt5.shutdown()

if __name__ == "__main__":
    test_entry_conditions()