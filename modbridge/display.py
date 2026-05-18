from __future__ import annotations
import asyncio
import sys
from datetime import datetime
from typing import Dict

from rich import box
from rich.console import Console
from rich.live import Live
from rich.table import Table

from .client import ModbusPoller

console = Console()


def _build_table(values: Dict[int, int], timestamp: str) -> Table:
    table = Table(
        title=f"[bold cyan]ModBridge[/bold cyan]  [dim]{timestamp}[/dim]",
        box=box.SIMPLE_HEAVY,
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column("Register", justify="right", style="bold", width=12)
    table.add_column("Value (dec)", justify="right", width=14)
    table.add_column("Value (hex)", justify="right", width=12)

    for addr in sorted(values):
        val = values[addr]
        table.add_row(str(addr), str(val), f"0x{val:04X}")

    return table


async def live_display(poller: ModbusPoller, start_register: int, count: int, interval: float) -> None:
    with Live(console=console, refresh_per_second=4, screen=False) as live:
        while True:
            try:
                values = await poller.poll(start_register, count)
                ts = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
                live.update(_build_table(values, ts))
            except Exception as exc:
                console.print(f"[red]Poll error:[/red] {exc}")
                print(file=sys.stderr)
            await asyncio.sleep(interval)
