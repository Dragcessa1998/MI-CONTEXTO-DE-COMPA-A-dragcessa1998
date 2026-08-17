-- Durable business-reporting objects for the Nexova weekly pipeline.
create schema if not exists reporting;

create table if not exists reporting.weekly_office_program_performance (
    id uuid primary key default gen_random_uuid(),
    office text not null,
    programme_id text not null,
    week_start date not null,
    total_material_cost numeric not null default 0 check (total_material_cost >= 0),
    kits_delivered_count integer not null default 0 check (kits_delivered_count >= 0),
    shortage_events_count integer not null default 0 check (shortage_events_count >= 0),
    cost_variance_events_count integer not null default 0 check (cost_variance_events_count >= 0),
    currency text not null,
    computed_at timestamptz not null default now(),
    unique (office, programme_id, week_start),
    check (
        (office = 'valencia' and currency = 'EUR') or
        (office = 'miami' and currency = 'USD')
    )
);

create table if not exists reporting.pipeline_runs (
    run_id uuid primary key,
    pipeline_name text not null,
    trigger_source text not null check (trigger_source in ('schedule', 'manual', 'backfill')),
    requested_by text null,
    week_start date not null,
    window_start timestamptz not null,
    window_end timestamptz not null,
    started_at timestamptz not null,
    finished_at timestamptz null,
    status text not null check (status in ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')),
    phase text not null,
    source_cursor jsonb null,
    records_extracted integer not null default 0,
    records_deduplicated integer not null default 0,
    records_rejected integer not null default 0,
    records_loaded integer not null default 0,
    source_checksum text null,
    output_checksum text null,
    error_code text null,
    invalidates_run_id uuid null references reporting.pipeline_runs(run_id)
);

create unique index if not exists pipeline_runs_one_active_week_idx
    on reporting.pipeline_runs (pipeline_name, week_start)
    where status in ('PENDING', 'RUNNING');

create table if not exists reporting.pipeline_run_inputs (
    run_id uuid not null references reporting.pipeline_runs(run_id),
    event_id uuid not null,
    request_id text null,
    event_timestamp timestamptz not null,
    primary key (run_id, event_id)
);

create or replace function reporting.publish_weekly_office_program_performance(
    p_week_start date,
    p_rows jsonb
) returns integer
language plpgsql
security definer
set search_path = reporting, public
as $$
begin
    if p_rows is null or jsonb_typeof(p_rows) <> 'array' then
        raise exception 'p_rows must be a JSON array';
    end if;

    perform pg_advisory_xact_lock(
        hashtextextended('weekly_office_program_performance:' || p_week_start::text, 0)
    );

    delete from reporting.weekly_office_program_performance target
    where target.week_start = p_week_start
      and not exists (
          select 1
          from jsonb_to_recordset(p_rows) as incoming(
              office text,
              programme_id text,
              week_start date,
              total_material_cost numeric,
              kits_delivered_count integer,
              shortage_events_count integer,
              cost_variance_events_count integer,
              currency text
          )
          where incoming.office = target.office
            and incoming.programme_id = target.programme_id
            and incoming.week_start = target.week_start
      );

    insert into reporting.weekly_office_program_performance (
        office,
        programme_id,
        week_start,
        total_material_cost,
        kits_delivered_count,
        shortage_events_count,
        cost_variance_events_count,
        currency,
        computed_at
    )
    select
        incoming.office,
        incoming.programme_id,
        incoming.week_start,
        incoming.total_material_cost,
        incoming.kits_delivered_count,
        incoming.shortage_events_count,
        incoming.cost_variance_events_count,
        incoming.currency,
        now()
    from jsonb_to_recordset(p_rows) as incoming(
        office text,
        programme_id text,
        week_start date,
        total_material_cost numeric,
        kits_delivered_count integer,
        shortage_events_count integer,
        cost_variance_events_count integer,
        currency text
    )
    where incoming.week_start = p_week_start
    on conflict (office, programme_id, week_start) do update set
        total_material_cost = excluded.total_material_cost,
        kits_delivered_count = excluded.kits_delivered_count,
        shortage_events_count = excluded.shortage_events_count,
        cost_variance_events_count = excluded.cost_variance_events_count,
        currency = excluded.currency,
        computed_at = excluded.computed_at;

    return jsonb_array_length(p_rows);
end;
$$;

alter table reporting.weekly_office_program_performance enable row level security;
alter table reporting.pipeline_runs enable row level security;
alter table reporting.pipeline_run_inputs enable row level security;

revoke all on schema reporting from public, anon, authenticated;
revoke all on all tables in schema reporting from anon, authenticated;
revoke all on function reporting.publish_weekly_office_program_performance(date, jsonb)
    from public, anon, authenticated;
grant usage on schema reporting to service_role;
grant select, insert, update, delete on reporting.weekly_office_program_performance to service_role;
grant select, insert, update on reporting.pipeline_runs to service_role;
grant select, insert on reporting.pipeline_run_inputs to service_role;
grant execute on function reporting.publish_weekly_office_program_performance(date, jsonb) to service_role;
