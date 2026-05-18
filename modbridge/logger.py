from __future__ import annotations
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .client import ModbusPoller


async def log_to_csv(
    poller: ModbusPoller,
    start_register: int,
    count: int,
    interval: float,
    output: str,
) -> None:
    path = Path(output)
    registers = list(range(start_register, start_register + count))
    columns = ["timestamp"] + [str(r) for r in registers]
    write_header = not path.exists()
    rows_written = 0

    print(f"  Logging {count} registers to {output}")
    print("  Press Ctrl+C to stop.\n")

    try:
        while True:
            try:
                values = await poller.poll(start_register, count)
                ts = datetime.now(timezone.utc).isoformat()
                row = [ts] + [values.get(r) for r in registers]
                df = pd.DataFrame([row], columns=columns)
                df.to_csv(path, mode="a", header=write_header, index=False)
                write_header = False
                rows_written += 1
                print(f"\r  Rows written: {rows_written}", end="", flush=True)
            except Exception as exc:
                print(f"\n  Poll error: {exc}", file=sys.stderr)
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        print(f"\n  Stopped. {rows_written} rows written to {output}")
