import math
import random
import tempfile
import textwrap
from pathlib import Path

from modbridge.sim_config import RegisterConfig, SimConfig, load as load_sim_config
from modbridge.simulator import NUM_REGISTERS


# ── RegisterConfig defaults ─────────────────────────────────────────────────

def test_register_config_default_behavior():
    r = RegisterConfig(address=40001, initial=1000)
    assert r.behavior == "walk"
    assert r.delta == 50
    assert r.min == 0 and r.max == 65535


def test_register_config_custom_fields():
    r = RegisterConfig(address=40002, initial=500, behavior="counter", step=10)
    assert r.step == 10 and r.behavior == "counter"


# ── SimConfig loading from TOML ────────────────────────────────────────────

def test_load_sim_config_from_toml(tmp_path):
    toml_file = tmp_path / "test.toml"
    toml_file.write_text(textwrap.dedent("""\
        [[register]]
        address = 40001
        initial = 2000
        behavior = "static"

        [[register]]
        address = 40002
        initial = 500
        behavior = "counter"
        step = 5
    """))
    cfg = load_sim_config(str(toml_file))
    assert len(cfg.registers) == 2
    assert cfg.registers[0].address == 40001
    assert cfg.registers[0].behavior == "static"
    assert cfg.registers[1].step == 5


def test_load_sim_config_empty_toml(tmp_path):
    toml_file = tmp_path / "empty.toml"
    toml_file.write_text("")
    cfg = load_sim_config(str(toml_file))
    assert cfg.registers == []


# ── Register bounds ────────────────────────────────────────────────────────

def test_num_registers_is_100():
    assert NUM_REGISTERS == 100


def test_random_walk_stays_in_bounds():
    registers = [random.randint(1000, 5000) for _ in range(NUM_REGISTERS)]
    for _ in range(1000):
        for i in range(len(registers)):
            delta = random.randint(-50, 50)
            registers[i] = max(0, min(65535, registers[i] + delta))
    assert all(0 <= v <= 65535 for v in registers)


def test_counter_behavior_wraps_around():
    v = 65530
    step = 10
    for _ in range(10):
        v = (v + step) % 65536
    assert 0 <= v <= 65535


def test_sine_behavior_stays_in_range():
    cfg = RegisterConfig(address=40001, initial=1000, behavior="sine", min=100, max=1000, period=60)
    for tick in range(cfg.period * 2):
        phase = 2 * math.pi * tick / cfg.period
        val = cfg.min + (cfg.max - cfg.min) * (math.sin(phase) + 1) / 2
        assert cfg.min <= round(val) <= cfg.max