# Frontend telemetry capture — implementation record

Date: 14/08/2026

Schema: `1.0.0`

## Delivery path

- `POST /telemetry/events` accepts `{ "events": [...] }`, validates every item
  with the reusable Pydantic `TelemetryEvent` envelope, logs the count and
  `event_type` values, and returns `{ "received": N }`.
- The backend declares `TELEMETRY_ENDPOINT`; the browser reads only
  `NEXT_PUBLIC_TELEMETRY_ENDPOINT`.
- `uis/backoffice/src/services/telemetry.ts` owns the in-memory queue, the
  10-second/20-event batch trigger, `visibilitychange` + `sendBeacon`, and up to
  three exponential-backoff retries. No component sends telemetry directly.
- The service generates `eventId`, `timestamp`, `sessionId`, `userId`,
  `schemaVersion`, and `requestId`. It filters properties through the Phase 1
  allowlist before enqueueing the event.

## Capture map

| Classification | Events | Capture point |
| --- | --- | --- |
| Mandatory | `inbound_order_created`, `outbound_order_created`, `stock_threshold_triggered`, `direct_stock_edit_rejected`, `kit_cost_variance_detected` | Typed post-commit/rejection boundary functions in `inventoryTelemetry.ts`; their signatures expose exactly the Phase 1 allowlists. |
| Navigation | `section_viewed` | Global `TelemetryProvider`, debounced for five seconds and normalized to a section enum. |
| Errors | `frontend_error_captured` | Global `error`/`unhandledrejection` listeners plus the App Router error boundary. Only a stable fingerprint is sent—never message or stack. |
| Performance | `page_load_recorded` | Next.js `useReportWebVitals`; TTFB, LCP, CLS and optional INP are correlated with the normalized section. |
| Performance | `api_latency_recorded` | Shared incident API client; URL IDs and query strings are removed before capture. |
| Authentication | `login_succeeded`, `login_failed`, `session_expired` | Authentication component/session boundary. Reasons are safe enums; email, password and JWT are never properties. |

The inventory application itself is not present in this monorepo branch. Its
five required capture boundaries are therefore centralized and typed so the
future inventory command handlers call them after a committed order, threshold
evaluation, or rejected direct edit; they must not be called optimistically by
form components.

## Verification evidence

- FastAPI: `43 passed` with collector success and invalid-envelope coverage.
- Backoffice: production `next build` compiled, type-checked, and generated all
  six routes successfully.
- Browser integration: Chrome loaded `http://127.0.0.1:3131/incidents`; after
  the navigation debounce/batch interval, Uvicorn recorded
  `POST /telemetry/events HTTP/1.1` with `200 OK`. Pydantic acceptance proves the
  emitted browser payload matched the complete envelope.
- Static checks: all five mandatory event types call the single `track()` entry
  point; telemetry has no direct fetch outside `TelemetryService`; the JSON
  schema parses with `jq`; `git diff --check` is clean.

## Submission note

The implementation and evidence are ready for a PR titled
`feat: telemetry event capture`. Publishing the branch/PR requires explicit
authorization, and the platform authorship declaration must be confirmed by the
student personally.
