#!/usr/bin/env python3
"""One-command verification for required panel routes."""
import sys
from urllib import request, error

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/api"

ROUTES = [
    ("GET", "/system/health"),
    ("POST", "/system/warm-cache"),
    ("GET", "/dashboard"),
    ("GET", "/dashboard/opportunities"),
    ("GET", "/dashboard/risk/session"),
    ("GET", "/dashboard/regime"),
    ("GET", "/dashboard/alerts"),
    ("GET", "/global/news"),
    ("GET", "/global/macro"),
    ("GET", "/global/geopolitics"),
    ("GET", "/agents"),
    ("GET", "/agents/calibration"),
    ("GET", "/assets/search?query=BTC"),
    ("GET", "/assets/BTC/overview"),
    ("GET", "/assets/BTC/chart"),
    ("GET", "/assets/BTC/technicals"),
    ("GET", "/assets/BTC/news"),
    ("GET", "/assets/BTC/flow"),
    ("GET", "/assets/BTC/signal"),
]

failed = 0
for method, path in ROUTES:
    url = f"{BASE}{path}"
    try:
        req = request.Request(url=url, method=method)
        with request.urlopen(req, timeout=30) as resp:
            status = resp.status
        ok = 200 <= status < 300
        print(f"{'OK' if ok else 'FAIL'} {method} {url} -> {status}")
        if not ok:
            failed += 1
    except error.HTTPError as exc:
        print(f"FAIL {method} {url} -> {exc.code}")
        failed += 1
    except Exception as exc:
        print(f"FAIL {method} {url} -> {exc}")
        failed += 1

if failed:
    print(f"\nVerification failed: {failed} route(s).")
    sys.exit(1)

print("\nVerification succeeded: all routes healthy.")
