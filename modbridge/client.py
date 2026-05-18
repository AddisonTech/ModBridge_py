from __future__ import annotations
from typing import Dict, Tuple

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException


def parse_register_range(spec: str) -> Tuple[int, int]:
    """Parse '40001-40010' or '30001-30010' into (start, end).

    30001-39999 = input registers (FC4), 40001-49999 = holding registers (FC3).
    """
    parts = spec.split("-")
    if len(parts) != 2:
        raise ValueError(f"Invalid register range {spec!r}. Expected format: 40001-40010")
    start, end = int(parts[0]), int(parts[1])
    if start > end:
        raise ValueError("Register range: start must be <= end")
    valid_fc4 = 30001 <= start <= 39999 and 30001 <= end <= 39999
    valid_fc3 = 40001 <= start <= 49999 and 40001 <= end <= 49999
    if not valid_fc4 and not valid_fc3:
        raise ValueError(
            "Register range must be 30001-39999 (input registers, FC4) "
            "or 40001-49999 (holding registers, FC3)"
        )
    return start, end


class ModbusPoller:
    """Async Modbus TCP client. Supports FC3 (holding) and FC4 (input) registers."""

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
        """Read registers. start_register uses Modbus numbering (30001+ = FC4, 40001+ = FC3)."""
        if not self._client or not self._client.connected:
            raise ConnectionError("Not connected to Modbus device")
        if 30001 <= start_register <= 39999:
            address = start_register - 30001
            result = await self._client.read_input_registers(
                address=address, count=count, device_id=self.unit_id
            )
        else:
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
