# IncuBrix Engineering Assessment 4 - Submission Form Data Reference

> **Submission Form Companion Guide**  
> Use the data, links, and measured figures in this document to populate the official Excel file (`Submission Form.xlsx`) provided by IncuBrix.

---

## 1. Must-Haves Checklist (All Must Pass)

| # | Must-Have Item | Status | How Verified & Link to Evidence |
|---|---|---|---|
| **1** | Exact connector contract (Appendix A methods, manifest, error codes) | **PASS (Yes)** | `app/connectors/base.py`<br>`tests/test_connector_runtime.py`<br>`app/runtime/router.py` |
| **2** | Six Core connectors certified: Discourse, Lemmy, Dev.to, Ghost, Webhook HMAC, Assisted | **PASS (Yes)** | `test_pack/outputs/certification_pack/`<br>`scripts/certify_all_core_connectors.py` |
| **3** | Configuration, not code: Adding another forum/community is one catalogue row | **PASS (Yes)** | `app/db/models.py` (`DestinationModel`)<br>`app/api/routes/destinations.py`<br>`data/real_destinations_150.csv` |
| **4** | Rules checked before every post (frequency cap, self-promo, link policy, AI disclosure) | **PASS (Yes)** | `app/rules/court.py`<br>`tests/test_preflight_court.py` (42 scenarios, 0 missed violations) |
| **5** | Never spam, never cheat: Test posts only to test instances, deleted in 10m, rate limits honored | **PASS (Yes)** | `app/connectors/{discourse,devto,ghost,lemmy}/connector.py`<br>`test_pack/outputs/hard_cases_results.txt` (#2 rate limit backoff) |
| **6** | Safe retries: Same idempotency key never creates second post even after timeout | **PASS (Yes)** | `app/idempotency/service.py`<br>`test_pack/outputs/hard_cases_results.txt` (#1 timeout & retry) |
| **7** | Secrets protected and simulation mode: Tokens never in logs or repo; mock platforms | **PASS (Yes)** | `app/logging.py` (`SecretRedactionFilter`)<br>`mockhub/app.py`<br>`test_pack/outputs/hard_cases_results.txt` (#14) |
| **8** | Local test instances: `docker compose up` starts service + local Lemmy and Ghost instances | **PASS (Yes)** | `docker-compose.yml`<br>`scripts/init_local_instances.ps1` / `.sh` |
| **9** | Integration Standard followed and live demo works for the review period | **PASS (Yes)** | Full 10-point Integration Standard compliance verified below |

---

## 2. Levels Reached

### Core (Required - 15 Marks)
* **All must-haves pass**: Yes (all 9 pass).
* **Each Core connector passes full certification run with stored evidence**: Yes (`test_pack/outputs/certification_pack/`).
* **Errors from each platform mapped to shared error codes**: Yes (`app/connectors/base.py`, error mapping in manifests).

### Advanced (15 Marks)
* **Catalogue import**: 1,000 rows in < 5 minutes (achieved **1.84s**), URL normalization, row-by-row error report (`app/catalogue/importer.py`).
* **Rules capture**: Community policy text parsed, human-in-the-loop review with audit logs (`app/rules_capture/service.py`, `app/api/routes/rules.py`).
* **Relevance score**: 1 to 5 against IncuBrix audience with explanation (`app/db/models.py`, `data/real_destinations_150.csv`).
* **Tailoring**: Per-destination fitting title and text, discussion framing for forums, canonical URLs for articles, word-boundary truncation (`app/tailor/engine.py`).
* **Three more connectors**: Hashnode, Slack, and MRSS video feed (`app/connectors/{hashnode,slack,mrss_feed}/`).

### Outstanding (10 Marks)
* **Recommender**: Multi-criteria ranking by fit (audience, rules, past results), Precision@10 evaluated at **100.00%** on labeled test set (`scripts/eval_recommender.py`, `data/labelled_recommender_set.csv`).
* **Metrics**: `fetch_metrics` implemented on Discourse, Dev.to, and Ghost, normalized to views, likes, comments, shares, clicks (`app/metrics/service.py`).
* **Recertification**: Scheduler re-tests destinations before 30 days; failing destination demoted and alerted (`app/passport/scheduler.py`).
* **Real catalogue**: 150 real, researched destinations with rules, relevance score, and connector type (`data/real_destinations_150.csv`).

---

## 3. Integration Standard (20 Marks / 2 Marks Each)

| # | Requirement | Status | Evidence / Verification Location |
|---|---|---|---|
| **1** | One-command start and test (`docker compose up`, `pytest`) | **YES** | `docker-compose.yml`, `pytest -v` (122 tests passed in 9.4s without API keys), `.env.example` |
| **2** | Documented HTTP API (`openapi.yaml` OpenAPI 3.1 matching service, all routes under `/api/v1/`) | **YES** | `openapi.yaml`, regression test `tests/test_openapi_contract.py` |
| **3** | Background jobs (>2s runs as job: 202 with `job_id`, status polling, HMAC callback) | **YES** | `app/queue/worker.py`, `app/api/routes/jobs.py`, `tests/test_idempotency_and_jobs.py` |
| **4** | Safe retries (`Idempotency-Key` header on every POST) | **YES** | `app/idempotency/service.py`, `tests/test_idempotency_and_jobs.py` |
| **5** | Clear errors (JSON envelope `{"error": {"code", "message", "retryable", "details"}}`) | **YES** | `app/api/main.py`, standard error codes table in `README.md` |
| **6** | Configuration (all settings from env vars or config, no hardcoded secrets) | **YES** | `app/config.py`, `.env.example` |
| **7** | Files in, files out (inputs via upload or URL, outputs stored in MinIO/S3) | **YES** | `app/storage/minio_client.py`, download links in manifests |
| **8** | Logs and health (Structured JSON logs, `X-Correlation-Id`, `/health`, `/ready`) | **YES** | `app/logging.py`, `app/api/routes/health.py`, `tests/test_foundation.py` |
| **9** | Output manifest (JSON manifest with models, timings, seed, cost, warnings, licence) | **YES** | `app/queue/worker.py` (`generate_output_manifest`) |
| **10** | Batch runner (CLI running test inputs against API, writing results to output folder) | **YES** | `cli/batch_runner.py`, `tests/test_batch_runner.py` |

---

## 4. Metrics Tab (Exact Measured Numbers)

| Metric | Measured Number / Value | Evidence Link |
|---|---|---|
| **Certification** | 6 core connectors certified (100% pass rate); avg 0.38s run time | `test_pack/outputs/certification_pack/` |
| **Reliability** | 100% publish success rate in simulation/mocks; **0 duplicate posts** under retry tests | `test_pack/outputs/hard_cases_results.txt` |
| **Rule Safety** | 42 / 42 rule violations caught (**0 missed violations**, 100% accuracy) | `tests/rules_cases.yaml`, `test_pack/logs/pytest_results.log#L19` |
| **Catalogue Ingestion** | 1,000 rows imported in **1.84 seconds** (< 5-min SLA); 0 duplicates allowed | `test_pack/inputs/destinations_1000.csv`, `tests/test_tailoring_catalogue_and_rules.py` |
| **Recommendation** | **100.00% Precision@10** on labeled test set (target: $\ge 70.00\%$) | `test_pack/outputs/recommender_evaluation.txt` |
| **Cost** | **$0.00** per 1,000 publications in standard simulation/mock and deterministic rule mode | `REPORT.md` Section 2 |
