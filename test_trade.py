import MetaTrader5 as mt5
import os
from dotenv import load_dotenv

def test_trade_execution():
    """Test if bot can execute a trade right now"""
    
    load_dotenv()
    
    # MT5 Connection
    mt5_path = os.getenv("MT5_PATH")
    mt5_login = int(os.getenv("MT5_LOGIN"))
    mt5_pass = os.getenv("MT5_PASSWORD")
    mt5_server = os.getenv("MT5_SERVER")
    
    if not mt5.initialize(path=mt5_path, login=mt5_login, password=mt5_pass, server=mt5_server):
        print(f"MT5 initialization failed: {mt5.last_error()}")
        return
    
    print("=== TRADE EXECUTION TEST ===")
    
    # Check current conditions
    symbol = "XAUUSD"
    tick = mt5.symbol_info_tick(symbol)
    
    if not tick:
        print("Failed to get tick data")
        return
    
    print(f"Current Bid: {tick.bid}")
    print(f"Current Ask: {tick.ask}")
    
    # Check account
    account_info = mt5.account_info()
    print(f"Balance: ${account_info.balance:.2f}")
    print(f"Trade Allowed: {account_info.trade_allowed}")
    
    # Check existing positions
    positions = mt5.positions_get(symbol=symbol)
    print(f"Open Positions: {len(positions) if positions else 0}")
    
    if positions:
        print("Cannot test - position already open")
        mt5.shutdown()
        return
    
    # Test small BUY order
    volume = 0.01  # Minimum volume
    entry_price = tick.ask
    stop_loss = round(entry_price - 5.0, 2)  # 5 points SL
    take_profit = round(entry_price + 10.0, 2)  # 10 points TP
    
    print(f"\nTesting BUY order:")
    print(f"Volume: {volume}")
    print(f"Entry: {entry_price}")
    print(f"SL: {stop_loss}")
    print(f"TP: {take_profit}")
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY,
        "price": entry_price,
        "sl": stop_loss,
        "tp": take_profit,
        "magic": 123456,
        "comment": "TEST_ORDER",
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    print("\nSending order...")
    result = mt5.order_send(request)
    
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"SUCCESS! Order executed: #{result.order}")
        print(f"Deal: #{result.deal}")
        print(f"Volume: {result.volume}")
        
        # Close the test position immediately
        print("\nClosing test position...")
        close_request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_SELL,
            "position": result.order,
            "price": tick.bid,
            "magic": 123456,
            "comment": "TEST_CLOSE",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        close_result = mt5.order_send(close_request)
        if close_result and close_result.retcode == mt5.TRADE_RETCODE_DONE:
            print("Test position closed successfully")
        else:
            print(f"Failed to close test position: {close_result.comment if close_result else 'Unknown error'}")
            
    else:
        print(f"ORDER FAILED: {result.comment if result else 'Unknown error'}")
        print(f"Return code: {result.retcode if result else 'None'}")
    
    mt5.shutdown()

if __name__ == "__main__":
    test_trade_execution()