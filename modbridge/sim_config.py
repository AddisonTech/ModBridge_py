from __future__ import annotations
import tomllib
from dataclasses import dataclass
from typing import List


@dataclass
class RegisterConfig:
    address: int
    initial: int
    behavior: str = "walk"   # walk | static | counter | sine
    delta: int = 50           # walk: max random delta per tick
    step: int = 1             # counter: increment per tick (negative counts down)
    min: int = 0              # sine: minimum value
    max: int = 65535          # sine: maximum value
    period: int = 60          # sine: period in ticks


@dataclass
class SimConfig:
    registers: List[RegisterConfig]


def load(path: str) -> SimConfig:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    regs = []
    for r in data.get("register", []):
        regs.append(RegisterConfig(
            address=r["address"],
            initial=r["initial"],
            behavior=r.get("behavior", "walk"),
            delta=r.get("delta", 50),
            step=r.get("step", 1),
            min=r.get("min", 0),
            max=r.get("max", 65535),
            period=r.get("period", 60),
        ))
    return SimConfig(registers=regs)
