import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any
from trading_utils import calculate_rsi_wilder, calculate_ut_trail, calculate_atr, calculate_dynamic_volume, is_sideways_market, calculate_triple_indicators, check_1dollar_reversal_exit
from trading_operations import close_position, modify_position, execute_market_order
from tick_config import REQUIRED_CONFIRMATIONS, CONFIRMATION_WINDOW
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    CHART_AVAILABLE = True
except ImportError:
    CHART_AVAILABLE = False
    print("Matplotlib not available. Chart display disabled.")



class TripleConfirmationBot:
    
    # Define the required timeframes and their MT5 values
    MULTI_TF_MAP = {
        '1M': mt5.TIMEFRAME_M1,
        '5M': mt5.TIMEFRAME_M5,
        '15M': mt5.TIMEFRAME_M15,
        '30M': mt5.TIMEFRAME_M30,
        '1H': mt5.TIMEFRAME_H1,
        '1D': mt5.TIMEFRAME_D1
    }
    
    def __init__(self, symbol: str, enable_chart: bool = True):
        self.symbol = symbol
        self.log_queue = []
        self.multi_tf_data: Dict[str, pd.DataFrame] = {}
        self.is_running = False
        self.breakeven_activated = {}   # ticket: True
        self.trailing_sl = {}           # ticket: current trailing sl value
        self.breakeven_points = 3.0
        self.trailing_points = 0.01     # Activate trailing after 0.01 points profit
        self.trailing_gap = 1.0         # Trail 1.0 pts behind current price
        self.fixed_sl_points = 1.0      # Fixed 1-point stop loss exit
        self.enable_chart = enable_chart and CHART_AVAILABLE
        
        # Trading state
        self.position_data = {}  # ticket: {metadata}
        
        # Tick confirmation system
        self.tick_confirmations = {
            'buy_signals': [],
            'sell_signals': []
        }
        self.required_confirmations = REQUIRED_CONFIRMATIONS
        self.confirmation_window = CONFIRMATION_WINDOW
        
        # Chart setup
        if self.enable_chart:
            plt.ion()
            self.fig, self.ax = plt.subplots(figsize=(12, 8))

    def log(self, message: str):
        """Simple logging utility."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{self.symbol}] {message}"
        print(log_entry)
        self.log_queue.append(log_entry)

    def fetch_multi_timeframe_data(self):
        """Fetches data for all 6 timeframes and calculates indicators."""
        self.log("Starting Multi-Timeframe Data Fetch...")
        for tf_name, tf_value in self.MULTI_TF_MAP.items():
            try:
                # Fetch last 500 bars for calculation stability
                rates = mt5.copy_rates_from_pos(self.symbol, tf_value, 0, 100) 
                
                if rates is not None and len(rates) > 30:
                    df = pd.DataFrame(rates)
                    df['time'] = pd.to_datetime(df['time'], unit='s')
                    df = calculate_triple_indicators(df)
                    self.multi_tf_data[tf_name] = df
                    self.log(f"✅ Data for {tf_name} loaded ({len(df)} bars).")
                else:
                    self.log(f"⚠️ Data for {tf_name} failed or insufficient data.")
                    
            except Exception as e:
                self.log(f"❌ Error fetching {tf_name} data: {e}")

    def check_multi_timeframe_consensus(self):
        """
        Updated Multi-Timeframe Consensus with Breakout/Pullback Entry:
        1. Trigger: 5M chart uses breakout/pullback logic (not momentum)
        2. Trend: 15M and 1H charts must be on the same side of the UT line
        """
        # 1. Check 5M Trigger with Breakout/Pullback Logic
        df_5m = self.multi_tf_data.get('5M')
        if df_5m is None or df_5m.empty or len(df_5m) < 2:
            return "NONE"
        
        # Add sideways filter using 5M UT trail data
        ut_trail_5m = calculate_ut_trail(df_5m, key_value=1.0)
        if is_sideways_market(ut_trail_5m):
            return "SIDEWAYS"  # Block trades
        
        last_5m = df_5m.iloc[-1]  # Current candle
        prev_5m = df_5m.iloc[-2]  # Previous closed candle
        
        # Get current tick for breakout/pullback check
        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            return "NONE"
        
        # Previous candle color determination
        if prev_5m['close'] > prev_5m['open']:
            prev_candle_color = "GREEN"
        elif prev_5m['close'] < prev_5m['open']:
            prev_candle_color = "RED"
        else:
            return "NONE"  # DOJI - ignore
        
        # Breakout/Pullback Entry Logic for 5M
        trigger_buy = False
        trigger_sell = False
        
        # SELL Entry Logic
        if last_5m['ut_bearish'] and last_5m['rsi'] < 70:
            if prev_candle_color == "RED":
                # Case 1: Previous RED → price crosses prev_close OR prev_low
                if tick.bid < prev_5m['close'] or tick.bid < prev_5m['low']:
                    trigger_sell = True
                    trigger_level = prev_5m['close'] if tick.bid < prev_5m['close'] else prev_5m['low']
                    self.log(f"🔴 5M SELL: Previous RED → Price {tick.bid:.2f} < {trigger_level:.2f}")
            elif prev_candle_color == "GREEN":
                # Case 2: Previous GREEN → price <= prev_open OR prev_low
                if tick.bid <= prev_5m['open'] or tick.bid <= prev_5m['low']:
                    trigger_sell = True
                    trigger_level = prev_5m['open'] if tick.bid <= prev_5m['open'] else prev_5m['low']
                    self.log(f"🔴 5M SELL: Previous GREEN → Price {tick.bid:.2f} <= {trigger_level:.2f}")
        
        # BUY Entry Logic
        if last_5m['ut_bullish'] and last_5m['rsi'] > 30:
            if prev_candle_color == "GREEN":
                # Case 1: Previous GREEN → price crosses prev_close OR prev_high
                if tick.ask > prev_5m['close'] or tick.ask > prev_5m['high']:
                    trigger_buy = True
                    trigger_level = prev_5m['close'] if tick.ask > prev_5m['close'] else prev_5m['high']
                    self.log(f"🟢 5M BUY: Previous GREEN → Price {tick.ask:.2f} > {trigger_level:.2f}")
            elif prev_candle_color == "RED":
                # Case 2: Previous RED → price >= prev_open OR prev_high
                if tick.ask >= prev_5m['open'] or tick.ask >= prev_5m['high']:
                    trigger_buy = True
                    trigger_level = prev_5m['open'] if tick.ask >= prev_5m['open'] else prev_5m['high']
                    self.log(f"🟢 5M BUY: Previous RED → Price {tick.ask:.2f} >= {trigger_level:.2f}")
        
        if not trigger_buy and not trigger_sell:
            return "NONE"

        # 2. Check 15M Trend
        df_15m = self.multi_tf_data.get('15M')
        if df_15m is None or df_15m.empty:
            return "NONE"
        last_15m = df_15m.iloc[-1]
        
        # 3. Check 1H Trend
        df_1h = self.multi_tf_data.get('1H')
        if df_1h is None or df_1h.empty:
            return "NONE"
        last_1h = df_1h.iloc[-1]

        # Final Unified Signals with Breakout/Pullback Trigger
        if trigger_buy and last_15m['ut_bullish'] and last_1h['ut_bullish']:
            return "BUY_CONFIRMED"
            
        elif trigger_sell and last_15m['ut_bearish'] and last_1h['ut_bearish']:
            return "SELL_CONFIRMED"
            
        return "NONE"

    def check_tick_confirmations(self, signal_type, current_time):
        """Check if we have enough consecutive tick confirmations for entry"""
        if signal_type == "BUY_CONFIRMED":
            self.tick_confirmations['buy_signals'].append(current_time)
            # Clean old confirmations outside window
            self.tick_confirmations['buy_signals'] = [
                t for t in self.tick_confirmations['buy_signals'] 
                if current_time - t <= self.confirmation_window
            ]
            self.tick_confirmations['sell_signals'].clear()
            confirmations = len(self.tick_confirmations['buy_signals'])
            return confirmations >= self.required_confirmations, confirmations
            
        elif signal_type == "SELL_CONFIRMED":
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

    def calculate_stop_loss(self, direction, entry_price):
        """Calculate stop loss using tighter of ATR SL or UT Trail from 15M timeframe"""
        tf_15m = self.multi_tf_data.get('15M')
        if tf_15m is None or tf_15m.empty:
            return entry_price * 0.98 if direction == "BUY" else entry_price * 1.02

        atr = tf_15m['atr14'].iloc[-1]
        ut_sl = tf_15m['ut_trail'].iloc[-1]
        atr_multiplier = 1.5

        if direction == "BUY":
            atr_sl = entry_price - (atr * atr_multiplier)
            stop_loss = max(atr_sl, ut_sl)  # closer to entry = higher
        else:
            atr_sl = entry_price + (atr * atr_multiplier)
            stop_loss = min(atr_sl, ut_sl)  # closer to entry = lower

        sl_source = "UT Trail" if (direction == "BUY" and ut_sl > atr_sl) or (direction == "SELL" and ut_sl < atr_sl) else "ATR SL"
        self.log(f"📐 SL Source: {sl_source} | ATR SL: {atr_sl:.5f} | UT Trail: {ut_sl:.5f} | Final SL: {stop_loss:.5f}")
        return stop_loss, ut_sl
    


    def execute_trade(self, signal):
        """Execute trade with immediate trailing stop activation"""
        direction = "BUY" if "BUY" in signal else "SELL"
        
        try:
            tick = mt5.symbol_info_tick(self.symbol)
            if not tick:
                self.log("Failed to get tick data")
                return

            entry_price = tick.ask if direction == "BUY" else tick.bid
            volume = calculate_dynamic_volume(entry_price, self.symbol)
            
            # Skip trade if volume is too small
            if volume <= 0:
                self.log("⚠️ Trade skipped - volume too small")
                return
            
            # Set initial trailing stop as broker SL (1 point gap)
            if direction == "BUY":
                initial_trailing_sl = round(tick.bid - self.trailing_gap, 2)
                take_profit = round(entry_price + 4.0, 2)  # 4.0 points distance
                order_type = mt5.ORDER_TYPE_BUY
                self.log(f"📐 BUY Initial Trailing SL: {initial_trailing_sl:.5f} | Entry: {entry_price:.5f}")
            else:
                initial_trailing_sl = round(tick.ask + self.trailing_gap, 2)
                take_profit = round(entry_price - 4.0, 2)  # 4.0 points distance
                order_type = mt5.ORDER_TYPE_SELL
                self.log(f"📐 SELL Initial Trailing SL: {initial_trailing_sl:.5f} | Entry: {entry_price:.5f}")
            
            symbol_info = mt5.symbol_info(self.symbol)
            if not symbol_info:
                self.log("Failed to get symbol info")
                return
            
            # Round to symbol digits
            digits = symbol_info.digits
            initial_trailing_sl = round(initial_trailing_sl, digits)
            take_profit = round(take_profit, digits)
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": volume,
                "type": order_type,
                "price": entry_price,
                "sl": initial_trailing_sl,  # Set trailing SL immediately
                "tp": take_profit,
                "magic": 123456,
                "comment": f"{signal[:20]}_TrailingOnly",
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)
            
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                self.log(f"✅ ORDER EXECUTED: {signal} | Initial Trailing SL: {initial_trailing_sl} | TP: {take_profit}")
                
                # Store position data with trailing NOT active yet
                self.position_data[result.order] = {
                    'entry_price': entry_price,
                    'reference_price': tick.bid if direction == 'BUY' else tick.ask,  # bid/ask at entry for trail activation
                    'entry_time': datetime.now(),
                    'direction': direction,
                    'dollar_trail_active': False,   # Starts in Phase 1 (Fixed 1pt SL)
                    'dollar_trail_sl': None,        # Set when $0.01 profit reached
                    'phase_label': 'Fixed 1pt SL'   # Current phase label for display
                }
                
                self.log(f"✅ PHASE 1: Fixed 1pt SL Active | PHASE 2: Dynamic Trail after 0.01pts profit")
            else:
                self.log(f"❌ ORDER FAILED: {result.comment if result else 'Unknown error'}")

        except Exception as e:
            self.log(f"❌ Error executing trade: {e}")

    def check_exit_conditions(self):
        """Two-phase exit management:
        PHASE 1: Fixed 1-point stop loss (hard stop, always on)
        PHASE 2: Dynamic trailing after 0.01 POINTS profit
        """
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return
        
        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            return
        
        symbol_info = mt5.symbol_info(self.symbol)
        if not symbol_info:
            return

        for pos in positions:
            ticket = pos.ticket
            pos_data = self.position_data.setdefault(ticket, {})
            direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"

            # ── PHASE 1: Fixed 1-Point Stop Loss ──────────────────
            if self.check_fixed_sl_exit(pos, tick):
                continue

            # ── PHASE 2: Dynamic Trailing (after 0.01 POINTS profit) ────
            dollar_trail_sl, trail_active, phase_label = self.calculate_trailing_stop_dollars(
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
                if pos.ticket in self.position_data:
                    del self.position_data[pos.ticket]
                return True
        else:  # SELL
            loss_pts = tick.ask - pos.price_open
            if loss_pts >= 1.0:
                self.log(
                    f"🛑 [FIXED 1PT SL] SELL #{pos.ticket} | Entry: {pos.price_open:.2f} | "
                    f"Ask: {tick.ask:.2f} | Loss: {loss_pts:.2f}pts → CLOSING"
                )
                close_position(pos.ticket, self.symbol, "Fixed_1pt_SL")
                if pos.ticket in self.position_data:
                    del self.position_data[pos.ticket]
                return True
        return False

    def calculate_trailing_stop_dollars(self, pos, tick, pos_data, symbol_info):
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
                new_trail_sl = round(tick.bid - 1.0, symbol_info.digits)
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
                new_trail_sl = round(tick.ask + 1.0, symbol_info.digits)
                best_sl = pos_data.get('dollar_trail_sl')  # None = not yet set
                if best_sl is None or new_trail_sl < best_sl:  # Only ratchet down
                    pos_data['dollar_trail_sl'] = new_trail_sl
                    pos_data['dollar_trail_active'] = True
                    pos_data['phase_label'] = 'Dynamic Trail'
                return pos_data['dollar_trail_sl'], True, 'Dynamic Trail'
            return None, False, 'Fixed 1pt SL'

    def calculate_dynamic_ut_trail(self, df, tick):
        """UT Bot trail that shows the ACTIVE exit condition as red dotted line"""
        # Calculate standard UT trail
        standard_trail = self.calculate_ut_trail(df, key_value=1.0)
        
        # Check if any position exists - show the ACTIVE exit level
        positions = mt5.positions_get(symbol=self.symbol)
        if positions and tick:
            for pos in positions:
                # Check if we're in Phase 2 (trailing active)
                if hasattr(self, '_trailing_active') and self._trailing_active.get(pos.ticket, False):
                    # PHASE 2: Show current trailing stop level
                    if pos.type == mt5.POSITION_TYPE_BUY:
                        trailing_sl = tick.bid - self.trailing_gap  # Current trailing level
                        print(f"[RED_LINE] PHASE 2 BUY | Trailing SL: {trailing_sl:.2f} (ONLY ACTIVE EXIT)")
                    else:  # SELL
                        trailing_sl = tick.ask + self.trailing_gap  # Current trailing level
                        print(f"[RED_LINE] PHASE 2 SELL | Trailing SL: {trailing_sl:.2f} (ONLY ACTIVE EXIT)")
                    
                    # Override red dotted line with trailing SL level
                    modified_trail = standard_trail.copy()
                    modified_trail[-1] = trailing_sl
                    return modified_trail
                
                else:
                    # PHASE 1: Show 1-point fixed SL level (static)
                    if pos.type == mt5.POSITION_TYPE_BUY:
                        fixed_sl_level = pos.price_open - self.fixed_sl_points  # 1.0 points below entry
                        print(f"[RED_LINE] PHASE 1 BUY | Fixed 1pt SL: {fixed_sl_level:.2f} (BROKER SL)")
                    else:  # SELL
                        fixed_sl_level = pos.price_open + self.fixed_sl_points  # 1.0 points above entry
                        print(f"[RED_LINE] PHASE 1 SELL | Fixed 1pt SL: {fixed_sl_level:.2f} (BROKER SL)")
                    
                    # Override red dotted line with 1-point fixed SL
                    modified_trail = standard_trail.copy()
                    modified_trail[-1] = fixed_sl_level
                    return modified_trail
        
        return standard_trail





    def update_chart(self):
        """Update live chart with UT trail red dotted line"""
        if not self.enable_chart:
            return
            
        try:
            # Get 5M data for chart (main trading timeframe)
            df_5m = self.multi_tf_data.get('5M')
            if df_5m is None or df_5m.empty:
                return
                
            tick = mt5.symbol_info_tick(self.symbol)
            if not tick:
                return
                
            # Calculate dynamic UT trail
            ut_trail_array = self.calculate_dynamic_ut_trail(df_5m, tick)
            current_price = df_5m['close'].iloc[-1]
            live_ut_trail = ut_trail_array[-1] if len(ut_trail_array) > 0 else 0
            
            self.ax.clear()
            
            # Plot last 50 candles
            plot_df = df_5m.tail(50)
            plot_ut = ut_trail_array[-50:] if len(ut_trail_array) >= 50 else ut_trail_array
            
            # Plot price line
            self.ax.plot(range(len(plot_df)), plot_df['close'], 'b-', linewidth=1.5, label='Price (5M)')
            
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
            
            # Check trailing mode
            trailing_mode = "TRAILING" if hasattr(self, '_trailing_active') and any(
                self._trailing_active.get(pos.ticket, False) for pos in positions
            ) else "STANDARD"
            
            self.ax.set_title(f'{self.symbol} - Multi-TF Strategy (Mode: {trailing_mode}) - Red Dotted = UT Trail')
            self.ax.legend(loc='upper left')
            self.ax.grid(True, alpha=0.3)
            
            plt.draw()
            plt.pause(0.01)
            
        except Exception as e:
            print(f"Chart update error: {e}")




    def run_strategy_cycle(self):
        """Simple loop to run data fetch and signal check."""
        if not self.is_running:
            self.log("Strategy is not running.")
            return
            
        self.fetch_multi_timeframe_data()
        signal = self.check_multi_timeframe_consensus()

        if signal == "SIDEWAYS":
            self.log("🔄 SIDEWAYS MARKET DETECTED - Trades blocked")
        elif signal != "NONE" and not mt5.positions_get(symbol=self.symbol):
            # Check tick confirmations for valid signals
            current_time = datetime.now().timestamp()
            confirmed, current_confirmations = self.check_tick_confirmations(signal, current_time)
            
            if confirmed:
                self.log(f"🎯 EXECUTE SIGNAL: {signal} confirmed after {current_confirmations} ticks!")
                self.execute_trade(signal)
            else:
                remaining = self.required_confirmations - current_confirmations
                self.log(f"⏳ {signal} - {current_confirmations}/{self.required_confirmations} confirmations (need {remaining} more)")
        else:
            # Clear confirmations if no signal present
            self.tick_confirmations['buy_signals'].clear()
            self.tick_confirmations['sell_signals'].clear()
            if signal != "NONE":
                self.log(f"Status: {signal}")

        # Monitor all exit conditions every cycle
        self.check_exit_conditions()
        
        # Update chart display (red dotted line) every 10 seconds
        if hasattr(self, '_last_chart_update'):
            if (datetime.now() - self._last_chart_update).total_seconds() >= 10:
                self.update_chart()
                self._last_chart_update = datetime.now()
        else:
            self._last_chart_update = datetime.now()
            self.update_chart()