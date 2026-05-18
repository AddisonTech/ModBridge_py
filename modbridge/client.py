from __future__ import annotations
from typing import Dict, Tuple

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException


def parse_register_range(spec: str) -> Tuple[int, int]:
    """Parse '40001-40010' into (40001, 40010)."""
    parts = spec.split("-")
    if len(parts) != 2:
        raise ValueError(f"Invalid register range {spec!r}. Expected format: 40001-40010")
    start, end = int(parts[0]), int(parts[1])
    if start < 40001 or end > 40999 or start > end:
        raise ValueError("Register range must be within 40001-40999 with start <= end")
    return start, end


class ModbusPoller:
    """Async Modbus TCP client that reads holding registers."""

    def __init__(self, host: str, port: int = 502, unit_id: int = 1):
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self._client: AsyncModbusTcpClient | None = None

    async def connect(self) -> None:
        self._client = AsyncModbusTcpClient(self.host, port=self.port)
        connected = await self._client.connect()
        if not connected:
            raise ConnectionError(f"Could not connect to {self.host}:{self.port}")

    async def close(self) -> None:
        if self._client:
            self._client.close()

    async def poll(self, start_register: int, count: int) -> Dict[int, int]:
        """Read holding registers. start_register uses Modbus numbering (e.g. 40001)."""
        if not self._client or not self._client.connected:
            raise ConnectionError("Not connected to Modbus device")
        address = start_register - 40001
        result = await self._client.read_holding_registers(
            address=address, count=count, device_id=self.unit_id
        )
        if result.isError():
            raise ModbusException(f"Modbus read error: {result}")
        return {start_register + i: result.registers[i] for i in range(count)}

    async def __aenter__(self) -> "ModbusPoller":
        await self.connect()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()
