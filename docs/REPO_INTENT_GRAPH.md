# REPO_INTENT_GRAPH
_Last updated: 2025-08-17_

Describes the code intelligence used by agents to plan and verify changes.

## Goals

- Provide a **deterministic map** of modules, symbols, and their relationships.
- Enable “who owns what” and “which tests exercise this code” queries.
- Support safe change planning (risk, reversibility, blast radius).

## Components

1) **Indexer**
   - Parses Python/TypeScript ASTs; extracts:
     - Modules, classes, functions, endpoints (FastAPI paths).
     - Imports, call sites, test markers.
   - Normalizes paths to repo‑relative form.

2) **Stable Symbol IDs**
   - Format: `pkg.module:Class#method@L<start>-<sha1(sig)>`
   - `sig` = normalized signature (args names/types when available).
   - SHA1 of `<fqname>(<sig>)` ensures stability across whitespace changes.

3) **Edges**
   - `imports`: `module -> imported_module`
   - `calls`: `symbol -> symbol`
   - `tests`: `test_symbol -> target_symbol`
   - `routes`: `endpoint -> handler_symbol`

4) **Ownership**
   - Derived from: path prefix rules (like CODEOWNERS), plus commit history when available.
   - Ownership file: `repo_ownership.json` (optional), falling back to heuristics:
     - `apps/orchestrator/orchestrator/api/**` → “api”
     - `apps/orchestrator/orchestrator/providers/**` → “providers”
     - `apps/orchestrator/tests/**` → “tests”
     - Etc.

5) **Hotspots**
   - Frequency x churn: count recent touches; combine with low coverage to flag risk.
   - Reported via `GET /repo/hotspots`.

## API Shapes

- `GET /repo/map` →  
{
"modules": [...], // sorted by name
"symbols": [...], // sorted by id
"edges": { "imports": [...], "calls": [...], "tests": [...], "routes": [...] }
}- `GET /repo/ownership` → `{ "rules": [...], "owners": {...} }`
- `GET /repo/hotspots` → `[ { "path": "...", "churn": 3, "coverage": 0.62 }, ... ]`

All arrays sorted; newline‑terminated; seeds recorded when sampling.

## Determinism

- Sort modules, symbols, edges lexicographically.
- Use normalized whitespace; ignore comments when hashing.
- Include version/seed in report headers for reproducibility.

## Usage by Agents

- **Phase 50** Test synthesis: map untested symbols → generate tests.
- **Phase 51** Speculative exec: compute blast radius from edges → choose sandbox suite.
- **Phase 52** Review: show impacted owners/tests; include in ADR.
