"""Simple load test: hit list / search / stats endpoints concurrently and report p50 / p95 latency.

Usage: python scripts/loadtest.py http://127.0.0.1:8000 admin admin123 [concurrency] [requests per endpoint]
"""
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import httpx


def main() -> None:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    username = sys.argv[2] if len(sys.argv) > 2 else "admin"
    password = sys.argv[3] if len(sys.argv) > 3 else "admin123"
    concurrency = int(sys.argv[4]) if len(sys.argv) > 4 else 20
    total = int(sys.argv[5]) if len(sys.argv) > 5 else 400

    with httpx.Client(base_url=base, timeout=30) as c:
        r = c.post("/api/auth/login", json={"username": username, "password": password})
        r.raise_for_status()
        token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    targets = [
        ("students p1", "/api/students?page=1&size=20"),
        ("students p100", "/api/students?page=100&size=20"),
        ("search name", "/api/students?keyword=Smith"),
        ("search number", "/api/students?keyword=2024000123"),
        ("classes", "/api/classes"),
        ("stats", "/api/stats"),
        ("grades", "/api/enrollments?student_id=1"),
    ]

    # Shared connection pool so connection setup is not counted as latency
    client = httpx.Client(base_url=base, timeout=30, headers=headers, limits=httpx.Limits(max_connections=concurrency))

    def hit(path: str) -> tuple[float, int]:
        t = time.perf_counter()
        r = client.get(path)
        return (time.perf_counter() - t) * 1000, r.status_code

    print(f"concurrency {concurrency}, {total} requests per endpoint\n")
    print(f"{'endpoint':<16}{'p50(ms)':>10}{'p95(ms)':>10}{'max(ms)':>10}{'fail':>6}{'QPS':>8}")
    for name, path in targets:
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            results = list(ex.map(hit, [path] * total))
        elapsed = time.perf_counter() - start
        lat = sorted(r[0] for r in results)
        fails = sum(1 for r in results if r[1] != 200)
        p95 = lat[int(len(lat) * 0.95) - 1]
        print(f"{name:<16}{statistics.median(lat):>10.1f}{p95:>10.1f}{lat[-1]:>10.1f}{fails:>6}{total / elapsed:>8.0f}")
    client.close()


if __name__ == "__main__":
    main()
