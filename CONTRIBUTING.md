# Contributing to TRINITY

Thank you for helping improve research infrastructure. The project consists of independent
laboratory prototypes, not certified production systems.

## Get started

1. Read `README.md`, `AGENTS.md`, `docs/ARCHITECTURE.md`, and `docs/SECURITY.md`.
2. Use Python 3.10 or newer; no mandatory third-party runtime dependencies.
3. Create a feature branch and keep changes scoped to one workstream where possible.
4. Add tests and state the limits of every new benchmark and protocol interface.
5. Run `python scripts/verify_all.py` and the two local integration demonstrations.
6. Open a pull request using the PR template. Describe safety implications and backwards compatibility.

## Code standards

- Standard-library-first, clear type hints, explicit validation and deterministic fixtures.
- Keep default operation offline. Network tests must use loopback, ephemeral local services,
  mock fixtures and prompt cleanup. Don't run against real industrial equipment.
- Security issues should follow `SECURITY.md`, not a public bug report containing exploitation details.
- Avoid unsupported speedup, financial or market-size claims. Share reproducible data and methodology.
- Do not introduce dependencies or adjust licensing without a rationale and license review.

## Changes most welcome

- More negative-case tests, reproducibility checks, documentation and portability fixes.
- Opt-in real-runtime adapters with verified output parity.
- Standards-based simulated OPC UA experiments and robust data-quality tests.
- Opt-in Arrow baselines and well-scoped equivalent-workload benchmarks.

Maintainers may revise architectural boundaries as research evidence develops.
