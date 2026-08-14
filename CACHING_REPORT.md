# Caching audit and implementation report

## Scope and evidence

This audit covers the Nexova backoffice (`uis/backoffice`) and the FastAPI
operations service (`services/api`). The frontend decisions target code-splitting
and repeated data joins. The backend decisions target repeated full-table scans
of shared company data. Authentication, user/profile payloads, and item detail
responses remain uncached so private or rapidly changing state is never placed in
a shared cache key.

## Frontend decisions

### Lazy-loaded routes/components

1. `Dashboard` is loaded with `next/dynamic` from the backoffice `/` route. It
   fetches four report datasets and renders the KPI and ranking sections. Users
   visiting incidents, suppliers, or processes do not need that client chunk, so
   keeping it behind its route boundary reduces JavaScript evaluation outside the
   dashboard.
2. `PipelineBoard` is loaded with `next/dynamic` from `/processes`. It contains
   interactive mutation controls, four stage columns, and three joined datasets.
   Those controls are irrelevant to every other backoffice route, which makes a
   separate chunk a deliberate route-level boundary.

Both imports include a lightweight loading state so the route gives immediate
feedback while its client chunk is fetched.

### Memoized computation

`DashboardContent` enriches every ranking row with candidate email and salary.
The previous implementation called `Array.find` for every row, an O(ranking ×
candidates) join on every render. A `useMemo` now builds a candidate `Map` and
performs an O(candidates + ranking) indexed join. Its dependency array is exactly
`[candidates, ranking]`, so opening the candidate form or other unrelated state
changes no longer rebuilds the rows.

## Backend endpoint audit

The estimates assume a 120-person company where the backoffice polls or refreshes
summary screens more often than users edit source records.

| Endpoint | Cost | Expected frequency | Data change rate | Decision |
| --- | --- | --- | --- | --- |
| `POST /auth/login`, `POST /auth/token` | bcrypt + JWT | Medium | Per request | Never cache credentials/tokens. |
| `GET /auth/me` | JWT + user lookup | Medium | User/session-specific | Never shared-cache. |
| `POST /users` | bcrypt + writes | Low | Every call | Mutation; no cache. |
| `GET /users`, `GET /users/{id}` | TinyDB scan/lookup | Low | Occasional | Private authorization-dependent data; no shared cache. |
| `PUT /users/{id}`, `DELETE /users/{id}` | TinyDB writes | Low | Every call | Mutations; no cache. |
| `GET /profiles/me`, `PUT /profiles/me` | TinyDB lookup/write | Low | User-specific | Never shared-cache. |
| `POST /suppliers` | TinyDB write | Low | Every call | Invalidates supplier-list cache. |
| `GET /suppliers` | Full scan + two optional filters + model validation | High: dashboard/filter refreshes | Low: contract/admin edits | Cache per `(country, category)` for 30 s. |
| `GET /suppliers/{id}` | Single lookup | Low | Occasional | Cheap and may be needed immediately after edit; no cache. |
| `PATCH /suppliers/{id}/rate` | Lookup + write | Low | Every call | Invalidates all supplier-list keys. |
| `PATCH /suppliers/{id}/status` | Lookup + write | Low | Every call | Invalidates all supplier-list keys. |
| `DELETE /suppliers/{id}` | Lookup + write | Rare | Every call | Invalidates all supplier-list keys. |
| `POST /api/incidents` | TinyDB writes | Medium | Every call | Invalidates incident summary. |
| `GET /api/incidents` | Full scan + optional filters | High | Frequent | Not cached: operations need newly opened incidents immediately. |
| `GET /api/incidents/summary` | Full scan + four complete aggregations | High: dashboard refreshes | Medium | Cache one company-wide aggregate for 15 s. |
| `GET /api/incidents/{id}` | Single lookup | Medium | Can change during handling | No cache to preserve operator freshness. |
| `PATCH /api/incidents/{id}/status` | Lookup + write | Medium | Every call | Invalidates incident summary. |
| `GET /health` | One table length | Monitoring cadence | Supplier count changes rarely | Too cheap to justify caching. |

## Backend decisions

`GET /suppliers` uses a thread-safe in-process `TTLCache` with a 30-second TTL.
Each key contains only the two directory filters; authorization is still checked
before the route executes, and the company directory response does not vary by
identity. Creating, changing the rate/status of, or deleting a supplier clears
all filter keys so the next read is fresh.

`GET /api/incidents/summary` uses the same primitive with a 15-second TTL and a
single `company-summary` key. The expensive part is scanning every incident and
building complete counts across status, category, origin, and branch. Creating an
incident or changing its status clears the aggregate immediately. The cached
value contains no reporter email, token, profile, or other session-specific data.

The cache is intentionally in-process: Nexova currently deploys one FastAPI
process over TinyDB. A move to multiple workers would require Redis (or another
shared backend) plus cross-process invalidation.

## Tradeoffs acknowledged

The supplier directory tolerates up to 30 seconds of staleness for changes made
outside the API (for example, a maintenance script). Contracts and rates change
far less often than the list is read, so that window is preferable to repeated
scan/filter/model conversion. Normal API writes do not incur the window because
they invalidate immediately.

The incident summary uses a shorter 15-second TTL because supervisors care about
operational movement. The detailed incident list is deliberately not cached:
showing a newly opened or reassigned incident late would save less computation but
could delay action against the 24-hour SLA.

## What was not cached and why

All authentication, user, and profile endpoints were rejected because their
responses are private or authorization-dependent. `GET /api/incidents/{id}` was
also rejected because operators need current status during active handling.
`GET /health` was measured conceptually as a constant-time table length and is
cheaper than the cache bookkeeping. On the frontend, trivial scalar formatting
such as percentages and labels was not memoized because that would add dependency
complexity without meaningful saved work.

## Verification

- Backend tests prove repeated reads hit the cached value, related writes
  invalidate it, and expiry recomputes after the TTL.
- The complete FastAPI suite covers contracts, authentication, serialization,
  errors, concurrency, and the new cache behavior.
- The backoffice production build verifies both dynamic route boundaries and the
  memoized TypeScript code under strict mode.
