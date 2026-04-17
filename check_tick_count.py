import MetaTrader5 as mt5
import os
from dotenv import load_dotenv
from enhanced_strategy import EnhancedTradingStrategy

def check_tick_count():
    """Check exactly how many ticks the Multi-Tick system is using"""
    load_dotenv()
    
    # Initialize MT5
    mt5_path = os.getenv("MT5_PATH")
    mt5_login = int(os.getenv("MT5_LOGIN"))
    mt5_pass = os.getenv("MT5_PASSWORD")
    mt5_server = os.getenv("MT5_SERVER")
    
    if not mt5.initialize(path=mt5_path, login=mt5_login, password=mt5_pass, server=mt5_server):
        print(f"MT5 initialization failed: {mt5.last_error()}")
        return
    
    print("TICK COUNT VERIFICATION")
    print("=" * 40)
    
    # Create strategy instance
    strategy = EnhancedTradingStrategy("XAUUSD", "M1")
    
    print(f"Max Tick History Setting: {strategy.max_tick_history}")
    print(f"Momentum Threshold: {strategy.momentum_threshold}")
    print()
    
    # Run 10 ticks to see the progression
    for i in range(10):
        print(f"TICK {i+1}:")
        
        # Get analysis (this updates tick history)
        analysis = strategy.analyze_timeframe("M1")
        if not analysis:
            print("  No analysis data")
            continue
        
        # Get current tick
        tick = mt5.symbol_info_tick("XAUUSD")
        if not tick:
            print("  No tick data")
            continue
        
        # Update tick history manually to see the count
        strategy.update_tick_history(tick)
        
        # Check entry conditions (this triggers Multi-Tick analysis)
        entry_signal = strategy.check_entry_conditions(analysis)
        
        print(f"  Tick History Length: {len(strategy.tick_history)}")
        print(f"  Max Allowed: {strategy.max_tick_history}")
        print(f"  Entry Signal: {entry_signal}")
        
        # Show Multi-Tick analysis details
        current_open = analysis.get('open', 0)
        current_low = analysis.get('low', 0)
        current_high = analysis.get('high', 0)
        
        buy_momentum, sell_momentum, momentum_analysis = strategy.analyze_multi_tick_momentum(
            current_open, current_low, current_high
        )
        
        print(f"  Momentum Analysis: {momentum_analysis}")
        print(f"  BUY: {buy_momentum} | SELL: {sell_momentum}")
        print()
        
        import time
        time.sleep(0.5)
    
    print("FINAL VERIFICATION:")
    print(f"Final Tick History Length: {len(strategy.tick_history)}")
    print(f"Expected Max Length: {strategy.max_tick_history}")
    print(f"System Working: {'YES' if len(strategy.tick_history) <= strategy.max_tick_history else 'NO'}")
    
    mt5.shutdown()

if __name__ == "__main__":
    check_tick_count()