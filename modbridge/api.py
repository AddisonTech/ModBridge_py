from __future__ import annotations
import asyncio
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException

from .client import ModbusPoller

# Shared state updated by the background poll loop
_state: Dict[str, Any] = {
    "registers": {},
    "last_updated": None,
    "error": None,
}

_poller: Optional[ModbusPoller] = None
_poll_task: Optional[asyncio.Task] = None


async def _poll_loop(start_register: int, count: int, interval: float) -> None:
    while True:
        try:
            values = await _poller.poll(start_register, count)
            _state["registers"] = {str(k): v for k, v in values.items()}
            _state["last_updated"] = datetime.now(timezone.utc).isoformat()
            _state["error"] = None
        except Exception as exc:
            _state["error"] = str(exc)
            print(f"  Poll error: {exc}", file=sys.stderr)
        await asyncio.sleep(interval)


def init_app(
    host: str,
    modbus_port: int,
    start_register: int,
    count: int,
    interval: float,
    unit_id: int,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        global _poller, _poll_task
        _poller = ModbusPoller(host, port=modbus_port, unit_id=unit_id)
        await _poller.connect()
        _poll_task = asyncio.create_task(_poll_loop(start_register, count, interval))
        yield
        _poll_task.cancel()
        try:
            await _poll_task
        except asyncio.CancelledError:
            pass
        await _poller.close()

    app = FastAPI(title="ModBridge", version="0.1.0", lifespan=lifespan)

    @app.get("/registers")
    async def get_all_registers():
        return {
            "registers": _state["registers"],
            "last_updated": _state["last_updated"],
            "error": _state["error"],
        }

    @app.get("/registers/{address}")
    async def get_register(address: int):
        key = str(address)
        if key not in _state["registers"]:
            raise HTTPException(status_code=404, detail=f"Register {address} not found or not polled yet")
        return {
            "address": address,
            "value": _state["registers"][key],
            "last_updated": _state["last_updated"],
        }

    return app
