import MetaTrader5 as mt5
import numpy as np
import time
from datetime import datetime
import pytz
import os
import sys
from dotenv import load_dotenv
from enhanced_strategy import EnhancedTradingStrategy
from terminal_formatter import TerminalFormatter
from tick_config import REQUIRED_CONFIRMATIONS, CONFIRMATION_WINDOW

# Enable Windows ANSI colors
def enable_windows_colors():
    """Enable ANSI colors on Windows"""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            return True
        except:
            return False
    return True

# Enable colors at import
enable_windows_colors()

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    CHART_AVAILABLE = True
except ImportError:
    CHART_AVAILABLE = False
    print("Matplotlib not available. Chart display disabled.")

# ANSI color codes for terminal highlighting
class Colors:
    # Force enable colors by setting environment variable
    import os
    os.environ['FORCE_COLOR'] = '1'
    
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    RESET = '\033[0m'
    PURPLE = '\033[95m'  # Same as MAGENTA
    ORANGE = '\033[38;5;208m'  # Orange color
    BLUE = '\033[94m'  # Blue color
    
    @staticmethod
    def get_candle_color(candle_type):
        """Get color based on candle type"""
        return Colors.GREEN if candle_type == 'GREEN' else Colors.RED
    
    @staticmethod
    def test_colors():
        """Test if colors are working"""
        print(f"{Colors.RED}RED{Colors.RESET} {Colors.GREEN}GREEN{Colors.RESET} {Colors.YELLOW}YELLOW{Colors.RESET} {Colors.BLUE}BLUE{Colors.RESET}")
        print(f"{Colors.MAGENTA}MAGENTA{Colors.RESET} {Colors.CYAN}CYAN{Colors.RESET} {Colors.ORANGE}ORANGE{Colors.RESET}")

