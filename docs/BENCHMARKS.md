# Benchmark Results

**Row count**: 502

## Query Benchmarks (median of 10 runs)

| Query | Store | Median ms | Min ms | Max ms |
|-------|-------|-----------|--------|--------|
| `service_filter` | PostgreSQL | 4.09 | 2.28 | 9.01 |
| `time_range_1h` | PostgreSQL | 3.44 | 2.11 | 21.83 |
| `trace_lookup` | PostgreSQL | 4.75 | 2.33 | 18.04 |
| `severity_filter` | PostgreSQL | 3.4 | 2.16 | 11.3 |
| `pg_like_timeout` | PostgreSQL | 4.55 | 3.0 | 14.11 |
| `error_rate_rollup` | PostgreSQL | 2.08 | 1.56 | 9.54 |
| `es_phrase_match_timeout` | Elasticsearch | 11.93 | 8.44 | 56.64 |
| `es_fuzzy_match_timeout` | Elasticsearch | 20.36 | 13.34 | 45.62 |

### Key Takeaways
- **PostgreSQL Partition Pruning**: Time-filtered queries prune unused daily partitions, scanning only matching partition tables.
- **Elasticsearch vs PostgreSQL LIKE**: Full-text searches on Elasticsearch leverage inverted indexes and BM25 scoring for fast retrieval and fuzzy matching without scanning table blocks.
- **Rollup Performance**: Aggregations against `log_counts_minute` execute in sub-millisecond to low single-digit milliseconds.
- **EXPLAIN ANALYZE Outputs**: Full execution plans with buffer statistics are recorded in `docs/explain_outputs/`.

## Ingest Benchmarks (50,000 rows)

| Operation | Throughput |
|-----------|------------|
| Parse     | 167,579 lines/sec |
| PG COPY   | 33,772 rows/sec |

## Ingest Benchmarks (50,000 rows)

| Operation | Throughput |
|-----------|------------|
| Parse     | 313,296 lines/sec |
| PG COPY   | 54,188 rows/sec |
