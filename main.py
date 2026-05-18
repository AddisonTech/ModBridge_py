#!/usr/bin/env python3
"""ModBridge -- Modbus TCP utility."""
from __future__ import annotations
import argparse
import asyncio
import sys


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--interval", type=float, default=1.0,
        metavar="SECONDS", help="Poll interval in seconds (default: 1)"
    )
    parser.add_argument(
        "--unit-id", type=int, default=1, dest="unit_id",
        metavar="ID", help="Modbus unit/slave ID (default: 1)"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="Modbus TCP utility -- poll, serve, log, or simulate",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- poll ---
    p_poll = sub.add_parser("poll", help="Live terminal table of register values")
    p_poll.add_argument("--host", required=True, metavar="IP", help="Modbus device host")
    p_poll.add_argument("--port", type=int, default=502, metavar="PORT", help="Modbus TCP port (default: 502)")
    p_poll.add_argument(
        "--registers", required=True, metavar="RANGE",
        help="Register range: 40001-40010 (holding, FC3) or 30001-30010 (input, FC4)"
    )
    _add_common(p_poll)

    # --- serve ---
    p_serve = sub.add_parser("serve", help="REST API server exposing live register values")
    p_serve.add_argument("--host", required=True, metavar="IP", help="Modbus device host")
    p_serve.add_argument(
        "--modbus-port", type=int, default=502, dest="modbus_port",
        metavar="PORT", help="Modbus TCP port (default: 502)"
    )
    p_serve.add_argument(
        "--registers", required=True, metavar="RANGE",
        help="Register range: 40001-40100 (holding, FC3) or 30001-30100 (input, FC4)"
    )
    p_serve.add_argument("--port", type=int, default=3000, metavar="PORT", help="REST API port (default: 3000)")
    _add_common(p_serve)

    # --- log ---
    p_log = sub.add_parser("log", help="Log register values to a CSV file")
    p_log.add_argument("--host", required=True, metavar="IP", help="Modbus device host")
    p_log.add_argument("--port", type=int, default=502, metavar="PORT", help="Modbus TCP port (default: 502)")
    p_log.add_argument(
        "--registers", required=True, metavar="RANGE",
        help="Register range: 40001-40010 (holding, FC3) or 30001-30010 (input, FC4)"
    )
    p_log.add_argument("--output", required=True, metavar="FILE", help="Output CSV file path")
    _add_common(p_log)

    # --- simulate ---
    p_sim = sub.add_parser("simulate", help="Run a fake Modbus TCP server")
    p_sim.add_argument("--host", default="localhost", metavar="ADDR", help="Bind address (default: localhost)")
    p_sim.add_argument("--port", type=int, default=502, metavar="PORT", help="Bind port (default: 502)")
    p_sim.add_argument(
        "--config", metavar="FILE", default=None,
        help="TOML config file for per-register behaviors (walk/static/counter/sine)"
    )
    _add_common(p_sim)

    return parser


async def cmd_poll(args: argparse.Namespace) -> None:
    from modbridge.client import parse_register_range
    from modbridge.display import live_display

    start, end = parse_register_range(args.registers)
    count = end - start + 1
    await live_display(args.host, args.port, args.unit_id, start, count, args.interval)


async def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn
    from modbridge.client import parse_register_range
    from modbridge.api import init_app

    start, end = parse_register_range(args.registers)
    count = end - start + 1
    app = init_app(
        host=args.host,
        modbus_port=args.modbus_port,
        start_register=start,
        count=count,
        interval=args.interval,
        unit_id=args.unit_id,
    )
    config = uvicorn.Config(app, host="0.0.0.0", port=args.port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def cmd_log(args: argparse.Namespace) -> None:
    from modbridge.client import parse_register_range
    from modbridge.logger import log_to_csv

    start, end = parse_register_range(args.registers)
    count = end - start + 1
    await log_to_csv(args.host, args.port, args.unit_id, start, count, args.interval, args.output)


async def cmd_simulate(args: argparse.Namespace) -> None:
    from modbridge.simulator import run_simulator
    await run_simulator(host=args.host, port=args.port, interval=args.interval, config_path=args.config)


async def _main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    dispatch = {
        "poll": cmd_poll,
        "serve": cmd_serve,
        "log": cmd_log,
        "simulate": cmd_simulate,
    }
    await dispatch[args.command](args)


def main() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        print("\n  Stopped.")
    except ConnectionError as exc:
        print(f"\n  Connection error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"\n  Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
