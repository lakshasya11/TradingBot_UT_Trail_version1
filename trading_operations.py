"""
Shared Trading Operations
Consolidates all duplicate trading operation logic (position management, orders).
"""
import MetaTrader5 as mt5
from datetime import datetime
from typing import Optional

def close_position(ticket: int, symbol: str, reason: str = "ManualExit") -> bool:
    """Close position at market price"""
    try:
        pos = mt5.positions_get(ticket=ticket)
        if not pos:
            return False
        
        p = pos[0]
        close_type = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return False
            
        price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": p.volume,
            "type": close_type,
            "position": ticket,
            "price": price,
            "magic": 123456,
            "comment": reason[:31],
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"🏁 Position #{ticket} closed. Reason: {reason}")
            return True
        else:
            print(f"❌ Failed to close position #{ticket}: {result.comment if result else 'Unknown error'}")
            return False
            
    except Exception as e:
        print(f"❌ Error closing position: {e}")
        return False

def modify_position(ticket: int, symbol: str, new_sl: float, new_tp: float) -> bool:
    """Modify position stop loss and take profit"""
    try:
        symbol_info = mt5.symbol_info(symbol)
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
            print(f"✅ Position {ticket} modified - New SL: {new_sl:.5f}")
            return True
        else:
            print(f"❌ Failed to modify position #{ticket}: {result.comment if result else 'Unknown error'}")
            return False
        
    except Exception as e:
        print(f"❌ Error modifying position: {e}")
        return False

def execute_market_order(symbol: str, order_type: int, volume: float, sl: float, tp: float, comment: str = "") -> Optional[int]:
    """Execute a market order and return ticket number if successful"""
    try:
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            print("Failed to get tick data")
            return None

        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            print("Failed to get symbol info")
            return None
        
        # Round to symbol digits
        digits = symbol_info.digits
        sl = round(sl, digits)
        tp = round(tp, digits)
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "magic": 123456,
            "comment": comment[:31],
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"✅ ORDER EXECUTED: {comment} | SL: {sl} | TP: {tp}")
            return result.order
        else:
            print(f"❌ ORDER FAILED: {result.comment if result else 'Unknown error'}")
            return None

    except Exception as e:
        print(f"❌ Error executing trade: {e}")
        return None