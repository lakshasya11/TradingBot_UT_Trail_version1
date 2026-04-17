import os
import sys
from datetime import datetime

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

class TerminalFormatter:
    def __init__(self):
        # Force enable colors
        os.environ['FORCE_COLOR'] = '1'
        os.environ['TERM'] = 'xterm-256color'
        
        # ANSI color codes
        self.CYAN = '\033[96m'
        self.GREEN = '\033[92m'
        self.RED = '\033[91m'
        self.YELLOW = '\033[93m'
        self.BLUE = '\033[94m'
        self.MAGENTA = '\033[95m'
        self.WHITE = '\033[97m'
        self.RESET = '\033[0m'
        self.BOLD = '\033[1m'
        
    def colorize_price(self, price):
        """Color price values in yellow"""
        return f"{self.YELLOW}{price}{self.RESET}"
        
    def colorize_trail(self, trail):
        """Color trail values in red"""
        return f"{self.RED}{trail}{self.RESET}"
        
    def colorize_rsi(self, rsi):
        """Color RSI values in red"""
        return f"{self.RED}{rsi}{self.RESET}"
        
    def colorize_candle(self, candle):
        """Color candle based on type"""
        if candle == 'GREEN':
            return f"{self.GREEN}{candle}{self.RESET}"
        elif candle == 'RED':
            return f"{self.RED}{candle}{self.RESET}"
        return candle
        
    def colorize_status(self, status):
        """Color status based on type"""
        if 'WAITING' in status:
            return f"{self.CYAN}{status}{self.RESET}"
        elif 'IN_POSITION' in status or 'IN POSITION' in status:
            return f"{self.GREEN}{status}{self.RESET}"
        elif 'SIGNAL' in status:
            return f"{self.MAGENTA}{status}{self.RESET}"
        return status
        
    def colorize_ticket(self, ticket):
        """Color ticket numbers in blue"""
        return f"{self.BLUE}{ticket}{self.RESET}"
        
    def print_trade_entry(self, trade_type, entry_price, volume, sl, tp, ticket, conditions, capital, trades_today):
        """Print formatted trade entry box"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        # Box border
        border = "─" * 50
        print(f"\n{self.CYAN}┌{border}┐{self.RESET}")
        print(f"{self.CYAN}│{self.BOLD}{'TRADE ENTERED':^50}{self.RESET}{self.CYAN}│{self.RESET}")
        print(f"{self.CYAN}├{border}┤{self.RESET}")
        
        # Trade details
        line1 = f" Time: {timestamp} | Type: {trade_type} | Ticket: #{ticket}"
        print(f"{self.CYAN}│{self.RESET}{line1}{' ' * (50 - len(line1))}{self.CYAN}│{self.RESET}")
        
        line2 = f" Entry: {entry_price} | Volume: {volume} | SL: {sl}"
        print(f"{self.CYAN}│{self.RESET}{line2}{' ' * (50 - len(line2))}{self.CYAN}│{self.RESET}")
        
        print(f"{self.CYAN}│{' ' * 50}│{self.RESET}")
        
        line3 = f" Entry Conditions: {conditions}"
        print(f"{self.CYAN}│{self.RESET}{line3}{' ' * (50 - len(line3))}{self.CYAN}│{self.RESET}")
        
        print(f"{self.CYAN}│{' ' * 50}│{self.RESET}")
        
        line4 = f" Capital: ${capital} | Trades Today: {trades_today}"
        print(f"{self.CYAN}│{self.RESET}{line4}{' ' * (50 - len(line4))}{self.CYAN}│{self.RESET}")
        
        print(f"{self.CYAN}└{border}┘{self.RESET}")
        
    def print_trade_exit(self, trade_type, entry_price, exit_price, duration, ticket, session_trades, win_rate, capital, total_profit):
        """Print formatted trade exit box"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        # Box border
        border = "─" * 50
        print(f"\n{self.CYAN}┌{border}┐{self.RESET}")
        print(f"{self.CYAN}│{self.BOLD}{'TRADE EXITED':^50}{self.RESET}{self.CYAN}│{self.RESET}")
        print(f"{self.CYAN}├{border}┤{self.RESET}")
        
        # Trade details
        print(f"{self.CYAN}│{self.RESET} Time: {timestamp} | Type: {trade_type} | Ticket: #{ticket}")
        print(f"{self.CYAN}│{self.RESET} Entry: {entry_price} | Exit: {exit_price} | Duration: {duration}")
        print(f"{self.CYAN}│{self.RESET}")
        print(f"{self.CYAN}│{self.RESET} Session: {session_trades} Trades | {win_rate}% Win ({win_rate}%)")
        print(f"{self.CYAN}│{self.RESET} Capital: ${capital} | Total Profit: ${total_profit}")
        print(f"{self.CYAN}└{border}┘{self.RESET}")
        
    def print_position_update(self, ticket, trail_value, price, rsi, candle, status, pnl):
        """Print position update line with P/L"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        # Color P/L based on profit/loss
        pnl_color = self.GREEN if pnl >= 0 else self.RED
        pnl_str = f"{pnl_color}${pnl:.2f}{self.RESET}"
        
        # Color other elements with proper formatting
        colored_ticket = self.colorize_ticket(f"#{ticket}")
        colored_trail = self.colorize_trail(f"{trail_value:.2f}")
        colored_price = self.colorize_price(f"{price:.2f}")
        colored_rsi = self.colorize_rsi(f"{rsi:.1f}")
        colored_candle = self.colorize_candle(candle)
        colored_status = self.colorize_status(status)
        
        print(f"[{timestamp}] Tick{colored_ticket} | Price: {colored_price} | Trail: {colored_trail} | Candle: {colored_candle} | RSI: {colored_rsi} | Status: {colored_status} | P/L: {pnl_str}")
        
    def print_trade_exit_with_condition(self, trade_type, entry_price, exit_price, duration, ticket, session_trades, win_rate, capital, total_profit, exit_condition):
        """Print formatted trade exit box with exit condition"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        # Box border
        border = "─" * 50
        print(f"\n{self.CYAN}┌{border}┐{self.RESET}")
        print(f"{self.CYAN}│{self.BOLD}{'TRADE EXITED':^50}{self.RESET}{self.CYAN}│{self.RESET}")
        print(f"{self.CYAN}├{border}┤{self.RESET}")
        
        # Trade details
        print(f"{self.CYAN}│{self.RESET} Time: {timestamp} | Type: {trade_type} | Ticket: #{ticket} {self.CYAN}│{self.RESET}")
        print(f"{self.CYAN}│{self.RESET} Entry: {entry_price} | Exit: {exit_price} | Duration: {duration}{' ' * (50 - len(f' Entry: {entry_price} | Exit: {exit_price} | Duration: {duration}') - 1)}{self.CYAN}│{self.RESET}")
        print(f"{self.CYAN}│{' ' * 50}{self.CYAN}│{self.RESET}")
        print(f"{self.CYAN}│{self.RESET} Exit Condition: {exit_condition}{' ' * (50 - len(f' Exit Condition: {exit_condition}') - 1)}{self.CYAN}│{self.RESET}")
        print(f"{self.CYAN}│{' ' * 50}{self.CYAN}│{self.RESET}")
        print(f"{self.CYAN}│{self.RESET} Session: {session_trades} Trades | {win_rate:.1f}% Win ({win_rate:.1f}%){' ' * (50 - len(f' Session: {session_trades} Trades | {win_rate:.1f}% Win ({win_rate:.1f}%)') - 1)}{self.CYAN}│{self.RESET}")
        print(f"{self.CYAN}│{self.RESET} Capital: ${capital} | Total Profit: ${total_profit:.2f}{' ' * (50 - len(f' Capital: ${capital} | Total Profit: ${total_profit:.2f}') - 1)}{self.CYAN}│{self.RESET}")
        print(f"{self.CYAN}└{border}┘{self.RESET}")