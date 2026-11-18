-- 002_partitions.sql  (idempotent)
-- PL/pgSQL helper to provision daily partitions and a DEFAULT fallback

CREATE OR REPLACE FUNCTION create_partitions(days_ahead INT DEFAULT 7)
RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    start_date DATE;
    end_date   DATE;
    part_name  TEXT;
    today      DATE := CURRENT_DATE;
BEGIN
    -- Provision from 7 days ago through today + days_ahead
    FOR i IN -7 .. days_ahead LOOP
        start_date := today + i;
        end_date   := start_date + 1;
        part_name  := 'logs_' || to_char(start_date, 'YYYY_MM_DD');

        IF NOT EXISTS (
            SELECT 1 FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = part_name AND n.nspname = 'public'
        ) THEN
            EXECUTE format(
                'CREATE TABLE %I PARTITION OF logs
                 FOR VALUES FROM (%L) TO (%L)',
                part_name,
                start_date::TIMESTAMPTZ,
                end_date::TIMESTAMPTZ
            );
            RAISE NOTICE 'Created partition %', part_name;
        END IF;
    END LOOP;
END;
$$;

-- DEFAULT partition catches rows outside provisioned range
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = 'logs_default' AND n.nspname = 'public'
    ) THEN
        CREATE TABLE logs_default PARTITION OF logs DEFAULT;
        RAISE NOTICE 'Created default partition';
    END IF;
END;
$$;

-- Provision initial partitions on first run
SELECT create_partitions(7);
