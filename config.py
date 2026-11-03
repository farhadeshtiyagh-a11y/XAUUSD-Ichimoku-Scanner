from pathlib import Path

# Project settings
SYMBOL = "XAUUSD"
TIMEFRAME = "M1"

# Backtest period
START_DATE = "2026-01-01"
END_DATE = "2026-11-04"

# Ichimoku settings
TENKAN = 9
KIJUN = 26
SENKOU_B = 52

# Trading settings
INITIAL_BALANCE = 10000
LOT_SIZE = 0.01

# Costs
COMMISSION = 0.0
SLIPPAGE = 0.0

# Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "xauusd"
RESULTS_DIR = BASE_DIR / "results"

BID_DIR = DATA_DIR / "bid" / "m1"
ASK_DIR = DATA_DIR / "ask" / "m1"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
