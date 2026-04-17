"""
FLEXIBLE ENTRY TEST DIAGNOSTIC TOOL
Specifically designed for flexible_entry_test.py
"""
import MetaTrader5 as mt5
import os
import time
from dotenv import load_dotenv
from enhanced_strategy import EnhancedTradingStrategy

class FlexibleEntryDiagnostic:
    def __init__(self, symbol="XAUUSD", timeframe="M1"):
        self.symbol = symbol
        self.timeframe = timeframe
        self.strategy = EnhancedTradingStrategy(symbol, timeframe)
        
    def diagnose_entry_failure(self):
        """Comprehensive diagnosis of why trades are not taken"""
        
        print("🔍 FLEXIBLE ENTRY TEST DIAGNOSTIC")
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
        
        # Step 5: Check entry conditions from enhanced_strategy.py
        print(f"\n🎯 ENTRY CONDITIONS (from enhanced_strategy.py):")
        rsi = analysis.get('rsi', 50)
        ut_buy = analysis.get('ut_buy', False)
        ut_sell = analysis.get('ut_sell', False)
        candle_color = analysis.get('candle_color', '')
        
        print(f"   RSI: {rsi:.1f}")
        print(f"   UT_Buy: {ut_buy}")
        print(f"   UT_Sell: {ut_sell}")
        print(f"   Candle: {candle_color}")
        print(f"   UT Trail: {analysis.get('trail_stop', 0):.2f}")
        
        # Check BUY conditions
        print(f"\n🟢 BUY SIGNAL CHECK:")
        buy_cond1 = ut_buy
        buy_cond2 = rsi > 30
        buy_cond3 = candle_color == 'GREEN'
        
        print(f"   1. Price > UT Trail: {buy_cond1} {'✅' if buy_cond1 else '❌'}")
        print(f"   2. RSI > 30: {rsi:.1f} > 30 = {buy_cond2} {'✅' if buy_cond2 else '❌'}")
        print(f"   3. Green candle: {candle_color} = {buy_cond3} {'✅' if buy_cond3 else '❌'}")
        
        buy_signal = buy_cond1 and buy_cond2 and buy_cond3
        print(f"   BUY SIGNAL: {buy_signal} {'🚀' if buy_signal else '❌'}")
        
        # Check SELL conditions
        print(f"\n🔴 SELL SIGNAL CHECK:")
        sell_cond1 = ut_sell
        sell_cond2 = rsi < 70
        sell_cond3 = candle_color == 'RED'
        
        print(f"   1. Price < UT Trail: {sell_cond1} {'✅' if sell_cond1 else '❌'}")
        print(f"   2. RSI < 70: {rsi:.1f} < 70 = {sell_cond2} {'✅' if sell_cond2 else '❌'}")
        print(f"   3. Red candle: {candle_color} = {sell_cond3} {'✅' if sell_cond3 else '❌'}")
        
        sell_signal = sell_cond1 and sell_cond2 and sell_cond3
        print(f"   SELL SIGNAL: {sell_signal} {'🚀' if sell_signal else '❌'}")
        
        # Step 6: Volume check if signal exists
        if buy_signal or sell_signal:
            print(f"\n💰 VOLUME CALCULATION:")
            entry_price = tick.ask if buy_signal else tick.bid
            
            try:
                account_info = mt5.account_info()
                if account_info:
                    effective_balance = min(account_info.balance, 5000.0)
                    calculated_volume = effective_balance / entry_price
                    calculated_volume = round(calculated_volume, 2)
                    
                    print(f"   Account balance: ${account_info.balance:.2f}")
                    print(f"   Effective balance (cap $5000): ${effective_balance:.2f}")
                    print(f"   Entry price: {entry_price:.2f}")
                    print(f"   Calculated volume: {calculated_volume:.2f}")
                    
                    if calculated_volume < 0.01:
                        print("   ❌ BLOCKED: Volume too small")
                        return
                    else:
                        print("   ✅ Volume OK")
                else:
                    print("   ❌ BLOCKED: Cannot get account info")
                    return
            except Exception as e:
                print(f"   ❌ BLOCKED: Volume calculation error: {e}")
                return
        
        # Step 7: Debug UT Trail calculation
        print(f"\n🔧 UT TRAIL DEBUG:")
        close_arr = analysis.get('df', {}).get('close', [])
        if hasattr(close_arr, 'values'):
            close_values = close_arr.values
            if len(close_values) > 0 and len(ut_trail_array) > 1:
                print(f"   Close[-1]: {close_values[-1]:.2f}")
                print(f"   UT Trail[-2]: {ut_trail_array[-2]:.2f}")
                print(f"   UT Trail[-1]: {ut_trail_array[-1]:.2f}")
                print(f"   Using [-2] for comparison (stable value)")
                
                # Show why UT_Buy/UT_Sell is True/False
                ut_buy_calc = close_values[-1] > ut_trail_array[-2]
                ut_sell_calc = close_values[-1] < ut_trail_array[-2]
                print(f"   UT_Buy calc: {close_values[-1]:.2f} > {ut_trail_array[-2]:.2f} = {ut_buy_calc}")
                print(f"   UT_Sell calc: {close_values[-1]:.2f} < {ut_trail_array[-2]:.2f} = {ut_sell_calc}")
        
        # Final verdict
        print(f"\n🎯 FINAL DIAGNOSIS:")
        if buy_signal:
            print("   🟢 BUY signal detected - trade should execute")
        elif sell_signal:
            print("   🔴 SELL signal detected - trade should execute")
        else:
            print("   ⏳ No signal - conditions not met")
            
            # Show what's missing
            if not (buy_cond1 or sell_cond1):
                print("   💡 Price not crossed UT Trail yet")
            if not (buy_cond2 or sell_cond2):
                print(f"   💡 RSI in neutral zone: {rsi:.1f} (need >30 for BUY or <70 for SELL)")
            if not (buy_cond3 or sell_cond3):
                print(f"   💡 Wrong candle color: {candle_color}")

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
    
    diagnostic = FlexibleEntryDiagnostic("XAUUSD", "M1")
    
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