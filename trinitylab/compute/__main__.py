"""Run: python -m trinitylab.compute benchmark --help"""
import argparse
import sys

from trinitylab.compute.core import (BatchedEngine, NumpyEngine, ReferenceEngine,
                                     benchmark, make_inputs, make_model)
from trinitylab.util import emit


def main() -> int:
    parser = argparse.ArgumentParser(description="TRINITY Compute: synthetic neural-network verification benchmark")
    parser.add_argument("command", choices=["benchmark"])
    parser.add_argument("--input-dim", type=int, default=32)
    parser.add_argument("--hidden-dim", type=int, default=48)
    parser.add_argument("--output-dim", type=int, default=8)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--repeats", type=int, default=15)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--numpy", action="store_true", help="Include optional NumPy backend")
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args()
    try:
        m = make_model(args.input_dim, args.hidden_dim, args.output_dim, args.seed)
        engines = [ReferenceEngine(m), BatchedEngine(m)]
        if args.numpy:
            engines.append(NumpyEngine(m))
        report = benchmark(engines, make_inputs(args.batch, args.input_dim, args.seed + 1), args.warmup, args.repeats)
        report["model"] = {"input_dim": args.input_dim, "hidden_dim": args.hidden_dim, "output_dim": args.output_dim, "seed": args.seed}
        emit(report, args.output)
        return 0 if all(e["correctness"]["passed"] for e in report["engines"]) else 2
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
