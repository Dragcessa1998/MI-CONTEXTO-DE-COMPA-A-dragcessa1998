# Telemetry technical report — implementation record

Date: 14/08/2026

## Operational questions

The reusable Pandas pipeline lives in `services/telemetry/analysis.py`. Every
function receives the same inclusive-start/exclusive-end UTC window, asks the
reader for only the required rows, converts types before grouping and returns
JSON-serialisable records without metric-calculation loops.

| Metric | Operational question | Dimension · aggregation |
| --- | --- | --- |
| `events_per_day` | Did instrumentation volume drop or spike? | UTC day · count of event IDs |
| `error_rate_by_type` | Which signal types are failing and when? | UTC day + event type · error sum / count |
| `latency_by_route` | Which backend routes are slow? | route template · mean duration + sample count |
| `auth_failure_rate` | Are authentication failures increasing? | UTC day · failed logins / all login attempts |

`SupabaseTelemetryReader` expresses timestamp bounds and optional event-type
filters in the PostgREST query, which pushes the equivalent `WHERE` work to
Postgres. Tag dimensions are refined in Pandas. Temporal functions call
`pd.to_datetime(..., utc=True)` before `groupby`.

## Endpoint and cache

`GET /telemetry/report` accepts optional ISO-8601 `start_date` and `end_date`.
When omitted, it resolves one seven-day UTC window and passes those exact
bounds to every metric. Its response is:

```json
{
  "period": {
    "from": "2026-08-07T01:36:08.837445Z",
    "to": "2026-08-14T01:36:08.837445Z"
  },
  "metrics": {
    "events_per_day": [{ "date": "2026-08-10", "event_count": 3 }],
    "error_rate_by_type": [],
    "latency_by_route": [{ "route_template": "/api/incidents", "mean_latency_ms": 100.0, "sample_count": 2 }],
    "auth_failure_rate": [{ "date": "2026-08-11", "login_attempts": 2, "login_failures": 1, "failure_rate": 0.5 }]
  }
}
```

The cache key represents the requested query window (including the default
window), and each entry expires after 60 seconds. A repeated request inside the
TTL returns the identical period and payload without calling any metric again.

## Technical dashboard

`uis/backoffice/src/app/telemetry/page.tsx` presents the same operational data
as four accessible tables. It displays the exact UTC period, empty/loading/error
states and a refresh action. It deliberately excludes business metrics. The
implementation uses existing Next.js/Tailwind dependencies only.

## Verification evidence

- Backend suite: **51 passed**.
- Production frontend build: compiled, type-checked and generated **7 routes**,
  including `/telemetry`.
- Local HTTP integration against a temporary Supabase REST stand-in returned
  six events through four query-scoped reads. Two identical report requests
  produced the same period and only the first request executed those reads.
- Chrome loaded `/telemetry` through the real Next.js proxy and rendered event
  counts, per-type error rates, 100 ms mean route latency and a 50% login
  failure rate. Refresh reused the cached payload.
- All temporary FastAPI, Next.js and stand-in processes were stopped.

## External verification still pending

The browser session is not authenticated in Supabase. The required screenshot
and sample with at least 20 **real cloud rows** cannot be produced until the
student signs in, applies the storage migration and provides the server-only
credentials outside the repository. Local fixtures are verification evidence,
not a claim that cloud data exists. Publishing the PR and confirming authorship
also remain explicit student actions.
