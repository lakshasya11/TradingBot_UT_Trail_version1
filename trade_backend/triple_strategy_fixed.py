import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any
from trading_utils import calculate_rsi_wilder, calculate_ut_trail, calculate_atr, calculate_dynamic_volume, is_sideways_market, calculate_triple_indicators, calculate_trailing_stop_points, check_2dollar_reversal_exit
from trading_operations import close_position, modify_position, execute_market_order
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
        self.trailing_points = 0.0
        self.trailing_gap = 1.0         # Trail 1.0 pts behind current price
        self.fixed_sl_points = 1.0      # Fixed 1-point stop loss exit
        self.enable_chart = enable_chart and CHART_AVAILABLE
        
        # Trading state
        self.position_data = {}  # ticket: {metadata}
        
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
        New Consensus for 5M Trading:
        1. Trigger: 5M chart must show a fresh UT crossover.
        2. Trend: 15M and 1H charts must be on the same side of the UT line.
        """
        # 1. Check 5M Trigger
        df_5m = self.multi_tf_data.get('5M')
        if df_5m is None or df_5m.empty:
            return "NONE"
        
        # Add sideways filter using 5M UT trail data
        ut_trail_5m = calculate_ut_trail(df_5m, key_value=1.0)
        if is_sideways_market(ut_trail_5m):
            return "SIDEWAYS"  # Block trades
        
        last_5m = df_5m.iloc[-1]
        candle_green_5m = last_5m['close'] > last_5m['open']
        candle_red_5m   = last_5m['close'] < last_5m['open']

        # Get current tick for momentum check
        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            return "NONE"

        # Price momentum conditions - Use OR logic for better flexibility
        # BUY: Current price > candle open OR current price > candle low (rising upward)
        buy_momentum1 = tick.bid > last_5m['open']   # Above open
        buy_momentum2 = tick.bid > last_5m['low']    # Above low
        buy_momentum = buy_momentum1 or buy_momentum2  # Either condition works
        
        # SELL: Current price < candle open OR current price < candle high (falling downward)
        sell_momentum1 = tick.ask < last_5m['open']  # Below open
        sell_momentum2 = tick.ask < last_5m['high']  # Below high
        sell_momentum = sell_momentum1 or sell_momentum2  # Either condition works

        # BUY: ut_buy + RSI > 30 + GREEN candle + BOTH momentum conditions (ALL 5 must be true)
        trigger_buy  = last_5m['ut_buy'] and last_5m['rsi'] > 30 and candle_green_5m and buy_momentum
        # SELL: ut_sell + RSI < 70 + RED candle + BOTH momentum conditions (ALL 5 must be true)
        trigger_sell = last_5m['ut_sell'] and last_5m['rsi'] < 70 and candle_red_5m and sell_momentum

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

        # Final Unified Signals
        if trigger_buy and last_15m['ut_bullish'] and last_1h['ut_bullish']:
            self.log("🎯 5M BUY TRIGGER with 15M/1H Trend Confirmation")
            return "UNIFIED_BUY_TRIPLE_CONFIRM"
            
        elif trigger_sell and last_15m['ut_bearish'] and last_1h['ut_bearish']:
            self.log("🎯 5M SELL TRIGGER with 15M/1H Trend Confirmation")
            return "UNIFIED_SELL_TRIPLE_CONFIRM"
            
        return "NONE"



    def execute_trade(self, signal):
        """Execute trade with 3-step exit system"""
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
            
            # Set initial fixed 1pt SL
            if direction == "BUY":
                initial_sl = round(entry_price - 1.0, 2)  # Fixed 1pt SL
                take_profit = round(entry_price + 4.0, 2)  # 4.0 points distance
                order_type = mt5.ORDER_TYPE_BUY
                self.log(f"📐 BUY [Fixed 1pt SL] → {initial_sl:.2f} | Entry: {entry_price:.2f}")
            else:
                initial_sl = round(entry_price + 1.0, 2)  # Fixed 1pt SL
                take_profit = round(entry_price - 4.0, 2)  # 4.0 points distance
                order_type = mt5.ORDER_TYPE_SELL
                self.log(f"📐 SELL [Fixed 1pt SL] → {initial_sl:.2f} | Entry: {entry_price:.2f}")
            
            symbol_info = mt5.symbol_info(self.symbol)
            if not symbol_info:
                self.log("Failed to get symbol info")
                return
            
            # Round to symbol digits
            digits = symbol_info.digits
            initial_sl = round(initial_sl, digits)
            take_profit = round(take_profit, digits)
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": volume,
                "type": order_type,
                "price": entry_price,
                "sl": initial_sl,  # Set fixed 1pt SL
                "tp": take_profit,
                "magic": 123456,
                "comment": f"{signal[:20]}_3StepExit",
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)
            
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                self.log(f"✅ ORDER EXECUTED: {signal} | Fixed 1pt SL: {initial_sl} | TP: {take_profit}"))
                
                # Store position data for 2-phase exit
                self.position_data[result.order] = {
                    'entry_price': entry_price,
                    'reference_price': tick.bid if direction == 'BUY' else tick.ask,  # bid/ask at entry
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
            self.log(f"🎯 EXECUTE SIGNAL: {signal}")
            self.execute_trade(signal)
        else:
            self.log(f"Status: {signal}")

        # Monitor all exit conditions every cycle
        self.check_exit_conditions()