# Architecture & Design Decisions

## Decision Log

### D-01: PostgreSQL as primary store
**Rationale**: SQL-first analytics gives strong consistency, ACID guarantees, and
powerful aggregation. Declarative range partitioning by day enables efficient
partition pruning for time-range queries and simplifies data retention.

### D-02: Elasticsearch as full-text index
**Rationale**: PostgreSQL LIKE/ILIKE on large text columns is slow even with GIN
indexes. Elasticsearch provides inverted-index-based full-text search with BM25
scoring, fuzzy matching, and phrase search with sub-millisecond latency at scale.
IDs are shared between both stores so hydration is a point-lookup.

### D-03: Daily partitions + DEFAULT safety net
**Rationale**: Daily granularity balances partition count vs. query pruning
efficiency. The DEFAULT partition catches rows outside provisioned range, preventing
insert failures. The create_partitions() function is called on agent startup and
hourly to provision ahead.

### D-04: COPY for bulk Postgres inserts
**Rationale**: psycopg3 COPY is 10-50x faster than individual INSERTs for bulk
data. Combined with the 1000-row / 1-second flush threshold, this achieves high
throughput while keeping latency acceptable.

### D-05: Client-side UUIDv4 as ES _id
**Rationale**: Using the Postgres BIGSERIAL id requires a round-trip before the ES
bulk call. Instead, a UUID is generated client-side and used as both the ES doc _id
and stored in a `doc_id` column in Postgres (added in schema). Postgres id is still
the primary key for keyset pagination.

### D-06: Keyset pagination in the API
**Rationale**: OFFSET-based pagination degrades as offset grows. Keyset pagination
on (ts DESC, id DESC) gives O(1) page fetches regardless of position.

### D-07: asyncpg for Postgres, elasticsearch-py with async client for ES
**Rationale**: asyncpg is the fastest Python Postgres driver; elasticsearch-py 8
ships a native AsyncElasticsearch client. Both integrate naturally with asyncio /
FastAPI.

### D-08: Rollup table log_counts_minute
**Rationale**: Real-time aggregation over millions of rows is expensive. A
pre-aggregated rollup table updated every 30 seconds makes error-rate API
calls sub-millisecond. The ingest worker triggers the rollup refresh.

### D-09: Z-score anomaly detection
**Rationale**: Simple, interpretable, and effective for time-series spike detection.
A 60-minute rolling window gives enough baseline without needing ML libraries.
Minimum count threshold (5) avoids false positives at low traffic.

### D-10: Grafana provisioning via YAML
**Rationale**: Provisioned datasources and dashboards load automatically on startup,
making the setup fully reproducible with one `docker compose up`.

### D-11: Security disabled for ES in local dev
**Rationale**: xpack.security.enabled=false simplifies local setup per the spec.
A production deployment would enable TLS + API key auth.

### D-12: asyncio watchdog for log tailing
**Rationale**: watchdog provides OS-native file-system events (inotify on Linux)
for efficient, low-latency detection of log appends and rotation, with no polling.

### D-13: Port 8080 external host mapping for FastAPI
**Rationale**: Port 8000 on the host machine may be occupied by existing processes
or containers. Mapping external port 8080 to container port 8000 avoids port collision
while keeping container network configuration intact.

### D-14: Pin elasticsearch-py to 8.x
**Rationale**: Elasticsearch 8.13 server enforces media-type version compatibility.
elasticsearch-py 9.x sends `compatible-with=9` headers which Elasticsearch 8.x rejects
with 400 Bad Request. Pinning client to `>=8.13.0,<9.0.0` ensures exact protocol compatibility.

### D-15: Binary copy via asyncpg copy_records_to_table
**Rationale**: Rather than constructing tab-separated strings in memory and manually
escaping delimiters and newlines, asyncpg `copy_records_to_table` streams binary tuples
directly using PostgreSQL's binary COPY protocol, providing type safety, robust encoding,
and over 33,000 rows/sec ingestion throughput.
