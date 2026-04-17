#!/usr/bin/env python3
import os
import sys

# Test ANSI colors
def test_colors():
    print("Testing ANSI colors...")
    
    # Basic colors
    colors = {
        'RED': '\033[91m',
        'GREEN': '\033[92m', 
        'YELLOW': '\033[93m',
        'BLUE': '\033[94m',
        'MAGENTA': '\033[95m',
        'CYAN': '\033[96m',
        'WHITE': '\033[97m',
        'RESET': '\033[0m'
    }
    
    for name, code in colors.items():
        print(f"{code}This text should be {name}{colors['RESET']}")
    
    print("\nIf you see colors above, ANSI works!")
    print("If all text is white, your terminal doesn't support ANSI colors.")
    
    # Test environment
    print(f"\nEnvironment info:")
    print(f"OS: {os.name}")
    print(f"Platform: {sys.platform}")
    print(f"Terminal: {os.environ.get('TERM', 'Unknown')}")
    print(f"COLORTERM: {os.environ.get('COLORTERM', 'Not set')}")

if __name__ == "__main__":
    test_colors()