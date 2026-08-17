# Telemetry storage — implementation record

Date: 14/08/2026

## Storage contract

`infra/supabase/20260814_create_telemetry_events.sql` defines an append-only
`public.telemetry_events` table with exactly eight columns: `id`, `timestamp`,
`service`, `event_type`, `level`, `value`, `message`, and `tags`. It creates
B-tree indexes for time and event type plus a GIN index for JSON tags. RLS is
enabled, only the server-side `service_role` receives `SELECT`/`INSERT`, and no
application route or policy permits `UPDATE` or `DELETE`.

The backend maps the unchanged `TelemetryEvent` 1.0.0 envelope to that row
contract. `properties` is already filtered by the producer's per-event
allowlist and is stored in `tags`; useful numeric measures are also projected
to `value`. The Supabase URL and service-role key are read only from backend
environment variables and never exposed as `NEXT_PUBLIC_*`.

## Ingestion behaviour

- `POST /telemetry/events` accepts the frontend's existing `{ "events": [] }`
  batch shape.
- Each item is validated independently with `TelemetryEvent.model_validate`.
  Invalid items are counted and rejected without discarding valid peers.
- All valid rows are sent to Supabase in one REST request, preserving one bulk
  insert per frontend batch.
- The response reports `received`, `stored`, and `rejected`; a storage outage is
  a sanitized 503 and does not pretend the rows were stored.
- The frontend capture code and typed inventory boundaries are unchanged from
  commit `322b4f8`.

## Verification evidence

- Backend suite: **47 passed**.
- Mixed batch test: 3 received, 1 stored, 2 rejected, and one storage call.
- Adapter test: the complete row list is serialized into exactly one POST to
  `/rest/v1/telemetry_events` with the server-only credentials.
- Real local HTTP smoke test: Uvicorn received a curl batch with one valid and
  one invalid event and returned
  `{ "received": 2, "stored": 1, "rejected": 1 }`; a temporary Supabase REST
  stand-in recorded exactly one POST containing only the valid eight-column
  row. Both temporary processes were stopped after the check.
- Row-contract test: the emitted dictionary contains exactly the eight SQL
  columns and retains the allowlisted context dimensions in `tags`.
- `git diff 322b4f8 -- uis/backoffice` is empty, proving storage work did not
  change frontend capture behaviour.

## Cloud verification still requiring the student account

The available browser session redirects `supabase.com/dashboard/projects` to
the Supabase sign-in page. Creating/selecting the project, applying the SQL,
providing its service-role key, generating real inventory events and querying
the resulting cloud rows therefore remain external account actions. They must
not be claimed as completed until an authenticated Supabase project is
available. No credential or account terms were accepted automatically.

Publishing a branch/PR and confirming the personal authorship declaration also
remain explicit student actions.
