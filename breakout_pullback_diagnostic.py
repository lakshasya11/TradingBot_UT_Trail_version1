"""
BREAKOUT/PULLBACK ENTRY DIAGNOSTIC TOOL
Specifically designed for the new breakout/pullback system
"""
import MetaTrader5 as mt5
import os
import time
from dotenv import load_dotenv
from enhanced_strategy import EnhancedTradingStrategy

class BreakoutPullbackDiagnostic:
    def __init__(self, symbol="XAUUSD", timeframe="M1"):
        self.symbol = symbol
        self.timeframe = timeframe
        self.strategy = EnhancedTradingStrategy(symbol, timeframe)
        
    def diagnose_entry_failure(self):
        """Comprehensive diagnosis of why breakout/pullback trades are not taken"""
        
        print("🔍 BREAKOUT/PULLBACK ENTRY DIAGNOSTIC")
        print("=" * 60)
        
        # Step 1: Check MT5 connection
        if not mt5.terminal_info():
            print("❌ CRITICAL: MT5 not connected")
            return
        
        # Step 2: Get market data
        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            print(f"❌ CRITICAL: No tick data for {self.symbol}")
            return
            
        analysis = self.strategy.analyze_timeframe(self.timeframe)
        if not analysis:
            print("❌ CRITICAL: Analysis failed - no data returned")
            return
        
        print(f"✅ Market data retrieved successfully")
        print(f"   Current price: {analysis.get('close', 0):.2f}")
        print(f"   Tick bid/ask: {tick.bid:.2f}/{tick.ask:.2f}")
        
        # Step 3: Check existing positions
        positions = mt5.positions_get(symbol=self.symbol)
        print(f"\n🏦 POSITION CHECK:")
        if positions:
            print(f"   ❌ BLOCKED: {len(positions)} existing position(s)")
            for pos in positions:
                print(f"      #{pos.ticket} {pos.type} {pos.volume} @ {pos.price_open:.2f}")
            return
        else:
            print("   ✅ No existing positions")
        
        # Step 4: Check sideways market filter
        ut_trail_array = analysis.get('ut_trail_array', [])
        print(f"\n📈 SIDEWAYS MARKET CHECK:")
        if len(ut_trail_array) >= 10:
            recent_trail = ut_trail_array[-10:]
            trail_range = max(recent_trail) - min(recent_trail)
            is_sideways = trail_range < 0.5
            
            print(f"   UT Trail range (10 candles): {trail_range:.3f}")
            print(f"   Threshold: 0.5")
            print(f"   Is sideways: {is_sideways}")
            
            if is_sideways:
                print("   ❌ BLOCKED: Market is sideways")
                print(f"   Recent UT Trail values: {[f'{x:.2f}' for x in recent_trail[-5:]]}")
                return
            else:
                print("   ✅ Market not sideways")
        else:
            print(f"   ⚠️ Insufficient data: only {len(ut_trail_array)} candles")
        
        # Step 5: Previous candle analysis
        df = analysis.get('df')
        if df is None or len(df) < 2:
            print("\n❌ CRITICAL: Insufficient candle data for previous candle analysis")
            return
        
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
        
        print(f"\n🕯️ PREVIOUS CANDLE ANALYSIS:")
        print(f"   Color: {prev_candle_color}")
        print(f"   OHLC: O:{prev_open:.2f} H:{prev_high:.2f} L:{prev_low:.2f} C:{prev_close:.2f}")
        
        if prev_candle_color == "DOJI":
            print("   ❌ BLOCKED: DOJI candle - no signals generated")
            return
        
        # Step 6: Check UT Bot and RSI filters
        rsi = analysis.get('rsi', 50)
        ut_buy = analysis.get('ut_buy', False)
        ut_sell = analysis.get('ut_sell', False)
        
        print(f"\n🎯 FILTER CONDITIONS:")
        print(f"   RSI: {rsi:.1f}")
        print(f"   UT_Buy: {ut_buy}")
        print(f"   UT_Sell: {ut_sell}")
        print(f"   UT Trail: {analysis.get('trail_stop', 0):.2f}")
        
        # Step 7: Breakout/Pullback Analysis
        print(f"\n🚀 BREAKOUT/PULLBACK ANALYSIS:")
        
        if prev_candle_color == "GREEN":
            print(f"   GREEN Candle Conditions:")
            
            # BUY Breakout
            buy_breakout = tick.ask > prev_high
            buy_ut_ok = ut_buy
            buy_rsi_ok = rsi > 30
            buy_signal = buy_ut_ok and buy_rsi_ok and buy_breakout
            
            print(f"   🟢 BUY Breakout: ask ({tick.ask:.2f}) > prev_high ({prev_high:.2f}) = {buy_breakout} {'✅' if buy_breakout else '❌'}")
            print(f"      - UT_Buy: {buy_ut_ok} {'✅' if buy_ut_ok else '❌'}")
            print(f"      - RSI > 30: {buy_rsi_ok} {'✅' if buy_rsi_ok else '❌'}")
            print(f"      - BUY SIGNAL: {buy_signal} {'🚀' if buy_signal else '❌'}")
            
            # SELL Pullback
            sell_pullback = tick.bid <= prev_open or tick.bid <= prev_low
            sell_ut_ok = ut_sell
            sell_rsi_ok = rsi < 70
            sell_signal = sell_ut_ok and sell_rsi_ok and sell_pullback
            
            print(f"   🔴 SELL Pullback: bid ({tick.bid:.2f}) <= prev_open ({prev_open:.2f}) OR prev_low ({prev_low:.2f}) = {sell_pullback} {'✅' if sell_pullback else '❌'}")
            print(f"      - UT_Sell: {sell_ut_ok} {'✅' if sell_ut_ok else '❌'}")
            print(f"      - RSI < 70: {sell_rsi_ok} {'✅' if sell_rsi_ok else '❌'}")
            print(f"      - SELL SIGNAL: {sell_signal} {'🚀' if sell_signal else '❌'}")
            
        elif prev_candle_color == "RED":
            print(f"   RED Candle Conditions:")
            
            # SELL Breakout
            sell_breakout = tick.bid < prev_low
            sell_ut_ok = ut_sell
            sell_rsi_ok = rsi < 70
            sell_signal = sell_ut_ok and sell_rsi_ok and sell_breakout
            
            print(f"   🔴 SELL Breakout: bid ({tick.bid:.2f}) < prev_low ({prev_low:.2f}) = {sell_breakout} {'✅' if sell_breakout else '❌'}")
            print(f"      - UT_Sell: {sell_ut_ok} {'✅' if sell_ut_ok else '❌'}")
            print(f"      - RSI < 70: {sell_rsi_ok} {'✅' if sell_rsi_ok else '❌'}")
            print(f"      - SELL SIGNAL: {sell_signal} {'🚀' if sell_signal else '❌'}")
            
            # BUY Pullback
            buy_pullback = tick.ask >= prev_open or tick.ask >= prev_high
            buy_ut_ok = ut_buy
            buy_rsi_ok = rsi > 30
            buy_signal = buy_ut_ok and buy_rsi_ok and buy_pullback
            
            print(f"   🟢 BUY Pullback: ask ({tick.ask:.2f}) >= prev_open ({prev_open:.2f}) OR prev_high ({prev_high:.2f}) = {buy_pullback} {'✅' if buy_pullback else '❌'}")
            print(f"      - UT_Buy: {buy_ut_ok} {'✅' if buy_ut_ok else '❌'}")
            print(f"      - RSI > 30: {buy_rsi_ok} {'✅' if buy_rsi_ok else '❌'}")
            print(f"      - BUY SIGNAL: {buy_signal} {'🚀' if buy_signal else '❌'}")
        
        # Final verdict
        print(f"\n🎯 FINAL DIAGNOSIS:")
        final_signal = any([
            prev_candle_color == "GREEN" and ut_buy and rsi > 30 and tick.ask > prev_high,
            prev_candle_color == "GREEN" and ut_sell and rsi < 70 and (tick.bid <= prev_open or tick.bid <= prev_low),
            prev_candle_color == "RED" and ut_sell and rsi < 70 and tick.bid < prev_low,
            prev_candle_color == "RED" and ut_buy and rsi > 30 and (tick.ask >= prev_open or tick.ask >= prev_high)
        ])
        
        if final_signal:
            signal_type = "BUY" if (ut_buy and ((prev_candle_color == "GREEN" and tick.ask > prev_high) or (prev_candle_color == "RED" and (tick.ask >= prev_open or tick.ask >= prev_high)))) else "SELL"
            print(f"   🚀 {signal_type} signal detected - trade should execute")
        else:
            print(f"   ⏳ No signal - conditions not met")
            
            # Show what's missing
            if not (ut_buy or ut_sell):
                print(f"   💡 Price not crossed UT Trail yet")
            if not (rsi > 30 or rsi < 70):
                print(f"   💡 RSI in neutral zone: {rsi:.1f} (need >30 for BUY or <70 for SELL)")
            if prev_candle_color == "GREEN":
                if not (tick.ask > prev_high or tick.bid <= prev_open or tick.bid <= prev_low):
                    print(f"   💡 No breakout/pullback: ask not > high ({prev_high:.2f}) and bid not <= open/low ({prev_open:.2f}/{prev_low:.2f})")
            elif prev_candle_color == "RED":
                if not (tick.bid < prev_low or tick.ask >= prev_open or tick.ask >= prev_high):
                    print(f"   💡 No breakout/pullback: bid not < low ({prev_low:.2f}) and ask not >= open/high ({prev_open:.2f}/{prev_high:.2f})")

def main():
    load_dotenv()
    
    # Initialize MT5
    mt5_path = os.getenv("MT5_PATH")
    mt5_login = int(os.getenv("MT5_LOGIN"))
    mt5_pass = os.getenv("MT5_PASSWORD")
    mt5_server = os.getenv("MT5_SERVER")
    
    if not mt5.initialize(path=mt5_path, login=mt5_login, password=mt5_pass, server=mt5_server):
        print(f"MT5 initialization failed: {mt5.last_error()}")
        return
    
    diagnostic = BreakoutPullbackDiagnostic("XAUUSD", "M1")
    
    try:
        while True:
            diagnostic.diagnose_entry_failure()
            print("\n" + "="*60)
            print("Press Ctrl+C to stop, waiting 10 seconds...")
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nDiagnostic stopped")
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    main()