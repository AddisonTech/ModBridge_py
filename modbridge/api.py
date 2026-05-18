from __future__ import annotations
import asyncio
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import FastAPI, HTTPException

from .client import ModbusPoller

_state: Dict[str, Any] = {
    "registers": {},
    "last_updated": None,
    "error": None,
}

_poll_task: asyncio.Task | None = None


async def _poll_loop(
    host: str,
    modbus_port: int,
    unit_id: int,
    start_register: int,
    count: int,
    interval: float,
) -> None:
    while True:
        try:
            async with ModbusPoller(host, port=modbus_port, unit_id=unit_id) as poller:
                while True:
                    try:
                        values = await poller.poll(start_register, count)
                        _state["registers"] = {str(k): v for k, v in values.items()}
                        _state["last_updated"] = datetime.now(timezone.utc).isoformat()
                        _state["error"] = None
                    except Exception as exc:
                        _state["error"] = str(exc)
                        print(f"  Poll error: {exc} -- reconnecting", file=sys.stderr)
                        break
                    await asyncio.sleep(interval)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            _state["error"] = f"connection failed: {exc}"
            print(f"  Connection failed: {exc} -- retrying in 2s", file=sys.stderr)
            await asyncio.sleep(2)


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
        global _poll_task
        _poll_task = asyncio.create_task(
            _poll_loop(host, modbus_port, unit_id, start_register, count, interval)
        )
        yield
        _poll_task.cancel()
        try:
            await _poll_task
        except asyncio.CancelledError:
            pass

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
            raise HTTPException(
                status_code=404,
                detail=f"Register {address} not found or not polled yet",
            )
        return {
            "address": address,
            "value": _state["registers"][key],
            "last_updated": _state["last_updated"],
        }

    return app
