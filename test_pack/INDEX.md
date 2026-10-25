# Test Pack Index & Evidence Verification Map

> **IncuBrix Engineering Assessment 4 &bull; Long-Tail Destination Network**  
> This index links every architectural claim, quantitative benchmark, hard case, and SLA requirement documented in `REPORT.md` to concrete input files, execution logs, and output evidence artifacts.

---

## 1. Directory Structure

```text
test_pack/
├── INDEX.md                                # This verification map
├── inputs/                                 # All input datasets and test articles
│   ├── sample_articles/                    # Markdown & JSON test articles (4 items)
│   │   ├── article_01_devto_distribution.md
│   │   ├── article_02_discourse_discussion.md
│   │   ├── article_03_ghost_saas_metrics.md
│   │   └── article_04_ai_video_syndication.json
│   ├── real_destinations_150.csv           # 150 real researched destinations (20-column Appendix A schema)
│   ├── destinations_1000.csv               # 1,000-row streaming ingestion benchmark dataset
│   ├── labelled_recommender_set.csv        # Ground truth destination relevance matrix
│   └── rules_cases.yaml                    # 42-case boundary test matrix for Preflight Court
├── outputs/                                # Verifiable test outputs and evidence
│   ├── certification_pack/                 # 6 Core certified connectors' run records + SVG screenshots
│   │   ├── discourse/                      # Full 7-step run (L4 certified)
│   │   ├── devto/                          # Full 7-step run (L4 certified)
│   │   ├── ghost/                          # Full 7-step run (L4 certified)
│   │   ├── lemmy/                          # Full 7-step run (L4 certified)
│   │   ├── webhook_hmac/                   # Full bridge verification (L2 certified)
│   │   └── assisted/                       # Direct MinIO package generation (L1 certified)
│   ├── recommender_evaluation.txt          # Precision@10 benchmark execution (100.00% >= 70%)
│   └── hard_cases_results.txt              # 14/14 automated production failure cases passed
└── logs/
    └── pytest_results.log                  # Complete 122/122 pytest test execution log
```

---

## 2. Claim-to-File Evidence Verification Matrix

| Claim in REPORT.md / Brief | Benchmark / SLA Target | Measured Result | Supporting Evidence File in Test Pack |
|---|---|---|---|
| **Streaming Catalogue Ingestion** | 1,000 rows in < 5.0 minutes | **1.84 seconds** | `inputs/destinations_1000.csv`<br>`logs/pytest_results.log#L23` (`test_tailoring_catalogue_and_rules.py`) |
| **Real Catalogue Dataset** | $\ge 150$ real, relevant destinations | **150 researched destinations** | `inputs/real_destinations_150.csv` (all 20 Appendix A columns) |
| **Recommender Precision@10** | $\ge 70.00\%$ precision | **100.00% Precision@10** | `inputs/labelled_recommender_set.csv`<br>`outputs/recommender_evaluation.txt` |
| **Preflight Court Zero Missed Rules** | 0 missed violations | **0 missed (100% caught)** | `inputs/rules_cases.yaml`<br>`logs/pytest_results.log#L19` (`test_preflight_court.py`) |
| **Zero Duplicate Posts Under Retries** | Exactly 0 duplicates | **0 duplicates (100% safe)** | `outputs/hard_cases_results.txt` (`test_hard_case_1_timeout_then_retry`) |
| **All 6 Core Connectors Certified** | Must-Have #2 Pass | **All 6 Core Certified** | `outputs/certification_pack/{discourse,devto,ghost,lemmy,webhook_hmac,assisted}` |
| **Canary Upstream Schema Drift** | Auto-demote to L0 on mismatch | **CERT_DRIFT_DETECTED** | `outputs/hard_cases_results.txt` (`test_hard_case_9_schema_drift`) |
| **Total Automated Test Suite** | 100% green without API keys | **122 / 122 passed (0 failures)** | `logs/pytest_results.log` |

---

## 3. Production Hard Cases Cross-Reference

| # | Hard Case Scenario | Expected Behavior | Verification Proof |
|---|---|---|---|
| **1** | Timeout followed by retry with same key | No duplicate post; returns original URL via `<!-- ibx:<key> -->` reconciliation | `outputs/hard_cases_results.txt#L9` |
| **2** | HTTP 429 with reset time | Reschedules job to execute after `Retry-After` epoch | `outputs/hard_cases_results.txt#L9` |
| **3** | Expired authentication token (401) | Maps to `CONNECTION_AUTH_EXPIRED`, pauses destination | `outputs/hard_cases_results.txt#L9` |
| **4** | Content rejection (422) | Preserves platform error details in JSON envelope | `outputs/hard_cases_results.txt#L9` |
| **5** | Title / body length exceeding limit | Word-boundary truncation with `...` or `DEST_SPEC_VIOLATION` | `outputs/hard_cases_results.txt#L9` |
| **6** | Unsupported media format | Returns `BLOCK DEST_SPEC_VIOLATION` with field reasons | `outputs/hard_cases_results.txt#L9` |
| **7** | Second post inside frequency cap | Reschedules with `earliest_allowed_at` window | `outputs/hard_cases_results.txt#L9` |
| **8** | Promotional post to non-promo community | Blocks with `DEST_RULE_PROMO_BLOCKED` | `outputs/hard_cases_results.txt#L9` |
| **9** | Upstream API renames a field | Drift Canary catches drift, demotes to L0, creates Alert row | `outputs/hard_cases_results.txt#L9` |
| **10** | CSV with duplicates and dirty URLs | URL normalization strips tracking parameters, skips dupes | `outputs/hard_cases_results.txt#L9` |
| **11** | Partner revokes HMAC access (403) | Maps to `CONNECTION_AUTH_EXPIRED` | `outputs/hard_cases_results.txt#L9` |
| **12** | Non-English community targeting | Emits explicit language mismatch warning | `outputs/hard_cases_results.txt#L9` |
| **13** | AI disclosure required | Appends standardized transparency footnote notice | `outputs/hard_cases_results.txt#L9` |
| **14** | Secrets leakage prevention | `SecretRedactionFilter` scrubs Bearer tokens and passwords | `outputs/hard_cases_results.txt#L9` |

---

## 4. How Reviewers Can Inspect and Reproduce

```bash
# 1. Run all 122 automated verification tests
pytest -v

# 2. Run the 14 production failure cases
pytest tests/test_hard_cases.py -v

# 3. Run the Recommender benchmark
python scripts/eval_recommender.py

# 4. Run the Batch Runner against test articles
python -m cli.batch_runner --input ./test_pack/inputs/sample_articles --out ./storage/batch_out

# 5. Re-run certification on all 6 Core connectors
python -m scripts.certify_all_core_connectors
```
