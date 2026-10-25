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


# ------------------------------------------------------------------------------
# Lemmy-Compatible Endpoints
# ------------------------------------------------------------------------------
@app.post("/api/v3/user/login")
async def lemmy_login(request: Request, x_chaos: str | None = Header(None, alias="X-Chaos")):
    fault = await check_chaos_fault(request, x_chaos)
    if fault:
        return fault
    return {"jwt": "mock_lemmy_jwt_token_123", "verify_2fa_ssl": False}


@app.post("/api/v3/post")
async def lemmy_create_post(
    request: Request,
    authorization: str | None = Header(None, alias="Authorization"),
    x_chaos: str | None = Header(None, alias="X-Chaos"),
):
    fault = await check_chaos_fault(request, x_chaos)
    if fault:
        return fault

    data = await request.json()
    auth_token = data.get("auth") or (authorization.replace("Bearer ", "") if authorization else None)
    if not auth_token:
        return JSONResponse(status_code=401, content={"error": "not_logged_in"})

    global ID_COUNTER
    ID_COUNTER += 1
    post_id = ID_COUNTER
    ap_id = f"http://localhost:8536/post/{post_id}"
    item = {
        "id": post_id,
        "name": data.get("name", "Untitled Lemmy Post"),
        "body": data.get("body", ""),
        "community_id": data.get("community_id", 1),
        "deleted": False,
        "ap_id": ap_id,
    }
    STORE[f"lemmy_{post_id}"] = item
    return {
        "post_view": {
            "post": item
        }
    }


@app.get("/api/v3/post")
async def lemmy_get_post(id: int, request: Request, x_chaos: str | None = Header(None, alias="X-Chaos")):
    fault = await check_chaos_fault(request, x_chaos)
    if fault:
        return fault

    item = STORE.get(f"lemmy_{id}")
    if not item:
        return JSONResponse(status_code=404, content={"error": "couldnt_find_post"})
    return {"post_view": {"post": item}}


@app.post("/api/v3/post/delete")
async def lemmy_delete_post(request: Request, x_chaos: str | None = Header(None, alias="X-Chaos")):
    fault = await check_chaos_fault(request, x_chaos)
    if fault:
        return fault

    data = await request.json()
    post_id = data.get("post_id")
    item = STORE.get(f"lemmy_{post_id}")
    if not item:
        return JSONResponse(status_code=404, content={"error": "couldnt_find_post"})

    item["deleted"] = data.get("deleted", True)
    return {"post_view": {"post": item}}


@app.get("/api/v3/site")
async def lemmy_site():
    return {"site_view": {"site": {"name": "Mock Lemmy Instance", "id": 1}}}


# ------------------------------------------------------------------------------
# Ghost Admin API Endpoints
# ------------------------------------------------------------------------------
@app.get("/ghost/api/admin/site")
@app.get("/ghost/api/admin/site/")
async def ghost_site():
    return {"site": {"title": "Mock Ghost Instance", "version": "5.0"}}
@app.post("/ghost/api/admin/posts")
@app.post("/ghost/api/admin/posts/")
async def ghost_create_post(
    request: Request,
    authorization: str | None = Header(None, alias="Authorization"),
    x_chaos: str | None = Header(None, alias="X-Chaos"),
):
    fault = await check_chaos_fault(request, x_chaos)
    if fault:
        return fault

    if not authorization or not authorization.startswith("Ghost "):
        # Real Ghost expects Ghost <token> or Bearer <token>
        if not authorization or not authorization.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"errors": [{"message": "Invalid token"}]})

    data = await request.json()
    posts_payload = data.get("posts", [{}])[0]

    global ID_COUNTER
    ID_COUNTER += 1
    ghost_id = f"64f{ID_COUNTER:06x}a1234567890a"
    post_url = f"http://localhost:2368/{ghost_id}/"

    STORE[f"ghost_{ghost_id}"] = {
        "id": ghost_id,
        "title": posts_payload.get("title", "Untitled Ghost Post"),
        "html": posts_payload.get("html", ""),
        "url": post_url,
        "canonical_url": posts_payload.get("canonical_url"),
        "status": posts_payload.get("status", "published"),
    }
    return {
        "posts": [
            {
                "id": ghost_id,
                "title": posts_payload.get("title", ""),
                "url": post_url,
                "status": "published",
            }
        ]
    }


@app.get("/ghost/api/admin/posts/{post_id}")
@app.get("/ghost/api/admin/posts/{post_id}/")
async def ghost_get_post(post_id: str, request: Request, x_chaos: str | None = Header(None, alias="X-Chaos")):
    fault = await check_chaos_fault(request, x_chaos)
    if fault:
        return fault

    item = STORE.get(f"ghost_{post_id}")
    if not item:
        return JSONResponse(status_code=404, content={"errors": [{"message": "Post not found."}]})
    return {"posts": [item]}


