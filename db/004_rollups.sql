-- 004_rollups.sql  (idempotent)
-- Rollup table for pre-aggregated per-minute counts

CREATE TABLE IF NOT EXISTS log_counts_minute (
    bucket    TIMESTAMPTZ NOT NULL,
    service   TEXT        NOT NULL,
    severity  TEXT        NOT NULL,
    count     BIGINT      NOT NULL DEFAULT 0,
    PRIMARY KEY (bucket, service, severity)
);

CREATE INDEX IF NOT EXISTS idx_lcm_bucket ON log_counts_minute (bucket DESC);
CREATE INDEX IF NOT EXISTS idx_lcm_service ON log_counts_minute (service, bucket DESC);

-- Function: idempotent rollup refresh for a given time window
CREATE OR REPLACE FUNCTION refresh_log_counts(
    from_ts TIMESTAMPTZ DEFAULT NOW() - INTERVAL '10 minutes',
    to_ts   TIMESTAMPTZ DEFAULT NOW()
)
RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO log_counts_minute (bucket, service, severity, count)
    SELECT
        date_trunc('minute', ts) AS bucket,
        service,
        severity,
        COUNT(*)                 AS count
    FROM logs
    WHERE ts >= from_ts AND ts < to_ts
    GROUP BY 1, 2, 3
    ON CONFLICT (bucket, service, severity)
    DO UPDATE SET count = EXCLUDED.count;
END;
$$;
