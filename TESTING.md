# Nexova authentication test plan

This milestone adds business-focused unit tests to the existing authentication API. The HTTP acceptance tests remain as regression coverage, while the new modules call authentication and route logic directly so failures point to business rules instead of framework serialisation.

## Test plan defined before implementation

| Endpoint / unit | Happy path | Edge cases | Failure modes |
| --- | --- | --- | --- |
| `POST /users` | Safe user plus separate profile; password is hashed | Normalised email and empty optional profile fields | Duplicate/malformed email, short password, bcrypt's 72-byte limit |
| `POST /auth/login` | Signed JWT with the configured lifetime | Email case and surrounding whitespace | Wrong password, unknown account, inactive account, empty password |
| `POST /auth/token` | OAuth2 form delegates to the same login rules | Explicitly expired token; configurable expiry | Malformed JWT, missing subject/user, inactive user, invalid environment configuration |
| `GET /auth/me` | Safe user projection with linked profile | Empty optional profile data | Missing linked profile |

The existing `test_auth.py` also keeps end-to-end coverage for ownership, admin access, all protected supplier routes, profile updates, user deletion, malformed bearer tokens, and the standard OAuth2 adapter.

## AI-assisted workflow

An AI coding review identified token expiration, UTF-8 byte length at bcrypt's 72-byte boundary, disabled accounts, and a missing profile record as cases that can be missed by happy-path testing. Those cases are included explicitly. Every generated test was reviewed against the implementation and rewritten to assert the public business contract.

## How to run

From `services/api`:

```bash
uv sync
uv run pytest
uv run pytest --cov
```

The `--cov` command is scoped in `pyproject.toml` to `auth_service`, `security`, `routes.auth`, and `routes.users` and measures branch coverage.

For the existing TypeScript error utilities:

```bash
cd services/talent-api
npm test
npm run typecheck
```

There is no authentication utility logic in TypeScript in this milestone, so the rubric's conditional authentication-Jest requirement does not apply. The existing TypeScript service suite covers the shared public-error contract.

## Extra backlog suites

- `services/api/tests/test_suppliers.py` covers supplier creation, validation, filters, updates, deletion, persistence, seed idempotency, and safe failures.
- `services/api/tests/test_incidents.py` covers incident creation, validation, filters, lifecycle rules, authentication, concurrent reads, safe error handling, and CSV ingestion.
- `uis/backoffice/src/lib/error-utils.test.ts` tests three frontend utility functions with Jest: the public Talent API error parser, the safe HTTP status fallback, and the FastAPI validation parser. Each has a normal case and an invalid/fallback case.

Run the extra frontend suite from `uis/backoffice`:

```bash
npm test
```

## Verified results

Validated locally on 14 August 2026:

- Full FastAPI suite: **67 passed**.
- Authentication coverage with branch measurement: **87% total** (`routes.auth` reached 100% and is omitted from the terminal table by `skip_covered`).
- Extra supplier and incident endpoint suites: **27 passed**, **98% combined branch coverage** (`routes.suppliers` reached 100%; `routes.incidents` reached 96%).
- Backoffice Jest suite: **6 passed** across three utility functions, with normal and fallback/failure cases for each.
- Existing TypeScript service error suite: **3 passed**.
- Backoffice production build: compiled, type-checked, and generated all seven static pages successfully.
