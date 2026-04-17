import os
import sys

def enable_windows_colors():
    """Enable ANSI colors on Windows"""
    if sys.platform == "win32":
        try:
            # Enable ANSI escape sequences on Windows 10+
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            print("Windows ANSI colors enabled!")
            return True
        except:
            print("Could not enable Windows ANSI colors")
            return False
    return True

def test_colors_with_windows_support():
    """Test colors with Windows support"""
    enable_windows_colors()
    
    colors = {
        'RED': '\033[91m',
        'GREEN': '\033[92m', 
        'YELLOW': '\033[93m',
        'BLUE': '\033[94m',
        'MAGENTA': '\033[95m',
        'CYAN': '\033[96m',
        'RESET': '\033[0m'
    }
    
    print("Testing colors with Windows support:")
    for name, code in colors.items():
        print(f"{code}■ {name} COLOR TEST{colors['RESET']}")

if __name__ == "__main__":
    test_colors_with_windows_support()