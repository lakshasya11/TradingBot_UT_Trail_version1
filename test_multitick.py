import MetaTrader5 as mt5
import os
from dotenv import load_dotenv
from enhanced_strategy import EnhancedTradingStrategy

def test_multitick_system():
    load_dotenv()
    
    # Initialize MT5
    mt5_path = os.getenv("MT5_PATH")
    mt5_login = int(os.getenv("MT5_LOGIN"))
    mt5_pass = os.getenv("MT5_PASSWORD")
    mt5_server = os.getenv("MT5_SERVER")
    
    if not mt5.initialize(path=mt5_path, login=mt5_login, password=mt5_pass, server=mt5_server):
        print(f"MT5 initialization failed: {mt5.last_error()}")
        return
    
    print("=== MULTI-TICK MOMENTUM SYSTEM TEST ===")
    
    # Create strategy instance
    strategy = EnhancedTradingStrategy("XAUUSD", "M1")
    
    # Test for 10 ticks to build history
    for i in range(15):
        print(f"\n--- TICK {i+1} ---")
        
        # Get analysis
        analysis = strategy.analyze_timeframe("M1")
        if not analysis:
            print("No analysis data")
            continue
            
        # Check entry conditions (this will update tick history)
        entry_signal = strategy.check_entry_conditions(analysis)
        
        print(f"Tick History Length: {len(strategy.tick_history)}")
        print(f"Entry Signal: {entry_signal}")
        
        if len(strategy.tick_history) >= 3:
            latest_ticks = strategy.tick_history[-3:]
            print("Recent Ticks:")
            for j, tick_data in enumerate(latest_ticks):
                print(f"  {j+1}: Bid={tick_data['bid']:.2f} Ask={tick_data['ask']:.2f}")
        
        # Small delay between ticks
        import time
        time.sleep(0.5)
    
    print(f"\nFinal tick history length: {len(strategy.tick_history)}")
    print("Multi-tick system test completed!")
    
    mt5.shutdown()

if __name__ == "__main__":
    test_multitick_system()