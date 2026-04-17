# UT Bot Trading Strategy

An automated MetaTrader 5 trading bot using UT Bot ATR Trailing Stop, RSI, and breakout/pullback entry logic for forex and gold trading.

## Features

- **UT Bot ATR Trailing Stop**: Key_Value=1.0, ATR_Period=1 (single candle range) for dynamic trend detection
- **RSI Filter**: 14-period RSI (Wilder's smoothing) for momentum confirmation
- **Breakout/Pullback Entry**: Price action based on previous candle analysis for precise entries
- **Sideways Market Detection**: Blocks trades when UT Trail range < 0.3 points over 10 candles
- **Fixed 1-Point Stop Loss**: Hard stop loss at exactly 1.0 points from entry price (highest priority)
- **Dynamic Trailing Stop**: Activates after 0.01 points profit, trails 1.0 points behind price
- **UT Trail Live Exit**: Position closed if price crosses back through the live UT trail
- **Dynamic Volume Cap**: Positions sized automatically based on account balance, capped at $5000 capital usage

---

## How the Bot Works

The bot runs in a continuous loop (every 1 second) and performs the following on each cycle:

1. Fetches the latest OHLCV candle data from MT5 (M5 timeframe by default)
2. Calculates RSI(14), ATR(20), and UT Bot ATR Trailing Stop
3. Evaluates entry conditions against the latest candle
4. If a signal is found and no position is open, executes a market order
5. Monitors open positions and applies trailing stop + UT trail live exit logic

---

## Entry Conditions

### BUY Signal
All conditions must be true:
- Price is **above** UT Bot trailing stop (`ut_buy = True`)
- RSI(14) **> 30**
- **Multi-Tick Momentum Confirmation** (60% of last 5 ticks show bullish momentum)
- **Breakout/Pullback Logic:**
  - **Previous GREEN candle:** Current price (`tick.ask`) **> previous close OR previous high** (breakout)
  - **Previous RED candle:** Current price (`tick.ask`) **> previous open OR previous high** (pullback)

### SELL Signal
All conditions must be true:
- Price is **below** UT Bot trailing stop (`ut_sell = True`)
- RSI(14) **< 70**
- **Multi-Tick Momentum Confirmation** (60% of last 5 ticks show bearish momentum)
- **Breakout/Pullback Logic:**
  - **Previous RED candle:** Current price (`tick.bid`) **< previous close OR previous low** (breakout)
  - **Previous GREEN candle:** Current price (`tick.bid`) **< previous open OR previous low** (pullback)

### Multi-Tick Momentum System
- **Collects last 5 price ticks** for momentum analysis
- **BUY Momentum:** 60% of ticks show `bid > current_open` OR `bid > current_low`
- **SELL Momentum:** 60% of ticks show `ask < current_open` OR `ask < current_high`
- **Trend Strength Boost:** Consistent directional movement in recent 3 ticks lowers threshold to 40%
- **Purpose:** Filters out weak signals during choppy price action

### Tick Confirmation System
- **Requires 2 consecutive tick confirmations** before entry
- **Confirmation Window:** 10 seconds maximum
- **Signal must persist** across multiple ticks to avoid false breakouts
- **Status:** Shows "CONFIRMING (X/2)" during confirmation phase

### Sideways Market Filter
- **Blocks all trades** when market is sideways
- Detection: UT Trail range < 0.3 points over last 10 candles
- Status displays "SIDEWAYS" when active
- Prevents false signals during low-volatility periods

### DOJI Candle Handling
- **DOJI candles ignored** (previous close = previous open)
- No signals generated when previous candle is DOJI
- System waits for clear directional candle

> Only one position per symbol is allowed at a time.

---

## UT Bot ATR Trailing Stop Calculation

- ATR Period = 1 (single candle high-low range)
- Key Value = 1.0 (multiplier)
- `n_loss = 1.0 × |high - low|`
- Trail ratchets up in uptrend, down in downtrend
- `ut_buy` = price > trail | `ut_sell` = price < trail

---

## Exit Conditions

### Fixed 1-Point Stop Loss (Highest Priority)
- **Hard stop loss** at exactly **1.0 points** from entry price
- BUY: `entry - 1.0 pts` (e.g., 4702.00 entry → 4701.00 exit)
- SELL: `entry + 1.0 pts` (e.g., 4700.00 entry → 4701.00 exit)
- Triggers **immediately** when price hits the 1-point level
- Takes precedence over all other exit conditions

### Dynamic Trailing Stop
- Activates after **0.01 points profit** (measured in points, not dollars)
- Trails **1.0 points** behind current price
- BUY: `current bid - 1.0 pts` (only moves up)
- SELL: `current ask + 1.0 pts` (only moves down)

### Exit Priority Order
1. **Fixed 1-Point Stop Loss** (highest priority)
2. **Dynamic Trailing Stop** (after $0.01 profit)
3. Take Profit (4.0 points)

---

## Live Log Format

Each tick outputs a single compact line:
```
[HH:MM:SS.mmm] Tick#N | Price: X | UTTrail: X | RSI: X | Candle: GREEN/RED | UT_Buy: T/F | UT_Sell: T/F | Move: Xpts | Trail: ACTIVE/need Xmore | TrailSL: X | BrokerSL: X | Status: IN_TRADE/SIGNAL/CONFIRMING/SIDEWAYS/WAITING
```

**Status Meanings:**
- **IN_TRADE:** Position is open
- **SIGNAL:** Entry conditions met, executing trade
- **CONFIRMING (X/2):** Signal detected, collecting tick confirmations
- **SIDEWAYS:** Market conditions block trading
- **WAITING:** No signals detected

---

## Setup Instructions

### 1. Prerequisites
- MetaTrader 5 installed and running
- Python 3.8 or higher
- Active MT5 account

### 2. Installation
```bash
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file with your MT5 credentials:
```
MT5_LOGIN=your_login
MT5_PASSWORD=your_password
MT5_SERVER=your_server
MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
```

### 4. Run the Bot
```bash
python flexible_entry_test.py
```

---

## Key Parameters (in `__init__`)

| Parameter | Value | Description |
|---|---|---|
| `atr_sl_multiplier` | 1.5 | ATR stop loss distance multiplier |
| `tp_points` | 4.0 | Take profit in points |
| `breakeven_points` | 3.0 | Points move needed to activate breakeven |
| `trailing_points` | 0.01 | Points profit needed to activate trailing stop |
| `trailing_gap` | 1.0 | Points trail behind current price |
| `fixed_sl_points` | 1.0 | Fixed 1-point stop loss exit |

## UT Bot Parameters

| Parameter | Value | Description |
|---|---|---|
| `key_value` | 1.0 | UT Bot ATR multiplier |
| `atr_period` | 1 | ATR period (single candle range) |
| `rsi_period` | 14 | RSI calculation period |
| `atr_sl_period` | 20 | ATR period for stop loss calculation |

## Multi-Tick Momentum Parameters

| Parameter | Value | Description |
|---|---|---|
| `max_tick_history` | 5 | Number of recent ticks stored for analysis |
| `momentum_threshold` | 3 | Minimum ticks needed for momentum confirmation |
| `momentum_confirmation_threshold` | 60.0 | Percentage of ticks required for momentum (60%) |
| `trend_strength_threshold` | 40.0 | Lower threshold when trend strength detected |

## Tick Confirmation Parameters

| Parameter | Value | Description |
|---|---|---|
| `required_confirmations` | 2 | Number of consecutive tick confirmations needed |
| `confirmation_window` | 10 | Maximum seconds for confirmation collection |

## Sideways Detection Parameters

| Parameter | Value | Description |
|---|---|---|
| `lookback` | 10 | Number of candles to analyze for sideways detection |
| `threshold` | 0.3 | UT Trail range threshold (points) for sideways market |

---

## File Structure

```
TradingBot_EMA_version-2/
├── enhanced_strategy.py           # Core strategy engine with breakout/pullback logic
├── flexible_entry_test.py         # Main trading bot runner
├── trade_backend/
│   ├── triple_strategy.py         # Multi-timeframe consensus strategy
│   ├── mt5_api_bridge.py          # MT5 API bridge
│   └── run_bot.py                 # Alternative bot runner
├── test_*.py                      # Testing and diagnostic files
├── requirements.txt
├── .env                           # MT5 credentials (not committed)
└── README.md
```

## Trading Symbols

Configured for:
- **XAUUSD** (Gold)
- **EURUSD** (Euro/Dollar)

## Disclaimer

This bot is for educational and research purposes. Trading forex and CFDs involves significant risk. Always test on a demo account before live trading.
