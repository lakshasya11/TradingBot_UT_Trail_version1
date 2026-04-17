import requests
from bs4 import BeautifulSoup
import MetaTrader5 as mt5
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta
import pytz
import atexit
import math

# --- Flask App Initialization & CORS ---
app = Flask(__name__)
CORS(app) 

# --- MT5 Connection Handler ---
import os
from dotenv import load_dotenv
load_dotenv()

def init_mt5_connection():
    MT5_PATH = os.getenv("MT5_PATH", "C:/Program Files/MetaTrader 5/terminal64.exe")
    LOGIN_ID = int(os.getenv("MT5_LOGIN"))
    PASSWORD = os.getenv("MT5_PASSWORD")
    SERVER   = os.getenv("MT5_SERVER")
    if not mt5.initialize(path=MT5_PATH, login=LOGIN_ID, password=PASSWORD, server=SERVER):
        error_code = mt5.last_error()
        print(f"MT5 initialize() FAILED! Error Code: {error_code}. Ensure terminal is running.")
        return False
    print("MT5 connection initialized successfully.")
    return True

init_mt5_connection()
atexit.register(mt5.shutdown)

def check_mt5_status():
    if not mt5.terminal_info():
        if not mt5.initialize():
            return False, {"error": "MT5 connection lost and failed to re-initialize.", "mt5_error": mt5.last_error()}
    return True, None

# --- API Routes ---
@app.route('/api/live_prices', methods=['GET'])
def get_live_prices():
    is_connected, error_response = check_mt5_status()
    if not is_connected:
        return jsonify(error_response), 503
    
    symbols_to_fetch = ['EURUSD', 'AUDNZD', 'EURCHF', 'XAUUSD', 'XAGUSD', 'BTCUSD']
    market_data = []
    
    for idx, symbol in enumerate(symbols_to_fetch):
        tick = mt5.symbol_info_tick(symbol)
        
        # Symbol resolution for crypto symbols
        if (not tick) and ('BTC' in symbol.upper()):
            try:
                all_symbols = mt5.symbols_get()
                candidates = [s.name for s in all_symbols if 'BTC' in s.name.upper() and 'USD' in s.name.upper()]
                if candidates:
                    resolved = candidates[0]
                    print(f"DEBUG: Resolving {symbol} to available symbol {resolved}")
                    tick = mt5.symbol_info_tick(resolved)
                    symbol = resolved
            except Exception as e:
                print(f"DEBUG: Error searching symbols for {symbol}: {e}")
                
        market_data.append({
            "id": idx + 1,
            "symbol": symbol,
            "bid": tick.bid if tick else 0.0,
            "ask": tick.ask if tick else 0.0,
            "time": tick.time if tick else 0
        })
        
        if not tick:
            print(f"DEBUG: No tick data for symbol {symbol}")
            
    return jsonify(market_data)

@app.route('/api/account_info', methods=['GET'])
def get_account_info():
    is_connected, error_response = check_mt5_status()
    if not is_connected:
        return jsonify(error_response), 503
    
    info = mt5.account_info()
    if info:
        return jsonify(info._asdict())
    return jsonify({"error": "Failed to retrieve account info.", "mt5_error": mt5.last_error()}), 404

