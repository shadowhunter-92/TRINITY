import argparse
import sys

from trinitylab.industrial.core import (benchmark, drift, load_profile,
                                        load_registers, snapshot)
from trinitylab.industrial.modbus import ModbusError, read_registers
from trinitylab.util import emit


def main() -> int:
    parser = argparse.ArgumentParser(description="TRINITY Industrial: simulated signals, profile drift, read-only Modbus")
    sub = parser.add_subparsers(dest="command", required=True)
    snap = sub.add_parser("snapshot")
    snap.add_argument("--profile", required=True)
    snap.add_argument("--registers", required=True)
    snap.add_argument("--captured-at", default="SIMULATED")
    diff = sub.add_parser("drift")
    diff.add_argument("--old", required=True)
    diff.add_argument("--new", required=True)
    bench = sub.add_parser("benchmark")
    bench.add_argument("--profile", required=True)
    bench.add_argument("--registers", required=True)
    bench.add_argument("--repeats", type=int, default=1000)
    mod = sub.add_parser("modbus-read", help="Explicitly authorized/read-only operation")
    mod.add_argument("--host", default="127.0.0.1")
    mod.add_argument("--port", type=int, default=15020)
    mod.add_argument("--address", type=int, default=0)
    mod.add_argument("--count", type=int, default=3)
    mod.add_argument("--unit-id", type=int, default=1)
    mod.add_argument("--kind", choices=["holding", "input"], default="holding")
    mod.add_argument("--enable-network", action="store_true")
    mod.add_argument("--allow-remote", action="store_true")
    mod.add_argument("--i-have-authorization", action="store_true")
    for cmd in (snap, diff, bench, mod):
        cmd.add_argument("--output")
    args = parser.parse_args()
    try:
        if args.command == "snapshot":
            result = snapshot(load_profile(args.profile), load_registers(args.registers), args.captured_at)
        elif args.command == "drift":
            result = drift(load_profile(args.old), load_profile(args.new))
        elif args.command == "benchmark":
            result = benchmark(load_profile(args.profile), load_registers(args.registers), args.repeats)
        else:
            values = read_registers(args.host, args.port, args.address, args.count, unit_id=args.unit_id, kind=args.kind, enable_network=args.enable_network, allow_remote=args.allow_remote, authorized=args.i_have_authorization)
            result = {"project": "trinity_industrial", "operation": "read_only_modbus", "host": args.host, "address": args.address, "kind": args.kind, "values": values, "warning": "Modbus TCP is unencrypted. Read-only does not make a production network inherently safe."}
        emit(result, args.output)
        return 0
    except (ValueError, OSError, PermissionError, ModbusError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
