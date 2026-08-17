-- Append-only storage contract for Nexova telemetry.
create table if not exists public.telemetry_events (
    id uuid primary key default gen_random_uuid(),
    timestamp timestamptz not null,
    service text not null,
    event_type text not null,
    level text not null default 'info' check (level in ('info', 'warn', 'error')),
    value numeric null,
    message text null,
    tags jsonb not null default '{}'::jsonb
);

create index if not exists telemetry_events_timestamp_idx
    on public.telemetry_events (timestamp);
create index if not exists telemetry_events_event_type_idx
    on public.telemetry_events (event_type);
create index if not exists telemetry_events_tags_gin_idx
    on public.telemetry_events using gin (tags);

alter table public.telemetry_events enable row level security;

-- Only the backend service role writes or reads raw telemetry. There are no
-- UPDATE/DELETE policies or application handlers: recorded facts are immutable.
revoke all on table public.telemetry_events from anon, authenticated;
grant select, insert on table public.telemetry_events to service_role;

comment on table public.telemetry_events is
    'Append-only Nexova telemetry; valid batches are inserted atomically.';
