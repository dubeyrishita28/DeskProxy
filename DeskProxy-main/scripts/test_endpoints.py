#!/usr/bin/env python3
"""
Manual end-to-end smoke test script.

Run against a live server:
    python scripts/test_endpoints.py [--base-url http://localhost:8000]

Exit code 0 = all checks passed.
Exit code 1 = one or more checks failed.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import urllib.error
from typing import Any

BASE_URL = "http://localhost:8000"
PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"


def _request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    url = BASE_URL + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, {}


def check(description: str, condition: bool) -> bool:
    status = PASS if condition else FAIL
    print(f"  {status}  {description}")
    return condition


def run_smoke_tests() -> int:
    failures = 0

    print("\n── Health ────────────────────────────────────────")
    code, data = _request("GET", "/health")
    failures += not check("GET /health returns 200", code == 200)
    failures += not check("status == 'healthy'", data.get("status") == "healthy")
    failures += not check("sqlite_ok is True", data.get("sqlite_ok") is True)
    failures += not check("chroma_ok is True", data.get("chroma_ok") is True)

    print("\n── Cache Purge (clean slate) ─────────────────────")
    code, data = _request("DELETE", "/cache")
    failures += not check("DELETE /cache returns 200", code == 200)

    print("\n── First Query (cache miss) ──────────────────────")
    payload = {"query": "show me the Q3 revenue dashboard"}
    code, data = _request("POST", "/query", payload)
    failures += not check("POST /query returns 200", code == 200)
    failures += not check("cache_hit is False", data.get("cache_hit") is False)
    failures += not check("result is non-empty", bool(data.get("result")))
    failures += not check("latency_ms > 0", (data.get("latency_ms") or 0) > 0)
    first_result = data.get("result", "")

    print("\n── Second Query (cache hit) ──────────────────────")
    code, data = _request("POST", "/query", payload)
    failures += not check("POST /query returns 200", code == 200)
    failures += not check("cache_hit is True", data.get("cache_hit") is True)
    failures += not check("similarity_score present", data.get("similarity_score") is not None)
    failures += not check("result matches first call", data.get("result") == first_result)

    print("\n── Cache Entries ─────────────────────────────────")
    code, data = _request("GET", "/cache/entries")
    failures += not check("GET /cache/entries returns 200", code == 200)
    failures += not check("total >= 1", (data.get("total") or 0) >= 1)

    print("\n── Telemetry ─────────────────────────────────────")
    code, data = _request("GET", "/telemetry/summary")
    failures += not check("GET /telemetry/summary returns 200", code == 200)
    failures += not check("total_queries >= 2", (data.get("total_queries") or 0) >= 2)
    failures += not check("cache_hits >= 1", (data.get("cache_hits") or 0) >= 1)

    print("\n── Validation ────────────────────────────────────")
    code, _ = _request("POST", "/query", {"query": ""})
    failures += not check("empty query rejected (422)", code == 422)

    print(f"\n{'─'*50}")
    if failures == 0:
        print(f"{PASS}  All checks passed")
    else:
        print(f"{FAIL}  {failures} check(s) failed")
    return failures


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    BASE_URL = args.base_url.rstrip("/")
    sys.exit(run_smoke_tests())
