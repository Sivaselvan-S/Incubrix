"""Asynchronous reachability validator for destination endpoint verification."""

import asyncio

import httpx


async def check_url_reachability(
    url: str,
    timeout: float = 3.0,
    headers: dict[str, str] | None = None,
) -> tuple[bool, int, str | None]:
    """Tests if a destination URL responds successfully to HEAD or GET within the timeout."""
    req_headers = {"User-Agent": "LongTailPassport-Canary/1.0", **(headers or {})}
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            try:
                resp = await client.head(url, headers=req_headers)
                if resp.status_code < 400:
                    return True, resp.status_code, None
            except Exception:
                pass

            # Fallback to GET for servers that block HEAD requests
            resp = await client.get(url, headers=req_headers)
            return resp.status_code < 400, resp.status_code, None
    except httpx.TimeoutException:
        return False, 0, "Connection timeout"
    except Exception as exc:
        return False, 0, str(exc)


async def batch_check_reachability(
    urls: list[str],
    max_concurrency: int = 25,
    timeout: float = 3.0,
) -> dict[str, bool]:
    """Checks reachability for a batch of URLs with bounded concurrency."""
    semaphore = asyncio.Semaphore(max_concurrency)
    results: dict[str, bool] = {}

    async def _check(url: str):
        async with semaphore:
            reachable, _, _ = await check_url_reachability(url, timeout=timeout)
            results[url] = reachable

    tasks = [_check(url) for url in urls]
    await asyncio.gather(*tasks, return_exceptions=True)
    return results
