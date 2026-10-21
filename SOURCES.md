# Sources, Attributions & Dependency Licensing

> **LongTail Passport &bull; IncuBrix Engineering Assessment 4**  
> All dependencies used in this project are under permissive, commercially compatible open-source licenses.  
> **AGPL Compliance**: Zero AGPL dependencies are used in the shipped application code.

---

## 1. Third-Party Dependencies & Licenses

| Dependency | Version | License | Commercial Use | Purpose |
|---|---|---|---|---|
| **Python** | 3.11+ / 3.13.2 | PSF License | Permitted | Core programming language runtime |
| **FastAPI** | $\ge 0.115.0$ | MIT | Permitted | High-performance asynchronous web API gateway |
| **Pydantic** | $\ge 2.10.0$ | MIT | Permitted | Data validation, contract models, and settings management |
| **Pydantic-Settings** | $\ge 2.7.0$ | MIT | Permitted | Environment variable parsing and type enforcement |
| **SQLAlchemy** | $\ge 2.0.36$ | MIT | Permitted | Object-relational mapping, transactional sessions, and DB schemas |
| **httpx** | $\ge 0.28.0$ | BSD-3-Clause | Permitted | Asynchronous and synchronous HTTP client for connector runtimes |
| **uvicorn** | $\ge 0.34.0$ | BSD-3-Clause | Permitted | ASGI web server for API and Chaos MockHub services |
| **PyYAML** | $\ge 6.0.2$ | MIT | Permitted | Parsing connector manifests (`manifest.yaml`) and test scenarios |
| **pytest** | $\ge 8.3.0$ | MIT | Permitted | Automated unit, integration, and contract test runner |
| **pytest-asyncio** | $\ge 0.25.0$ | Apache-2.0 | Permitted | Async test execution fixtures |
| **ruff** | $\ge 0.9.0$ | MIT / Apache-2.0 | Permitted | High-speed static analysis, linting, and formatting |
| **jsonschema** | $\ge 4.23.0$ | MIT | Permitted | Validation for Drift Canary schema enforcement |

---

## 2. Platform Protocols & Standards Attributions

* **Media RSS 2.0 Specification**:
  * Namespace: `xmlns:media="http://search.yahoo.com/mrss/"`
  * Standard: Media RSS (MRSS) 2.0 specification for media syndication and enclosures.
* **ActivityPub / Lemmy API v3**:
  * Standard: W3C ActivityPub specification and Lemmy HTTP API v3 documentation.
  * Auth: JSON Web Tokens (JWT) for authentication.
* **Ghost Admin API v5**:
  * Specification: Ghost Admin API v5 token format using HS256 JWT with `kid: id` header and `aud: "/admin/"` claim.
  * Implementation: Pure-Python standard library implementation (`hmac`, `hashlib`, `base64`, `json`) requiring zero external dependencies.
* **Discourse API**:
  * Documentation: Discourse API documentation for `/posts.json`, topic creation, and categorization.
  * Headers: `Api-Key` and `Api-Username` header conventions.
* **Dev.to / Forem API**:
  * Documentation: Forem API v0 specification for article creation (`/api/articles`) and unpublishing.
* **Slack Web API**:
  * Specification: Slack Web API (`chat.postMessage`, `chat.delete`, `conversations.history`).
* **Hashnode GraphQL API**:
  * Specification: Hashnode Public GraphQL API (`publishPost`, `removePost`).
* **Google Fonts**:
  * Typography: *Plus Jakarta Sans* (OFL License) and *JetBrains Mono* (OFL License) used in the Mission Flight Deck UI.

---

## 3. License Suitability Audit

A comprehensive review of the project dependency graph confirms:
* **No AGPL or Copyleft Contamination**: Neither Lemmy's AGPL server code nor Ghost's AGPL backend is imported as a Python package. Both Lemmy and Ghost are orchestrated strictly as external black-box Docker containers, interacting only over standard HTTP REST/GraphQL boundaries.
* **Commercially Viable**: Every Python package imported into `app/` and `cli/` is licensed under MIT, BSD-3-Clause, Apache-2.0, or Python Software Foundation (PSF) licenses, permitting unrestricted commercial distribution and sublicensing.