@app.delete("/ghost/api/admin/posts/{post_id}")
@app.delete("/ghost/api/admin/posts/{post_id}/")
async def ghost_delete_post(post_id: str, request: Request, x_chaos: str | None = Header(None, alias="X-Chaos")):
    fault = await check_chaos_fault(request, x_chaos)
    if fault:
        return fault

    item = STORE.pop(f"ghost_{post_id}", None)
    if not item:
        return JSONResponse(status_code=404, content={"errors": [{"message": "Post not found."}]})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------------------
# Hashnode GraphQL Endpoint
# ------------------------------------------------------------------------------
@app.post("/graphql")
async def hashnode_graphql(
    request: Request,
    authorization: str | None = Header(None, alias="Authorization"),
    x_chaos: str | None = Header(None, alias="X-Chaos"),
):
    fault = await check_chaos_fault(request, x_chaos)
    if fault:
        return fault

    data = await request.json()
    query = data.get("query", "")
    variables = data.get("variables", {})

    if "publishPost" in query:
        global ID_COUNTER
        ID_COUNTER += 1
        post_id = f"hn_{ID_COUNTER}"
        live_url = f"https://blog.hashnode.dev/post-{post_id}"
        input_data = variables.get("input", {})
        STORE[f"hashnode_{post_id}"] = {
            "id": post_id,
            "url": live_url,
            "title": input_data.get("title", "Hashnode Post"),
            "deleted": False,
        }
        return {
            "data": {
                "publishPost": {
                    "post": {
                        "id": post_id,
                        "url": live_url,
                        "title": input_data.get("title", "Hashnode Post"),
                    }
                }
            }
        }
    elif "removePost" in query or "delete" in query.lower():
        target_id = variables.get("id") or str(ID_COUNTER)
        item = STORE.get(f"hashnode_{target_id}")
        if item:
            item["deleted"] = True
        return {"data": {"removePost": {"post": {"id": target_id}}}}

    target_id = variables.get("id") or str(ID_COUNTER)
    item = STORE.get(f"hashnode_{target_id}")
    if item and not item.get("deleted"):
        return {"data": {"post": item}}
    return {"data": {"post": None}}


# ------------------------------------------------------------------------------
# Slack Web API Endpoints
# ------------------------------------------------------------------------------
@app.post("/api/chat.postMessage")
async def slack_post_message(
    request: Request,
    authorization: str | None = Header(None, alias="Authorization"),
    x_chaos: str | None = Header(None, alias="X-Chaos"),
):
    fault = await check_chaos_fault(request, x_chaos)
    if fault:
        return fault

    data = await request.json()
    channel = data.get("channel", "general")
    text = data.get("text", "")

    global ID_COUNTER
    ID_COUNTER += 1
    ts = f"1729425{ID_COUNTER:03d}.000100"
    STORE[f"slack_{ts}"] = {"channel": channel, "ts": ts, "text": text, "deleted": False}
    return {
        "ok": True,
        "channel": channel,
        "ts": ts,
        "message": {"text": text, "type": "message", "user": "U123456", "ts": ts},
    }


@app.post("/api/chat.delete")
async def slack_delete_message(
    request: Request,
    authorization: str | None = Header(None, alias="Authorization"),
    x_chaos: str | None = Header(None, alias="X-Chaos"),
):
    fault = await check_chaos_fault(request, x_chaos)
    if fault:
        return fault

    data = await request.json()
    ts = data.get("ts")
    item = STORE.get(f"slack_{ts}")
    if not item:
        return {"ok": False, "error": "message_not_found"}
    item["deleted"] = True
    return {"ok": True, "channel": data.get("channel"), "ts": ts}


@app.get("/api/conversations.history")
@app.get("/api/chat.get")
async def slack_get_message(
    channel: str = "general",
    latest: str | None = None,
    ts: str | None = None,
    request: Request = None,
    x_chaos: str | None = Header(None, alias="X-Chaos"),
):
    fault = await check_chaos_fault(request, x_chaos)
    if fault:
        return fault

    target_ts = ts or latest
    if target_ts:
        item = STORE.get(f"slack_{target_ts}")
        if not item or item.get("deleted"):
            return {"ok": False, "error": "message_not_found"}
        return {"ok": True, "messages": [item]}

    return {"ok": True, "messages": [v for k, v in STORE.items() if k.startswith("slack_") and not v.get("deleted")]}

