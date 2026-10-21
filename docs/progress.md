# LongTail Passport - Progress & Verification Log

This document tracks completed milestones, test proofs, and metrics for the final submission and live demonstration.

## Milestone Status Overview

| Milestone | Status | Verified How | Known Gaps |
|---|---|---|---|
| Phase 1: Foundation & Data Engine | Completed | Pytest (5 passed in 0.09s), Ruff (all checks passed) | None |
| Phase 2: Preflight Court | Completed | Table-driven pytest 42 scenarios + API endpoint (43 passed in 0.20s), 0 missed violations | None |
| Phase 3: Connector Base & Runtime | Completed | Pytest (7 passed in 0.11s), Ruff (all checks passed), dynamic dispatch verified | None |
| Phase 4: Idempotency & Job Queue | Completed | Pytest (6 passed in 0.11s), Ruff (all checks passed), ledger and worker verified | None |
| Phase 5: Chaos Mock Hub & Core Connectors | Completed | Pytest (6 passed in 0.17s), Ruff (all checks passed), all 4 connectors & faults verified | None |
| Phase 6: Drift Canary & Certification | Completed | Pytest (8 passed in 2.17s), Ruff (all checks passed), 7-step harness & demotion verified | None |
| Phase 7: Real Instances & Extra Connectors | Completed | Pytest (10 passed in 4.01s, 85 passed total), Ruff (all checks passed), all 5 extra connectors verified | None |
| Phase 8: Tailoring, Catalogue & Rules Capture | Completed | Pytest (10 passed in 0.21s, 95 passed total), Ruff (all checks passed), 1,000-row benchmark (< 5s) | None |
| Phase 9: Recommender, Recertification & Metrics | Completed | Pytest (8 passed in 0.89s, 103 passed total), Precision@10 evaluated (100.0% >= 70%), Ruff passed | None |
| Phase 10: Flight Deck, CLI & Submission | Completed | Pytest (122 passed in 9.4s across 11 test modules), 13 hard cases verified, Ruff passed | None |

## Verification Evidence Log
- **Phase 1: Foundation & Data Engine (Verified)**:
  - Docker Compose pinned for all 5 core containers (`api`, `worker`, `db`, `minio`, `mockhub`).
  - Structured JSON logging with `X-Correlation-Id` extraction and context injection.
  - Secret redaction filter verified: scrubbed `token`, `secret`, `password`, `authorization`, and Bearer tokens.
  - All 11 SQLAlchemy models instantiated and verified with relationships.
  - Endpoints `/health` and `/ready` tested and verified.
- **Phase 2: Preflight Court (Verified)**:
  - Pure deterministic rules engine with zero I/O (`evaluate()`).
  - 8 ordered validation checks: circuit/kill-switch, passport validity, automation flag, surface format limits, self-promo, link policy, AI disclosure, and frequency caps.
  - Word boundary truncation with ellipsis implemented.
  - 42-row table-driven YAML test set (`tests/rules_cases.yaml`) verified with **0 missed violations**.
  - Synchronous dry-run endpoint `POST /api/v1/preflight` implemented and tested.
- **Phase 3: Connector Base & Runtime (Verified)**:
  - Abstract `BaseConnector` contract specified with all 7 lifecycle methods.
  - YAML manifest parser and standard HTTP status code mapper implemented.
  - Generic `POST /connector/v1/{connector_key}/{method}` router dispatches dynamically without hardcoded if/else branching.
  - Enforced kill switch and circuit breaker checks at runtime.
- **Phase 4: Idempotency & Job Queue (Verified)**:
  - Intent-first ledger reserving state `INTENT` in database before any platform call.
  - Same key + same hash re-submittal returns cached publication result.
  - Same key + different hash re-submittal raises `409 IDEMPOTENCY_KEY_REUSED`.
  - Background worker claims jobs atomically via `SELECT ... FOR UPDATE SKIP LOCKED` (with SQLite fallback).
  - Invisible reconciliation marker `<!-- ibx:<idempotency_key> -->` embedded in content body.
  - Output manifest with 10 standard keys generated for every result.
  - Webhook callback with HMAC-SHA256 signature in `X-IncuBrix-Signature` header verified.
