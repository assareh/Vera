#!/usr/bin/env python3
"""
Performance benchmark for HashiCorp documentation search.

Tests search latency, throughput, and quality metrics with different
configurations (with/without reranking, various candidate counts).

Usage:
    python tests/benchmark_search.py                    # Quick benchmark
    python tests/benchmark_search.py --full             # Full benchmark
    python tests/benchmark_search.py --compare v1 v2    # Compare two indices
"""

import json
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from hashicorp_doc_search import HashiCorpDocSearchIndex


@dataclass
class QueryMetrics:
    """Metrics for a single query execution."""

    query: str
    latency_ms: float
    num_results: int
    top_result_url: str
    top_result_score: float
    rerank_latency_ms: float | None = None


@dataclass
class BenchmarkResults:
    """Aggregated benchmark results."""

    config_name: str
    num_queries: int

    # Latency metrics (milliseconds)
    latency_p50: float
    latency_p95: float
    latency_p99: float
    latency_mean: float
    latency_min: float
    latency_max: float

    # Throughput
    queries_per_second: float

    # Index stats
    num_parent_chunks: int
    num_child_chunks: int

    # Configuration
    enable_reranking: bool
    index_version: str


# Test queries covering different types of searches
QUICK_QUERIES = [
    "vault installation",
    "consul stale reads default",
    "nomad job specification",
    "boundary credential management",
    "terraform workspace",
]

FULL_QUERIES = [
    # Installation queries
    "vault installation",
    "consul agent installation",
    "nomad server setup",
    "boundary controller configuration",
    # Configuration queries
    "consul stale reads default",
    "vault seal configuration",
    "nomad driver configuration",
    "boundary worker filters",
    # Feature queries
    "consul service mesh",
    "vault dynamic secrets",
    "nomad autoscaling",
    "boundary session recording",
    # Version-specific queries
    "what's new in vault 1.20",
    "vault 1.21 release notes",
    "consul 1.21 features",
    "nomad 1.9 changes",
    "boundary 0.18 release",
    # API queries
    "vault api authentication",
    "consul http api",
    "nomad rest api",
    "boundary api tokens",
    # Troubleshooting queries
    "vault seal issues",
    "consul gossip encryption",
    "nomad allocation failures",
    "boundary connection refused",
]

CRITICAL_QUERIES = [
    # These are queries we MUST get right
    ("consul stale reads default", "https://developer.hashicorp.com/consul"),
    ("vault 1.20 release notes", "https://developer.hashicorp.com/vault/docs/v1.20.x/updates/release-notes"),
    ("nomad 1.9 release notes", "https://developer.hashicorp.com/nomad/docs/release-notes/nomad/v1_9_x"),
    ("boundary 0.18 release notes", "https://developer.hashicorp.com/boundary/docs/v0.18.x/release-notes"),
]


def run_query(index: HashiCorpDocSearchIndex, query: str, top_k: int = 5) -> QueryMetrics:
    """Run a single query and measure performance."""
    start = time.time()

    try:
        results = index.search(query, top_k=top_k)

        latency_ms = (time.time() - start) * 1000

        if results:
            return QueryMetrics(
                query=query,
                latency_ms=latency_ms,
                num_results=len(results),
                top_result_url=results[0].get("url", "N/A"),
                top_result_score=results[0].get("score", 0.0),
            )
        else:
            return QueryMetrics(
                query=query, latency_ms=latency_ms, num_results=0, top_result_url="N/A", top_result_score=0.0
            )
    except Exception as e:
        print(f"❌ Query failed: {query}")
        print(f"   Error: {e}")
        return QueryMetrics(query=query, latency_ms=0.0, num_results=0, top_result_url="ERROR", top_result_score=0.0)


