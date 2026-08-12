CREATE SCHEMA IF NOT EXISTS orchestration;

CREATE TABLE IF NOT EXISTS orchestration.job_runs (
  id uuid PRIMARY KEY,
  job_name text NOT NULL,
  target_date date NOT NULL,
  status text NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
  started_at timestamptz,
  finished_at timestamptz,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_job_runs_name_date
  ON orchestration.job_runs (job_name, target_date);

-- El estado processing ES el lock; el índice sólo hace atómica esa regla.
CREATE UNIQUE INDEX IF NOT EXISTS uq_job_runs_one_processing
  ON orchestration.job_runs (job_name)
  WHERE status = 'processing';

CREATE UNIQUE INDEX IF NOT EXISTS uq_job_runs_completed_date
  ON orchestration.job_runs (job_name, target_date)
  WHERE status = 'completed';
