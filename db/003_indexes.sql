-- 003_indexes.sql  (idempotent)
-- Indexes for efficient filtering and lookups

-- Composite indexes for the most common API filter patterns
CREATE INDEX IF NOT EXISTS idx_logs_service_ts
    ON logs (service, ts DESC);

CREATE INDEX IF NOT EXISTS idx_logs_severity_ts
    ON logs (severity, ts DESC);

CREATE INDEX IF NOT EXISTS idx_logs_host_ts
    ON logs (host, ts DESC);

-- Trace lookup (exact match)
CREATE INDEX IF NOT EXISTS idx_logs_trace_id
    ON logs (trace_id)
    WHERE trace_id IS NOT NULL;

-- doc_id lookup (ES hydration)
CREATE INDEX IF NOT EXISTS idx_logs_doc_id
    ON logs (doc_id);

-- BRIN index on ts for sequential scan pruning
CREATE INDEX IF NOT EXISTS idx_logs_ts_brin
    ON logs USING BRIN (ts)
    WITH (pages_per_range = 32);
