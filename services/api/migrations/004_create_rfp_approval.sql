ALTER TABLE rfp_department_sections
    ADD COLUMN IF NOT EXISTS approval_iteration INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS approval_feedback TEXT;

CREATE TABLE IF NOT EXISTS rfp_final_documents (
    ticket_id UUID PRIMARY KEY REFERENCES rfp_tickets(ticket_id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    file_path TEXT NOT NULL,
    currency TEXT NOT NULL CHECK (currency IN ('EUR', 'USD')),
    sections JSONB NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL
);

DO $$
DECLARE
    status_constraint TEXT;
BEGIN
    SELECT conname INTO status_constraint
    FROM pg_constraint
    WHERE conrelid = 'rfp_tickets'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) LIKE '%status%'
    LIMIT 1;

    IF status_constraint IS NOT NULL THEN
        EXECUTE format('ALTER TABLE rfp_tickets DROP CONSTRAINT %I', status_constraint);
    END IF;

    ALTER TABLE rfp_tickets ADD CONSTRAINT rfp_tickets_status_check
        CHECK (status IN (
            'analyzing', 'discarded', 'intake_complete',
            'drafting', 'under_evaluation', 'needs_human_review',
            'waiting_for_approval', 'done'
        ));
END $$;