def run_benchmark(
    index: HashiCorpDocSearchIndex, queries: list[str], config_name: str, warmup: bool = True
) -> BenchmarkResults:
    """Run benchmark with given queries and configuration."""

    print(f"\n{'='*80}")
    print(f"BENCHMARK: {config_name}")
    print(f"{'='*80}")
    print(f"Queries: {len(queries)}")
    print(f"Reranking: {index.enable_reranking}")
    print(f"Parent chunks: {len(index.parent_chunks)}")
    print(f"Child chunks: {len(index.child_to_parent)}")

    # Warmup query to load models into memory
    if warmup:
        print("\n🔥 Warming up (first query)...")
        _ = index.search("test warmup query", top_k=5)
        time.sleep(1)

    # Run queries
    print(f"\n🏃 Running {len(queries)} queries...")
    query_metrics = []

    for i, query in enumerate(queries, 1):
        if i % 10 == 0 or i == len(queries):
            print(f"  [{100*i//len(queries):3d}%] {i}/{len(queries)} queries")

        metrics = run_query(index, query)
        query_metrics.append(metrics)

    # Calculate aggregate metrics
    latencies = [m.latency_ms for m in query_metrics if m.latency_ms > 0]

    if not latencies:
        print("❌ No successful queries!")
        return None

    latencies_sorted = sorted(latencies)

    total_time = sum(latencies) / 1000  # Convert to seconds
    qps = len(latencies) / total_time if total_time > 0 else 0

    results = BenchmarkResults(
        config_name=config_name,
        num_queries=len(queries),
        latency_p50=latencies_sorted[len(latencies_sorted) // 2],
        latency_p95=latencies_sorted[int(len(latencies_sorted) * 0.95)],
        latency_p99=latencies_sorted[int(len(latencies_sorted) * 0.99)],
        latency_mean=statistics.mean(latencies),
        latency_min=min(latencies),
        latency_max=max(latencies),
        queries_per_second=qps,
        num_parent_chunks=len(index.parent_chunks),
        num_child_chunks=len(index.child_to_parent),
        enable_reranking=index.enable_reranking,
        index_version=getattr(index, "_index_version", "unknown"),
    )

    # Print results
    print(f"\n{'Results':-^80}")
    print("  Latency (ms):")
    print(f"    p50: {results.latency_p50:7.1f}")
    print(f"    p95: {results.latency_p95:7.1f}")
    print(f"    p99: {results.latency_p99:7.1f}")
    print(f"    mean: {results.latency_mean:6.1f}")
    print(f"    min: {results.latency_min:7.1f}")
    print(f"    max: {results.latency_max:7.1f}")
    print(f"  Throughput: {results.queries_per_second:.2f} queries/sec")

    # Show slowest queries
    print(f"\n{'Slowest Queries':-^80}")
    slowest = sorted(query_metrics, key=lambda m: m.latency_ms, reverse=True)[:5]
    for m in slowest:
        print(f"  {m.latency_ms:7.1f}ms - {m.query}")

    return results


def check_critical_queries(index: HashiCorpDocSearchIndex) -> int:
    """Test critical queries and return number of failures."""
    print(f"\n{'='*80}")
    print("CRITICAL QUERY VALIDATION")
    print(f"{'='*80}")

    failures = 0

    for query, expected_url_prefix in CRITICAL_QUERIES:
        results = index.search(query, top_k=5)

        if not results:
            print(f"❌ FAIL: {query}")
            print(f"   Expected: {expected_url_prefix}")
            print("   Got: No results")
            failures += 1
            continue

        top_url = results[0].get("url", "")

        if top_url.startswith(expected_url_prefix):
            print(f"✅ PASS: {query}")
            print(f"   Result: {top_url}")
        else:
            print(f"❌ FAIL: {query}")
            print(f"   Expected: {expected_url_prefix}")
            print(f"   Got: {top_url}")
            failures += 1

    print(f"\n{'Summary':-^80}")
    print(f"  Passed: {len(CRITICAL_QUERIES) - failures}/{len(CRITICAL_QUERIES)}")
    print(f"  Failed: {failures}/{len(CRITICAL_QUERIES)}")

    return failures


def save_results(results: BenchmarkResults, output_dir: Path):
    """Save benchmark results to JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = output_dir / f"benchmark_{timestamp}.json"

    with open(filename, "w") as f:
        json.dump(asdict(results), f, indent=2)

    print(f"\n💾 Results saved to: {filename}")


def compare_results(results1: BenchmarkResults, results2: BenchmarkResults):
    """Compare two benchmark results."""
    print(f"\n{'='*80}")
    print("COMPARISON")
    print(f"{'='*80}")

    print(f"\n{'Metric':<30} {'Config 1':>15} {'Config 2':>15} {'Change':>15}")
    print(f"{'-'*30} {'-'*15} {'-'*15} {'-'*15}")

    metrics = [
        ("Latency p50 (ms)", results1.latency_p50, results2.latency_p50),
        ("Latency p95 (ms)", results1.latency_p95, results2.latency_p95),
        ("Latency p99 (ms)", results1.latency_p99, results2.latency_p99),
        ("Throughput (q/s)", results1.queries_per_second, results2.queries_per_second),
    ]

    for name, val1, val2 in metrics:
        if "Throughput" in name:
            change = ((val2 - val1) / val1) * 100 if val1 > 0 else 0
            arrow = "↑" if change > 0 else "↓"
        else:
            change = ((val2 - val1) / val1) * 100 if val1 > 0 else 0
            arrow = "↓" if change < 0 else "↑"

        print(f"{name:<30} {val1:>15.2f} {val2:>15.2f} {arrow}{abs(change):>13.1f}%")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark HashiCorp documentation search")
    parser.add_argument("--full", action="store_true", help="Run full benchmark (30+ queries)")
    parser.add_argument("--no-rerank", action="store_true", help="Disable reranking")
    parser.add_argument("--cache-dir", default="./hashicorp_web_docs", help="Cache directory")
    parser.add_argument("--output", default="./benchmark_results", help="Output directory for results")
    parser.add_argument("--critical-only", action="store_true", help="Only test critical queries")

    args = parser.parse_args()

    queries = FULL_QUERIES if args.full else QUICK_QUERIES

    print("=" * 80)
    print("HASHICORP DOCUMENTATION SEARCH BENCHMARK")
    print("=" * 80)
    print("Configuration:")
    print(f"  Cache dir: {args.cache_dir}")
    print(f"  Queries: {'Full' if args.full else 'Quick'} ({len(queries)} queries)")
    print(f"  Reranking: {'Disabled' if args.no_rerank else 'Enabled'}")

    # Create index
    print("\n📦 Loading search index...")
    index = HashiCorpDocSearchIndex(cache_dir=args.cache_dir, enable_reranking=not args.no_rerank)

    print("🔨 Ensuring index is built...")
    index.initialize()

    # Test critical queries first
    if args.critical_only:
        failures = check_critical_queries(index)
        return 0 if failures == 0 else 1

    # Run benchmark
    config_name = f"{'full' if args.full else 'quick'}_{'with' if not args.no_rerank else 'no'}_rerank"
    results = run_benchmark(index, queries, config_name)

    if results:
        # Save results
        output_dir = Path(args.output)
        save_results(results, output_dir)

        # Test critical queries
        failures = check_critical_queries(index)

        print(f"\n{'='*80}")
        print("BENCHMARK COMPLETE")
        print(f"{'='*80}")

        return 0 if failures == 0 else 1
    else:
        print("\n❌ Benchmark failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
