import MetaTrader5 as mt5
print(f"SYMBOL_FILLING_FOK: {getattr(mt5, 'SYMBOL_FILLING_FOK', 'MISSING')}")
print(f"SYMBOL_FILLING_IOC: {getattr(mt5, 'SYMBOL_FILLING_IOC', 'MISSING')}")
print(f"ORDER_FILLING_FOK: {getattr(mt5, 'ORDER_FILLING_FOK', 'MISSING')}")
print(f"ORDER_FILLING_IOC: {getattr(mt5, 'ORDER_FILLING_IOC', 'MISSING')}")
