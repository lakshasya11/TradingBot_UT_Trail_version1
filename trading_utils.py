"""
Shared Trading Utilities
Consolidates all duplicate calculation logic across the trading bot project.
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

def calculate_rsi_wilder(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate RSI using Wilder's smoothing method"""
    close = df['close']
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    alpha = 1.0 / period
    avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_ut_trail(df: pd.DataFrame, key_value: float = 1.0) -> np.ndarray:
    """UT Bot ATR trailing stop (ATR_Period=1 = single candle range)"""
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

def calculate_atr(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Calculate ATR using Wilder's smoothing (RMA)"""
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - df['close'].shift()).abs()
    tr3 = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0/period, adjust=False).mean()
    return atr

def calculate_dynamic_volume(current_price: float, symbol: str, balance_cap: float = 5000.0) -> float:
    """Calculate volume based on balance and current price with configurable cap"""
    try:
        account_info = mt5.account_info()
        if not account_info:
            return 0.01  # Fallback to minimum
        
        # Capital cap
        effective_balance = min(account_info.balance, balance_cap)
        
        # Volume = Effective Balance / Current Price
        calculated_volume = effective_balance / current_price
        
        # Round to 2 decimal places
        calculated_volume = round(calculated_volume, 2)
        
        # Safety minimum check
        if calculated_volume < 0.01:
            return 0.0  # Return 0 to skip trade
        
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info:
            # Ensure within broker limits
            min_volume = symbol_info.volume_min
            max_volume = symbol_info.volume_max
            calculated_volume = max(min_volume, min(max_volume, calculated_volume))
        
        return calculated_volume
        
    except Exception as e:
        print(f"❌ Error calculating dynamic volume: {e}")
        return 0.01

def is_sideways_market(ut_trail_array: np.ndarray, lookback: int = 10, threshold: float = 0.5) -> bool:
    """Detect sideways market based on UT trail flatness"""
    if len(ut_trail_array) < lookback:
        return False
    
    recent_trail = ut_trail_array[-lookback:]
    trail_range = max(recent_trail) - min(recent_trail)
    
    return trail_range < threshold  # Block if range < threshold points

def calculate_trailing_stop_points(pos, tick, pos_data, symbol_info):
    """
    $1 Trailing Stop — activates after price moves 0.25 pt in profit direction.
    Measures profit from bid_at_entry (BUY) or ask_at_entry (SELL).
    Trails 1.0 pt behind current price, only moves in your favour.
    Returns (trail_sl, is_active, phase_label)
    """
    direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
    
    # Use bid/ask at entry time for profit measurement (NOT fill price)
    ref_price = pos_data.get('reference_price')
    
    if not ref_price:  # Fallback if reference_price not stored
        return None, False, '$1 Reversal'

    if direction == "BUY":
        # Profit measured from bid at entry time
        profit_pts = tick.bid - ref_price
        if profit_pts >= 0.01:  # 0.01 POINTS profit threshold
            # Activate / advance trail
            new_trail_sl = round(tick.bid - 1.0, symbol_info.digits)
            best_sl = pos_data.get('dollar_trail_sl') or 0
            if new_trail_sl > best_sl:               # Only ratchet up
                pos_data['dollar_trail_sl'] = new_trail_sl
                pos_data['dollar_trail_active'] = True
                pos_data['phase_label'] = '$1 Trail'
            return pos_data['dollar_trail_sl'], True, '$1 Trail'
        return None, False, '$1 Reversal'

    else:  # SELL
        # Profit measured from ask at entry time
        profit_pts = ref_price - tick.ask
        if profit_pts >= 0.01:  # 0.01 POINTS profit threshold
            # Activate / advance trail
            new_trail_sl = round(tick.ask + 1.0, symbol_info.digits)
            best_sl = pos_data.get('dollar_trail_sl')
            if best_sl is None or new_trail_sl < best_sl:  # Only ratchet down
                pos_data['dollar_trail_sl'] = new_trail_sl
                pos_data['dollar_trail_active'] = True
                pos_data['phase_label'] = '$1 Trail'
            return pos_data['dollar_trail_sl'], True, '$1 Trail'
        return None, False, '$1 Reversal'

def check_1dollar_reversal_exit(pos, tick, symbol, position_data):
    """
    $1 Reversal Hard Stop — fires when price moves 1.0 pts against entry.
    Measures from pos.price_open (actual fill price).
    BUY:  tick.bid <= price_open - 1.0  → EXIT
    SELL: tick.ask >= price_open + 1.0  → EXIT
    """
    direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"

    if direction == "BUY":
        loss_pts = pos.price_open - tick.bid
        if loss_pts >= 1.0:
            close_position(pos.ticket, symbol, "$1_Reversal")
            if pos.ticket in position_data:
                del position_data[pos.ticket]
            return True
    else:  # SELL
        loss_pts = tick.ask - pos.price_open
        if loss_pts >= 1.0:
            close_position(pos.ticket, symbol, "$1_Reversal")
            if pos.ticket in position_data:
                del position_data[pos.ticket]
            return True
    return False

def calculate_triple_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate RSI, UT Trail, and ATR indicators for a dataframe"""
    df = df.copy()
    
    # RSI calculation
    df['rsi'] = calculate_rsi_wilder(df, period=14)
    
    # UT Bot Trailing Stop
    ut_trail = calculate_ut_trail(df, key_value=1.0)
    df['ut_trail'] = ut_trail
    df['ut_buy'] = (df['close'] > df['ut_trail']) & (df['close'].shift(1) <= df['ut_trail'].shift(1))
    df['ut_sell'] = (df['close'] < df['ut_trail']) & (df['close'].shift(1) >= df['ut_trail'].shift(1))
    df['ut_bullish'] = df['close'] > df['ut_trail']
    df['ut_bearish'] = df['close'] < df['ut_trail']
    
    # ATR calculation
    df['atr14'] = calculate_atr(df, period=20)
    
    return df