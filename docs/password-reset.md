# AUTH-03 — Password recovery and change

## Delivery

The platform now supports all three password operations:

- `POST /auth/forgot-password` always returns the same `200` response. For an
  active account it creates a signed reset JWT and queues a Resend email.
- `POST /auth/reset-password` validates signature, purpose, expiry, persisted
  SHA-256 hash, ownership, and one-time state before updating the bcrypt hash.
- `POST /auth/change-password` requires a valid access token and verifies the
  current password before changing it.

Raw reset tokens are never stored. TinyDB keeps only a hash, token identifier,
expiry, and use timestamp. A successful reset or authenticated password change
invalidates every outstanding reset token for that user.

Both internal Next.js applications expose `/forgot-password`,
`/reset-password?token=...`, and `/account/change-password`. Their login pages
link to recovery. The public website remains unchanged.

## Resend configuration

Set these only in `services/api/.env` (which is ignored by Git):

```dotenv
RESEND_API_KEY=re_your_key
PASSWORD_RESET_FROM_EMAIL=Nexova <onboarding@resend.dev>
PASSWORD_RESET_FRONTEND_URL=http://localhost:3000/reset-password
PASSWORD_RESET_EXPIRE_MINUTES=30
```

No Resend key is present in the repository. The adapter, authorization header,
payload, reset URL, and mobile-readable HTML are covered by an isolated test;
an actual inbox delivery requires a personal Resend key.

## Verification

- 31 FastAPI acceptance tests pass, including unknown-email parity, expiry,
  replay rejection, password replacement, wrong-current-password rejection,
  and Resend request construction.
- Production builds pass for both internal Next.js applications.
- Browser walkthrough passes for neutral confirmation, invalid-token recovery,
  matching-password validation, authenticated change, successful reset,
  redirect to `/login`, and success feedback.
