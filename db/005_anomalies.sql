-- 005_anomalies.sql  (idempotent)
-- Anomalies table for z-score based spike detection

CREATE TABLE IF NOT EXISTS anomalies (
    id             BIGSERIAL PRIMARY KEY,
    detected_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    bucket         TIMESTAMPTZ NOT NULL,
    service        TEXT        NOT NULL,
    metric         TEXT        NOT NULL DEFAULT 'error_count',
    value          DOUBLE PRECISION NOT NULL,
    baseline_mean  DOUBLE PRECISION NOT NULL,
    baseline_std   DOUBLE PRECISION NOT NULL,
    zscore         DOUBLE PRECISION NOT NULL,
    UNIQUE (bucket, service, metric)
);

CREATE INDEX IF NOT EXISTS idx_anomalies_detected_at
    ON anomalies (detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_anomalies_service
    ON anomalies (service, detected_at DESC);
