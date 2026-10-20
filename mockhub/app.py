"""Chaos Mock Hub: mock platform imitating Discourse, Dev.to, and Partner Webhook with X-Chaos faults."""

import asyncio
import hashlib
import hmac
import time
from typing import Any

from fastapi import FastAPI, Header, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Chaos Mock Hub", version="1.0.0")

# In-memory post store enabling real stateful get_status & delete checks
STORE: dict[str, dict[str, Any]] = {}
GLOBAL_CHAOS: dict[str, Any] = {"fault": None}
ID_COUNTER = 1000


class ChaosConfig(BaseModel):
    fault: str | None = Field(
        None, description="timeout | 429 | 401 | 422 | rename_field | slow | 403"
    )


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Chaos Mock Hub", "stored_posts": len(STORE)}


@app.post("/__chaos/config")
def set_chaos(config: ChaosConfig):
    GLOBAL_CHAOS["fault"] = config.fault
    return {"status": "chaos_configured", "current": GLOBAL_CHAOS}


@app.get("/__chaos/config")
def get_chaos():
    return {"current": GLOBAL_CHAOS}


@app.post("/__chaos/reset")
def reset_store():
    global STORE, ID_COUNTER, GLOBAL_CHAOS
    STORE.clear()
    GLOBAL_CHAOS = {"fault": None}
    ID_COUNTER = 1000
    return {"status": "reset_complete"}


async def check_chaos_fault(request: Request, x_chaos: str | None = None) -> Response | None:
    """Evaluates request-level or global chaos injection."""
    fault = x_chaos or GLOBAL_CHAOS.get("fault")
    if not fault:
        return None

    fault = fault.lower()
    if fault == "timeout":
        # Simulate gateway timeout
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"error": "Gateway Timeout", "message": "Upstream platform timed out."},
        )
    elif fault == "429":
        # Simulate rate limit backoff
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": "Rate limit exceeded", "message": "Slow down your requests."},
            headers={"Retry-After": "3", "X-RateLimit-Reset": str(int(time.time()) + 3)},
        )
    elif fault == "401":
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "Unauthorized",
                "message": "Invalid API token or expired credentials.",
            },
        )
    elif fault == "403":
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "Forbidden", "message": "Access revoked by destination owner."},
        )
    elif fault == "422":
        return JSONResponse(
            status_code=422,
            content={
                "error": "Unprocessable Entity",
                "message": "Post was rejected by community moderation filter.",
            },
        )
    elif fault == "slow":
        await asyncio.sleep(0.5)

    return None


# ------------------------------------------------------------------------------
# Discourse-Compatible Endpoints
# ------------------------------------------------------------------------------
@app.post("/posts.json")
async def discourse_create_post(
    request: Request,
    api_key: str | None = Header(None, alias="Api-Key"),
    api_username: str | None = Header(None, alias="Api-Username"),
    x_chaos: str | None = Header(None, alias="X-Chaos"),
):
    fault_resp = await check_chaos_fault(request, x_chaos)
    if fault_resp:
        return fault_resp

    if not api_key:
        return JSONResponse(status_code=401, content={"error": "Missing Api-Key"})

    data = await request.json()
    global ID_COUNTER
    ID_COUNTER += 1
    post_id = ID_COUNTER

    STORE[f"discourse_{post_id}"] = {
        "id": post_id,
        "title": data.get("title", ""),
        "raw": data.get("raw", ""),
        "topic_id": 42,
        "deleted": False,
    }

    # If chaos fault is rename_field, rename id to post_identifier to test Drift Canary
    fault = x_chaos or GLOBAL_CHAOS.get("fault")
    if fault == "rename_field":
        return {
            "post_identifier": post_id,
            "topic_id": 42,
            "post_number": 1,
            "live_url": f"http://localhost:8010/t/42/{post_id}",
        }

    return {
        "id": post_id,
        "topic_id": 42,
        "post_number": 1,
        "live_url": f"http://localhost:8010/t/42/{post_id}",
    }


@app.get("/posts/{post_id}.json")
async def discourse_get_post(
    post_id: int, request: Request, x_chaos: str | None = Header(None, alias="X-Chaos")
):
    fault_resp = await check_chaos_fault(request, x_chaos)
    if fault_resp:
        return fault_resp

    item = STORE.get(f"discourse_{post_id}")
    if not item or item.get("deleted"):
        return JSONResponse(status_code=404, content={"error": "Post not found"})
    return item


