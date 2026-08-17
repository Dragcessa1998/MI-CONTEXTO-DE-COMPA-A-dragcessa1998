# AUTH-02 — Authentication flows and protected frontend views

This delivery connects the JWT contract from AUTH-01 to both internal Next.js
applications in the monorepo.

## Protected views

- `uis/backoffice`: `/`, `/processes`, `/suppliers`, and `/account/profile`.
- `uis/talent-pipeline-tracker`: `/`, `/candidates/new`,
  `/candidates/[id]`, `/candidates/[id]/edit`, and `/account/profile`.

Each internal application has public `/login` and `/register` routes. A client
shell verifies the saved token with `GET /auth/me` before rendering protected
content. An absent, invalid, or expired token redirects to `/login`.

## Token lifecycle

1. Registration calls `POST /users`, then `POST /auth/login` with the same
   credentials.
2. Login stores `access_token` as `nexova_access_token` in `localStorage`.
3. Protected API clients attach `Authorization: Bearer <token>`.
4. Any protected `401` clears storage and emits a shared session-expired event;
   the client shell then redirects to `/login`.
5. Logout clears the token and redirects immediately.

The `/account/profile` view displays the email returned by `GET /auth/me` and
updates `name`, `phone`, and `address` with `PUT /profiles/me`.

## Public website

`uis/website` is intentionally unchanged. It does not import the auth provider,
check `localStorage`, or redirect visitors.

## Verification

- Production builds pass for both internal Next.js applications.
- The AUTH-01 FastAPI suite passes (26 tests).
- A local browser walkthrough verified route redirect, registration + automatic
  login, profile retrieval/update, logout, and invalid-JWT cleanup after key
  rotation.
