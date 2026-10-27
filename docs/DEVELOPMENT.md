# Developer setup and repository operations

## Tools

- Python 3.10+ on Windows, Linux or macOS
- Git
- No dependency installation is needed for standard-library tests and benchmarks
- Optional: `python -m pip install -e '.[compute-numpy]'` for a third CPU backend

## Clone and test

```bash
git clone https://github.com/shadowhunter-92/TRINITY.git
cd TRINITY
python scripts/verify_all.py
python scripts/demo_end_to_end.py
python scripts/demo_modbus_loopback.py
```

Alternatively, after `pip install -e .`:

```bash
trinity-compute benchmark --repeats 15
trinity-industrial snapshot --profile fixtures/industrial/profile_v1.json --registers fixtures/industrial/registers.json
trinity-data benchmark --rows 3000 --repeats 7
```

Commands from the repository root work without pip installation. CI runs the default
verification on Python 3.10, 3.11, 3.12 and 3.13. Local results are written to the
ignored `results/` directory; selected historical examples are in `benchmarks/baselines/`.

## Branching and pull requests

Create branches such as `feat/compute-onnx`, `feat/industrial-opcua-sim`, or
`feat/data-arrow-benchmark`. Make each PR independently reviewable. Include tests,
reproduction commands, performance caveats and explicit treatment of security constraints.

## Keeping benchmarks useful

Always record model/dataset, size, runtime/dependency versions, host characteristics,
warmups, repetition count and correctness. Never compare different operation semantics
as though they are directly interchangeable. The initial baselines are workstation
artifacts, not deployment benchmarks.

## Package layout

`trinitylab/compute`, `trinitylab/industrial`, and `trinitylab/data` have independent
CLIs and tests. Keep `scripts/demo_end_to_end.py` as a synthetic integration contract.
See `docs/ARCHITECTURE.md` for module-level details and `AGENTS.md` for Codex rules.