@app.delete("/posts/{post_id}.json")
async def discourse_delete_post(
    post_id: int, request: Request, x_chaos: str | None = Header(None, alias="X-Chaos")
):
    fault_resp = await check_chaos_fault(request, x_chaos)
    if fault_resp:
        return fault_resp

    item = STORE.get(f"discourse_{post_id}")
    if not item:
        return JSONResponse(status_code=404, content={"error": "Post not found"})
    item["deleted"] = True
    return {"deleted": True}


# ------------------------------------------------------------------------------
# Dev.to (Forem)-Compatible Endpoints
# ------------------------------------------------------------------------------
@app.post("/api/articles")
async def devto_create_article(
    request: Request,
    api_key: str | None = Header(None, alias="api-key"),
    x_chaos: str | None = Header(None, alias="X-Chaos"),
):
    fault_resp = await check_chaos_fault(request, x_chaos)
    if fault_resp:
        return fault_resp

    if not api_key:
        return JSONResponse(status_code=401, content={"error": "Missing api-key"})

    body = await request.json()
    article = body.get("article", {})
    global ID_COUNTER
    ID_COUNTER += 1
    art_id = ID_COUNTER

    canonical_url = article.get("canonical_url") or f"http://localhost:8010/devto/{art_id}"
    STORE[f"devto_{art_id}"] = {
        "id": art_id,
        "title": article.get("title", ""),
        "body_markdown": article.get("body_markdown", ""),
        "published": article.get("published", True),
        "url": canonical_url,
    }

    # Test Drift Canary: rename 'url' to 'live_link'
    fault = x_chaos or GLOBAL_CHAOS.get("fault")
    if fault == "rename_field":
        return {
            "id": art_id,
            "live_link": canonical_url,
            "published": True,
        }

    return {
        "id": art_id,
        "url": canonical_url,
        "published": True,
    }


@app.get("/api/articles/{article_id}")
async def devto_get_article(
    article_id: int, request: Request, x_chaos: str | None = Header(None, alias="X-Chaos")
):
    fault_resp = await check_chaos_fault(request, x_chaos)
    if fault_resp:
        return fault_resp

    item = STORE.get(f"devto_{article_id}")
    if not item:
        return JSONResponse(status_code=404, content={"error": "Article not found"})
    return item


@app.put("/api/articles/{article_id}")
async def devto_update_article(
    article_id: int,
    request: Request,
    x_chaos: str | None = Header(None, alias="X-Chaos"),
):
    """Dev.to has no true delete endpoint; delete is implemented via unpublishing (published=false)."""
    fault_resp = await check_chaos_fault(request, x_chaos)
    if fault_resp:
        return fault_resp

    item = STORE.get(f"devto_{article_id}")
    if not item:
        return JSONResponse(status_code=404, content={"error": "Article not found"})

    body = await request.json()
    article_updates = body.get("article", {})
    item.update(article_updates)
    return item


# ------------------------------------------------------------------------------
# Webhook HMAC Partner Receiver Endpoint
# ------------------------------------------------------------------------------
@app.post("/partner/webhook")
async def partner_webhook_receiver(
    request: Request,
    x_signature: str | None = Header(None, alias="X-IncuBrix-Signature"),
    x_chaos: str | None = Header(None, alias="X-Chaos"),
):
    fault_resp = await check_chaos_fault(request, x_chaos)
    if fault_resp:
        return fault_resp

    raw_body = await request.body()
    body_str = raw_body.decode("utf-8")

    # Validate HMAC signature: t=<timestamp>,v1=<sig>
    if not x_signature or "t=" not in x_signature or "v1=" not in x_signature:
        return JSONResponse(
            status_code=401,
            content={"error": "Missing or malformed X-IncuBrix-Signature"},
        )

    parts = dict(part.split("=", 1) for part in x_signature.split(","))
    timestamp = parts.get("t")
    sig = parts.get("v1")

    # Reject replay attacks older than 300 seconds
    try:
        ts_int = int(timestamp)
        if abs(time.time() - ts_int) > 300:
            return JSONResponse(status_code=401, content={"error": "Signature timestamp expired"})
    except Exception:
        return JSONResponse(status_code=401, content={"error": "Invalid timestamp format"})

    # Validate signature against partner secret
    partner_secret = "incubrix_partner_secret"
    expected = hmac.new(
        partner_secret.encode("utf-8"),
        f"{timestamp}.{body_str}".encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(sig, expected):
        return JSONResponse(status_code=401, content={"error": "HMAC signature mismatch"})

    global ID_COUNTER
    ID_COUNTER += 1
    event_id = f"evt_{ID_COUNTER}"
    STORE[f"webhook_{event_id}"] = {"event_id": event_id, "body": body_str}

    return {"status": "received", "event_id": event_id}
