import pandas as pd
import numpy as np
from pathlib import Path

# ==========================================
# XAUUSD ICHIMOKU SCANNER
# Timeframe: M1
# ==========================================

SYMBOL = "XAUUSD"
TIMEFRAME = "M1"

START_DATE = "2026-01-01"
END_DATE = "2026-11-04"

INITIAL_CAPITAL = 10000.0
LOT_SIZE = 0.01
CONTRACT_SIZE = 100

TENKAN_PERIOD = 9
KIJUN_PERIOD = 26
SENKOU_B_PERIOD = 52
DISPLACEMENT = 26

COMMISSION = 0.0
SLIPPAGE = 0.0

DATA_ROOTS = [
    Path("data/xauusd"),
    Path("xauusd")
]

OUTPUT_DIR = Path("results")


# ==========================================
# READ CSV DATA
# ==========================================

def find_files(side):
    for root in DATA_ROOTS:
        folder = root / side / "m1"
        if folder.exists():
            files = sorted(folder.glob("*.csv"))
            if files:
                return files
    return []


def normalize_columns(df):
    df.columns = [
        str(c).strip().lower().replace(" ", "_")
        for c in df.columns
    ]

    aliases = {
        "gmt_time": "datetime",
        "time": "time",
        "date_time": "datetime",
        "timestamp": "datetime",
        "vol": "volume",
        "tickvol": "volume"
    }

    df = df.rename(columns=aliases)

    if "datetime" not in df.columns:
        if "date" in df.columns and "time" in df.columns:
            df["datetime"] = (
                df["date"].astype(str) + " " +
                df["time"].astype(str)
            )
        elif "date" in df.columns:
            df["datetime"] = df["date"]

    if "datetime" not in df.columns:
        raise ValueError("ستون تاریخ و زمان در CSV پیدا نشد.")

    df["datetime"] = pd.to_datetime(
        df["datetime"], errors="coerce", utc=True
    )

    for col in ["open", "high", "low", "close"]:
        if col not in df.columns:
            raise ValueError(f"ستون {col} در CSV وجود ندارد.")
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.dropna(
        subset=["datetime", "open", "high", "low", "close"]
    )


def load_side(side):
    files = find_files(side)

    if not files:
        raise FileNotFoundError(
            f"فایل‌های {side} پیدا نشدند."
        )

    frames = []

    for file in files:
        df = pd.read_csv(file)
        df = normalize_columns(df)

        df = df[
            ["datetime", "open", "high", "low", "close"]
        ]

        df = df.rename(columns={
            "open": f"{side}_open",
            "high": f"{side}_high",
            "low": f"{side}_low",
            "close": f"{side}_close"
        })

        frames.append(df)

    result = pd.concat(frames, ignore_index=True)

    return (
        result.drop_duplicates("datetime")
        .sort_values("datetime")
        .reset_index(drop=True)
    )


# ==========================================
# MERGE ASK AND BID
# ==========================================

def load_market_data():
    print("Loading ASK data...")
    ask = load_side("ask")

    print("Loading BID data...")
    bid = load_side("bid")

    df = pd.merge(
        ask, bid,
        on="datetime",
        how="inner"
    )

    df = df.dropna()

    start = pd.Timestamp(START_DATE, tz="UTC")
    end = pd.Timestamp(END_DATE, tz="UTC")

    df = df[
        (df["datetime"] >= start) &
        (df["datetime"] < end)
    ].copy()

    df = df.sort_values("datetime").reset_index(drop=True)

    if df.empty:
        raise ValueError(
            "هیچ داده‌ای برای بازه انتخابی وجود ندارد."
        )

    print(f"Loaded candles: {len(df):,}")

    return df


# ==========================================
# ICHIMOKU INDICATOR
# ==========================================

def midpoint(high, low, period):
    return (
        high.rolling(period).max() +
        low.rolling(period).min()
    ) / 2


def calculate_ichimoku(df):

    # Mid-price OHLC
    high = (df["ask_high"] + df["bid_high"]) / 2
    low = (df["ask_low"] + df["bid_low"]) / 2
    close = (df["ask_close"] + df["bid_close"]) / 2

    df["tenkan"] = midpoint(
        high, low, TENKAN_PERIOD
    )

    df["kijun"] = midpoint(
        high, low, KIJUN_PERIOD
    )

    df["senkou_a"] = (
        (df["tenkan"] + df["kijun"]) / 2
    )

    df["senkou_b"] = midpoint(
        high, low, SENKOU_B_PERIOD
    )

    # Cloud values available at the current candle
    df["cloud_a"] = df["senkou_a"].shift(DISPLACEMENT)
    df["cloud_b"] = df["senkou_b"].shift(DISPLACEMENT)

    df["price"] = close

    df["cloud_top"] = df[
        ["cloud_a", "cloud_b"]
    ].max(axis=1)

    df["cloud_bottom"] = df[
        ["cloud_a", "cloud_b"]
    ].min(axis=1)

    # Entry conditions
    bullish_cross = (
        (df["tenkan"] > df["kijun"]) &
        (df["tenkan"].shift(1) <= df["kijun"].shift(1))
    )

    bearish_cross = (
        (df["tenkan"] < df["kijun"]) &
        (df["tenkan"].shift(1) >= df["kijun"].shift(1))
    )

    df["buy_signal"] = (
        bullish_cross &
        (close > df["cloud_top"])
    )

    df["sell_signal"] = (
        bearish_cross &
        (close < df["cloud_bottom"])
    )

    return df


