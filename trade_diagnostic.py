import MetaTrader5 as mt5
import os
from dotenv import load_dotenv
from enhanced_strategy import EnhancedTradingStrategy

def check_trading_conditions():
    """Diagnostic script to check if bot can take trades"""
    
    # Load environment
    load_dotenv()
    
    # MT5 Connection
    mt5_path = os.getenv("MT5_PATH")
    mt5_login = int(os.getenv("MT5_LOGIN"))
    mt5_pass = os.getenv("MT5_PASSWORD")
    mt5_server = os.getenv("MT5_SERVER")
    
    print("=== TRADING BOT DIAGNOSTIC ===")
    print(f"MT5 Login: {mt5_login}")
    print(f"MT5 Server: {mt5_server}")
    
    # Initialize MT5
    if not mt5.initialize(path=mt5_path, login=mt5_login, password=mt5_pass, server=mt5_server):
        print(f"[ERROR] MT5 initialization failed: {mt5.last_error()}")
        return
    
    print("[OK] MT5 Connected Successfully")
    
    # Check account info
    account_info = mt5.account_info()
    if account_info:
        print(f"Account Balance: ${account_info.balance:.2f}")
        print(f"Account Equity: ${account_info.equity:.2f}")
        print(f"Trade Allowed: {account_info.trade_allowed}")
        print(f"Trade Expert: {account_info.trade_expert}")
    
    # Check symbol info
    symbol = "XAUUSD"
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info:
        print(f"Symbol: {symbol}")
        print(f"Trade Mode: {symbol_info.trade_mode}")
        print(f"Min Volume: {symbol_info.volume_min}")
        print(f"Max Volume: {symbol_info.volume_max}")
        print(f"Volume Step: {symbol_info.volume_step}")
    else:
        print(f"[ERROR] Symbol {symbol} not found")
        return
    
    # Get current tick
    tick = mt5.symbol_info_tick(symbol)
    if tick:
        print(f"Current Bid: {tick.bid}")
        print(f"Current Ask: {tick.ask}")
        print(f"Spread: {tick.ask - tick.bid:.5f}")
    
    # Check existing positions
    positions = mt5.positions_get(symbol=symbol)
    print(f"Open Positions: {len(positions) if positions else 0}")
    
    # Test strategy analysis
    print("\n=== STRATEGY ANALYSIS ===")
    strategy = EnhancedTradingStrategy(symbol, "M1")
    analysis = strategy.analyze_timeframe("M1")
    
    if analysis:
        print(f"RSI: {analysis.get('rsi', 0):.1f}")
        print(f"ATR: {analysis.get('atr', 0):.5f}")
        print(f"Close Price: {analysis.get('close', 0):.2f}")
        print(f"UT Trail: {analysis.get('trail_stop', 0):.2f}")
        print(f"Candle Color: {analysis.get('candle_color', '')}")
        print(f"UT Buy: {analysis.get('ut_buy', False)}")
        print(f"UT Sell: {analysis.get('ut_sell', False)}")
        
        # Check entry conditions
        signal = strategy.check_entry_conditions(analysis)
        print(f"\nENTRY SIGNAL: {signal}")
        
        if signal == "BUY":
            print("[OK] BUY CONDITIONS MET:")
            print(f"   - UT Buy: {analysis.get('ut_buy', False)}")
            print(f"   - RSI > 30: {analysis.get('rsi', 0):.1f} > 30 = {analysis.get('rsi', 0) > 30}")
            print(f"   - Green Candle: {analysis.get('candle_color', '') == 'GREEN'}")
        elif signal == "SELL":
            print("[OK] SELL CONDITIONS MET:")
            print(f"   - UT Sell: {analysis.get('ut_sell', False)}")
            print(f"   - RSI < 70: {analysis.get('rsi', 0):.1f} < 70 = {analysis.get('rsi', 0) < 70}")
            print(f"   - Red Candle: {analysis.get('candle_color', '') == 'RED'}")
        else:
            print("[WARNING] NO ENTRY CONDITIONS MET:")
            print(f"   - UT Buy: {analysis.get('ut_buy', False)} (need True)")
            print(f"   - UT Sell: {analysis.get('ut_sell', False)} (need True)")
            print(f"   - RSI: {analysis.get('rsi', 0):.1f} (BUY needs >30, SELL needs <70)")
            print(f"   - Candle: {analysis.get('candle_color', '')} (BUY needs GREEN, SELL needs RED)")
        
        # Test volume calculation
        current_price = tick.ask if signal == "BUY" else tick.bid
        volume = strategy.calculate_dynamic_volume(current_price)
        print(f"\nCalculated Volume: {volume:.2f}")
        
        if volume > 0:
            print("[OK] Volume is valid for trading")
        else:
            print("[ERROR] Volume too small - trades will be skipped")
    
    else:
        print("[ERROR] Failed to get strategy analysis")
    
    print("\n=== DIAGNOSTIC COMPLETE ===")
    mt5.shutdown()

if __name__ == "__main__":
    check_trading_conditions()