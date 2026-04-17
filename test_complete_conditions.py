import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import os
from dotenv import load_dotenv

def test_complete_entry_conditions():
    """Test all 5 entry conditions exactly as implemented in the bot"""
    
    # Load environment variables
    load_dotenv()
    
    # Initialize MT5
    mt5_path = os.getenv("MT5_PATH")
    mt5_login = int(os.getenv("MT5_LOGIN"))
    mt5_pass = os.getenv("MT5_PASSWORD")
    mt5_server = os.getenv("MT5_SERVER")
    
    if not mt5.initialize(path=mt5_path, login=mt5_login, password=mt5_pass, server=mt5_server):
        print(f"MT5 initialization failed: {mt5.last_error()}")
        return
    
    symbol = "XAUUSD"
    timeframe = mt5.TIMEFRAME_M1
    
    # Fetch data exactly like the bot does
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 100)
    if rates is None or len(rates) == 0:
        print("Failed to get rates data")
        mt5.shutdown()
        return
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    
    # Get current tick
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print("Failed to get tick data")
        mt5.shutdown()
        return
    
    print("=" * 80)
    print("COMPLETE ENTRY CONDITIONS TEST (Exactly as in Bot)")
    print("=" * 80)
    print(f"Symbol: {symbol}")
    print(f"Current Tick - Bid: {tick.bid:.2f}, Ask: {tick.ask:.2f}")
    print()
    
    # 1. Calculate RSI exactly like the bot
    close = df['close']
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    alpha = 1.0 / 14
    avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    current_rsi = rsi.iloc[-1] if len(rsi) > 0 and not pd.isna(rsi.iloc[-1]) else 50
    
    # 2. Calculate UT Trail exactly like the bot
    def calculate_ut_trail(df, key_value=1.0):
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        n = len(close)
        atr = np.abs(high - low)  # ATR period=1
        trail = np.zeros(n)
        trail[0] = close[0]
        for i in range(1, n):
            n_loss = key_value * atr[i]
            prev_stop = trail[i - 1]
            prev_close = close[i - 1]
            if close[i] > prev_stop and prev_close > prev_stop:
                trail[i] = max(prev_stop, close[i] - n_loss)
            elif close[i] < prev_stop and prev_close < prev_stop:
                trail[i] = min(prev_stop, close[i] + n_loss)
            elif close[i] > prev_stop:
                trail[i] = close[i] - n_loss
            else:
                trail[i] = close[i] + n_loss
        return trail
    
    ut_trail = calculate_ut_trail(df, key_value=1.0)
    close_arr = close.values
    # Use previous closed candle [-2] for UT trail — stable, not repainting
    ut_buy = bool(close_arr[-1] > ut_trail[-2])
    ut_sell = bool(close_arr[-1] < ut_trail[-2])
    
    # 3. Candle color
    candle_color = 'GREEN' if close.iloc[-1] > df['open'].iloc[-1] else 'RED'
    
    # 4. Get current candle data for momentum check
    current_open = df['open'].iloc[-1]
    current_low = df['low'].iloc[-1]
    current_high = df['high'].iloc[-1]
    
    # 5. Sideways market check
    def is_sideways_market(ut_trail_array, lookback=10, threshold=0.5):
        if len(ut_trail_array) < lookback:
            return False
        recent_trail = ut_trail_array[-lookback:]
        trail_range = max(recent_trail) - min(recent_trail)
        return trail_range < threshold
    
    is_sideways = is_sideways_market(ut_trail)
    
    # 6. Price momentum conditions
    buy_momentum1 = tick.bid > current_open   # Above open
    buy_momentum2 = tick.bid > current_low    # Above low
    buy_momentum = buy_momentum1 or buy_momentum2  # Either condition works
    
    sell_momentum1 = tick.ask < current_open  # Below open
    sell_momentum2 = tick.ask < current_high  # Below high
    sell_momentum = sell_momentum1 or sell_momentum2  # Either condition works
    
    print("CONDITION ANALYSIS:")
    print("-" * 50)
    print(f"1. RSI: {current_rsi:.1f}")
    print(f"   - RSI > 30 (BUY): {current_rsi > 30}")
    print(f"   - RSI < 70 (SELL): {current_rsi < 70}")
    print()
    
    print(f"2. UT Trail: {ut_trail[-2]:.2f} (previous candle)")
    print(f"   - Current Close: {close_arr[-1]:.2f}")
    print(f"   - UT Buy (close > trail): {ut_buy}")
    print(f"   - UT Sell (close < trail): {ut_sell}")
    print()
    
    print(f"3. Candle Color: {candle_color}")
    print(f"   - Open: {current_open:.2f}, Close: {close.iloc[-1]:.2f}")
    print()
    
    print(f"4. Sideways Market: {is_sideways}")
    if is_sideways:
        print("   - TRADES BLOCKED due to sideways market")
    print()
    
    print(f"5. Price Momentum:")
    print(f"   BUY Conditions:")
    print(f"     - Bid ({tick.bid:.2f}) > Open ({current_open:.2f}): {buy_momentum1}")
    print(f"     - Bid ({tick.bid:.2f}) > Low ({current_low:.2f}): {buy_momentum2}")
    print(f"     - BUY Momentum (OR): {buy_momentum}")
    print()
    print(f"   SELL Conditions:")
    print(f"     - Ask ({tick.ask:.2f}) < Open ({current_open:.2f}): {sell_momentum1}")
    print(f"     - Ask ({tick.ask:.2f}) < High ({current_high:.2f}): {sell_momentum2}")
    print(f"     - SELL Momentum (OR): {sell_momentum}")
    print()
    
    # Final signal determination
    print("FINAL SIGNAL DETERMINATION:")
    print("=" * 50)
    
    if is_sideways:
        signal = "SIDEWAYS"
        print(f"Signal: {signal} (Market is sideways - trades blocked)")
    else:
        # BUY signal: ALL 5 conditions must be TRUE
        buy_conditions = [
            ut_buy,
            current_rsi > 30,
            candle_color == 'GREEN',
            buy_momentum
        ]
        
        # SELL signal: ALL 5 conditions must be TRUE  
        sell_conditions = [
            ut_sell,
            current_rsi < 70,
            candle_color == 'RED',
            sell_momentum
        ]
        
        print("BUY Signal Requirements (ALL must be TRUE):")
        print(f"  1. UT Buy: {ut_buy}")
        print(f"  2. RSI > 30: {current_rsi > 30}")
        print(f"  3. Green Candle: {candle_color == 'GREEN'}")
        print(f"  4. Buy Momentum: {buy_momentum}")
        print(f"  -> BUY Signal: {all(buy_conditions)}")
        print()
        
        print("SELL Signal Requirements (ALL must be TRUE):")
        print(f"  1. UT Sell: {ut_sell}")
        print(f"  2. RSI < 70: {current_rsi < 70}")
        print(f"  3. Red Candle: {candle_color == 'RED'}")
        print(f"  4. Sell Momentum: {sell_momentum}")
        print(f"  -> SELL Signal: {all(sell_conditions)}")
        print()
        
        if all(buy_conditions):
            signal = "BUY"
        elif all(sell_conditions):
            signal = "SELL"
        else:
            signal = "NONE"
        
        print(f"FINAL SIGNAL: {signal}")
    
    print()
    print("MOMENTUM CONDITIONS STATUS:")
    print("-" * 30)
    if buy_momentum:
        print("[OK] BUY momentum condition is WORKING (price rising upward)")
    else:
        print("[NO] BUY momentum condition not met")
        
    if sell_momentum:
        print("[OK] SELL momentum condition is WORKING (price falling downward)")
    else:
        print("[NO] SELL momentum condition not met")
    
    mt5.shutdown()

if __name__ == "__main__":
    test_complete_entry_conditions()