## Summary

Completes **Milestone — Pipeline Enhancement: Subflows and Tests (Part 3 of 3)**
for Nexova's weekly office/programme performance report.

- splits the existing Prefect orchestration into independently runnable extract,
  transform and load subflows with explicit inputs/outputs;
- runs the optional evaluation snapshot as a fourth subflow with
  `return_state=True`, so its failure remains non-critical;
- adds four isolated transformation-task tests, including invalid input,
  deduplication and a hand-calculated material-cost KPI;
- adds the authenticated `/reporting` dashboard for Laura Mendoza and Elena
  Vargas, backed by the existing reporting endpoint and showing the exact four
  required KPIs for a visible ISO week;
- keeps EUR and USD separate and adds office/programme filtering;
- updates the backoffice to patched Next.js 16, React 19 and PostCSS versions.

The append-only `telemetry_events` source and
`services/telemetry/analysis.py` remain unchanged.

## Validation

- `uv run --project services/api --group dev pytest -q services/api/tests tests/pipelines`
  — **61 passed**;
- real Prefect CLI backfill for `2026-08-03` — **Completed**, 7 extracted,
  2 loaded, all four subflows completed;
- `npm run build` in `uis/backoffice` — production build passes and generates
  `/reporting` plus all existing routes;
- `npm audit --audit-level=high` — **0 vulnerabilities**;
- `git diff --check` — clean.

## Delivery note

This PR targets `project/11-telemetry`, the branch containing the submitted
Part 2 pipeline, so the course reviewer receives the intended incremental
Part 3 diff.
