-- Phase 4: metric registry constraints + the read-only executor role (design §6.2).

-- Allow explicit NULL mappings = typed abstention (e.g. a bank has no gross profit).
ALTER TABLE metric_mappings ALTER COLUMN us_gaap_tag DROP NOT NULL;

-- One default row (company_id NULL) per metric; one override per (metric, company).
-- (Tag-switch history via multiple valid_from rows is a later Phase 4 slice.)
CREATE UNIQUE INDEX IF NOT EXISTS metric_mappings_default_uq
  ON metric_mappings (metric_key) WHERE company_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS metric_mappings_company_uq
  ON metric_mappings (metric_key, company_id) WHERE company_id IS NOT NULL;

-- Read-only role for the SQL executor: SELECT everywhere, write nowhere. This is the
-- SQL branch's structural safety guarantee (the executor connects as this role).
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'usrag_ro') THEN
    CREATE ROLE usrag_ro LOGIN PASSWORD 'usrag_ro';
  END IF;
END $$;
GRANT CONNECT ON DATABASE usrag TO usrag_ro;
GRANT pg_read_all_data TO usrag_ro;