- **Phase 5: Chaos Mock Hub & Core Connectors (Verified)**:
  - Standalone FastAPI Chaos Mock Hub imitating Discourse, Dev.to, and Partner Webhook receiver.
  - Header-driven fault switch `X-Chaos: timeout | 429 | 401 | 422 | rename_field | slow | 403` and `/__chaos/config` control endpoint.
  - Four core connectors (`discourse`, `devto`, `webhook_hmac`, `assisted`) implemented with YAML manifests.
  - Honest Dev.to unpublishing workaround for deletion implemented and documented.
- **Phase 6: Drift Canary & Certification Harness (Verified)**:
  - Pinned JSON schemas created under `schemas/{discourse,devto,webhook_hmac}/publish.json`.
  - Deterministic `schema_fingerprint` calculated from sorted field paths and types.
  - Full 7-step certification harness (validate -> publish -> drift check -> live check -> read status -> delete -> confirm deleted -> evidence bundle).
  - Evidence JSON bundled and saved with MinIO storage adapter and local fallback.
  - Upstream field rename detected (`CERT_DRIFT_DETECTED`), auto-demotes destination and Passport to `L0`, creates Alert row, and blocks in Preflight Court.
  - Endpoints `GET /api/v1/destinations/{id}/passport` and `POST /api/v1/destinations/{id}/certify` tested and verified.
- **Phase 7: Real Instances & Extra Connectors (Verified)**:
  - Docker Compose configured with `real-instances` profile for local Ghost and Lemmy containers.
  - Bootstrap scripts `scripts/init_local_instances.sh` and `scripts/init_local_instances.ps1` implemented with healthcheck waiting logic.
  - Five advanced extra connectors implemented with YAML manifests and pinned JSON schemas:
    - `lemmy`: API v3 (`/api/v3/post`, `/api/v3/post/delete`, JWT auth).
    - `ghost`: Admin API v5 with zero-dependency HS256 JWT generation, HTML posting, and honest deletion.
    - `mrss_feed`: Media RSS 2.0 XML generator with Yahoo Media namespace, in-place update idempotency, and storage integration.
    - `hashnode`: GraphQL mutations (`publishPost`, `removePost`) and queries.
    - `slack`: Slack Web API (`chat.postMessage`, `chat.delete`, `conversations.history`).
  - All 9 platform connectors registered in global dynamic registry (`app/connectors/init_connectors.py`).
  - Runtime router `POST /connector/v1/{connector_key}/{method}` verified across new connectors.
  - Full 7-step certification harness verified on Ghost and Lemmy destinations, promoting to `L4`.
- **Phase 8: Tailoring, Catalogue & Rules Capture (Verified)**:
  - Content Tailoring Engine implemented with surface-specific adaptations:
    - Forums: Discussion hooks in title and discussion prompts appended to body.
    - Articles/Blogs: Canonical URL preservation, hashtag extraction.
    - Chat/Slack: Automated bulletization of lengthy announcements.
    - Universal: AI disclosure footnote enforcement and URL shortener sanitization.
    - Word boundary ellipsis truncation.
  - Streaming Catalogue Importer:
    - URL normalization (stripping `www.`, scheme casing, trailing slash, tracking params `utm_*`, `ref`).
    - Robust deduplication preventing duplicate records across chunks.
    - Stream-based batch insertion (`batch_size=250/500`) with initial L0 Passports.
    - Benchmark verified: 1,000 destinations ingested in < 2 seconds (far below the 5-minute requirement).
  - Rules Capture & Human Confirmation Workflow:
    - Rule extractor parsing free-form policy text into frequency caps, self-promo, link policy, and AI disclosure.
    - API endpoints `POST /api/v1/rules/extract` and `POST /api/v1/rules/confirm`.
    - Immutable Audit Log entries (`audit_logs` table) generated on confirmation with before/after diffs and actor signatures.
    - Endpoint `POST /api/v1/destinations/import-csv` verified for file uploads and JSON payloads.
  - Test suite `tests/test_tailoring_catalogue_and_rules.py` passing (10/10 tests, 95 passed total).
