import argparse
import sys

from trinitylab.data.core import benchmark
from trinitylab.data.schema import compare_schemas, load_schema
from trinitylab.util import emit


def main() -> int:
    parser = argparse.ArgumentParser(description="TRINITY Data: measurable data conversion and schema compatibility")
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("benchmark")
    b.add_argument("--rows", type=int, default=3000)
    b.add_argument("--repeats", type=int, default=7)
    b.add_argument("--seed", type=int, default=19)
    d = sub.add_parser("schema-diff")
    d.add_argument("--old", required=True)
    d.add_argument("--new", required=True)
    for p in (b, d):
        p.add_argument("--output")
    args = parser.parse_args()
    try:
        if args.command == "benchmark":
            result = benchmark(args.rows, args.repeats, args.seed)
        else:
            result = compare_schemas(load_schema(args.old), load_schema(args.new))
        emit(result, args.output)
        return 0 if args.command != "schema-diff" or result["compatible"] else 1
    except (ValueError, OSError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
