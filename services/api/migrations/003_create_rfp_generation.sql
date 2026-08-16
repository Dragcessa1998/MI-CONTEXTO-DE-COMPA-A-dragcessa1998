ALTER TABLE rfp_department_sections
    ADD COLUMN IF NOT EXISTS generation_iteration INTEGER NOT NULL DEFAULT 0;

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
            'drafting', 'under_evaluation', 'needs_human_review'
        ));
END $$;
