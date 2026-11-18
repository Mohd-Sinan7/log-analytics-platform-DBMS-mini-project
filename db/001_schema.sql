-- 001_schema.sql  (idempotent)
-- Core logs table with declarative range partitioning by timestamp

CREATE TABLE IF NOT EXISTS logs (
    id         BIGSERIAL,
    doc_id     UUID          NOT NULL DEFAULT gen_random_uuid(),
    ts         TIMESTAMPTZ   NOT NULL,
    severity   TEXT          NOT NULL,
    service    TEXT          NOT NULL,
    host       TEXT          NOT NULL,
    trace_id   TEXT,
    message    TEXT          NOT NULL,
    PRIMARY KEY (id, ts),
    CONSTRAINT chk_severity CHECK (severity IN ('DEBUG','INFO','WARN','ERROR','FATAL'))
) PARTITION BY RANGE (ts);

-- Dead-letter table for unparseable / failed rows
CREATE TABLE IF NOT EXISTS dead_letter (
    id          BIGSERIAL PRIMARY KEY,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_line    TEXT        NOT NULL,
    error       TEXT        NOT NULL
);
