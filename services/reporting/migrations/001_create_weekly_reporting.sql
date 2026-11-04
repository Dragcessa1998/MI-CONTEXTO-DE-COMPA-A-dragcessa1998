CREATE SCHEMA IF NOT EXISTS reporting;

CREATE TABLE IF NOT EXISTS reporting.weekly_office_program_performance (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  office text NOT NULL,
  programme_id text NOT NULL,
  week_start date NOT NULL,
  total_material_cost numeric NOT NULL DEFAULT 0,
  kits_delivered_count integer NOT NULL DEFAULT 0,
  shortage_events_count integer NOT NULL DEFAULT 0,
  cost_variance_events_count integer NOT NULL DEFAULT 0,
  currency text NOT NULL,
  computed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (office, programme_id, week_start)
);

CREATE TABLE IF NOT EXISTS reporting.pipeline_runs (
  id uuid PRIMARY KEY,
  pipeline_name text NOT NULL,
  target_week date NOT NULL,
  status text NOT NULL CHECK (status IN ('processing', 'completed', 'failed')),
  rows_extracted integer NOT NULL DEFAULT 0,
  rows_valid integer NOT NULL DEFAULT 0,
  rows_quarantined integer NOT NULL DEFAULT 0,
  duplicates_count integer NOT NULL DEFAULT 0,
  started_at timestamptz NOT NULL,
  finished_at timestamptz,
  error_message text
);