class TradingBot:
    def __init__(self, symbol="XAUUSD", timeframe="M1", enable_chart=True):
        self.symbol = symbol
        self.timeframe = timeframe
        self.strategy = EnhancedTradingStrategy(symbol, timeframe)
        self.tick_count = 0
        self.session_start = time.time()
        self.enable_chart = enable_chart and CHART_AVAILABLE
        self.formatter = TerminalFormatter()
        
        # Chart setup
        if self.enable_chart:
            print("Chart enabled - matplotlib window should open")
            plt.ion()
            self.fig, self.ax = plt.subplots(figsize=(12, 8))
            plt.show()  # Show the window immediately
        else:
            print("Chart disabled - no matplotlib window")
        
        # Trading state
        self.position_data = {}  # Store position-specific data
        self.last_candle_time = None
        self.fixed_sl_points = 1.0      # Fixed 1-point stop loss exit
        
        # Tick confirmation system
        self.tick_confirmations = {
            'buy_signals': [],
            'sell_signals': []
        }
        self.required_confirmations = REQUIRED_CONFIRMATIONS  # From config file
        self.confirmation_window = CONFIRMATION_WINDOW        # From config file
        
        # Statistics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = 0.0
        self.session_capital = 7149.74
        
    def log(self, message: str, color: str = Colors.RESET):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"{color}[{timestamp}] {message}{Colors.RESET}")

    def get_market_data(self):
        """Get current market data and analysis"""
        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            return None, None
            
        analysis = self.strategy.analyze_timeframe(self.timeframe)
        if not analysis:
            return None, None
            
        return tick, analysis

    def is_sideways_market(self, ut_trail_array, lookback=10, threshold=0.3):
        """Detect sideways market based on UT trail flatness"""
        if len(ut_trail_array) < lookback:
            return False
        
        recent_trail = ut_trail_array[-lookback:]
        trail_range = max(recent_trail) - min(recent_trail)
        
        return trail_range < threshold  # Block if range < 0.3 points (reduced from 0.5)

    def check_tick_confirmations(self, signal_type, current_time):
        """Check if we have enough consecutive tick confirmations for entry"""
        if signal_type == "BUY":
            self.tick_confirmations['buy_signals'].append(current_time)
            # Clean old confirmations outside window
            self.tick_confirmations['buy_signals'] = [
                t for t in self.tick_confirmations['buy_signals'] 
                if current_time - t <= self.confirmation_window
            ]
            # Clear sell signals when buy detected
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
            # Clear buy signals when sell detected
            self.tick_confirmations['buy_signals'].clear()
            
            confirmations = len(self.tick_confirmations['sell_signals'])
            return confirmations >= self.required_confirmations, confirmations
        
        return False, 0

    def check_entry_conditions(self, analysis):
        """Check if entry conditions are met with tick confirmation"""
        # Check for existing positions first
        positions = mt5.positions_get(symbol=self.symbol)
        if positions:
            # Clear confirmations if already in position
            self.tick_confirmations['buy_signals'].clear()
            self.tick_confirmations['sell_signals'].clear()
            return "NONE"  # Already in position
        
        # Add sideways filter
        ut_trail_array = analysis.get('ut_trail_array', [])
        if self.is_sideways_market(ut_trail_array):
            # Clear confirmations during sideways market
            self.tick_confirmations['buy_signals'].clear()
            self.tick_confirmations['sell_signals'].clear()
            return "SIDEWAYS"  # Block trades
            
        # Get basic entry signal from strategy
        basic_signal = self.strategy.check_entry_conditions(analysis)
        
        if basic_signal in ["NONE", "SIDEWAYS"]:
            # Clear confirmations if no signal
            self.tick_confirmations['buy_signals'].clear()
            self.tick_confirmations['sell_signals'].clear()
            return basic_signal
        
        # Check tick confirmations for valid signals
        current_time = time.time()
        confirmed, current_confirmations = self.check_tick_confirmations(basic_signal, current_time)
        
        if confirmed:
            self.log(f"✅ {basic_signal} CONFIRMED after {current_confirmations} ticks!", Colors.GREEN)
            return basic_signal  # Signal confirmed - ready to trade
        else:
            remaining = self.required_confirmations - current_confirmations
            self.log(f"⏳ {basic_signal} signal - {current_confirmations}/{self.required_confirmations} confirmations (need {remaining} more)", Colors.YELLOW)
            return "CONFIRMING"  # Still collecting confirmations

    def calculate_dynamic_volume(self, current_price: float) -> float:
        """Calculate volume based on balance and current price with $5000 cap"""
        try:
            account_info = mt5.account_info()
            if not account_info:
                return 0.01  # Fallback to minimum
            
            # Capital cap at $5000
            effective_balance = min(account_info.balance, 5000.0)
            
            # Volume = Effective Balance / Current Price
            calculated_volume = effective_balance / current_price
            
            # Round to 2 decimal places
            calculated_volume = round(calculated_volume, 2)
            
            # Safety minimum check
            if calculated_volume < 0.01:
                self.log(f"Warning: Calculated volume {calculated_volume:.3f} too small, skipping trade", Colors.RED)
                return 0.0  # Return 0 to skip trade
            
            symbol_info = mt5.symbol_info(self.symbol)
            if symbol_info:
                # Ensure within broker limits
                min_volume = symbol_info.volume_min
                max_volume = symbol_info.volume_max
                calculated_volume = max(min_volume, min(max_volume, calculated_volume))
            
            self.log(f"Dynamic Volume: Balance=${account_info.balance:.2f} | Cap=${effective_balance:.2f} | Price=${current_price:.2f} | Volume={calculated_volume:.2f}", Colors.CYAN)
            return calculated_volume
            
        except Exception as e:
            self.log(f"❌ Error calculating dynamic volume: {e}", Colors.RED)
            return 0.01

    def execute_entry(self, signal, tick, analysis):
        """Execute trade entry with immediate trailing stop activation"""
        try:
            symbol_info = mt5.symbol_info(self.symbol)
            if not symbol_info:
                self.log("Failed to get symbol info", Colors.RED)
                return False

            entry_price = tick.ask if signal == "BUY" else tick.bid
            volume = self.calculate_dynamic_volume(entry_price)
            
            # Skip trade if volume is too small
            if volume <= 0:
                self.log("Warning: Trade skipped - volume too small", Colors.RED)
                return False
            
            # Set initial trailing stop as broker SL (1 point gap)
            if signal == "BUY":
                initial_trailing_sl = round(entry_price - 1.0, symbol_info.digits)  # $1 Reversal hard stop
                take_profit = round(entry_price + 4.0, symbol_info.digits)
                order_type = mt5.ORDER_TYPE_BUY
                self.log(f"📐 BUY [$1 Reversal SL] → {initial_trailing_sl:.2f} | Entry: {entry_price:.2f}", Colors.CYAN)
            else:
                initial_trailing_sl = round(entry_price + 1.0, symbol_info.digits)  # $1 Reversal hard stop
                take_profit = round(entry_price - 4.0, symbol_info.digits)
                order_type = mt5.ORDER_TYPE_SELL
                self.log(f"📐 SELL [$1 Reversal SL] → {initial_trailing_sl:.2f} | Entry: {entry_price:.2f}", Colors.CYAN)

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": volume,
                "type": order_type,
                "price": entry_price,
                "sl": initial_trailing_sl,  # Set trailing SL immediately
                "tp": take_profit,
                "magic": 123456,
                "comment": f"{signal}_TrailingOnly",
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)
            
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                self.total_trades += 1
                conditions = f"RSI/{analysis.get('rsi', 0):.1f} UTBot/{analysis.get('trail_stop', 0):.2f} Candle/{analysis.get('candle_color', '')}"
                
                # Print formatted trade entry box
                self.formatter.print_trade_entry(
                    signal, entry_price, volume, initial_trailing_sl, take_profit, 
                    result.order, conditions, self.session_capital, self.total_trades
                )
                
                # Store position data in BOTH systems for sync
                self.position_data[result.order] = {
                    'entry_price': entry_price,
                    'reference_price': tick.bid if signal == 'BUY' else tick.ask,  # Store bid for BUY, ask for SELL
                    'entry_time': datetime.now(),
                    'direction': signal,
                    'volume': volume,  # Store volume for profit calculation
                    'ut_trail_at_entry': analysis.get('trail_stop', 0),
                    'dollar_trail_active': False,   # Starts in Phase 1 (Fixed 1pt SL)
                    'dollar_trail_sl': None,        # Set when 0.01pt profit reached
                    'phase_label': 'Fixed 1pt SL'   # Current phase label for display
                }
                
                # SYNC: Also store in strategy's open_positions
                self.strategy.open_positions[result.order] = self.position_data[result.order].copy()
                
                self.log(f"✅ POSITION OPENED: $1 Reversal SL active. Trailing activates after +0.01pts profit", Colors.GREEN)
                return True
            else:
                error_msg = result.comment if result else 'Unknown error'
                self.log(f"❌ ORDER FAILED: {error_msg}", Colors.RED)
                return False
                
        except Exception as e:
            self.log(f"❌ Error executing trade: {e}", Colors.RED)
            return False

    def check_1dollar_reversal_exit(self, pos, tick):
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
                self.log(
                    f"🛑 [$1 REVERSAL] BUY #{pos.ticket} | Entry: {pos.price_open:.2f} | "
                    f"Bid: {tick.bid:.2f} | Loss: {loss_pts:.2f}pts → CLOSING",
                    Colors.RED
                )
                self.close_position(pos, "$1_Reversal")
                return True
        else:  # SELL
            loss_pts = tick.ask - pos.price_open
            if loss_pts >= 1.0:
                self.log(
                    f"🛑 [$1 REVERSAL] SELL #{pos.ticket} | Entry: {pos.price_open:.2f} | "
                    f"Ask: {tick.ask:.2f} | Loss: {loss_pts:.2f}pts → CLOSING",
                    Colors.RED
                )
                self.close_position(pos, "$1_Reversal")
                return True
        return False

    def calculate_trailing_stop_points(self, pos, tick, pos_data, symbol_info):
        """
        Dynamic Trailing Stop — activates after price moves 0.01 POINTS in profit direction.
        Measures profit from reference_price (bid/ask at entry) in POINTS.
        Trails 1.0 pt behind current price, only moves in your favour.
        Returns (trail_sl, is_active, phase_label)
        """
        direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
        
        # Use bid/ask at entry time for profit measurement (NOT fill price)
        reference_price = pos_data.get('reference_price')  # bid at entry for BUY, ask at entry for SELL
        
        if not reference_price:  # Fallback if reference_price not stored
            return None, False, '$1 Reversal'

        if direction == "BUY":
            # Profit measured from bid at entry time in POINTS
            profit_points = tick.bid - reference_price
            if profit_points >= 0.01:  # 0.01 POINTS profit threshold
                # First time activation - log it
                if not pos_data.get('dollar_trail_active', False):
                    pos_data['dollar_trail_active'] = True
                    self.log(f"🎯 TRAILING ACTIVATED: +{profit_points:.3f}pts profit → $1 Trail now active", Colors.GREEN)
                
                # Calculate new trail with 1.0 point gap ($1.00)
                new_trail_sl = round(tick.bid - 1.0, symbol_info.digits)
                best_sl = pos_data.get('dollar_trail_sl') or 0
                if new_trail_sl > best_sl:               # Only ratchet up
                    pos_data['dollar_trail_sl'] = new_trail_sl
                    pos_data['phase_label'] = '$1 Trail'
                return pos_data['dollar_trail_sl'], True, '$1 Trail'
            return None, False, '$1 Reversal'

        else:  # SELL
            # Profit measured from ask at entry time in POINTS
            profit_points = reference_price - tick.ask
            if profit_points >= 0.01:  # 0.01 POINTS profit threshold
                # First time activation - log it
                if not pos_data.get('dollar_trail_active', False):
                    pos_data['dollar_trail_active'] = True
                    self.log(f"🎯 TRAILING ACTIVATED: +{profit_points:.3f}pts profit → $1 Trail now active", Colors.GREEN)
                
                # Calculate new trail with 1.0 point gap ($1.00)
                new_trail_sl = round(tick.ask + 1.0, symbol_info.digits)
                best_sl = pos_data.get('dollar_trail_sl')  # None = not yet set
                if best_sl is None or new_trail_sl < best_sl:  # Only ratchet down
                    pos_data['dollar_trail_sl'] = new_trail_sl
                    pos_data['phase_label'] = '$1 Trail'
                return pos_data['dollar_trail_sl'], True, '$1 Trail'
            return None, False, '$1 Reversal'

    def check_exit_conditions(self, tick, analysis):
        """Three-step exit management:
        STEP 1: $1 Reversal check (hard stop, always on)
        STEP 2: $1 Trail activation (bid/ask vs ref_price)
        STEP 3: Compare $1 Trail vs UT Trail → tightest SL wins
        STEP 4: Manual exit checks (backup if broker SL fails)
        """
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return

        symbol_info = mt5.symbol_info(self.symbol)
        if not symbol_info:
            return

        for pos in positions:
            ticket = pos.ticket
            pos_data = self.position_data.setdefault(ticket, {})
            direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"

            # ── STEP 1: $1 Reversal hard stop (HIGHEST PRIORITY - always checked first) ──────────────
            if self.check_1dollar_reversal_exit(pos, tick):
                continue  # Position closed by $1 Reversal — skip to next

            # ── STEP 2: $1 Dynamic Trailing (after 0.01pts profit) ────────────────────────
            dollar_trail_sl, trail_active, phase_label = self.calculate_trailing_stop_points(
                pos, tick, pos_data, symbol_info
            )

            # ── STEP 3: Use ONLY $1 Trail (UT Trail competition DEACTIVATED) ──────────────────
            final_sl = None
            final_label = '$1 Reversal'

            if direction == "BUY":
                if trail_active and dollar_trail_sl:
                    final_sl = dollar_trail_sl
                    final_label = '$1 Trail'
                    # NO UT Trail override - use $1 Trail only

                    # Update broker SL if needed
                    if final_sl > pos.sl:
                        self.update_trailing_stop(ticket, final_sl, pos.tp)
                        
                # ── STEP 4: Manual exit checks (backup safety) ──────────────
                # Check $1 Trail manual exit only (UT Trail exit DEACTIVATED)
                if trail_active and dollar_trail_sl and tick.bid <= dollar_trail_sl:
                    self.log(f"🛑 [$1 TRAIL EXIT] BUY #{pos.ticket} | Bid: {tick.bid:.2f} <= Trail SL: {dollar_trail_sl:.2f} → CLOSING", Colors.RED)
                    self.close_position(pos, "$1_Trail_Exit")
                    continue

            else:  # SELL
                if trail_active and dollar_trail_sl:
                    final_sl = dollar_trail_sl
                    final_label = '$1 Trail'
                    # NO UT Trail override - use $1 Trail only

                    # Update broker SL if needed
                    if pos.sl == 0 or final_sl < pos.sl:
                        self.update_trailing_stop(ticket, final_sl, pos.tp)
                        
                # ── STEP 4: Manual exit checks (backup safety) ──────────────
                # Check $1 Trail manual exit only (UT Trail exit DEACTIVATED)
                if trail_active and dollar_trail_sl and tick.ask >= dollar_trail_sl:
                    self.log(f"🛑 [$1 TRAIL EXIT] SELL #{pos.ticket} | Ask: {tick.ask:.2f} >= Trail SL: {dollar_trail_sl:.2f} → CLOSING", Colors.RED)
                    self.close_position(pos, "$1_Trail_Exit")
                    continue

    def update_trailing_stop(self, ticket, new_sl, new_tp):
        """Update trailing stop loss with error handling"""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": new_sl,
            "tp": new_tp
        }
        
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            self.log(f"✅ SL Updated #{ticket}: {new_sl:.2f}", Colors.GREEN)
        else:
            error_msg = result.comment if result else 'Unknown error'
            self.log(f"❌ Failed to update SL #{ticket}: {error_msg}", Colors.RED)
            # If broker SL update fails, we rely on manual exit checks

    def close_position(self, pos, reason):
        """Close position at market price"""
        try:
            tick = mt5.symbol_info_tick(self.symbol)
            if not tick:
                return

            close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": pos.volume,
                "type": close_type,
                "position": pos.ticket,
                "price": price,
                "magic": 123456,
                "comment": reason[:31],
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                # Calculate trade details for exit box
                pos_data = self.position_data.get(pos.ticket, {})
                entry_time = pos_data.get('entry_time', datetime.now())
                duration = str(datetime.now() - entry_time).split('.')[0]
                direction = pos_data.get('direction', 'UNKNOWN')
                
                # Format exit condition based on reason
                exit_condition = self.format_exit_condition(reason, pos, tick)
                
                # Calculate win rate
                total_closed = self.winning_trades + self.losing_trades + 1
                win_rate = (self.winning_trades / total_closed * 100) if total_closed > 0 else 0
                
                # Print formatted trade exit box with exit condition
                self.formatter.print_trade_exit_with_condition(
                    direction, pos.price_open, price, duration, pos.ticket,
                    total_closed, win_rate, self.session_capital, self.total_profit, exit_condition
                )
                
                # Calculate profit
                profit = pos.profit
                self.total_profit += profit
                
                if profit >= 0:
                    self.winning_trades += 1
                else:
                    self.losing_trades += 1
                
                # Cleanup position data from BOTH systems
                if pos.ticket in self.position_data:
                    del self.position_data[pos.ticket]
                if pos.ticket in self.strategy.open_positions:
                    del self.strategy.open_positions[pos.ticket]
                    
        except Exception as e:
            self.log(f"❌ Error closing position: {e}", Colors.RED)
            
    def format_exit_condition(self, reason, pos, tick):
        """Format exit condition based on exit reason"""
        direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
        
        if reason == "$1_Reversal":
            loss_pts = pos.price_open - tick.bid if direction == "BUY" else tick.ask - pos.price_open
            return f"$1 Reversal: -{loss_pts:.2f}pts loss"
        elif reason == "$1_Trail_Exit":
            return f"$1 Trailing Stop: Price hit trail SL"
        elif reason == "UT_Trail_Exit":
            return f"UT Trail Exit: Price crossed UT trail"
        elif reason == "TakeProfit":
            return f"Take Profit: +4.0pts target reached"
        else:
            return f"Exit: {reason}"

    def display_status(self, tick, analysis):
        """Display clean single-line status with tick confirmation info"""
        self.tick_count += 1
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        # Get position info
        positions = mt5.positions_get(symbol=self.symbol)
        if positions:
            pos = positions[0]
            pos_data = self.position_data.get(pos.ticket, {})
            direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
            
            # Calculate P/L
            if direction == "BUY":
                pnl = (tick.bid - pos.price_open) * pos.volume
            else:
                pnl = (pos.price_open - tick.ask) * pos.volume
            
            # Determine active SL type
            ut_trail = analysis.get('trail_stop', 0)
            sl_type = "(UT Trail)" if ut_trail > 0 else "($1 Reversal)"
            active_sl = ut_trail if ut_trail > 0 else (pos.price_open - 1.0 if direction == "BUY" else pos.price_open + 1.0)
            
            # Colors for position display
            pnl_color = Colors.GREEN if pnl >= 0 else Colors.RED
            
            # Clean single-line format with exact colors
            print(f"[{timestamp}] {Colors.CYAN}Tick#{self.tick_count}{Colors.RESET} | "
                  f"Price: {Colors.ORANGE}{analysis['close']:.5f}{Colors.RESET} | "
                  f"UTBot: {Colors.GREEN}{ut_trail:.2f}{Colors.RESET} | "
                  f"Candle: {Colors.GREEN if analysis['candle_color'] == 'GREEN' else Colors.RED}{analysis['candle_color']}{Colors.RESET} | "
                  f"SL: {Colors.GREEN}{active_sl:.2f} {sl_type}{Colors.RESET} | "
                  f"RSI: {Colors.GREEN if analysis['rsi'] > 30 else Colors.RED}{analysis['rsi']:.1f}{Colors.RESET} | "
                  f"Status: {Colors.CYAN}IN POSITION{Colors.RESET} | "
                  f"P/L: {pnl_color}${pnl:.2f}{Colors.RESET}")
            return
        
        # When not in position - show confirmation status
        entry_signal = self.check_entry_conditions(analysis)
        
        # Get confirmation counts for display
        buy_confirmations = len(self.tick_confirmations['buy_signals'])
        sell_confirmations = len(self.tick_confirmations['sell_signals'])
        
        if entry_signal == "CONFIRMING":
            if buy_confirmations > 0:
                status = f"BUY CONFIRMING ({buy_confirmations}/{self.required_confirmations})"
                status_color = Colors.YELLOW
            elif sell_confirmations > 0:
                status = f"SELL CONFIRMING ({sell_confirmations}/{self.required_confirmations})"
                status_color = Colors.YELLOW
            else:
                status = "CONFIRMING"
                status_color = Colors.YELLOW
        elif entry_signal == "SIDEWAYS":
            status = "SIDEWAYS"
            status_color = Colors.YELLOW
        elif entry_signal == "NONE":
            status = "WAITING"
            status_color = Colors.CYAN
        else:
            status = f"SIGNAL: {entry_signal}"
            status_color = Colors.MAGENTA
        
        print(f"[{timestamp}] {Colors.CYAN}Tick#{self.tick_count}{Colors.RESET} | "
              f"Price: {Colors.ORANGE}{analysis['close']:.5f}{Colors.RESET} | "
              f"UTBot: {Colors.GREEN}{analysis['trail_stop']:.2f}{Colors.RESET} | "
              f"Candle: {Colors.GREEN if analysis['candle_color'] == 'GREEN' else Colors.RED}{analysis['candle_color']}{Colors.RESET} | "
              f"RSI: {Colors.GREEN if analysis['rsi'] > 30 else Colors.RED}{analysis['rsi']:.1f}{Colors.RESET} | "
              f"Status: {status_color}{status}{Colors.RESET}")

    def calculate_dynamic_ut_trail(self, df, tick):
        """Red dotted line shows ACTIVE exit level: Phase 1 (Fixed 1pt SL) → Phase 2 (Dynamic Trail)"""
        # Calculate standard UT trail
        standard_trail = self.calculate_ut_trail(df, key_value=1.0)
        
        # Check if any position exists - show the ACTIVE exit level
        positions = mt5.positions_get(symbol=self.symbol)
        if positions and tick:
            for pos in positions:
                pos_data = self.position_data.get(pos.ticket, {})
                
                # Check if we're in Phase 2 (dynamic trailing active)
                if pos_data.get('dollar_trail_active', False):
                    # PHASE 2: Show current dynamic trailing stop level
                    if pos.type == mt5.POSITION_TYPE_BUY:
                        trailing_sl = tick.bid - 1.0  # Current trailing: bid - 1.0
                    else:  # SELL
                        trailing_sl = tick.ask + 1.0  # Current trailing: ask + 1.0
                    
                    # Override red dotted line with dynamic trailing level
                    modified_trail = standard_trail.copy()
                    modified_trail[-1] = trailing_sl
                    return modified_trail
                
                else:
                    # PHASE 1: Show Fixed 1-Point Stop Loss (ALWAYS ACTIVE, HIGHEST PRIORITY)
                    if pos.type == mt5.POSITION_TYPE_BUY:
                        fixed_sl_level = pos.price_open - self.fixed_sl_points  # entry - 1.0
                    else:  # SELL
                        fixed_sl_level = pos.price_open + self.fixed_sl_points  # entry + 1.0
                    
                    # Override red dotted line with Fixed 1pt SL level
                    modified_trail = standard_trail.copy()
                    modified_trail[-1] = fixed_sl_level
                    return modified_trail
        
        return standard_trail

    def calculate_ut_trail(self, df, key_value=1.0):
        """UT Bot ATR trailing stop (ATR_Period=1 = single candle range)"""
        close = df['close'].values
        high  = df['high'].values
        low   = df['low'].values
        n     = len(close)
        atr   = np.abs(high - low)  # ATR period=1
        trail = np.zeros(n)
        trail[0] = close[0]
        for i in range(1, n):
            n_loss     = key_value * atr[i]
            prev_stop  = trail[i - 1]
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

    def update_chart(self, tick, analysis):
        """Update live chart with UT trail red dotted line"""
        if not self.enable_chart:
            print("Chart disabled - enable_chart=False")
            return
            
        try:
            # Get fresh data for chart
            df = self.strategy.fetch_data(self.timeframe, bars=50)
            if df.empty:
                print("Chart update failed - no data")
                return
                
            # Calculate dynamic UT trail
            ut_trail_array = self.calculate_dynamic_ut_trail(df, tick)
            current_price = analysis.get('close', 0)
            live_ut_trail = ut_trail_array[-1] if len(ut_trail_array) > 0 else 0
            
            print(f"Chart update: Price={current_price:.2f}, UT Trail={live_ut_trail:.2f}")
            
            self.ax.clear()
            
            # Plot last 50 candles
            plot_df = df.tail(50)
            plot_ut = ut_trail_array[-50:] if len(ut_trail_array) >= 50 else ut_trail_array
            
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
            
            # Check trailing mode
            trailing_mode = "TRAILING" if positions and any(
                self.position_data.get(pos.ticket, {}).get('trailing_set', False) for pos in positions
            ) else "STANDARD"
            
            self.ax.set_title(f'{self.symbol} - UT Bot Strategy (Mode: {trailing_mode}) - Red Dotted = UT Trail')
            self.ax.legend(loc='upper left')
            self.ax.grid(True, alpha=0.3)
            
            plt.draw()
            plt.pause(0.01)
            plt.show()  # Force show the window
            
            print("Chart updated successfully")
            
        except Exception as e:
            print(f"Chart update error: {e}")
    def get_statistics(self):
        """Get trading statistics"""
        total = self.winning_trades + self.losing_trades
        win_rate = (self.winning_trades / total * 100) if total > 0 else 0
        session_time = (time.time() - self.session_start) / 60
        
        return f"""
TRADING STATISTICS:
Total Trades: {self.total_trades}
Winning Trades: {self.winning_trades}
Losing Trades: {self.losing_trades}
Win Rate: {win_rate:.1f}%
Total Profit: ${self.total_profit:.2f}
Session Time: {session_time:.1f} minutes
        """

    def run(self):
        """Main trading loop - CLEAN STRUCTURE"""
        # Test colors first
        print("Testing colors:")
        Colors.test_colors()
        print("\n" + "="*50 + "\n")
        
        self.log(">> Fixed Trading Bot Started", Colors.CYAN)
        self.log(f"Symbol: {self.symbol} | Timeframe: {self.timeframe}")
        self.log(f"Entry: UT_Cross + RSI + Breakout/Pullback + {self.required_confirmations}-Tick Confirmation | Exit: $1 Reversal + $1 Trailing Stop")
        
        # Track previous positions to detect closures
        previous_positions = set()
        
        try:
            while True:
                # 1. GET MARKET DATA
                tick, analysis = self.get_market_data()
                if not tick or not analysis:
                    time.sleep(1)
                    continue

                # 2. CHECK FOR POSITION CLOSURES FIRST
                current_positions = mt5.positions_get(symbol=self.symbol)
                current_tickets = set(pos.ticket for pos in current_positions) if current_positions else set()
                
                # Detect closed positions
                closed_tickets = previous_positions - current_tickets
                for ticket in closed_tickets:
                    if ticket in self.position_data:
                        pos_data = self.position_data[ticket]
                        entry_time = pos_data.get('entry_time', datetime.now())
                        duration = str(datetime.now() - entry_time).split('.')[0]
                        direction = pos_data.get('direction', 'UNKNOWN')
                        entry_price = pos_data.get('entry_price', 0)
                        
                        # Get exit price from recent deals
                        deals = mt5.history_deals_get(position=ticket)
                        exit_price = entry_price  # fallback
                        if deals and len(deals) > 1:
                            exit_price = deals[-1].price  # last deal is the exit
                        
                        # Calculate win rate
                        total_closed = self.winning_trades + self.losing_trades + 1
                        win_rate = (self.winning_trades / total_closed * 100) if total_closed > 0 else 0
                        
                        # Format exit condition for position closure detection
                        exit_condition = "Position Closed: Broker SL/TP or Manual"
                        
                        # Print formatted trade exit box with exit condition
                        self.formatter.print_trade_exit_with_condition(
                            direction, entry_price, exit_price, duration, ticket,
                            total_closed, win_rate, self.session_capital, self.total_profit, exit_condition
                        )
                        
                        # Update statistics
                        volume = pos_data.get('volume', 1.0)  # Get volume from stored data
                        profit_points = (exit_price - entry_price) if direction == 'BUY' else (entry_price - exit_price)
                        profit_dollars = profit_points * volume
                        self.total_profit += profit_dollars
                        
                        if profit_points >= 0:
                            self.winning_trades += 1
                        else:
                            self.losing_trades += 1
                        
                        # Cleanup from BOTH systems
                        del self.position_data[ticket]
                        if ticket in self.strategy.open_positions:
                            del self.strategy.open_positions[ticket]
                
                # Update previous positions
                previous_positions = current_tickets

                # 3. CHECK EXITS (for existing positions) - Use strategy's exit logic
                if current_positions:
                    self.strategy.check_exit_conditions(analysis)

                # 4. CHECK ENTRIES (only if no positions)
                if not current_positions:
                    entry_signal = self.check_entry_conditions(analysis)
                    if entry_signal not in ["NONE", "SIDEWAYS", "CONFIRMING"]:
                        self.execute_entry(entry_signal, tick, analysis)

                # 5. DISPLAY STATUS
                self.display_status(tick, analysis)

                # 6. UPDATE CHART (Red Dotted Line)
                if self.tick_count % 5 == 0:  # Update chart every 5 ticks for performance
                    self.update_chart(tick, analysis)

                # 7. BRIEF PAUSE
                time.sleep(1)

        except KeyboardInterrupt:
            self.log("\n>> Bot stopped by user", Colors.YELLOW)
            self.log(self.get_statistics())
        except Exception as e:
            self.log(f">> Critical error: {e}", Colors.RED)
        finally:
            mt5.shutdown()

def main():
    """Initialize and run the fixed trading bot"""
    load_dotenv()
    
    # MT5 Connection
    mt5_path = os.getenv("MT5_PATH")
    mt5_login = int(os.getenv("MT5_LOGIN"))
    mt5_pass = os.getenv("MT5_PASSWORD")
    mt5_server = os.getenv("MT5_SERVER")
    
    if not mt5.initialize(path=mt5_path, login=mt5_login, password=mt5_pass, server=mt5_server):
        print(f"MT5 initialization failed: {mt5.last_error()}")
        return
    
    # Create and run bot with chart enabled
    bot = TradingBot("XAUUSD", "M1", enable_chart=True)
    bot.run()

if __name__ == "__main__":
    main()