# ==========================================
# BACKTEST ENGINE
# ==========================================

def run_backtest(df):

    capital = INITIAL_CAPITAL
    position = None

    trades = []
    equity_curve = []

    for i in range(1, len(df) - 1):

        row = df.iloc[i]
        next_row = df.iloc[i + 1]

        buy_signal = bool(row["buy_signal"])
        sell_signal = bool(row["sell_signal"])

        exit_reason = None

        if position == "BUY":

            if sell_signal or row["price"] < row["kijun"]:
                exit_reason = "EXIT BUY"

        elif position == "SELL":

            if buy_signal or row["price"] > row["kijun"]:
                exit_reason = "EXIT SELL"

        # Exit existing position at next candle
        if position is not None and exit_reason:

            if position == "BUY":
                exit_price = next_row["bid_open"]
                pnl = (
                    exit_price - entry_price
                ) * CONTRACT_SIZE * LOT_SIZE

            else:
                exit_price = next_row["ask_open"]
                pnl = (
                    entry_price - exit_price
                ) * CONTRACT_SIZE * LOT_SIZE

            pnl -= COMMISSION
            pnl -= SLIPPAGE * CONTRACT_SIZE * LOT_SIZE

            capital += pnl

            trades.append({
                "entry_time": entry_time,
                "exit_time": next_row["datetime"],
                "type": position,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "lot": LOT_SIZE,
                "pnl": pnl,
                "capital": capital,
                "reason": exit_reason
            })

            position = None

        # Open a new position only when flat
        if position is None:

            if buy_signal:
                position = "BUY"
                entry_price = next_row["ask_open"]
                entry_time = next_row["datetime"]

            elif sell_signal:
                position = "SELL"
                entry_price = next_row["bid_open"]
                entry_time = next_row["datetime"]

        equity_curve.append({
            "datetime": next_row["datetime"],
            "equity": capital
        })

    return pd.DataFrame(trades), pd.DataFrame(equity_curve), capital


# ==========================================
# REPORT
# ==========================================

def print_report(trades, equity, final_capital):

    total = len(trades)

    if total:
        wins = (trades["pnl"] > 0).sum()
        losses = (trades["pnl"] <= 0).sum()
        win_rate = wins / total * 100

        gross_profit = trades.loc[
            trades["pnl"] > 0, "pnl"
        ].sum()

        gross_loss = abs(
            trades.loc[trades["pnl"] < 0, "pnl"].sum()
        )

        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0 else float("inf")
        )

        max_drawdown = (
            equity["equity"] /
            equity["equity"].cummax() - 1
        ).min() * 100

    else:
        wins = losses = 0
        win_rate = 0
        profit_factor = 0
        max_drawdown = 0

    print("\n========== BACKTEST REPORT ==========")
    print(f"Symbol: {SYMBOL}")
    print(f"Timeframe: {TIMEFRAME}")
    print(f"Initial Capital: ${INITIAL_CAPITAL:.2f}")
    print(f"Final Capital: ${final_capital:.2f}")
    print(f"Net Profit: ${final_capital - INITIAL_CAPITAL:.2f}")
    print(f"Total Trades: {total}")
    print(f"Winning Trades: {wins}")
    print(f"Losing Trades: {losses}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Profit Factor: {profit_factor:.2f}")
    print(f"Max Drawdown: {max_drawdown:.2f}%")
    print("=====================================")


# ==========================================
# LIVE SIGNAL
# ==========================================

def show_latest_signal(df):

    row = df.iloc[-1]

    print("\n========== LATEST SIGNAL ==========")
    print("Time:", row["datetime"])

    if row["buy_signal"]:
        print("SIGNAL: BUY")
        print("ورود خرید: سیگنال خرید")

    elif row["sell_signal"]:
        print("SIGNAL: SELL")
        print("ورود فروش: سیگنال فروش")

    else:
        print("SIGNAL: NO ENTRY")
        print("سیگنال ورود وجود ندارد")

    print("===================================")


# ==========================================
# MAIN
# ==========================================

def main():

    OUTPUT_DIR.mkdir(exist_ok=True)

    df = load_market_data()

    df = calculate_ichimoku(df)

    trades, equity, final_capital = run_backtest(df)

    trades.to_csv(
        OUTPUT_DIR / "trades.csv",
        index=False
    )

    equity.to_csv(
        OUTPUT_DIR / "equity.csv",
        index=False
    )

    df.to_csv(
        OUTPUT_DIR / "signals.csv",
        index=False
    )

    print_report(
        trades,
        equity,
        final_capital
    )

    show_latest_signal(df)

    print("\nFiles saved in results/")


if __name__ == "__main__":
    main()
