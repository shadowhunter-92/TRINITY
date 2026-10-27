#!/usr/bin/env python3
"""Offline reproducible gate: tests and then the benchmark suite."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    for args in ([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], [sys.executable, "scripts/bench_all.py"]):
        print("RUN", " ".join(args), flush=True)
        code = subprocess.run(args, cwd=ROOT, check=False).returncode
        if code:
            return code
    print("Verification passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
