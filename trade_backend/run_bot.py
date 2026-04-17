import MetaTrader5 as mt5
from triple_strategy import TripleConfirmationBot
import time
from datetime import datetime
import os
from dotenv import load_dotenv

# Load MT5 connection details from .env
load_dotenv()

def main():
    """Initializes MT5 and runs the Triple Confirmation Bot loop."""
    
    # MT5 Initialization
    mt5_path = os.getenv("MT5_PATH")
    mt5_login = os.getenv("MT5_LOGIN")
    mt5_pass = os.getenv("MT5_PASSWORD")
    mt5_server = os.getenv("MT5_SERVER")
    
    if not all([mt5_path, mt5_login, mt5_pass, mt5_server]):
        print("CRITICAL: .env file is missing MT5 credentials.")
        return

    # Connect to MT5 terminal
    if not mt5.initialize(path=mt5_path, login=int(mt5_login), password=mt5_pass, server=mt5_server):
        print(f"MT5 initialization FAILED! Error Code: {mt5.last_error()}")
        return
    
    print("Global MT5 connection established.")
    
    # Initialize the strategy bot with chart enabled
    SYMBOL = "XAUUSD" 
    try:
        bot = TripleConfirmationBot(symbol=SYMBOL, enable_chart=True)
    except Exception as e:
        print(f"CRITICAL: Failed to initialize bot: {e}")
        mt5.shutdown()
        return

    # Main Strategy Loop
    bot.is_running = True
    print(f"Starting strategy loop for {SYMBOL}...")
    
    while bot.is_running:
        try:
            # Run the data fetch and signal check cycle
            bot.run_strategy_cycle()
            
            # Pause for 1 second before the next check
            time.sleep(1) 
            
        except KeyboardInterrupt:
            print("\nStrategy manually stopped by user.")
            bot.is_running = False
            break
        except Exception as e:
            print(f"CRITICAL ERROR in main loop: {e}")
            time.sleep(30)

    # Shutdown
    mt5.shutdown()
    print("MT5 connection terminated.")

if __name__ == "__main__":
    main()