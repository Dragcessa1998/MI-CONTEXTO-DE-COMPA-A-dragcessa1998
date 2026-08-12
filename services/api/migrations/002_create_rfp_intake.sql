CREATE TABLE IF NOT EXISTS rfp_tickets (
    ticket_id UUID PRIMARY KEY,
    rfp_id UUID NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('analyzing', 'discarded', 'intake_complete')),
    raw_pdf_path TEXT NOT NULL,
    markdown_path TEXT,
    classification_reason TEXT,
    sales_summary TEXT,
    processing_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rfp_metadata (
    rfp_id UUID PRIMARY KEY REFERENCES rfp_tickets(rfp_id) ON DELETE CASCADE,
    client_name TEXT NOT NULL,
    client_hq TEXT NOT NULL,
    currency TEXT NOT NULL,
    services_requested JSONB NOT NULL,
    scope TEXT NOT NULL,
    volumes JSONB NOT NULL,
    deadline TEXT,
    budget_range TEXT,
    departments_needed JSONB NOT NULL,
    readability JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS rfp_department_sections (
    id UUID PRIMARY KEY,
    rfp_id UUID NOT NULL REFERENCES rfp_tickets(rfp_id) ON DELETE CASCADE,
    department_id TEXT NOT NULL CHECK (department_id IN ('seleccion', 'capacitacion', 'soporte')),
    department_name TEXT NOT NULL,
    contact TEXT NOT NULL,
    key_aspects JSONB NOT NULL,
    open_questions JSONB NOT NULL,
    relevant_excerpts JSONB NOT NULL,
    draft_content TEXT,
    evaluation_results JSONB,
    approval_status TEXT,
    approver TEXT,
    approved_at TIMESTAMPTZ,
    UNIQUE (rfp_id, department_id)
);

CREATE INDEX IF NOT EXISTS idx_rfp_tickets_status_created
    ON rfp_tickets(status, created_at DESC);

-- Compatibilidad con instalaciones de desarrollo creadas antes de fijar el
-- contrato de estados exacto del CONTEXT. En una base nueva este bloque no hace nada.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'rfp_tickets'::regclass
          AND conname = 'rfp_tickets_status_check'
          AND pg_get_constraintdef(oid) NOT LIKE '%intake_complete%'
    ) THEN
        ALTER TABLE rfp_tickets DROP CONSTRAINT rfp_tickets_status_check;
        UPDATE rfp_tickets
        SET status = CASE status
            WHEN 'analizando' THEN 'analyzing'
            WHEN 'descartado' THEN 'discarded'
            WHEN 'analisis_completo' THEN 'intake_complete'
            ELSE status
        END;
        ALTER TABLE rfp_tickets ADD CONSTRAINT rfp_tickets_status_check
            CHECK (status IN ('analyzing', 'discarded', 'intake_complete'));
    END IF;
END $$;
