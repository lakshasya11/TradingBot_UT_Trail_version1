import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import math
from datetime import datetime
from typing import Dict, Any, Optional
from terminal_formatter import TerminalFormatter
from trading_utils import calculate_rsi_wilder, calculate_ut_trail, calculate_atr, calculate_dynamic_volume, is_sideways_market
from trading_operations import close_position, modify_position
from tick_config import REQUIRED_CONFIRMATIONS, CONFIRMATION_WINDOW
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    CHART_AVAILABLE = True
except ImportError:
    CHART_AVAILABLE = False
    print("Matplotlib not available. Chart display disabled.")

class EnhancedTradingStrategy:
    
    TIMEFRAMES = {
        'M1': mt5.TIMEFRAME_M1,
        'M5': mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15,
        'M30': mt5.TIMEFRAME_M30,
        'H1': mt5.TIMEFRAME_H1,
        'H4': mt5.TIMEFRAME_H4,
        'D1': mt5.TIMEFRAME_D1
    }
    
    def __init__(self, symbol: str, base_timeframe: str = 'M5', enable_chart: bool = False):
        self.symbol = symbol
        self.base_timeframe = base_timeframe
        self.data_cache = {}
        self.open_positions = {}
        self.tick_count = 0
        self.enable_chart = enable_chart and CHART_AVAILABLE
        self.formatter = TerminalFormatter()
        self.trades_today = 0
        self.session_capital = 7149.74  # Starting capital
        
        # Multi-tick price movement tracking
        self.tick_history = []  # Store recent ticks for momentum analysis
        self.max_tick_history = 5  # OPTIMIZED: 5 ticks for fast 1-min candle signals
        self.momentum_threshold = 3  # Minimum ticks needed for momentum confirmation
        
        # Chart setup
        if self.enable_chart:
            plt.ion()
            self.fig, self.ax = plt.subplots(figsize=(12, 8))
            self.chart_data = []
        
        # Exit Configuration (Points-based)
        self.atr_sl_multiplier = 1.5    # Stop loss at 1.5x ATR
        self.tp_points = 4.0           # Take profit after 4.0 pts move
        self.breakeven_points = 3.0     # Activate breakeven after 3.0 pts move
        self.trailing_points = 0.01     # Activate trailing after 0.01 pts profit
        self.trailing_gap = 1.0         # Trail 1.0 pts behind current price ($1.00 for XAUUSD)
        self.fixed_sl_points = 1.0      # Fixed 1-point stop loss exit
        
        # Tick confirmation system
        self.tick_confirmations = {
            'buy_signals': [],
            'sell_signals': []
        }
        self.required_confirmations = REQUIRED_CONFIRMATIONS
        self.confirmation_window = CONFIRMATION_WINDOW
        
    def update_tick_history(self, tick):
        """Update tick history for multi-tick momentum analysis"""
        if not tick:
            return
            
        # Store tick data with timestamp
        tick_data = {
            'timestamp': datetime.now(),
            'bid': tick.bid,
            'ask': tick.ask,
            'time': tick.time
        }
        
        # Add to history
        self.tick_history.append(tick_data)
        
        # Keep only recent ticks
        if len(self.tick_history) > self.max_tick_history:
            self.tick_history.pop(0)
    
    def analyze_multi_tick_momentum(self, current_open, current_low, current_high):
        """Analyze price momentum using multiple recent ticks"""
        if len(self.tick_history) < self.momentum_threshold:
            # Not enough tick data - fallback to single tick logic
            if len(self.tick_history) > 0:
                latest_tick = self.tick_history[-1]
                buy_momentum1 = latest_tick['bid'] > current_open
                buy_momentum2 = latest_tick['bid'] > current_low
                buy_momentum = buy_momentum1 or buy_momentum2
                
                sell_momentum1 = latest_tick['ask'] < current_open
                sell_momentum2 = latest_tick['ask'] < current_high
                sell_momentum = sell_momentum1 or sell_momentum2
                
                return buy_momentum, sell_momentum, "SINGLE_TICK"
            else:
                return False, False, "NO_TICKS"
        
        # Multi-tick momentum analysis
        buy_signals = 0
        sell_signals = 0
        total_ticks = len(self.tick_history)
        
        for tick_data in self.tick_history:
            # BUY momentum: bid > open OR bid > low
            if tick_data['bid'] > current_open or tick_data['bid'] > current_low:
                buy_signals += 1
            
            # SELL momentum: ask < open OR ask < high
            if tick_data['ask'] < current_open or tick_data['ask'] < current_high:
                sell_signals += 1
        
        # Calculate momentum percentages
        buy_momentum_pct = (buy_signals / total_ticks) * 100
        sell_momentum_pct = (sell_signals / total_ticks) * 100
        
        # OPTIMIZED: Adjusted for 5-tick analysis (fast signals)
        momentum_confirmation_threshold = 60.0  # 60% of 5 ticks = 3 ticks minimum
        
        buy_momentum = buy_momentum_pct >= momentum_confirmation_threshold
        sell_momentum = sell_momentum_pct >= momentum_confirmation_threshold
        
        # Additional trend strength analysis
        if len(self.tick_history) >= 3:
            # Check if recent ticks show consistent direction (last 3 ticks for 5-tick system)
            recent_ticks = self.tick_history[-3:]
            
            # BUY trend: recent bids are generally increasing
            buy_trend_strength = 0
            for i in range(1, len(recent_ticks)):
                if recent_ticks[i]['bid'] > recent_ticks[i-1]['bid']:
                    buy_trend_strength += 1
            
            # SELL trend: recent asks are generally decreasing  
            sell_trend_strength = 0
            for i in range(1, len(recent_ticks)):
                if recent_ticks[i]['ask'] < recent_ticks[i-1]['ask']:
                    sell_trend_strength += 1
            
            # Boost momentum if trend is consistent (2+ out of 2 moves in same direction)
            if buy_trend_strength >= 2:
                buy_momentum = buy_momentum or (buy_momentum_pct >= 40.0)  # Lower threshold with trend
            if sell_trend_strength >= 2:
                sell_momentum = sell_momentum or (sell_momentum_pct >= 40.0)  # Lower threshold with trend
        
        analysis_type = f"MULTI_TICK({total_ticks}): BUY={buy_momentum_pct:.1f}% SELL={sell_momentum_pct:.1f}%"
        
        return buy_momentum, sell_momentum, analysis_type
        
    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] {message}")

    def fetch_data(self, timeframe: str, bars: int = 100) -> pd.DataFrame:
        """Fetch OHLCV data with minimal delay"""
        tf_const = self.TIMEFRAMES[timeframe]
            
        # Fetch fresh data every tick (no cache)
        rates = mt5.copy_rates_from_pos(self.symbol, tf_const, 0, bars)

        
        if rates is not None and len(rates) > 0:
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)
            
            return df
        
        return pd.DataFrame()



    def calculate_ema(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate EMA indicator"""
        return df['close'].ewm(span=period, adjust=False).mean()

    def calculate_supertrend_pinescript(self, df: pd.DataFrame, atr_length: int = 5, atr_multiplier: float = 3.5, smoothing_period: int = 1) -> Dict:
        hl2 = (df['high'] + df['low']) / 2
        if smoothing_period > 1:
            smoothed_source = hl2.ewm(span=smoothing_period, adjust=False).mean()
        else:
            smoothed_source = hl2

        tr1 = df['high'] - df['low']
        tr2 = (df['high'] - df['close'].shift()).abs()
        tr3 = (df['low'] - df['close'].shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr_raw = tr.ewm(alpha=1.0/atr_length, adjust=False).mean()

        upper_band = smoothed_source + (atr_raw * atr_multiplier)
        lower_band = smoothed_source - (atr_raw * atr_multiplier)

        supertrend = pd.Series(index=df.index, dtype=float)
        trend = pd.Series(index=df.index, dtype=int)

        # Track ratcheted bands separately
        final_upper = upper_band.copy()
        final_lower = lower_band.copy()

        supertrend.iloc[0] = lower_band.iloc[0]
        trend.iloc[0] = 1

        for i in range(1, len(df)):
            # Ratchet bands: lower only moves up, upper only moves down
            final_lower.iloc[i] = max(lower_band.iloc[i], final_lower.iloc[i-1]) if df['close'].iloc[i-1] > final_lower.iloc[i-1] else lower_band.iloc[i]
            final_upper.iloc[i] = min(upper_band.iloc[i], final_upper.iloc[i-1]) if df['close'].iloc[i-1] < final_upper.iloc[i-1] else upper_band.iloc[i]

            if trend.iloc[i-1] == 1:  # Bullish
                if df['close'].iloc[i] <= final_lower.iloc[i]:
                    trend.iloc[i] = -1
                    supertrend.iloc[i] = final_upper.iloc[i]
                else:
                    trend.iloc[i] = 1
                    supertrend.iloc[i] = final_lower.iloc[i]
            else:  # Bearish
                if df['close'].iloc[i] >= final_upper.iloc[i]:
                    trend.iloc[i] = 1
                    supertrend.iloc[i] = final_lower.iloc[i]
                else:
                    trend.iloc[i] = -1
                    supertrend.iloc[i] = final_upper.iloc[i]

        return {
            'supertrend': supertrend,
            'direction': trend,
            'atr': atr_raw
        }






    def get_trend_extreme_stop_loss(self, supertrend_values, directions, current_direction):
        """Get highest/lowest SuperTrend value during continuous trend"""
        if len(directions) == 0:
            return 0
        
        # Find the start of current continuous trend
        trend_start = len(directions) - 1
        for i in range(len(directions) - 2, -1, -1):
            if directions.iloc[i] != current_direction:
                break
            trend_start = i
        
        # Get SuperTrend values for current trend period
        trend_values = supertrend_values.iloc[trend_start:]
        
        if current_direction == 1:  # Bullish trend - use highest value
            return trend_values.max()
        else:  # Bearish trend - use lowest value
            return trend_values.min()

    def calculate_ema_angle(self, ema_series: pd.Series) -> float:
        """Calculate live EMA angle by blending current tick with candle EMA"""
        if len(ema_series) < 2:
            return 0.0
            
        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            return 0.0
            
        prev_ema9 = ema_series.iloc[-2]
        last_ema9 = ema_series.iloc[-1]
        
        # Blend tick price into EMA 9 (Step 4)
        multiplier = 2 / (9 + 1)  # 0.2
        curr_ema9 = (tick.bid * multiplier) + (last_ema9 * (1 - multiplier))
        
        # Calculate slope normalized by price (Step 5)
        slope = ((curr_ema9 - prev_ema9) / prev_ema9) * 100000
        
        # Convert to degrees (Step 6)
        ema_angle = round(math.degrees(math.atan(slope)), 2)
        return ema_angle

    def analyze_timeframe(self, timeframe: str) -> Dict:
        """Updated analysis using Pine Script SuperTrend algorithm"""
        df = self.fetch_data(timeframe, bars=100)
        if df.empty or len(df) < 50:
            return {}
        
        close = df['close']
        
        # RSI calculation (Wilder's smoothing)
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        alpha = 1.0 / 14
        avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
        avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        # --- EMA conditions commented out (replaced by UT Bot) ---
        # ema9 = close.ewm(span=9, adjust=False).mean()
        # ema21 = close.ewm(span=21, adjust=False).mean()
        # ema_angle = self.calculate_ema_angle(ema9)

        # ATR calculation (Wilder's, 20 period)
        atr_val = calculate_atr(df, period=20)
        
        # Cache current ATR for red line calculation
        self._current_atr = atr_val.iloc[-1] if len(atr_val) > 0 and not pd.isna(atr_val.iloc[-1]) else 0.01

        # --- UT Bot Trailing Stop (Key_Value=2.0, ATR_Period=1) ---
        # Get current positions and tick for dynamic trailing
        positions = mt5.positions_get(symbol=self.symbol)
        tick = mt5.symbol_info_tick(self.symbol)
        
        # Also update the red dotted line to reflect current phase
        ut_trail = self.calculate_dynamic_ut_trail(df, positions, tick, key_value=1.0)
        close_arr = close.values
        # Use previous closed candle [-2] for UT trail — stable, not repainting
        ut_buy  = bool(close_arr[-1] > ut_trail[-2])
        ut_sell = bool(close_arr[-1] < ut_trail[-2])
        candle_color = 'GREEN' if close.iloc[-1] > df['open'].iloc[-1] else 'RED'
        
        # Debug UT Bot calculation - REMOVED FOR CLEAN OUTPUT

        return {
                'rsi': rsi.iloc[-1] if len(rsi) > 0 and not pd.isna(rsi.iloc[-1]) else 50,
                'atr': atr_val.iloc[-1] if len(atr_val) > 0 and not pd.isna(atr_val.iloc[-1]) else 0.01,
                'close': close.iloc[-1],
                'open': df['open'].iloc[-1],  # Add open price
                'low': df['low'].iloc[-1],
                'high': df['high'].iloc[-1],
                'candle_color': candle_color,
                'ut_buy': ut_buy,
                'ut_sell': ut_sell,
                'trail_stop': ut_trail[-2],  # previous closed candle — stable value
                'ut_trail_array': ut_trail,  # full array for chart display
                'df': df  # dataframe for chart display
            }




    def calculate_dynamic_ut_trail(self, df: pd.DataFrame, positions, tick, key_value: float = 1.0) -> np.ndarray:
        """Red dotted line shows ACTIVE exit level: Phase 1 (Fixed 1pt SL) → Phase 2 (Dynamic Trail)"""
        # Calculate standard UT trail
        standard_trail = calculate_ut_trail(df, key_value)
        
        # Check if any position exists - show the ACTIVE exit level
        if positions and tick:
            for pos in positions:
                pos_data = self.open_positions.get(pos.ticket, {})
                
                # Check if we're in Phase 2 (dynamic trailing active)
                if pos_data.get('dollar_trail_active', False):
                    # PHASE 2: Show current dynamic trailing stop level
                    if pos.type == mt5.POSITION_TYPE_BUY:
                        trailing_sl = tick.bid - self.trailing_gap  # Current trailing: bid - 1.0
                    else:  # SELL
                        trailing_sl = tick.ask + self.trailing_gap  # Current trailing: ask + 1.0
                    
                    # Override red dotted line with dynamic trailing level
                    modified_trail = standard_trail.copy()
                    modified_trail[-1] = trailing_sl
                    return modified_trail
                
                else:
                    # PHASE 1: Show Fixed 1-Point Stop Loss (ALWAYS ACTIVE, HIGHEST PRIORITY)
                    if pos.type == mt5.POSITION_TYPE_BUY:
                        fixed_sl = pos.price_open - self.fixed_sl_points  # entry - 1.0
                    else:  # SELL
                        fixed_sl = pos.price_open + self.fixed_sl_points  # entry + 1.0
                    
                    # Override red dotted line with Fixed 1pt SL level
                    modified_trail = standard_trail.copy()
                    modified_trail[-1] = fixed_sl
                    return modified_trail
        
        return standard_trail

    def is_sideways_market(self, ut_trail_array, lookback=10, threshold=0.5):
        """Detect sideways market based on UT trail flatness"""
        if len(ut_trail_array) < lookback:
            return False
        
        recent_trail = ut_trail_array[-lookback:]
        trail_range = max(recent_trail) - min(recent_trail)
        
        return trail_range < threshold  # Block if range < 0.5 points

    def check_tick_confirmations(self, signal_type, current_time):
        """Check if we have enough consecutive tick confirmations for entry"""
        if signal_type == "BUY":
            self.tick_confirmations['buy_signals'].append(current_time)
            # Clean old confirmations outside window
            self.tick_confirmations['buy_signals'] = [
                t for t in self.tick_confirmations['buy_signals'] 
                if current_time - t <= self.confirmation_window
            ]
            self.tick_confirmations['sell_signals'].clear()
            confirmations = len(self.tick_confirmations['buy_signals'])
            return confirmations >= self.required_confirmations, confirmations
            
        elif signal_type == "SELL":
            self.tick_confirmations['sell_signals'].append(current_time)
            # Clean old confirmations outside window
            self.tick_confirmations['sell_signals'] = [
                t for t in self.tick_confirmations['sell_signals']
                if current_time - t <= self.confirmation_window
            ]
            self.tick_confirmations['buy_signals'].clear()
            confirmations = len(self.tick_confirmations['sell_signals'])
            return confirmations >= self.required_confirmations, confirmations
        
        return False, 0





    def check_entry_conditions(self, analysis: Dict) -> str:
        """
        MULTI-TICK ENHANCED ENTRY LOGIC
        
        Combines traditional breakout/pullback logic with Multi-Tick momentum analysis:
        1. Traditional UT, RSI, Sideways filters
        2. Multi-Tick momentum confirmation (5-tick analysis)
        3. Breakout/pullback price action validation
        """
        if not analysis:
            return "NONE"

        # Get basic filters (keep existing)
        rsi = analysis.get('rsi', 50)
        ut_buy = analysis.get('ut_buy', False)
        ut_sell = analysis.get('ut_sell', False)
        
        # Get current tick and update tick history
        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            return "NONE"
        
        # Update tick history for Multi-Tick analysis
        self.update_tick_history(tick)
        
        # Get dataframe for previous candle analysis
        df = analysis.get('df')
        if df is None or len(df) < 2:
            return "NONE"
        
        # Use current candle for Multi-Tick analysis
        current_candle = df.iloc[-1]
        current_open = current_candle['open']
        current_high = current_candle['high']
        current_low = current_candle['low']
        
        # Sideways market filter (keep existing)
        ut_trail_array = analysis.get('ut_trail_array', [])
        if self.is_sideways_market(ut_trail_array):
            return "SIDEWAYS"
        
        # MULTI-TICK MOMENTUM ANALYSIS
        buy_momentum, sell_momentum, analysis_type = self.analyze_multi_tick_momentum(
            current_open, current_low, current_high
        )
        
        # Use df.iloc[-2] (previous closed candle) for breakout/pullback validation
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
            # DOJI: ignore (return NONE)
            return "NONE"
        
        # SELL ENTRY LOGIC: UT + RSI + Multi-Tick + Breakout/Pullback
        if ut_sell and rsi < 70 and sell_momentum:  # Add Multi-Tick momentum filter
            if prev_candle_color == "RED":
                # Case 1: Previous RED → price crosses prev_close OR prev_low
                if tick.bid < prev_close or tick.bid < prev_low:
                    trigger = "prev_close" if tick.bid < prev_close else "prev_low"
                    trigger_value = prev_close if trigger == "prev_close" else prev_low
                    self.log(f"🔴 SELL SIGNAL: {analysis_type} + Previous RED → Price {tick.bid:.2f} < {trigger} {trigger_value:.2f}")
                    return "SELL"
            elif prev_candle_color == "GREEN":
                # Case 2: Previous GREEN → price crosses prev_open OR prev_low
                if tick.bid < prev_open or tick.bid < prev_low:
                    trigger = "prev_open" if tick.bid < prev_open else "prev_low"
                    trigger_value = prev_open if trigger == "prev_open" else prev_low
                    self.log(f"🔴 SELL SIGNAL: {analysis_type} + Previous GREEN → Price {tick.bid:.2f} < {trigger} {trigger_value:.2f}")
                    return "SELL"
        
        # BUY ENTRY LOGIC: UT + RSI + Multi-Tick + Breakout/Pullback
        if ut_buy and rsi > 30 and buy_momentum:  # Add Multi-Tick momentum filter
            if prev_candle_color == "GREEN":
                # Case 1: Previous GREEN → price crosses prev_close OR prev_high
                if tick.ask > prev_close or tick.ask > prev_high:
                    trigger = "prev_close" if tick.ask > prev_close else "prev_high"
                    trigger_value = prev_close if trigger == "prev_close" else prev_high
                    self.log(f"🟢 BUY SIGNAL: {analysis_type} + Previous GREEN → Price {tick.ask:.2f} > {trigger} {trigger_value:.2f}")
                    return "BUY"
            elif prev_candle_color == "RED":
                # Case 2: Previous RED → price crosses prev_open OR prev_high
                if tick.ask > prev_open or tick.ask > prev_high:
                    trigger = "prev_open" if tick.ask > prev_open else "prev_high"
                    trigger_value = prev_open if trigger == "prev_open" else prev_high
                    self.log(f"🟢 BUY SIGNAL: {analysis_type} + Previous RED → Price {tick.ask:.2f} > {trigger} {trigger_value:.2f}")
                    return "BUY"
        
        return "NONE"




    def dollars_to_price(self, dollars: float, volume: float) -> float:
        """Convert dollar amount to price distance for the symbol"""
        symbol_info = mt5.symbol_info(self.symbol)
        if not symbol_info:
            return 0.0
        tick_value = symbol_info.trade_tick_value
        tick_size = symbol_info.trade_tick_size
        if tick_value > 0 and volume > 0:
            return (dollars / (volume * tick_value)) * tick_size
        return 0.0

    def execute_trade(self, signal: str, analysis: Dict):
        """Execute trade with fixed 1-point stop loss initially"""
        try:
            tick = mt5.symbol_info_tick(self.symbol)
            if not tick:
                self.log("Failed to get tick data")
                return

            symbol_info = mt5.symbol_info(self.symbol)
            if not symbol_info:
                return

            entry_price = tick.ask if signal == "BUY" else tick.bid
            volume = calculate_dynamic_volume(entry_price, self.symbol)
            
            # Skip trade if volume is too small
            if volume <= 0:
                self.log("⚠️ Trade skipped - volume too small")
                return

            # Start with fixed 1-point stop loss only
            if signal == "BUY":
                initial_sl = round(entry_price - self.fixed_sl_points, symbol_info.digits)  # Fixed 1pt SL
                take_profit = round(entry_price + self.tp_points, symbol_info.digits)
                order_type = mt5.ORDER_TYPE_BUY
                
                self.log(f"📐 BUY Entry: Fixed 1pt SL = {initial_sl:.5f}")
            else:
                initial_sl = round(entry_price + self.fixed_sl_points, symbol_info.digits)  # Fixed 1pt SL
                take_profit = round(entry_price - self.tp_points, symbol_info.digits)
                order_type = mt5.ORDER_TYPE_SELL
                
                self.log(f"📐 SELL Entry: Fixed 1pt SL = {initial_sl:.5f}")

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": volume,
                "type": order_type,
                "price": entry_price,
                "sl": initial_sl,  # Fixed 1-point SL only
                "tp": take_profit,
                "magic": 123456,
                "comment": f"{signal}_Fixed1ptSL",
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)

            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                self.trades_today += 1
                conditions = f"RSI/{analysis.get('rsi', 0):.1f} Candle/{analysis.get('candle_color', '')}"
                
                # Print formatted trade entry box
                self.formatter.print_trade_entry(
                    signal, entry_price, volume, initial_sl, take_profit, 
                    result.order, conditions, self.session_capital, self.trades_today
                )
                
                # Store position data for 2-phase exit system
                self.open_positions[result.order] = {
                    'entry_price': entry_price,
                    'reference_price': tick.bid if signal == 'BUY' else tick.ask,  # bid/ask at entry
                    'entry_time': datetime.now(),
                    'direction': signal,
                    'dollar_trail_active': False,
                    'dollar_trail_sl': None,
                    'phase': 'Fixed 1pt SL'
                }
                
                self.log(f"✅ PHASE 1: Fixed 1pt SL Active | PHASE 2: Dynamic Trail after 0.01pts profit")
            else:
                self.log(f"❌ ORDER FAILED: {result.comment if result else 'Unknown error'}")
        except Exception as e:
            self.log(f"❌ Error executing trade: {e}")

    def check_fixed_sl_exit(self, pos, tick):
        """
        Fixed 1-Point Stop Loss — fires when price moves 1.0 pts against entry.
        Measures from pos.price_open (actual fill price).
        BUY:  tick.bid <= price_open - 1.0  → EXIT
        SELL: tick.ask >= price_open + 1.0  → EXIT
        """
        direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"

        if direction == "BUY":
            loss_pts = pos.price_open - tick.bid
            if loss_pts >= 1.0:
                self.log(
                    f"🛑 [FIXED 1PT SL] BUY #{pos.ticket} | Entry: {pos.price_open:.2f} | "
                    f"Bid: {tick.bid:.2f} | Loss: {loss_pts:.2f}pts → CLOSING"
                )
                close_position(pos.ticket, self.symbol, "Fixed_1pt_SL")
                if pos.ticket in self.open_positions:
                    del self.open_positions[pos.ticket]
                return True
        else:  # SELL
            loss_pts = tick.ask - pos.price_open
            if loss_pts >= 1.0:
                self.log(
                    f"🛑 [FIXED 1PT SL] SELL #{pos.ticket} | Entry: {pos.price_open:.2f} | "
                    f"Ask: {tick.ask:.2f} | Loss: {loss_pts:.2f}pts → CLOSING"
                )
                close_position(pos.ticket, self.symbol, "Fixed_1pt_SL")
                if pos.ticket in self.open_positions:
                    del self.open_positions[pos.ticket]
                return True
        return False

    def calculate_trailing_stop_points(self, pos, tick, pos_data, symbol_info):
        """
        Dynamic Trailing Stop — activates after price moves 0.01 POINTS in profit direction.
        Measures profit from bid_at_entry (BUY) or ask_at_entry (SELL) in POINTS.
        Trails 1.0 pt behind current price, only moves in your favour.
        Returns (trail_sl, is_active, phase_label)
        """
        direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
        
        # Use bid/ask at entry time for profit measurement (NOT fill price)
        reference_price = pos_data.get('reference_price')  # bid at entry for BUY, ask at entry for SELL
        
        if not reference_price:  # Fallback if reference_price not stored
            return None, False, 'Fixed 1pt SL'

        if direction == "BUY":
            # Profit measured from bid at entry time in POINTS
            profit_points = tick.bid - reference_price
            if profit_points >= 0.01:  # 0.01 POINTS profit threshold
                # Activate / advance trail
                new_trail_sl = round(tick.bid - self.trailing_gap, symbol_info.digits)
                best_sl = pos_data.get('dollar_trail_sl') or 0
                if new_trail_sl > best_sl:               # Only ratchet up
                    pos_data['dollar_trail_sl'] = new_trail_sl
                    pos_data['dollar_trail_active'] = True
                    pos_data['phase_label'] = 'Dynamic Trail'
                return pos_data['dollar_trail_sl'], True, 'Dynamic Trail'
            return None, False, 'Fixed 1pt SL'

        else:  # SELL
            # Profit measured from ask at entry time in POINTS
            profit_points = reference_price - tick.ask
            if profit_points >= 0.01:  # 0.01 POINTS profit threshold
                # Activate / advance trail
                new_trail_sl = round(tick.ask + self.trailing_gap, symbol_info.digits)
                best_sl = pos_data.get('dollar_trail_sl')  # None = not yet set
                if best_sl is None or new_trail_sl < best_sl:  # Only ratchet down
                    pos_data['dollar_trail_sl'] = new_trail_sl
                    pos_data['dollar_trail_active'] = True
                    pos_data['phase_label'] = 'Dynamic Trail'
                return pos_data['dollar_trail_sl'], True, 'Dynamic Trail'
            return None, False, 'Fixed 1pt SL'

    def check_exit_conditions(self, analysis: Dict):
        """Two-phase exit management:
        PHASE 1: Fixed 1-point stop loss (hard stop, always on)
        PHASE 2: Dynamic trailing after 0.01 POINTS profit
        """
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return

        tick = mt5.symbol_info_tick(self.symbol)
        if not tick: return

        symbol_info = mt5.symbol_info(self.symbol)
        if not symbol_info: return

        for pos in positions:
            ticket = pos.ticket
            pos_data = self.open_positions.setdefault(ticket, {})
            direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"

            # ── PHASE 1: Fixed 1-Point Stop Loss ──────────────────
            if self.check_fixed_sl_exit(pos, tick):
                continue

            # ── PHASE 2: Dynamic Trailing (after 0.01 POINTS profit) ────
            dollar_trail_sl, trail_active, phase_label = self.calculate_trailing_stop_points(
                pos, tick, pos_data, symbol_info
            )

            # Apply dynamic trailing if active
            if trail_active and dollar_trail_sl:
                final_sl = dollar_trail_sl
                final_label = 'Dynamic Trail'
                
                # Apply dynamic trailing SL
                if direction == "BUY":
                    if final_sl > pos.sl:
                        modify_position(ticket, self.symbol, final_sl, pos.tp)
                        self.log(f"🚀 [{final_label}] BUY #{ticket} | SL → {final_sl:.2f}")
                else:
                    if pos.sl == 0 or final_sl < pos.sl:
                        modify_position(ticket, self.symbol, final_sl, pos.tp)
                        self.log(f"🚀 [{final_label}] SELL #{ticket} | SL → {final_sl:.2f}")
            else:
                # Phase 1: Show fixed 1-point SL status
                reference_price = pos_data.get('reference_price', pos.price_open)
                if direction == "BUY":
                    profit_points = tick.bid - reference_price
                    fixed_sl = round(pos.price_open - 1.0, 2)
                else:
                    profit_points = reference_price - tick.ask
                    fixed_sl = round(pos.price_open + 1.0, 2)
                
                self.log(f"📍 [Fixed 1pt SL] {direction} #{ticket} | SL: {fixed_sl:.2f} | Profit: {profit_points:.3f}pts | Need: 0.01pts for Dynamic Trail")
        




    def update_chart(self, analysis: Dict):
        """Update live chart with UT trail red dotted line"""
        if not self.enable_chart:
            return
            
        try:
            df = analysis.get('df')
            ut_trail_array = analysis.get('ut_trail_array')
            current_price = analysis.get('close')
            live_ut_trail = analysis.get('trail_stop')
            
            if df is None or ut_trail_array is None:
                return
                
            self.ax.clear()
            
            # Plot last 50 candles for better visibility
            plot_df = df.tail(50)
            plot_ut = ut_trail_array[-50:]
            
            # Plot price line
            self.ax.plot(range(len(plot_df)), plot_df['close'], 'b-', linewidth=1.5, label='Price')
            
            # Plot UT Trail as RED DOTTED LINE
            self.ax.plot(range(len(plot_ut)), plot_ut, 'r:', linewidth=2, label='UT Trail', alpha=0.8)
            
            # Highlight current live UT trail as horizontal line
            self.ax.axhline(y=live_ut_trail, color='red', linestyle='--', linewidth=2, alpha=0.9, 
                          label=f'Live UT Trail: {live_ut_trail:.2f}')
            
            # Current price marker
            self.ax.axhline(y=current_price, color='blue', linestyle='-', alpha=0.7, 
                          label=f'Current Price: {current_price:.2f}')
            
            # Mark positions if any
            positions = mt5.positions_get(symbol=self.symbol)
            if positions:
                pos = positions[0]
                color = 'green' if pos.type == mt5.POSITION_TYPE_BUY else 'red'
                self.ax.axhline(y=pos.price_open, color=color, linestyle='-', alpha=0.5,
                              label=f'Entry: {pos.price_open:.2f}')
            
            self.ax.set_title(f'{self.symbol} - UT Bot Strategy (Red Dotted = UT Trail)')
            self.ax.legend(loc='upper left')
            self.ax.grid(True, alpha=0.3)
            
            plt.draw()
            plt.pause(0.01)
            
        except Exception as e:
            print(f"Chart update error: {e}")



    def run_strategy(self):
        """Main strategy execution loop"""
        self.tick_count += 1
        
        # Analyze current timeframe
        analysis = self.analyze_timeframe(self.base_timeframe)
        if not analysis:
            return
        
        # Check for entry signals and current positions
        signal = self.check_entry_conditions(analysis)
        positions = mt5.positions_get(symbol=self.symbol)
        
        # Remove deactivation message since trading is now active
        # Determine Status string
        if positions:
            status = "IN_TRADE"
        elif signal == "SIDEWAYS":
            status = "SIDEWAYS"
        elif signal != "NONE":
            status = f"SIGNAL: {signal}"
        else:
            status = "WAITING"

        # Add colored signal detection output
        if signal != "NONE":
            colored_rsi = self.formatter.colorize_rsi(f"RSI:{analysis.get('rsi', 0):.1f}")
            colored_trail = self.formatter.colorize_trail(f"Trail:{analysis.get('trail_stop', 0):.2f}")
            colored_candle = self.formatter.colorize_candle(f"Candle:{analysis.get('candle_color', '')}")
            colored_price = self.formatter.colorize_price(f"{analysis.get('close', 0):.2f}")
            
            signal_line = f"[SIGNAL] {signal} | {colored_rsi} | {colored_trail} | {colored_candle} | Low:{analysis.get('low', 0):.2f} | High:{analysis.get('high', 0):.2f}"
            print(signal_line)
        
        # Show Multi-Tick analysis for debugging (every 10 ticks to avoid spam)
        if self.tick_count % 10 == 0 and len(self.tick_history) >= 3:
            tick = mt5.symbol_info_tick(self.symbol)
            if tick and analysis:
                df = analysis.get('df')
                if df is not None and len(df) >= 1:
                    current_candle = df.iloc[-1]
                    buy_momentum, sell_momentum, analysis_type = self.analyze_multi_tick_momentum(
                        current_candle['open'], current_candle['low'], current_candle['high']
                    )
                    momentum_threshold_pct = 60.0
                    buy_status = "✅ PASSES" if buy_momentum else "❌ FAILS"
                    sell_status = "✅ PASSES" if sell_momentum else "❌ FAILS"
                    
                    print(f"\n[MULTI-TICK DEBUG] {analysis_type}")
                    print(f"BUY Momentum : {buy_status} threshold ({momentum_threshold_pct}%)")
                    print(f"SELL Momentum: {sell_status} threshold ({momentum_threshold_pct}%)\n")

        trade_info_str = ""
        if positions:
            pos0 = positions[0]
            tick0 = mt5.symbol_info_tick(self.symbol)
            if tick0:
                pos0_data = self.open_positions.get(pos0.ticket, {})
                
                # Use correct reference prices for move calculation
                if pos0.type == mt5.POSITION_TYPE_BUY:
                    entry_bid = pos0_data.get('entry_bid', pos0.price_open)
                    pm = tick0.bid - entry_bid  # bid-to-bid comparison
                    trail_sl_live = round(tick0.bid - self.trailing_gap, 2)
                    pnl = (tick0.bid - pos0.price_open) * pos0.volume
                else:
                    entry_ask = pos0_data.get('entry_ask', pos0.price_open)
                    pm = entry_ask - tick0.ask  # ask-to-ask comparison (inverted)
                    trail_sl_live = round(tick0.ask + self.trailing_gap, 2)
                    pnl = (pos0.price_open - tick0.ask) * pos0.volume
                    
                trail_status = "ACTIVE" if pm >= self.trailing_points else f"need {self.trailing_points - pm:.2f}more"
                trade_info_str = f"Move: {pm:.2f}pts | Trail: {trail_status} | TrailSL: {trail_sl_live:.2f} | BrokerSL: {pos0.sl:.2f} | "
                
                # Print position update with P/L
                self.formatter.print_position_update(
                    pos0.ticket, analysis['trail_stop'], analysis['close'],
                    analysis['rsi'], analysis['candle_color'], "IN_POSITION", pnl
                )
                return  # Skip regular log when in position

        # Consolidate log into a single compact line with colors
        colored_price = self.formatter.colorize_price(f"{analysis['close']:.2f}")
        colored_trail = self.formatter.colorize_trail(f"{analysis['trail_stop']:.2f}")
        colored_rsi = self.formatter.colorize_rsi(f"{analysis['rsi']:.1f}")
        colored_candle = self.formatter.colorize_candle(analysis['candle_color'])
        colored_status = self.formatter.colorize_status(status)
        colored_tick = self.formatter.colorize_ticket(f"#{self.tick_count}")
        
        log_line = (
            f"Tick{colored_tick} | "
            f"Price: {colored_price} | "
            f"UTTrail: {colored_trail} | "
            f"RSI: {colored_rsi} | "
            f"Candle: {colored_candle} | "
            f"UT_Buy: {analysis['ut_buy']} | UT_Sell: {analysis['ut_sell']} | "
            + trade_info_str
            + f"Status: {colored_status}"
        )
        self.log(log_line)

        # Execute signals (only entry allowed)
        if signal != "NONE" and signal != "SIDEWAYS" and not positions:
            # Check consecutive tick confirmations (2 ticks)
            current_time = datetime.now().timestamp()
            confirmed, current_confirmations = self.check_tick_confirmations(signal, current_time)
            
            if confirmed:
                self.log(f"✅ {signal} CONFIRMED after {current_confirmations} ticks!")
                self.execute_trade(signal, analysis)
            else:
                remaining = self.required_confirmations - current_confirmations
                self.log(f"⏳ {signal} - {current_confirmations}/{self.required_confirmations} confirmations (need {remaining} more)")
        else:
            # Clear confirmations if no signal present
            self.tick_confirmations['buy_signals'].clear()
            self.tick_confirmations['sell_signals'].clear()
        
        # Check exit conditions (Phase 1 and Phase 2)
        if positions:
            self.check_exit_conditions(analysis)
        
        # Update chart display (red dotted line)
        if self.tick_count % 5 == 0:  # Update chart every 5 ticks for performance
            self.update_chart(analysis)

# Usage example
if __name__ == "__main__":
    import time
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
    
    # Create strategy instance with chart enabled
    strategy = EnhancedTradingStrategy("XAUUSD", "M1", enable_chart=True)
    
    # Run strategy loop
    try:
        while True:
            strategy.run_strategy()
            time.sleep(1)  # Check every 1 second for real-time
    except KeyboardInterrupt:
        print("\nStrategy stopped by user")
    finally:
        mt5.shutdown()