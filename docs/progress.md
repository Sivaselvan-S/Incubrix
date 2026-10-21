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
| Phase 7: Real Instances & Extra Connectors | Planned | Pending Phase 6 | None |
| Phase 8: Tailoring, Catalogue & Rules Capture | Planned | Pending Phase 7 | None |
| Phase 9: Recommender, Recertification & Metrics | Planned | Pending Phase 8 | None |
| Phase 10: Flight Deck, CLI & Submission | Planned | Pending Phase 9 | None |

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
  - Partner webhook HMAC verification and signature replay expiration verified.
- **Phase 6: Drift Canary & Certification Harness (Verified)**:
  - Pinned JSON schemas created under `schemas/{discourse,devto,webhook_hmac}/publish.json`.
  - Deterministic `schema_fingerprint` calculated from sorted field paths and types.
  - Full 7-step certification harness (validate -> publish -> drift check -> live check -> read status -> delete -> confirm deleted -> evidence bundle).
  - Evidence JSON bundled and saved with MinIO storage adapter and local fallback.
  - Upstream field rename detected (`CERT_DRIFT_DETECTED`), auto-demotes destination and Passport to `L0`, creates Alert row, and blocks in Preflight Court.
  - Endpoints `GET /api/v1/destinations/{id}/passport` and `POST /api/v1/destinations/{id}/certify` tested and verified.
