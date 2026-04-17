"""
Entry Diagnostic Tool - Debug why trades are not taken
"""
import MetaTrader5 as mt5
from enhanced_strategy import EnhancedTradingStrategy
import time

def diagnose_entry_conditions(symbol="XAUUSD", timeframe="M1"):
    """Comprehensive entry condition diagnostics"""
    
    strategy = EnhancedTradingStrategy(symbol, timeframe)
    
    print("🔍 ENTRY DIAGNOSTIC TOOL")
    print("=" * 50)
    
    # Get current analysis
    analysis = strategy.analyze_timeframe(timeframe)
    if not analysis:
        print("❌ CRITICAL: Analysis failed - no data returned")
        return
    
    # Check each condition step by step
    print("\n📊 CURRENT MARKET DATA:")
    print(f"   Price: {analysis.get('close', 0):.2f}")
    print(f"   UT Trail: {analysis.get('trail_stop', 0):.2f}")
    print(f"   RSI: {analysis.get('rsi', 0):.1f}")
    print(f"   Candle: {analysis.get('candle_color', 'UNKNOWN')}")
    print(f"   UT_Buy: {analysis.get('ut_buy', False)}")
    print(f"   UT_Sell: {analysis.get('ut_sell', False)}")
    
    # Check positions
    positions = mt5.positions_get(symbol=symbol)
    print(f"\n🏦 POSITION CHECK:")
    print(f"   Existing positions: {len(positions) if positions else 0}")
    if positions:
        print("   ❌ BLOCKED: Already in position")
        return
    
    # Check sideways market
    ut_trail_array = analysis.get('ut_trail_array', [])
    if len(ut_trail_array) >= 10:
        recent_trail = ut_trail_array[-10:]
        trail_range = max(recent_trail) - min(recent_trail)
        is_sideways = trail_range < 0.5
        print(f"\n📈 SIDEWAYS FILTER:")
        print(f"   UT Trail range (10 candles): {trail_range:.3f}")
        print(f"   Threshold: 0.5")
        print(f"   Is sideways: {is_sideways}")
        if is_sideways:
            print("   ❌ BLOCKED: Market is sideways")
            return
    
    # Check BUY conditions
    print(f"\n🟢 BUY CONDITIONS:")
    ut_buy = analysis.get('ut_buy', False)
    rsi = analysis.get('rsi', 0)
    candle_color = analysis.get('candle_color', '')
    
    print(f"   1. UT_Buy (price > trail): {ut_buy} {'✅' if ut_buy else '❌'}")
    print(f"   2. RSI > 30: {rsi:.1f} > 30 = {rsi > 30} {'✅' if rsi > 30 else '❌'}")
    print(f"   3. Green candle: {candle_color} = {candle_color == 'GREEN'} {'✅' if candle_color == 'GREEN' else '❌'}")
    
    buy_signal = ut_buy and rsi > 30 and candle_color == 'GREEN'
    print(f"   BUY SIGNAL: {buy_signal} {'🚀' if buy_signal else '❌'}")
    
    # Check SELL conditions
    print(f"\n🔴 SELL CONDITIONS:")
    ut_sell = analysis.get('ut_sell', False)
    
    print(f"   1. UT_Sell (price < trail): {ut_sell} {'✅' if ut_sell else '❌'}")
    print(f"   2. RSI < 70: {rsi:.1f} < 70 = {rsi < 70} {'✅' if rsi < 70 else '❌'}")
    print(f"   3. Red candle: {candle_color} = {candle_color == 'RED'} {'✅' if candle_color == 'RED' else '❌'}")
    
    sell_signal = ut_sell and rsi < 70 and candle_color == 'RED'
    print(f"   SELL SIGNAL: {sell_signal} {'🚀' if sell_signal else '❌'}")
    
    # Check volume calculation
    if buy_signal or sell_signal:
        print(f"\n💰 VOLUME CHECK:")
        tick = mt5.symbol_info_tick(symbol)
        if tick:
            entry_price = tick.ask if buy_signal else tick.bid
            volume = strategy.calculate_dynamic_volume(entry_price)
            print(f"   Entry price: {entry_price:.2f}")
            print(f"   Calculated volume: {volume:.2f}")
            if volume <= 0:
                print("   ❌ BLOCKED: Volume too small")
            else:
                print("   ✅ Volume OK")
        else:
            print("   ❌ BLOCKED: No tick data")
    
    # Final verdict
    print(f"\n🎯 FINAL VERDICT:")
    if buy_signal:
        print("   🟢 BUY signal detected - should enter trade")
    elif sell_signal:
        print("   🔴 SELL signal detected - should enter trade")
    else:
        print("   ⏳ No signal - waiting for conditions")

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Initialize MT5
    mt5_path = os.getenv("MT5_PATH")
    mt5_login = int(os.getenv("MT5_LOGIN"))
    mt5_pass = os.getenv("MT5_PASSWORD")
    mt5_server = os.getenv("MT5_SERVER")
    
    if not mt5.initialize(path=mt5_path, login=mt5_login, password=mt5_pass, server=mt5_server):
        print(f"MT5 initialization failed: {mt5.last_error()}")
        exit()
    
    try:
        while True:
            diagnose_entry_conditions()
            print("\n" + "="*50)
            time.sleep(5)  # Check every 5 seconds
    except KeyboardInterrupt:
        print("\nDiagnostic stopped")
    finally:
        mt5.shutdown()