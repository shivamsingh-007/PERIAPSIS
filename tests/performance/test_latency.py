from __future__ import annotations

import asyncio
import time
import statistics
from typing import Callable

import httpx


class LatencyTest:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: list[float] = []

    async def measure_endpoint(
        self,
        method: str,
        path: str,
        iterations: int = 100,
        **kwargs,
    ) -> dict:
        latencies = []
        errors = 0

        async with httpx.AsyncClient() as client:
            for _ in range(iterations):
                start = time.perf_counter()
                try:
                    response = await client.request(
                        method,
                        f"{self.base_url}{path}",
                        **kwargs,
                    )
                    elapsed = (time.perf_counter() - start) * 1000
                    latencies.append(elapsed)

                    if response.status_code >= 400:
                        errors += 1
                except Exception:
                    errors += 1
                    elapsed = (time.perf_counter() - start) * 1000
                    latencies.append(elapsed)

        if not latencies:
            return {"error": "No successful requests"}

        latencies.sort()
        p50_idx = int(len(latencies) * 0.5)
        p95_idx = int(len(latencies) * 0.95)
        p99_idx = int(len(latencies) * 0.99)

        return {
            "endpoint": f"{method} {path}",
            "iterations": iterations,
            "errors": errors,
            "error_rate": errors / iterations,
            "latency_ms": {
                "min": min(latencies),
                "max": max(latencies),
                "mean": statistics.mean(latencies),
                "median": latencies[p50_idx],
                "p95": latencies[p95_idx],
                "p99": latencies[p99_idx],
            },
            "passed": latencies[p95_idx] < 300,
        }

    async def run_all_tests(self) -> list[dict]:
        endpoints = [
            ("GET", "/health"),
            ("GET", "/"),
            ("GET", "/docs"),
        ]

        results = []
        for method, path in endpoints:
            result = await self.measure_endpoint(method, path)
            results.append(result)
            status = "PASS" if result.get("passed", False) else "FAIL"
            p95 = result.get("latency_ms", {}).get("p95", 0)
            print(f"  {status} {method} {path} - P95: {p95:.1f}ms")

        return results

    def print_summary(self, results: list[dict]):
        print("\n=== Performance Test Summary ===")
        passed = sum(1 for r in results if r.get("passed", False))
        total = len(results)
        print(f"Passed: {passed}/{total}")

        if passed < total:
            print("\nFailed endpoints:")
            for r in results:
                if not r.get("passed", False):
                    print(f"  {r['endpoint']} - P95: {r['latency_ms']['p95']:.1f}ms")


async def main():
    test = LatencyTest()
    print("Running performance tests...")
    results = await test.run_all_tests()
    test.print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())
