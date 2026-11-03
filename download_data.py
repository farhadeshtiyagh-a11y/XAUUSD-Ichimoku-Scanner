import subprocess
import calendar
from pathlib import Path
from datetime import date

from config import START_DATE, END_DATE, BID_DIR, ASK_DIR

INSTRUMENT = "xauusd"

def download_side(side, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)

    start = date.fromisoformat(START_DATE)
    end = date.fromisoformat(END_DATE)

    year, month = start.year, start.month

    while date(year, month, 1) < end:
        last_day = calendar.monthrange(year, month)[1]
        month_end = date(year, month, last_day)

        next_month = (
            date(year + 1, 1, 1)
            if month == 12
            else date(year, month + 1, 1)
        )

        period_end = min(next_month, end)

        filename = f"xauusd_{side}_m1_{year}_{month:02d}"

        command = [
            "npx", "--yes", "dukascopy-node",
            "-i", INSTRUMENT,
            "-from", date(year, month, 1).isoformat(),
            "-to", period_end.isoformat(),
            "-t", "m1",
            "-p", side,
            "-f", "csv",
            "-dir", str(output_dir),
            "-fn", filename,
            "--cache",
            "--retries", "3",
            "--batch-pause", "1000"
        ]

        print("Downloading:", filename)
        subprocess.run(command, check=True)

        year, month = next_month.year, next_month.month


if __name__ == "__main__":
    download_side("bid", BID_DIR)
    download_side("ask", ASK_DIR)
    print("Download completed!")
