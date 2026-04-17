# FIXED EXIT CONDITIONS - Replace the problematic functions

def check_1dollar_reversal_exit(self, pos, tick):
    """
    FIXED: $1 Reversal Hard Stop — Direct price comparison (no loss calculation)
    BUY:  tick.bid <= entry_price - 1.0  → EXIT
    SELL: tick.ask >= entry_price + 1.0  → EXIT
    """
    direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"

    if direction == "BUY":
        reversal_level = pos.price_open - 1.0
        if tick.bid <= reversal_level:
            self.log(
                f"🛑 [$1 REVERSAL] BUY #{pos.ticket} | Entry: {pos.price_open:.2f} | "
                f"Bid: {tick.bid:.2f} | Reversal Level: {reversal_level:.2f} → CLOSING",
                Colors.RED
            )
            self.close_position(pos, "$1_Reversal")
            return True
    else:  # SELL
        reversal_level = pos.price_open + 1.0
        if tick.ask >= reversal_level:
            self.log(
                f"🛑 [$1 REVERSAL] SELL #{pos.ticket} | Entry: {pos.price_open:.2f} | "
                f"Ask: {tick.ask:.2f} | Reversal Level: {reversal_level:.2f} → CLOSING",
                Colors.RED
            )
            self.close_position(pos, "$1_Reversal")
            return True
    return False

def calculate_trailing_stop_points(self, pos, tick, pos_data, symbol_info):
    """
    FIXED: Dynamic Trailing Stop — Uses pos.price_open consistently
    Activates after 0.01 POINTS profit from FILL PRICE
    """
    direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
    
    if direction == "BUY":
        # Profit measured from fill price in POINTS
        profit_points = tick.bid - pos.price_open
        if profit_points >= 0.01:  # 0.01 POINTS profit threshold
            # First time activation - log it
            if not pos_data.get('dollar_trail_active', False):
                pos_data['dollar_trail_active'] = True
                self.log(f"🎯 TRAILING ACTIVATED: +{profit_points:.3f}pts profit → $1 Trail now active", Colors.GREEN)
            
            # Calculate new trail with 1.0 point gap
            new_trail_sl = round(tick.bid - 1.0, symbol_info.digits)
            best_sl = pos_data.get('dollar_trail_sl', pos.price_open - 1.0)  # Start from initial SL
            if new_trail_sl > best_sl:  # Only ratchet up
                pos_data['dollar_trail_sl'] = new_trail_sl
                pos_data['phase_label'] = '$1 Trail'
            return pos_data['dollar_trail_sl'], True, '$1 Trail'
        return None, False, '$1 Reversal'

    else:  # SELL
        # Profit measured from fill price in POINTS
        profit_points = pos.price_open - tick.ask
        if profit_points >= 0.01:  # 0.01 POINTS profit threshold
            # First time activation - log it
            if not pos_data.get('dollar_trail_active', False):
                pos_data['dollar_trail_active'] = True
                self.log(f"🎯 TRAILING ACTIVATED: +{profit_points:.3f}pts profit → $1 Trail now active", Colors.GREEN)
            
            # Calculate new trail with 1.0 point gap
            new_trail_sl = round(tick.ask + 1.0, symbol_info.digits)
            best_sl = pos_data.get('dollar_trail_sl', pos.price_open + 1.0)  # Start from initial SL
            if best_sl is None or new_trail_sl < best_sl:  # Only ratchet down
                pos_data['dollar_trail_sl'] = new_trail_sl
                pos_data['phase_label'] = '$1 Trail'
            return pos_data['dollar_trail_sl'], True, '$1 Trail'
        return None, False, '$1 Reversal'

def check_exit_conditions(self, tick, analysis):
    """
    FIXED: Simplified exit management - Remove broker SL conflicts
    STEP 1: Manual $1 Reversal check (highest priority)
    STEP 2: Manual $1 Trailing check (after 0.01pts profit)
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

        # ── STEP 1: $1 Reversal hard stop (always checked first) ──────────────
        if self.check_1dollar_reversal_exit(pos, tick):
            continue  # Position closed — skip to next

        # ── STEP 2: $1 Trailing check (after 0.01pts profit) ────────────────────────
        dollar_trail_sl, trail_active, phase_label = self.calculate_trailing_stop_points(
            pos, tick, pos_data, symbol_info
        )

        # Manual trailing exit check (no broker SL updates)
        if trail_active and dollar_trail_sl:
            if direction == "BUY":
                if tick.bid <= dollar_trail_sl:
                    self.log(f"🛑 [$1 TRAIL EXIT] BUY #{pos.ticket} | Bid: {tick.bid:.2f} <= Trail SL: {dollar_trail_sl:.2f} → CLOSING", Colors.RED)
                    self.close_position(pos, "$1_Trail_Exit")
                    continue
            else:  # SELL
                if tick.ask >= dollar_trail_sl:
                    self.log(f"🛑 [$1 TRAIL EXIT] SELL #{pos.ticket} | Ask: {tick.ask:.2f} >= Trail SL: {dollar_trail_sl:.2f} → CLOSING", Colors.RED)
                    self.close_position(pos, "$1_Trail_Exit")
                    continue

def execute_entry(self, signal, tick, analysis):
    """
    FIXED: Remove initial broker SL - Use manual exits only
    """
    try:
        symbol_info = mt5.symbol_info(self.symbol)
        if not symbol_info:
            self.log("Failed to get symbol info", Colors.RED)
            return False

        entry_price = tick.ask if signal == "BUY" else tick.bid
        volume = self.calculate_dynamic_volume(entry_price)
        
        if volume <= 0:
            self.log("Warning: Trade skipped - volume too small", Colors.RED)
            return False
        
        # Set only Take Profit - NO STOP LOSS (manual exits only)
        if signal == "BUY":
            take_profit = round(entry_price + 4.0, symbol_info.digits)
            order_type = mt5.ORDER_TYPE_BUY
            self.log(f"📐 BUY Entry: Manual $1 Reversal at {entry_price - 1.0:.2f}", Colors.CYAN)
        else:
            take_profit = round(entry_price - 4.0, symbol_info.digits)
            order_type = mt5.ORDER_TYPE_SELL
            self.log(f"📐 SELL Entry: Manual $1 Reversal at {entry_price + 1.0:.2f}", Colors.CYAN)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": volume,
            "type": order_type,
            "price": entry_price,
            "sl": 0,  # NO BROKER SL - Manual exits only
            "tp": take_profit,
            "magic": 123456,
            "comment": f"{signal}_ManualExits",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            self.total_trades += 1
            conditions = f"RSI/{analysis.get('rsi', 0):.1f} UTBot/{analysis.get('trail_stop', 0):.2f}"
            
            # Store position data
            self.position_data[result.order] = {
                'entry_price': entry_price,
                'entry_time': datetime.now(),
                'direction': signal,
                'volume': volume,
                'dollar_trail_active': False,
                'dollar_trail_sl': None,
                'phase_label': 'Manual $1 Reversal'
            }
            
            self.log(f"✅ POSITION OPENED: Manual exits active. Trailing after +0.01pts profit", Colors.GREEN)
            return True
        else:
            error_msg = result.comment if result else 'Unknown error'
            self.log(f"❌ ORDER FAILED: {error_msg}", Colors.RED)
            return False
            
    except Exception as e:
        self.log(f"❌ Error executing trade: {e}", Colors.RED)
        return False