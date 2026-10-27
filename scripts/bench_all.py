#!/usr/bin/env python3
"""Single command for deterministic workload definitions and report collection.

Timings are necessarily host-dependent; compare only same-host controlled runs.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "lab_benchmarks.json"
COMMANDS = {
    "compute": ["-m", "trinitylab.compute", "benchmark", "--input-dim", "24", "--hidden-dim", "32", "--output-dim", "8", "--batch", "6", "--seed", "7", "--repeats", "12"],
    "industrial": ["-m", "trinitylab.industrial", "benchmark", "--profile", "fixtures/industrial/profile_v1.json", "--registers", "fixtures/industrial/registers.json", "--repeats", "250"],
    "data": ["-m", "trinitylab.data", "benchmark", "--rows", "2000", "--repeats", "5", "--seed", "19"],
}


def main() -> int:
    env = dict(os.environ)
    env.update({"PYTHONHASHSEED": "0", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
    collected = {}
    for key, arguments in COMMANDS.items():
        cmd = [sys.executable] + arguments
        done = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
        if done.returncode:
            print(f"{key} failed: {done.stderr}", file=sys.stderr)
            return done.returncode
        collected[key] = json.loads(done.stdout)
        print(f"PASS {key}")
    payload = {"suite": "trinity_lab_0.1.0", "results": collected, "notes": ["Simulated/workstation results; not representative of production hardware", "No measured dollar savings or real industrial telemetry", "Repeat on the target hardware with reference datasets"]}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