- **Phase 9: Recommender, Recertification & Metrics (Verified)**:
  - Multi-Criteria Recommender Engine (`app/recommend/engine.py`):
    - Scoring formula: `0.50 * relevance + 0.25 * rules_fit + 0.25 * past_result_score`.
    - Relevance: topic category alignment, audience tag overlap, and language matching.
    - Rules fit: Passport health score, Passport level (L4 bonus), frequency cap readiness, and hard block enforcement.
    - Past result score: historical publication delivery success and engagement averages with neutral cold-start baseline (0.50).
    - API route: `POST /api/v1/recommendations` returning ranked destinations with granular sub-score rationales.
  - Precision@10 Evaluation Benchmark (`scripts/eval_recommender.py`):
    - Evaluated against labeled test set (`data/labelled_recommender_set.csv`).
    - Demonstrated **Precision@10: 100.00%**, meeting and exceeding the target threshold of `>= 70.00%`.
  - Background Recertification Scheduler (`app/passport/scheduler.py`):
    - Discovers stale Passports older than 25 days (or 10 seconds in demo mode) and enqueues background `certify` jobs.
    - Verified on-demand via `POST /api/v1/destinations/recertify-stale`.
  - Normalized Metrics Aggregation (`app/metrics/service.py`):
    - Queried from platform connectors (Discourse, Dev.to, Ghost) and persisted to `metrics` table.
    - Endpoints `POST /api/v1/publications/{id}/metrics` and `GET /api/v1/publications/{id}/metrics` tested and verified.
  - Test suite `tests/test_recommender_recertification_metrics.py` passing (8/8 tests, 103 passed total).
- **Phase 10: Flight Deck, CLI & Submission (Verified)**:
  - Flight Deck Interactive Dashboard (`static/index.html`, `static/style.css`, `static/app.js`):
    - Dark mode glassmorphism UI served natively at root `/` via FastAPI StaticFiles.
    - Real-time Passport explorer with L0-L4 level progression badges, health progress meters, and cryptographic schema fingerprints.
    - Synchronous Preflight Court simulator with live PASS/REWRITE/BLOCK rulings and auto-fixed diff preview.
    - Idempotency & publication console with live job telemetry polling, manifest inspector, and cached replay testing.
    - Chaos MockHub fault generator with interactive "Break Dev.to API" trigger demonstrating automated schema drift detection, auto-demotion to L0, and alerting.
    - Human-in-the-loop rules capture extractor and audit log confirmation workflow.
  - Batch Runner CLI (`cli/batch_runner.py`):
    - Multi-file content ingestion (Markdown with frontmatter, pure Markdown, or JSON).
    - Stable content-hashed idempotency key generation, automated destination routing, and job polling.
    - Produces `<stem>_result.json` and `<stem>_manifest.json` in output directory.
    - Unit tests in `tests/test_batch_runner.py` (4/4 passed).
  - Production Hard-Cases Verification Suite (`tests/test_hard_cases.py`):
    - 14 automated edge-case scenarios covering network timeouts, 429 backoff rescheduling, 401/403 expired auth, 422 rejected content, title/body truncation, unsupported media, frequency caps, no-promo enforcement, schema drift auto-demotion, messy CSV imports, language divergence warnings, AI disclosures, and secrets redaction.
    - 14/14 passed.
  - OpenAPI 3.1 Contract Specification (`openapi.yaml`):
    - Full OpenAPI 3.1.0 schema generated and committed at root.
    - Verified by CI regression test `tests/test_openapi_contract.py` (1/1 passed).
  - Complete Submission Documentation:
    - `README.md` with under 10 commands quickstart, Mermaid architecture diagram, core concepts, and error codes table.
    - `REPORT.md` 2-4 pages technical report with benchmark tables, hard-case resolutions, trade-offs, and live session rehearsal guide.
    - `SOURCES.md` confirming commercial license compliance, zero AGPL dependencies in shipping code, and protocol attributions.
    - `AI_USE.md` providing full transparency and disclosure of AI assistance.
  - Final Test Suite Verification: **122 passed, 0 failures** in 9.4s. Ruff checks: **0 errors**.



