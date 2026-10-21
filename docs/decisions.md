# LongTail Passport - Decisions Log

## ADR 001: Hybrid Database Support (PostgreSQL 16 + SQLite Fallback)
- **Context**: The production requirement mandates PostgreSQL 16 with background jobs claimed via `SELECT ... FOR UPDATE SKIP LOCKED`. However, developers and CI environments need to run lightning-fast unit tests and integration tests without forcing external database daemons to be running.
- **Decision**: Use SQLAlchemy 2 with a database URL configured via `DATABASE_URL`. If `DATABASE_URL` starts with `sqlite`, row-level locking falls back gracefully to transaction isolation while retaining identical table schemas, foreign keys, and JSON serialization. Production Docker Compose pins `postgres:16`.
- **Status**: Accepted.

## ADR 002: Structured JSON Logging with Strict Secret Redaction Filter
- **Context**: Tokens, passwords, HMAC keys, and API secrets must never leak into log files or console streams under any circumstances.
- **Decision**: Implement a custom Python `logging.Filter` with compiled regex patterns matching `token`, `secret`, `password`, `authorization`, `api[-_]?key`, and bearer tokens. All logs are emitted as single-line JSON objects with ISO-8601 timestamps, log level, correlation ID, and sanitized messages.
- **Status**: Accepted.

## ADR 003: Postgres-Backed Job Queue (No Redis / No Celery)
- **Context**: The specification strictly prohibits Redis and Celery to minimize moving parts and ensure transactional integrity with business records.
- **Decision**: Job records live in the `jobs` table with states `queued`, `running`, `succeeded`, `failed`. The worker process polls and claims pending jobs atomically using `SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1`.
- **Status**: Accepted.

## ADR 004: Pure-Python HS256 JWT Generation for Ghost Admin API
- **Context**: Ghost Admin API v5 requires HS256 JWTs signed with a hexadecimal secret key (`id:secret`). Introducing heavy or platform-dependent C-extensions or external JWT libraries creates deployment vulnerabilities and dependency drift.
- **Decision**: Implemented zero-dependency HS256 JWT generation using Python's standard library (`hmac`, `hashlib`, `base64`, `json`). Token validity follows the Ghost specification (`kid: id`, `aud: '/admin/'`, 5-minute TTL).
- **Status**: Accepted.

## ADR 005: MRSS Feed Generator with Single Namespace Registration and In-Place Idempotency
- **Context**: Media RSS requires valid RSS 2.0 XML with the Yahoo Media RSS namespace (`xmlns:media="http://search.yahoo.com/mrss/"`). In Python ElementTree, setting namespace attributes manually alongside `ET.register_namespace` creates duplicate attribute serialization errors (`ParseError: duplicate attribute`). Re-submitting feed items must not produce duplicate entries in the RSS feed.
- **Decision**: Use `ET.register_namespace("media", ...)` exclusively for namespace emission on serialization. Use `idempotency_key` as `<guid isPermaLink="false">`, updating matching item elements in-place when re-published and pruning elements upon deletion. Feeds persist deterministically in MinIO/local storage.
- **Status**: Accepted.

## ADR 006: Streaming Catalogue Import with URL Normalization and Chunking
- **Context**: Importing large catalogues (1,000+ destinations) must scale without memory spikes or database connection exhaustion, meeting the < 5 minute throughput SLA while eliminating duplicate domains and tracking parameters.
- **Decision**: Implemented streaming `csv.DictReader` iteration with batch database flushes (`batch_size=250/500`). Pre-loaded normalized URL sets prevent repetitive query overhead. In-memory SQLite / Postgres benchmark ingests 1,000 rows in < 2.0 seconds.
- **Status**: Accepted.

## ADR 007: Human-in-the-Loop Rules Confirmation with Immutable Audit Logging
- **Context**: Community rules extracted by automated NLP or AI models are probabilistic. Applying unverified rule changes to automated publishing can cause wrongful bans or account suspensions.
- **Decision**: Candidate rules extracted via `POST /api/v1/rules/extract` require human review and explicit confirmation via `POST /api/v1/rules/confirm`. Every confirmation writes an immutable entry into `audit_logs` storing the full before/after JSON diff, actor identity, and UTC timestamp.
- **Status**: Accepted.

## ADR 008: Multi-Criteria Recommender with Cold-Start Neutral Prior
- **Context**: Content distribution requires matching content to the most suitable destinations considering topic relevance, rules fit, and historical performance. New destinations without publication history would otherwise be penalized to 0.0.
- **Decision**: Formula `0.50 * relevance + 0.25 * rules_fit + 0.25 * past_result_score`. Past performance uses a neutral prior baseline of 0.50 for cold-start destinations. Hard constraints (inactive, self-promo disallowed on promotional content, open circuit breakers) produce a hard zero for `rules_fit`, preventing inappropriate recommendations.
- **Status**: Accepted.

## ADR 009: Background Recertification Scheduler
- **Context**: Passports must remain verified over time. Expired or stale Passports (> 25 days) must be recertified automatically without manual human intervention.
- **Decision**: A periodic scanner detects active destinations whose `last_certified_at` timestamp exceeds the 25-day cutoff (or 10-second demo mode). Stale destinations are scheduled for recertification by enqueuing `certify` jobs into the standard database queue, processed asynchronously by the worker.
- **Status**: Accepted.



