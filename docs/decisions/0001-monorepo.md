# ADR 0001: Keep three laboratory MVPs in a monorepo

- Status: Accepted for v0.1.x
- Date: 2026-10-27

## Context

Compute, Industrial and Data are distinct future businesses but currently share a
Python toolchain, test conventions, safety guardrails and one cross-project experiment.

## Decision

Keep the three workstreams under `trinitylab/` in one monorepo and use separate modules,
unit tests and independently runnable CLI entry points. Keep the combined integration
demo strictly synthetic. Prefer compatibility with Python 3.10+ and zero mandatory
runtime dependencies for the core.

## Trade-offs

Benefits: atomic integration tests, one security policy, shared CI and easier Codex context.
Risks: growing coupling, longer CI and broad accidental changes.

Reconsider separate repositories if teams, release cycles, distribution channels,
license obligations or security boundaries actually diverge.
