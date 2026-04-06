import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any, Optional

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
    
    def __init__(self, symbol: str, base_timeframe: str = 'M5'):
        self.symbol = symbol
        self.base_timeframe = base_timeframe
        self.data_cache = {}
        self.open_positions = {}
        
        # Exit Configuration
        self.atr_sl_multiplier = 2.0    # Stop loss at 2.0x ATR
        self.tp_usd = 10.0              # Take profit at $10
        self.trailing_activation = 5.0  # Activate trailing + breakeven at $5 profit
        self.trailing_offset = 2.0      # Trail $2 behind current price
        
    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{self.symbol}] {message}")

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

    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

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



    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate ATR using Wilder's smoothing (RMA)"""
        tr1 = df['high'] - df['low']
        tr2 = (df['high'] - df['close'].shift()).abs()
        tr3 = (df['low'] - df['close'].shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1.0/period, adjust=False).mean()
        return atr


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
        
        # EMA calculations
        ema9 = close.ewm(span=9, adjust=False).mean()
        ema21 = close.ewm(span=21, adjust=False).mean()
        
        # ATR calculation (Wilder's, 5 period)
        tr1 = df['high'] - df['low']
        tr2 = (df['high'] - close.shift()).abs()
        tr3 = (df['low'] - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_val = tr.ewm(alpha=1.0/14, adjust=False).mean()
        
        return {
                'rsi': rsi.iloc[-1] if len(rsi) > 0 and not pd.isna(rsi.iloc[-1]) else 50,
                'ema9': ema9.iloc[-1] if len(ema9) > 0 and not pd.isna(ema9.iloc[-1]) else close.iloc[-1],
                'ema21': ema21.iloc[-1] if len(ema21) > 0 and not pd.isna(ema21.iloc[-1]) else close.iloc[-1],
                'candle_color': 'GREEN' if close.iloc[-1] > df['open'].iloc[-1] else 'RED',
                'atr': atr_val.iloc[-1] if len(atr_val) > 0 and not pd.isna(atr_val.iloc[-1]) else 0.01,
                'close': close.iloc[-1],
                'low': df['low'].iloc[-1],
                'high': df['high'].iloc[-1]
            }




    def check_entry_conditions(self, analysis: Dict) -> str:
        if not analysis:
            return "NONE"

        rsi = analysis.get('rsi', 0)
        ema9 = analysis.get('ema9', 0)
        ema21 = analysis.get('ema21', 0)
        candle_color = analysis.get('candle_color', '')
        low = analysis.get('low', 0)
        high = analysis.get('high', 0)

        # BUY Condition: RSI(14) > 50, EMA 9 > EMA 21, Green Candle, Candle Low > EMA 9
        buy_conditions = (
            rsi > 50 and
            ema9 > ema21 and
            candle_color == 'GREEN' and
            low > ema9
        )

        # SELL Condition: RSI(14) < 50, EMA 9 < EMA 21, Red Candle, Candle High < EMA 9
        sell_conditions = (
            rsi < 50 and
            ema9 < ema21 and
            candle_color == 'RED' and
            high < ema9
        )

        if buy_conditions:
            return "BUY"
        elif sell_conditions:
            return "SELL"
        return "NONE"


    def calculate_position_size(self, entry_price: float, stop_loss: float, risk_amount: float = 100) -> float:
        """Calculate position size based on risk"""
        try:
            symbol_info = mt5.symbol_info(self.symbol)
            if not symbol_info:
                return 0.01
            
            risk_distance = abs(entry_price - stop_loss)
            tick_value = symbol_info.trade_tick_value
            tick_size = symbol_info.trade_tick_size
            
            if risk_distance > 0 and tick_value > 0 and tick_size > 0:
                position_size = risk_amount / (risk_distance / tick_size * tick_value)
                # Round to valid volume step
                volume_step = symbol_info.volume_step
                position_size = round(position_size / volume_step) * volume_step
                
                # Ensure within broker limits
                min_volume = symbol_info.volume_min
                max_volume = symbol_info.volume_max
                position_size = max(min_volume, min(max_volume, position_size))
                
                return position_size
            
            return 0.01
        except Exception:
            return 0.01

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
        """Execute trade with adaptive 2.5x ATR SL and $10 TP"""
        try:
            tick = mt5.symbol_info_tick(self.symbol)
            if not tick:
                self.log("Failed to get tick data")
                return

            symbol_info = mt5.symbol_info(self.symbol)
            if not symbol_info:
                return

            entry_price = tick.ask if signal == "BUY" else tick.bid
            volume = symbol_info.volume_min

            atr = analysis.get('atr', 0)
            sl_distance = atr * self.atr_sl_multiplier
            tp_distance = self.dollars_to_price(self.tp_usd, volume)

            if signal == "BUY":
                stop_loss = round(entry_price - sl_distance, symbol_info.digits)
                take_profit = round(entry_price + tp_distance, symbol_info.digits)
                order_type = mt5.ORDER_TYPE_BUY
            else:
                stop_loss = round(entry_price + sl_distance, symbol_info.digits)
                take_profit = round(entry_price - tp_distance, symbol_info.digits)
                order_type = mt5.ORDER_TYPE_SELL

            self.log(f"📐 ATR SL | ATR: {atr:.5f} | x{self.atr_sl_multiplier} = {sl_distance:.5f} | SL: {stop_loss:.5f}")

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": volume,
                "type": order_type,
                "price": entry_price,
                "sl": stop_loss,
                "tp": take_profit,
                "magic": 123456,
                "comment": f"{signal}_Strategy",
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)

            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                self.log(f"✅ {signal} ORDER EXECUTED")
                self.log(f"   Entry: {entry_price:.5f} | SL: {stop_loss:.5f} | TP: {take_profit:.5f}")
                self.log(f"   ATR: {atr:.5f} | SL Multiplier: {self.atr_sl_multiplier} | Target: ${self.tp_usd} | Volume: {volume}")
                self.open_positions[result.order] = {
                    'entry_price': entry_price,
                    'direction': signal,
                    'breakeven_set': False
                }
            else:
                self.log(f"❌ ORDER FAILED: {result.comment if result else 'Unknown error'}")

        except Exception as e:
            self.log(f"❌ Error executing trade: {e}")

    def check_exit_conditions(self):
        """Check exit conditions: breakeven + trailing stop loss"""
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
            current_sl = pos.sl
            current_tp = pos.tp
            profit_usd = pos.profit
            volume = pos.volume
            pos_data = self.open_positions.get(ticket, {'breakeven_set': False})

            if profit_usd >= self.trailing_activation:
                trailing_distance = self.dollars_to_price(self.trailing_offset, volume)

                if pos.type == mt5.POSITION_TYPE_BUY:
                    current_price = tick.bid
                    # Set breakeven once
                    if not pos_data.get('breakeven_set'):
                        self.log(f"🔒 Breakeven set for BUY #{ticket}")
                        self.modify_position(ticket, pos.price_open, current_tp)
                        pos_data['breakeven_set'] = True
                        self.open_positions[ticket] = pos_data
                    # Trailing SL — only moves up
                    new_sl = current_price - trailing_distance
                    if new_sl > current_sl:
                        self.log(f"🚀 Trailing SL BUY #{ticket} | Profit: ${profit_usd:.2f} | New SL: {new_sl:.5f}")
                        self.modify_position(ticket, new_sl, current_tp)

                elif pos.type == mt5.POSITION_TYPE_SELL:
                    current_price = tick.ask
                    # Set breakeven once
                    if not pos_data.get('breakeven_set'):
                        self.log(f"🔒 Breakeven set for SELL #{ticket}")
                        self.modify_position(ticket, pos.price_open, current_tp)
                        pos_data['breakeven_set'] = True
                        self.open_positions[ticket] = pos_data
                    # Trailing SL — only moves down
                    new_sl = current_price + trailing_distance
                    if current_sl == 0 or new_sl < current_sl:
                        self.log(f"🚀 Trailing SL SELL #{ticket} | Profit: ${profit_usd:.2f} | New SL: {new_sl:.5f}")
                        self.modify_position(ticket, new_sl, current_tp)

    def modify_position(self, ticket: int, new_sl: float, new_tp: float):
        """Modify position stop loss and take profit"""
        try:
            symbol_info = mt5.symbol_info(self.symbol)
            if symbol_info:
                digits = symbol_info.digits
                new_sl = round(new_sl, digits)
                new_tp = round(new_tp, digits)
            
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "sl": new_sl,
                "tp": new_tp
            }
            
            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                self.log(f"✅ Position {ticket} modified - New SL: {new_sl:.5f}")
            
        except Exception as e:
            self.log(f"❌ Error modifying position: {e}")

    def run_strategy(self):
        """Main strategy execution loop"""
        self.log("Starting Enhanced ATR Strategy...")
        
        # Analyze current timeframe
        analysis = self.analyze_timeframe(self.base_timeframe)
        if not analysis:
            self.log("No data available for analysis")
            return
        
        # Log current market conditions
        self.log(f"RSI: {analysis.get('rsi', 0):.2f}")
        self.log(f"EMA9: {analysis.get('ema9', 0):.5f} | EMA21: {analysis.get('ema21', 0):.5f}")
        self.log(f"Candle: {analysis.get('candle_color', '')} | Low: {analysis.get('low', 0):.5f} | High: {analysis.get('high', 0):.5f}")

        # Check for entry signals
        signal = self.check_entry_conditions(analysis)
        
        if signal != "NONE":
            # Check if we already have a position
            positions = mt5.positions_get(symbol=self.symbol)
            if not positions or len(positions) == 0:
                self.log(f"🎯 ENTRY SIGNAL: {signal}")
                self.execute_trade(signal, analysis)
            else:
                self.log(f"Position already open, skipping {signal} signal")
        
        # Check exit conditions for existing positions
        self.check_exit_conditions()

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
    
    # Create strategy instance
    strategy = EnhancedTradingStrategy("XAUUSD", "M5")
    
    # Run strategy loop
    try:
        while True:
            strategy.run_strategy()
            time.sleep(1)  # Check every 1 second for real-time
    except KeyboardInterrupt:
        print("\nStrategy stopped by user")
    finally:
        mt5.shutdown()