@app.route('/api/chart_data', methods=['GET'])
def get_chart_data():
    is_connected, error_response = check_mt5_status()
    if not is_connected:
        return jsonify(error_response), 503
        
    symbol = request.args.get('symbol', 'EURUSD')
    timeframe_str = request.args.get('timeframe', 'M5')
    count = int(request.args.get('count', 200))
    
    TIME_MAP = {
        'M1': mt5.TIMEFRAME_M1, 'M5': mt5.TIMEFRAME_M5, 'M15': mt5.TIMEFRAME_M15, 
        'M30': mt5.TIMEFRAME_M30, 'H1': mt5.TIMEFRAME_H1, 'H2': mt5.TIMEFRAME_H2, 
        'D1': mt5.TIMEFRAME_D1
    }
    timeframe = TIME_MAP.get(timeframe_str, mt5.TIMEFRAME_M5)
    
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count + 1)
    if rates is None or len(rates) == 0:
        return jsonify({"error": f"Failed to get rates for {symbol}/{timeframe_str}.", "mt5_error": mt5.last_error()}), 500
    
    df = pd.DataFrame(rates)
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['timestamp'] = (df['time'] * 1000).astype(int)

    # Provide explicit MT5-aligned time fields:
    # - mt5_epoch: raw epoch seconds as returned by MT5 (useful for exact comparison)
    # - timestamp: epoch milliseconds (used by frontend charts)
    # - time_utc: human-readable UTC time (MT5 server times are typically represented UTC)
    # - time_local: local system time representation for convenience
    df['mt5_epoch'] = df['time'].astype(int)
    df['time_utc'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.strftime('%Y-%m-%d %H:%M:%S %Z')
    df['time_local'] = pd.to_datetime(df['time'], unit='s').dt.strftime('%Y-%m-%d %H:%M:%S')

    # Y-axis calculation
    all_prices = df[['open', 'high', 'low', 'close']].values.flatten()
    min_price = float(all_prices.min())
    max_price = float(all_prices.max())
    price_range = max_price - min_price
    
    buffer = max(price_range * 0.1, 0.0001)
    y_min = min_price - buffer
    y_max = max_price + buffer
    
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info:
        tick_size = symbol_info.point
        digits = symbol_info.digits
        
        if 'USD' in symbol:
            pip_value = 0.0001 if digits == 5 else 0.01
            base_step = 5 * pip_value
            
            range_pips = (y_max - y_min) / pip_value
            if range_pips > 100:
                step = base_step * 4
            elif range_pips > 50:
                step = base_step * 2
            else:
                step = base_step
        else:
            step = 5 * tick_size
        
        start_tick = math.floor(y_min / step) * step
        y_ticks = []
        current_tick = start_tick
        while current_tick <= y_max + step:
            if current_tick >= y_min:
                y_ticks.append(round(current_tick, digits))
            current_tick += step
    else:
        step = (y_max - y_min) / 7
        y_ticks = [round(y_min + i * step, 5) for i in range(8)]
        
    formatted_data = df[['mt5_epoch','timestamp','time_utc','time_local','open', 'high', 'low', 'close', 'tick_volume']].to_dict('records')
    
    return jsonify({
        'data': formatted_data,
        'yAxis': {
            'min': y_ticks[0] if y_ticks else y_min,
            'max': y_ticks[-1] if y_ticks else y_max,
            'ticks': y_ticks,
            'step': step
        }
    })

@app.route('/api/open_trades', methods=['GET'])
def get_open_trades():
    is_connected, error_response = check_mt5_status()
    if not is_connected:
        return jsonify(error_response), 503
        
    positions = mt5.positions_get()
    if positions is None:
        return jsonify({"error": "Failed to get open positions.", "mt5_error": mt5.last_error()}), 500
        
    trade_list = []
    for pos in positions:
        trade_data = pos._asdict()
        # Provide both MT5/UTC and local representations so callers can align with MT5 terminal
        trade_data['time_mt5_utc'] = datetime.utcfromtimestamp(pos.time).strftime('%Y-%m-%d %H:%M:%S UTC')
        trade_data['time_local'] = datetime.fromtimestamp(pos.time).strftime('%Y-%m-%d %H:%M:%S')
        trade_data['type_str'] = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
        trade_list.append(trade_data)
        
    return jsonify(trade_list)

@app.route('/api/trade/execute', methods=['POST'])
def execute_trade_order():
    is_connected, error_response = check_mt5_status()
    if not is_connected:
        return jsonify(error_response), 503
        
    data = request.get_json()
    symbol = data.get('symbol', 'EURUSD')
    try:
        volume = float(data.get('volume', 0.01))
        if math.isnan(volume) or volume <= 0:
            return jsonify({"error": "Invalid volume value."}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Volume must be a valid number."}), 400
    direction = data.get('direction', 'BUY')
    
    symbol_info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if not symbol_info or not tick:
        return jsonify({"error": f"Symbol data not available for {symbol}."}), 400

    price = tick.ask if direction == 'BUY' else tick.bid
    point = symbol_info.point
    
    SL_POINTS = 50
    SL_PRICE_DISTANCE = SL_POINTS * point
    
    if direction == 'BUY':
        sl_level = round(price - SL_PRICE_DISTANCE, symbol_info.digits)
        tp_level = round(price + (SL_PRICE_DISTANCE * 2), symbol_info.digits)
        action = mt5.ORDER_TYPE_BUY
    else:
        sl_level = round(price + SL_PRICE_DISTANCE, symbol_info.digits)
        tp_level = round(price - (SL_PRICE_DISTANCE * 2), symbol_info.digits)
        action = mt5.ORDER_TYPE_SELL
        
    request_dict = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": action,
        "price": price,
        "sl": sl_level,
        "tp": tp_level,
        "magic": 99999,
        "comment": "TradeBotManual",
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = mt5.order_send(request_dict)
    
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        return jsonify({
            "success": True, 
            "message": f"Order executed. Ticket: {result.order}",
            "ticket": result.order
        }), 200
    else:
        error_comment = result.comment if result else "MT5 connection failure."
        return jsonify({
            "success": False, 
            "error": f"Order Failed. {error_comment}",
        }), 400

@app.route('/api/trade/close', methods=['POST'])
def close_trade_order():
    is_connected, error_response = check_mt5_status()
    if not is_connected:
        return jsonify(error_response), 503
        
    data = request.get_json()
    ticket = data.get('ticket')
    volume = data.get('volume')
    
    if not ticket or not volume:
        return jsonify({"error": "Missing ticket or volume."}), 400

    position = mt5.positions_get(ticket=ticket)
    if not position:
        return jsonify({"error": f"Position {ticket} not found."}), 404
    
    position = position[0]
    tick = mt5.symbol_info_tick(position.symbol)
    
    if position.type == mt5.POSITION_TYPE_BUY:
        close_price = tick.bid
        order_type = mt5.ORDER_TYPE_SELL
    else:
        close_price = tick.ask
        order_type = mt5.ORDER_TYPE_BUY
    
    request_dict = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": position.symbol,
        "volume": volume,
        "type": order_type,
        "position": ticket,
        "price": close_price,
        "magic": 99999,
        "comment": "TradeBotClose",
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = mt5.order_send(request_dict)
    
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        return jsonify({
            "success": True, 
            "message": f"Position {ticket} closed.",
            "ticket": result.order
        }), 200
    else:
        return jsonify({
            "success": False, 
            "error": result.comment if result else "MT5 Close failed."
        }), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)