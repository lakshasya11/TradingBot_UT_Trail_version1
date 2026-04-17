import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import pandas as pd

class ChartDisplay:
    def __init__(self):
        plt.ion()  # Interactive mode
        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        self.price_line = None
        self.ut_trail_line = None
        
    def update_chart(self, df, ut_trail_values, current_price, live_ut_trail):
        """Update chart with price and UT trail"""
        self.ax.clear()
        
        # Plot candlesticks (simplified as line)
        self.ax.plot(df.index, df['close'], 'b-', linewidth=1, label='Price')
        
        # Plot UT Trail as red dotted line
        self.ax.plot(df.index, ut_trail_values, 'r--', linewidth=2, label='UT Trail', alpha=0.8)
        
        # Highlight current live UT trail
        self.ax.axhline(y=live_ut_trail, color='red', linestyle=':', linewidth=3, alpha=0.9, label=f'Live UT Trail: {live_ut_trail:.2f}')
        
        # Current price marker
        self.ax.axhline(y=current_price, color='blue', linestyle='-', alpha=0.7, label=f'Current Price: {current_price:.2f}')
        
        self.ax.set_title('UT Bot Strategy - Live Chart')
        self.ax.legend()
        self.ax.grid(True, alpha=0.3)
        
        plt.draw()
        plt.pause(0.01)