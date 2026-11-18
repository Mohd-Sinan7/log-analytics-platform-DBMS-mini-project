"""
test_anomaly_e2e.py — End-to-end verification of anomaly detector against real PostgreSQL.
"""
import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncpg
from datetime import datetime, timezone, timedelta
from anomaly.detector import _detect_once

DSN = "postgresql://logs:logspassword@localhost:5432/logs"

async def run_test():
    pool = await asyncpg.create_pool(DSN)
    
    # Clean previous anomalies
    await pool.execute("DELETE FROM anomalies")
    
    # 1. Fetch latest completed minute
    now_m = await pool.fetchval("SELECT date_trunc('minute', NOW() - INTERVAL '1 minute')")
    
    # 2. Insert baseline: 1-3 errors per minute for the previous 20 minutes
    for i in range(2, 22):
        bucket = now_m - timedelta(minutes=i)
        err_count = 2 if i % 2 == 0 else 3
        await pool.execute(
            """
            INSERT INTO log_counts_minute (bucket, service, severity, count)
            VALUES ($1, 'payments', 'ERROR', $2), ($1, 'payments', 'INFO', 50)
            ON CONFLICT (bucket, service, severity) DO UPDATE SET count = EXCLUDED.count
            """,
            bucket, err_count,
        )
    
    # 3. Insert spike: high error count that easily exceeds 3 * std
    # Even if previous benchmarks had large batches, 1500 errors will trigger zscore > 3.0
    spike_count = 1500
    await pool.execute(
        """
        INSERT INTO log_counts_minute (bucket, service, severity, count)
        VALUES ($1, 'payments', 'ERROR', $2), ($1, 'payments', 'INFO', 10)
        ON CONFLICT (bucket, service, severity) DO UPDATE SET count = EXCLUDED.count
        """,
        now_m, spike_count,
    )
    
    # 4. Run detection for that specific bucket
    await _detect_once(pool, zscore_threshold=3.0, min_count=5, bucket=now_m)
    
    # 5. Verify anomaly row in database
    rows = await pool.fetch("SELECT * FROM anomalies WHERE service = 'payments'")
    assert len(rows) > 0, "No anomaly was detected for payments spike!"
    r = rows[0]
    print(f"ANOMALY DETECTED: service={r['service']}, zscore={r['zscore']:.2f}, value={r['value']}, baseline_mean={r['baseline_mean']:.2f}")
    assert r['zscore'] > 3.0
    assert r['value'] == float(spike_count)
    
    await pool.close()
    print("Anomaly detector verified successfully!")

if __name__ == "__main__":
    asyncio.run(run_test())
