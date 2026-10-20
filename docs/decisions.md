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
