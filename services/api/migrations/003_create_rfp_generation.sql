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

    -- Una instalación que ya ejecutó Parte 3 tiene estados más amplios. No
    -- degradar temporalmente el constraint al reiniciar la API.
    IF status_constraint IS NOT NULL AND NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'rfp_tickets'::regclass
          AND conname = status_constraint
          AND pg_get_constraintdef(oid) LIKE '%waiting_for_approval%'
    ) THEN
        EXECUTE format('ALTER TABLE rfp_tickets DROP CONSTRAINT %I', status_constraint);
        ALTER TABLE rfp_tickets ADD CONSTRAINT rfp_tickets_status_check
            CHECK (status IN (
                'analyzing', 'discarded', 'intake_complete',
                'drafting', 'under_evaluation', 'needs_human_review'
            ));
    END IF;
END $$;
