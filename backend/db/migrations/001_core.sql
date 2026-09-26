-- Phase 1: the data spine (design §4). Applied by us_rag.store.migrate.

-- Extensions are per-database: db/init covers the compose default DB, this line
-- covers any other target (the pytest-created test DB, CI service DB).
CREATE EXTENSION IF NOT EXISTS vector;

-- ---------- security master (design §4.3) ----------

CREATE TABLE companies (
    company_id  SERIAL PRIMARY KEY,
    cik         CHAR(10) UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    sector      TEXT NOT NULL,
    fye_month_hint INT,                       -- hint for humans; U8: real boundaries from fiscal_calendars
    week_52_53_calendar BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE tickers (
    company_id  INT NOT NULL REFERENCES companies,
    ticker      TEXT NOT NULL,
    exchange    TEXT,
    valid_from  DATE NOT NULL,                -- '1970-01-01' = "since before our window"
    valid_to    DATE,                         -- NULL = still current
    note        TEXT,
    PRIMARY KEY (company_id, ticker, valid_from)
);

CREATE TABLE identifiers (
    company_id  INT NOT NULL REFERENCES companies,
    scheme      TEXT NOT NULL CHECK (scheme IN ('FIGI')),
    value       TEXT NOT NULL,
    PRIMARY KEY (company_id, scheme)
);

-- aliases are NOT unique across companies: ambiguity is representable and must be
-- surfaced by entity resolution, never silently resolved (design §6.6)
CREATE TABLE name_aliases (
    company_id  INT NOT NULL REFERENCES companies,
    alias       TEXT NOT NULL,
    PRIMARY KEY (company_id, alias)
);

-- ---------- document registry (design §4.4) ----------

CREATE TABLE documents (
    accession           TEXT PRIMARY KEY,     -- native globally-unique idempotency key
    company_id          INT NOT NULL REFERENCES companies,
    form                TEXT NOT NULL,
    filed_date          DATE NOT NULL,
    acceptance_datetime TIMESTAMPTZ NOT NULL, -- authoritative knowledge_time source (§4.2)
    primary_doc_url     TEXT,
    blob_path           TEXT,
    status              TEXT NOT NULL DEFAULT 'registered'
);

-- ---------- bitemporal facts (design §4.2, pin U11) ----------

CREATE TABLE facts (
    fact_id        BIGSERIAL PRIMARY KEY,
    company_id     INT NOT NULL REFERENCES companies,
    concept        TEXT NOT NULL,             -- us-gaap tag or 8K-EX99 pseudo-concept
    axis           TEXT,                      -- segment dimension (D-US-3)
    member         TEXT,
    value          NUMERIC NOT NULL,
    unit           TEXT NOT NULL,
    period_start   DATE,                      -- NULL for instant facts
    period_end     DATE NOT NULL,
    period_kind    TEXT NOT NULL CHECK (period_kind IN ('duration', 'instant')),
    knowledge_time TIMESTAMPTZ NOT NULL,      -- EDGAR acceptance datetime, never filing date
    accession      TEXT NOT NULL REFERENCES documents,
    source         TEXT NOT NULL CHECK (source IN ('10-K', '10-Q', '8K-EX99', 'derived')),
    preliminary    BOOLEAN NOT NULL DEFAULT FALSE,
    superseded_by  BIGINT REFERENCES facts (fact_id),
    human_verified BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (period_kind != 'duration' OR period_start IS NOT NULL)
);

CREATE INDEX facts_asof_idx ON facts (company_id, concept, period_end, knowledge_time);

-- U11 enforcement: facts is append-only. The ONLY permitted mutation is setting
-- superseded_by exactly once (the write-once supersession link); everything else
-- is a new row. DELETE is always forbidden. (TRUNCATE bypasses row triggers and is
-- banned by the Phase 1 code lint instead.)
CREATE FUNCTION facts_append_only() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'facts is append-only (U11): DELETE forbidden';
    END IF;
    IF OLD.superseded_by IS NOT NULL THEN
        RAISE EXCEPTION 'facts is append-only (U11): row % already superseded', OLD.fact_id;
    END IF;
    IF NEW.superseded_by IS NULL OR
       ROW(NEW.fact_id, NEW.company_id, NEW.concept, NEW.axis, NEW.member, NEW.value,
           NEW.unit, NEW.period_start, NEW.period_end, NEW.period_kind,
           NEW.knowledge_time, NEW.accession, NEW.source, NEW.preliminary,
           NEW.human_verified)
       IS DISTINCT FROM
       ROW(OLD.fact_id, OLD.company_id, OLD.concept, OLD.axis, OLD.member, OLD.value,
           OLD.unit, OLD.period_start, OLD.period_end, OLD.period_kind,
           OLD.knowledge_time, OLD.accession, OLD.source, OLD.preliminary,
           OLD.human_verified) THEN
        RAISE EXCEPTION 'facts is append-only (U11): only setting superseded_by once is permitted';
    END IF;
    RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER facts_append_only
BEFORE UPDATE OR DELETE ON facts
FOR EACH ROW EXECUTE FUNCTION facts_append_only();

-- ---------- fiscal calendars (design §4.6, pin U8) ----------

CREATE TABLE fiscal_calendars (
    company_id       INT NOT NULL REFERENCES companies,
    fiscal_year      INT NOT NULL,
    fiscal_period    TEXT NOT NULL CHECK (fiscal_period IN ('FY', 'Q1', 'Q2', 'Q3', 'Q4')),
    period_start     DATE NOT NULL,
    period_end       DATE NOT NULL,
    weeks            INT,                     -- 13|14|52|53 for week-based calendars; NULL for month-based
    source           TEXT NOT NULL DEFAULT 'seed' CHECK (source IN ('seed', 'xbrl')),
    source_accession TEXT,
    knowledge_time   TIMESTAMPTZ,
    PRIMARY KEY (company_id, fiscal_year, fiscal_period),
    CHECK (period_end > period_start)
);

-- ---------- corporate actions & prices (design §3.5, §4.7) ----------

CREATE TABLE corporate_actions (
    action_id   SERIAL PRIMARY KEY,
    company_id  INT NOT NULL REFERENCES companies,
    action_type TEXT NOT NULL CHECK (action_type IN ('split', 'dividend')),
    ex_date     DATE NOT NULL,
    factor      NUMERIC,                      -- split: 10 for a 10:1
    amount      NUMERIC,                      -- dividend per share, USD
    source      TEXT NOT NULL,
    UNIQUE (company_id, action_type, ex_date)
);

CREATE TABLE prices (
    company_id INT NOT NULL REFERENCES companies,
    trade_date DATE NOT NULL,
    open NUMERIC, high NUMERIC, low NUMERIC,
    close NUMERIC NOT NULL,                   -- UNADJUSTED (design §3.5); adjust at query time
    volume BIGINT,
    source TEXT NOT NULL DEFAULT 'tiingo',
    PRIMARY KEY (company_id, trade_date)
);

-- ---------- narrative chunks (design §4.5) ----------

CREATE TABLE chunks (
    chunk_id       BIGSERIAL PRIMARY KEY,
    accession      TEXT NOT NULL REFERENCES documents,
    company_id     INT NOT NULL REFERENCES companies,
    doc_type       TEXT NOT NULL,
    section        TEXT NOT NULL,
    fiscal_context TEXT,
    knowledge_time TIMESTAMPTZ NOT NULL,      -- inherited from the accession; retrieval as-of filter
    text           TEXT NOT NULL,
    tsv            tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    embedding      vector(1024)               -- bge-m3 (U9)
);

CREATE INDEX chunks_tsv_idx ON chunks USING GIN (tsv);
CREATE INDEX chunks_asof_idx ON chunks (company_id, knowledge_time);
CREATE INDEX chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);

-- ---------- metric mappings (design §6.2 — populated at Phase 4) ----------

CREATE TABLE metric_mappings (
    metric_key  TEXT NOT NULL,
    company_id  INT REFERENCES companies,     -- NULL = default mapping; company rows override
    us_gaap_tag TEXT NOT NULL,
    unit        TEXT NOT NULL,
    comparable  BOOLEAN NOT NULL DEFAULT TRUE,
    provenance  TEXT,
    verified_by TEXT,
    valid_from  DATE
);
