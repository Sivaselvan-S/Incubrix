# AI Usage Disclosure & Pair-Programming Record

> **LongTail Passport &bull; IncuBrix Engineering Assessment 4**  
> In accordance with the assessment instructions, this document provides full transparency on how AI assistance was utilized throughout the design, implementation, and verification of the project.

---

## 1. Tool Disclosure

* **AI Assistant**: Antigravity IDE (powered by Gemini models via Google DeepMind Advanced Agentic Coding).
* **Role**: Senior backend engineering pair-programmer collaborating on architecture, implementation, test scaffolding, and documentation.
* **Operating Mode**: Milestone-driven iterative pair programming with continuous automated test verification (`pytest`) and Git commit history tracking.

---

## 2. Scope of AI Assistance

AI assistance was utilized in the following areas:

1. **Test Scaffolding & Edge-Case Generation**:
   * Assisting in compiling the 42-scenario table-driven test matrix (`tests/rules_cases.yaml`) to ensure comprehensive coverage across format boundary limits (e.g. exactly at limit vs. 1 character over limit).
   * Generating the 13 required hard-case verification scenarios in `tests/test_hard_cases.py`.
2. **Schema & Contract Structuring**:
   * Scaffolding initial Pydantic v2 schemas for connector manifests, surface specifications, and rule context objects.
   * Assisting in drafting pinned JSON Schemas under `schemas/` for the Drift Canary.
3. **Connector Boilerplate Reduction**:
   * Writing boilerplate HTTP request payloads for repetitive endpoints across Discourse, Dev.to, Ghost Admin API, Slack Web API, and Hashnode GraphQL.
4. **Flight Deck UI Frontend**:
   * Styling the dark-mode glassmorphic single-page dashboard (`static/index.html`, `static/style.css`, `static/app.js`) to provide an interactive demonstration console for live review.

---

## 3. Human Engineering Decisions & Critical Oversight

All core architectural decisions, invariant designs, and critical code paths were reviewed and validated by human engineering:

* **Elimination of Distributed Broker Complexity**: Explicit decision to reject Redis/Celery in favor of PostgreSQL's native `SELECT ... FOR UPDATE SKIP LOCKED` for transactional atomicity, simpler deployment, and lower resource overhead.
* **Pure Deterministic Function for Preflight Court**: Strict insistence that `evaluate()` remain a pure, zero-I/O function taking immutable Pydantic models, ensuring instantaneous, completely deterministic test execution.
* **Zero External Dependencies for Ghost JWT Signer**: Deliberate design choice to write a standard library HS256 JWT generator using Python's built-in `hmac`, `hashlib`, and `base64` modules, eliminating heavy C-extension crypto dependencies.
* **Two-Phase Intent-First Idempotency Protocol**: Defining the exact state machine (`INTENT` $\rightarrow$ `UNKNOWN` $\rightarrow$ `SUCCEEDED` / `FAILED`) and reconciliation via invisible HTML comment markers (`<!-- ibx:<key> -->`).
* **Rigorous Verification Gate**: Every milestone was required to achieve 100% test pass rates and zero linter warnings before declaring completion and committing to Git.
