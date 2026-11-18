-- 007_advanced_queries.sql
-- PES University UE23CS351A DBMS Evaluation Queries & Advanced Concepts

-- ============================================================================
-- 1. STORED PROCEDURE / FUNCTION: Automated Daily Partition Creation
-- ============================================================================
CREATE OR REPLACE PROCEDURE pr_create_daily_partition(p_date DATE)
LANGUAGE plpgsql
AS $$
DECLARE
    v_part_name TEXT;
    v_start_ts  TIMESTAMPTZ;
    v_end_ts    TIMESTAMPTZ;
    v_sql       TEXT;
BEGIN
    v_part_name := 'logs_' || to_char(p_date, 'YYYY_MM_DD');
    v_start_ts  := p_date::timestamptz;
    v_end_ts    := (p_date + INTERVAL '1 day')::timestamptz;

    -- Check if partition already exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = v_part_name AND n.nspname = 'public'
    ) THEN
        v_sql := format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF logs FOR VALUES FROM (%L) TO (%L);',
            v_part_name, v_start_ts, v_end_ts
        );
        EXECUTE v_sql;
        RAISE NOTICE 'Created partition % for range % to %', v_part_name, v_start_ts, v_end_ts;
    ELSE
        RAISE NOTICE 'Partition % already exists', v_part_name;
    END IF;
END;
$$;

-- ============================================================================
-- 2. TRIGGER & FUNCTION: Automated Anomaly Audit Logging
-- ============================================================================
CREATE OR REPLACE FUNCTION trg_fn_audit_anomaly()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO audit_log (username, action, entity, details, ts)
    VALUES (
        current_user,
        'ANOMALY_RECORDED',
        'anomalies',
        jsonb_build_object(
            'service', NEW.service,
            'metric', NEW.metric,
            'zscore', NEW.zscore,
            'value', NEW.value,
            'baseline_mean', NEW.baseline_mean,
            'bucket', NEW.bucket
        ),
        NOW()
    );
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_audit_anomaly ON anomalies;
CREATE TRIGGER trg_audit_anomaly
AFTER INSERT ON anomalies
FOR EACH ROW
EXECUTE FUNCTION trg_fn_audit_anomaly();

-- ============================================================================
-- 3. JOIN QUERY: Multi-Table Operational Telemetry Join
-- Joins partitioned logs, services dimension, hosts dimension, and anomalies
-- ============================================================================
-- VIEW: vw_operational_telemetry
CREATE OR REPLACE VIEW vw_operational_telemetry AS
SELECT 
    l.id AS log_id,
    l.ts,
    l.severity,
    l.service,
    s.tier AS service_tier,
    s.owner_team,
    l.host,
    h.datacenter,
    h.ip_address,
    l.trace_id,
    l.message,
    a.zscore AS anomaly_zscore
FROM logs l
INNER JOIN services_dim s ON l.service = s.service_name
INNER JOIN hosts_dim h ON l.host = h.hostname
LEFT JOIN anomalies a 
    ON l.service = a.service 
    AND date_trunc('minute', l.ts) = a.bucket;

-- ============================================================================
-- 4. NESTED QUERY: Filter Logs for High-Risk Services
-- Finds ERROR logs occurring only in services that had severe anomalies (zscore > 3.0)
-- ============================================================================
-- SELECT l.id, l.ts, l.service, l.severity, l.message
-- FROM logs l
-- WHERE l.severity IN ('ERROR', 'FATAL')
--   AND l.service IN (
--       SELECT a.service 
--       FROM anomalies a 
--       WHERE a.zscore >= 3.0
--   )
-- ORDER BY l.ts DESC
-- LIMIT 50;

-- ============================================================================
-- 5. CORRELATED SUBQUERY: Services Exceeding Tier Average Error Count
-- Evaluates outer service error count against the average of all services in the same tier
-- ============================================================================
-- SELECT 
--     s.service_name,
--     s.tier,
--     COUNT(l.id) AS service_error_count
-- FROM services_dim s
-- LEFT JOIN logs l ON s.service_name = l.service AND l.severity IN ('ERROR', 'FATAL')
-- GROUP BY s.service_name, s.tier
-- HAVING COUNT(l.id) > (
--     SELECT AVG(tier_sub.err_cnt)
--     FROM (
--         SELECT s_in.service_name, COUNT(l_in.id) AS err_cnt
--         FROM services_dim s_in
--         LEFT JOIN logs l_in ON s_in.service_name = l_in.service AND l_in.severity IN ('ERROR', 'FATAL')
--         WHERE s_in.tier = s.tier
--         GROUP BY s_in.service_name
--     ) tier_sub
-- );

-- ============================================================================
-- 6. RECURSIVE QUERY (WITH RECURSIVE): Trace Dependency & Gap Generation
-- Generates continuous 5-minute bucket intervals to ensure zero-gap monitoring
-- ============================================================================
-- WITH RECURSIVE time_intervals AS (
--     SELECT date_trunc('hour', NOW()) - INTERVAL '2 hours' AS interval_start
--     UNION ALL
--     SELECT interval_start + INTERVAL '10 minutes'
--     FROM time_intervals
--     WHERE interval_start < date_trunc('hour', NOW())
-- )
-- SELECT 
--     ti.interval_start,
--     COUNT(l.id) AS log_count,
--     COUNT(CASE WHEN l.severity IN ('ERROR', 'FATAL') THEN 1 END) AS error_count
-- FROM time_intervals ti
-- LEFT JOIN logs l 
--     ON l.ts >= ti.interval_start 
--    AND l.ts < ti.interval_start + INTERVAL '10 minutes'
-- GROUP BY ti.interval_start
-- ORDER BY ti.interval_start;

-- ============================================================================
-- 7. ADVANCED ANALYTICAL CTE (Window Functions: LAG, RANK, Moving Average)
-- ============================================================================
-- WITH minute_stats AS (
--     SELECT 
--         bucket,
--         service,
--         SUM(count) AS total_logs,
--         SUM(CASE WHEN severity IN ('ERROR', 'FATAL') THEN count ELSE 0 END) AS error_logs
--     FROM log_counts_minute
--     WHERE bucket >= NOW() - INTERVAL '2 hours'
--     GROUP BY bucket, service
-- ),
-- velocity_analysis AS (
--     SELECT 
--         bucket,
--         service,
--         error_logs,
--         LAG(error_logs, 1, 0) OVER (PARTITION BY service ORDER BY bucket) AS prev_minute_errors,
--         AVG(error_logs) OVER (PARTITION BY service ORDER BY bucket ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) AS rolling_5m_avg_errors,
--         RANK() OVER (PARTITION BY bucket ORDER BY error_logs DESC) AS error_rank_in_bucket
--     FROM minute_stats
-- )
-- SELECT 
--     bucket,
--     service,
--     error_logs,
--     prev_minute_errors,
--     (error_logs - prev_minute_errors) AS error_delta,
--     ROUND(rolling_5m_avg_errors, 2) AS rolling_5m_avg,
--     error_rank_in_bucket
-- FROM velocity_analysis
-- ORDER BY bucket DESC, error_logs DESC;
