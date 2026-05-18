"""
Fake Modbus TCP server for offline testing.

Implements Modbus TCP (FC3 and FC4) directly over asyncio TCP.
No pymodbus server dependency -- works with any pymodbus version.

Hosts 100 registers (internal addresses 0-99) served as both holding
registers (FC3, 40001-40100) and input registers (FC4, 30001-30100).
Values random-walk each interval, or follow per-register behaviors
from an optional config file.
"""
from __future__ import annotations
import asyncio
import math
import random
from typing import List, Optional

NUM_REGISTERS = 100


async def _handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    lock: asyncio.Lock,
    registers: List[int],
) -> None:
    try:
        while True:
            header = await reader.readexactly(7)
            trans_id = header[0:2]
            proto_id = header[2:4]
            length = int.from_bytes(header[4:6], "big")
            unit_id = header[6]

            pdu = await reader.readexactly(length - 1)
            func_code = pdu[0]

            # FC3 = Read Holding Registers, FC4 = Read Input Registers -- same PDU shape.
            if func_code in (0x03, 0x04) and len(pdu) >= 5:
                start = int.from_bytes(pdu[1:3], "big")
                qty = int.from_bytes(pdu[3:5], "big")
                qty = max(1, min(qty, NUM_REGISTERS - start))

                async with lock:
                    values = registers[start : start + qty]

                byte_count = len(values) * 2
                resp_pdu = bytes([func_code, byte_count])
                for v in values:
                    resp_pdu += v.to_bytes(2, "big")

                pdu_len = len(resp_pdu) + 1
                response = (
                    trans_id
                    + proto_id
                    + pdu_len.to_bytes(2, "big")
                    + bytes([unit_id])
                    + resp_pdu
                )
                writer.write(response)
                await writer.drain()
    except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError):
        pass
    finally:
        writer.close()


async def _random_walk(lock: asyncio.Lock, registers: List[int], interval: float) -> None:
    while True:
        await asyncio.sleep(interval)
        async with lock:
            for i in range(len(registers)):
                delta = random.randint(-50, 50)
                registers[i] = max(0, min(65535, registers[i] + delta))


async def _config_walk(lock: asyncio.Lock, registers: List[int], configs, interval: float) -> None:
    config_map = {}
    for cfg in configs:
        idx = cfg.address - 40001
        if 0 <= idx < len(registers):
            registers[idx] = cfg.initial
            config_map[idx] = cfg

    tick = 0
    while True:
        await asyncio.sleep(interval)
        tick += 1
        async with lock:
            for i in range(len(registers)):
                if i in config_map:
                    cfg = config_map[i]
                    if cfg.behavior == "static":
                        pass
                    elif cfg.behavior == "walk":
                        delta = random.randint(-cfg.delta, cfg.delta)
                        registers[i] = max(0, min(65535, registers[i] + delta))
                    elif cfg.behavior == "counter":
                        registers[i] = (registers[i] + cfg.step) % 65536
                    elif cfg.behavior == "sine":
                        phase = 2 * math.pi * tick / cfg.period
                        val = cfg.min + (cfg.max - cfg.min) * (math.sin(phase) + 1) / 2
                        registers[i] = round(val)
                else:
                    delta = random.randint(-50, 50)
                    registers[i] = max(0, min(65535, registers[i] + delta))


async def run_simulator(
    host: str = "localhost",
    port: int = 502,
    interval: float = 1.0,
    config_path: Optional[str] = None,
) -> None:
    lock = asyncio.Lock()
    registers: List[int] = [random.randint(1000, 5000) for _ in range(NUM_REGISTERS)]

    if config_path:
        from .sim_config import load as load_config
        cfg = load_config(config_path)
        walk_task = asyncio.create_task(_config_walk(lock, registers, cfg.registers, interval))
        reg_desc = f"{len(cfg.registers)} configured registers"
    else:
        walk_task = asyncio.create_task(_random_walk(lock, registers, interval))
        reg_desc = f"{NUM_REGISTERS} registers (40001-40100) with random-walking values"

    server = await asyncio.start_server(
        lambda r, w: _handle_client(r, w, lock, registers),
        host=host,
        port=port,
    )

    print(f"  Simulator running on {host}:{port}")
    print(f"  Serving {reg_desc}")
    print("  Press Ctrl+C to stop")

    try:
        async with server:
            await server.serve_forever()
    except asyncio.CancelledError:
        pass
    finally:
        walk_task.cancel()
        try:
            await walk_task
        except asyncio.CancelledError:
            pass
