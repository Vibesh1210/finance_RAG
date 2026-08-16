-- Phase 2: ingestion additions.

-- Corpus membership is a property of the document, not of its form: the facts
-- loader also registers PRE-corpus accessions (metadata-only, no blob) so that
-- supersession pairs and as-reported-then baselines exist (DECISIONS.md #9).
-- Gate registry counts are scoped to corpus = TRUE.
ALTER TABLE documents ADD COLUMN corpus BOOLEAN NOT NULL DEFAULT FALSE;

-- supersession pass groups facts by identity and walks them in knowledge order
CREATE INDEX facts_identity_idx
    ON facts (company_id, concept, unit, period_end, knowledge_time);
CREATE INDEX facts_accession_idx ON facts (accession);
CREATE INDEX documents_company_form_idx ON documents (company_id, form);
