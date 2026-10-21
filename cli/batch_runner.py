"""Batch Runner CLI for LongTail Passport.

Usage:
    python -m cli.batch_runner --input <folder|file> --out <folder> --api http://localhost:8000 [--destination-id <id>]
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx


def parse_markdown_file(file_path: Path) -> dict[str, Any]:
    """Extracts frontmatter metadata and markdown content."""
    text = file_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    title = None
    body = text
    destination_id = None
    tags = []
    canonical_url = None

    # Check for basic frontmatter
    if text.startswith("---"):
        try:
            parts = text.split("---", 2)
            if len(parts) >= 3:
                fm_raw = parts[1].strip()
                body = parts[2].strip()
                for line in fm_raw.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        k = k.strip().lower()
                        v = v.strip().strip("\"'")
                        if k == "title":
                            title = v
                        elif k == "destination_id":
                            destination_id = v
                        elif k == "canonical_url":
                            canonical_url = v
                        elif k == "tags":
                            tags = [t.strip() for t in v.strip("[]").split(",") if t.strip()]
        except Exception:
            body = text

    # If title not in frontmatter, look for first markdown heading
    if not title:
        for line in lines:
            if line.startswith("# "):
                title = line[2:].strip()
                break

    # Fallback to file stem
    if not title:
        title = file_path.stem.replace("-", " ").replace("_", " ").title()

    return {
        "title": title,
        "body": body,
        "destination_id": destination_id,
        "tags": tags,
        "canonical_url": canonical_url,
    }


def parse_json_file(file_path: Path) -> dict[str, Any]:
    """Reads a JSON content definition."""
    data = json.loads(file_path.read_text(encoding="utf-8"))
    return {
        "title": data.get("title", file_path.stem),
        "body": data.get("body", ""),
        "destination_id": data.get("destination_id"),
        "tags": data.get("tags", []),
        "canonical_url": data.get("canonical_url"),
    }


def collect_input_files(input_path: Path) -> list[Path]:
    """Gathers all markdown and JSON files from a path or directory."""
    if input_path.is_file():
        return [input_path]
    if not input_path.is_dir():
        return []

    collected = []
    for ext in ("*.md", "*.markdown", "*.json"):
        collected.extend(input_path.glob(ext))
    return sorted(collected)


def poll_job(client: httpx.Client, api_url: str, job_id: str, timeout_s: float = 30.0) -> dict[str, Any]:
    """Polls a publication job until completion or timeout."""
    start_time = time.time()
    while time.time() - start_time < timeout_s:
        resp = client.get(f"{api_url}/api/v1/jobs/{job_id}")
        if resp.status_code == 200:
            data = resp.json()
            status = data.get("status")
            if status in ("succeeded", "failed"):
                return data
        time.sleep(0.5)

    raise TimeoutError(f"Job {job_id} did not complete within {timeout_s}s")


def run_batch(
    input_path: Path,
    out_dir: Path,
    api_url: str,
    default_dest_id: str | None = None,
    poll_timeout: float = 30.0,
) -> int:
    """Executes batch publication and stores output manifests."""
    out_dir.mkdir(parents=True, exist_ok=True)
    files = collect_input_files(input_path)
    if not files:
        print(f"[ERROR] No valid input files found at '{input_path}'")
        return 1

    print(f"[INFO] Discovered {len(files)} content file(s) to process.")
    print(f"[INFO] Target API: {api_url}")
    print(f"[INFO] Output Directory: {out_dir}")

    client = httpx.Client(timeout=15.0)

    # 1. Health check
    try:
        health_resp = client.get(f"{api_url}/health")
        if health_resp.status_code != 200:
            print(f"[ERROR] API is unhealthy: HTTP {health_resp.status_code}")
            return 1
    except Exception as e:
        print(f"[ERROR] Could not reach API at {api_url}: {e}")
        return 1

    # 2. Resolve default destination if needed
    active_dest_id = default_dest_id
    if not active_dest_id:
        try:
            dest_resp = client.get(f"{api_url}/api/v1/destinations")
            if dest_resp.status_code == 200:
                dest_list = dest_resp.json()
                items = dest_list.get("items", dest_list)
                if items:
                    active_dest_id = items[0]["id"]
                    print(f"[INFO] Using default destination: {items[0]['name']} ({active_dest_id})")
        except Exception as e:
            print(f"[WARN] Failed to auto-resolve destination: {e}")

    succeeded_count = 0
    failed_count = 0
    start_all = time.time()

    for idx, f in enumerate(files, 1):
        print(f"\n[{idx}/{len(files)}] Processing: {f.name}")
        try:
            if f.suffix.lower() == ".json":
                parsed = parse_json_file(f)
            else:
                parsed = parse_markdown_file(f)

            target_dest_id = parsed.get("destination_id") or active_dest_id
            if not target_dest_id:
                print("  -> [FAIL] No destination_id specified and no default found.")
                failed_count += 1
                continue

            # Compute stable idempotency key based on file content and dest
            content_hash = hashlib.sha256(f"{target_dest_id}:{parsed['title']}:{parsed['body']}".encode()).hexdigest()[:16]
            idemp_key = f"cli_idemp_{f.stem}_{content_hash}"

            pub_payload = {
                "destination_id": target_dest_id,
                "rendition": {
                    "title": parsed["title"],
                    "body": parsed["body"],
                    "canonical_url": parsed.get("canonical_url"),
                    "tags": parsed.get("tags", []),
                    "is_promotional": False,
                    "ai_generated": True,
                    "language": "en",
                },
            }

            headers = {
                "Content-Type": "application/json",
                "Idempotency-Key": idemp_key,
            }

            pub_resp = client.post(
                f"{api_url}/api/v1/publications",
                json=pub_payload,
                headers=headers,
            )

            if pub_resp.status_code not in (200, 202):
                print(f"  -> [FAIL] HTTP {pub_resp.status_code}: {pub_resp.text}")
                failed_count += 1
                continue

            pub_data = pub_resp.json()
            job_id = pub_data.get("job_id")
            print(f"  -> Enqueued Job: {job_id}")

            # Poll for completion
            job_result = poll_job(client, api_url, job_id, timeout_s=poll_timeout)
            status = job_result.get("status")

            # Persist output files
            result_file = out_dir / f"{f.stem}_result.json"
            manifest_file = out_dir / f"{f.stem}_manifest.json"

            result_file.write_text(json.dumps(job_result, indent=2), encoding="utf-8")

            res_data = job_result.get("result_json") or {}
            manifest_data = res_data.get("manifest", res_data)
            manifest_file.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

            if status == "succeeded":
                post_id = res_data.get("platform_post_id", "N/A")
                live_url = res_data.get("live_url", "N/A")
                print(f"  -> [SUCCESS] Post ID: {post_id} | Live URL: {live_url}")
                succeeded_count += 1
            else:
                err = job_result.get("error_json", {})
                print(f"  -> [FAILED] Reason: {err.get('message', 'Unknown error')}")
                failed_count += 1

        except Exception as exc:
            print(f"  -> [ERROR] Failed processing {f.name}: {exc}")
            failed_count += 1

    total_time = time.time() - start_all
    print("\n" + "=" * 55)
    print(" BATCH RUNNER EXECUTION SUMMARY")
    print("=" * 55)
    print(f" Total Files Processed: {len(files)}")
    print(f" Succeeded:             {succeeded_count}")
    print(f" Failed:                {failed_count}")
    print(f" Wall Clock Time:       {total_time:.2f}s")
    print(f" Output Directory:      {out_dir.resolve()}")
    print("=" * 55)

    return 0 if failed_count == 0 else 1


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="LongTail Passport Batch Runner CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        type=Path,
        help="Path to markdown/JSON file or directory of content files",
    )
    parser.add_argument(
        "--out",
        "-o",
        required=True,
        type=Path,
        help="Output directory for publication results and manifests",
    )
    parser.add_argument(
        "--api",
        "-a",
        default="http://localhost:8000",
        help="LongTail Passport API base URL",
    )
    parser.add_argument(
        "--destination-id",
        "-d",
        default=None,
        help="Target destination ID (overrides auto-detection)",
    )
    parser.add_argument(
        "--poll-timeout",
        type=float,
        default=30.0,
        help="Job completion polling timeout in seconds",
    )

    args = parser.parse_args()
    code = run_batch(
        input_path=args.input,
        out_dir=args.out,
        api_url=args.api.rstrip("/"),
        default_dest_id=args.destination_id,
        poll_timeout=args.poll_timeout,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
