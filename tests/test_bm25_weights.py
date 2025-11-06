#!/usr/bin/env python3
"""Test different BM25 vs semantic weight configurations to find optimal balance.

This test systematically tries different weight combinations for the hybrid search
to determine which configuration best retrieves the target chunks for both test cases.
"""
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from hashicorp_doc_search import get_doc_search_index

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Suppress debug logs for cleaner output
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Test configurations to try
WEIGHT_CONFIGS = [
    {"bm25": 0.3, "semantic": 0.7, "name": "30/70 (Heavy Semantic)"},
    {"bm25": 0.4, "semantic": 0.6, "name": "40/60 (Favor Semantic)"},
    {"bm25": 0.5, "semantic": 0.5, "name": "50/50 (Balanced - Current)"},
    {"bm25": 0.6, "semantic": 0.4, "name": "60/40 (Favor Keywords)"},
    {"bm25": 0.7, "semantic": 0.3, "name": "70/30 (Heavy Keywords)"},
]

# Test cases
TEST_CASES = [
    {
        "name": "Consul Stale Reads",
        "query": "what's the consul default for stale reads",
        "product": "consul",
        "target_url_fragment": "consul-operating-guides-adoption",
        "target_content": ["max_stale", "10 years"],
        "description": "Should find Consul Adoption Guide with 10 years default"
    },
    {
        "name": "Vault Disk Throughput",
        "query": "what disk throughput is needed to run vault",
        "product": "vault",
        "target_url_fragment": "hardware-sizing-for-vault-servers",
        "target_content": ["75", "MB/s", "250"],
        "description": "Should find hardware sizing table with 75+ MB/s and 250+ MB/s"
    }
]


def test_weight_configuration(index, weight_config, test_case):
    """Test a single weight configuration for a test case.

    Returns:
        dict with results including whether target chunk was found
    """
    # Update ensemble retriever weights
    if index.ensemble_retriever is not None:
        index.ensemble_retriever.weights = [weight_config["bm25"], weight_config["semantic"]]

    # Search with larger top_k to see if target is in results
    results = index.search(
        test_case["query"],
        top_k=20,  # Get more results to check retrieval
        product_filter=test_case["product"]
    )

    # Check if target chunk is retrieved
    target_found = False
    target_rank = None
    target_score = None

    for i, result in enumerate(results, 1):
        # Check if this is the target chunk
        if test_case["target_url_fragment"] in result["url"]:
            # Also verify it has the expected content
            has_content = all(
                content.lower() in result["text"].lower()
                for content in test_case["target_content"]
            )
            if has_content:
                target_found = True
                target_rank = i
                target_score = result["score"]
                break

    return {
        "target_found": target_found,
        "target_rank": target_rank,
        "target_score": target_score,
        "top_result_url": results[0]["url"] if results else None,
        "top_result_score": results[0]["score"] if results else None,
    }


def main():
    """Run BM25 weight tuning tests."""
    print("\n" + "="*80)
    print("BM25 WEIGHT TUNING TEST")
    print("="*80)
    print("\nTesting different BM25 vs Semantic weight configurations")
    print("to find optimal balance for both test cases.\n")

    # Initialize search index
    print("Loading search index...")
    index = get_doc_search_index()
    if index.vectorstore is None:
        index.initialize()
    print("✓ Index loaded\n")

    # Store results for all configurations
    all_results = {}

    # Test each weight configuration
    for config in WEIGHT_CONFIGS:
        print(f"\n{'='*80}")
        print(f"Testing: {config['name']}")
        print(f"Weights: BM25={config['bm25']:.1f}, Semantic={config['semantic']:.1f}")
        print(f"{'='*80}")

        config_results = {}

        for test_case in TEST_CASES:
            print(f"\n  {test_case['name']}:")
            print(f"    Query: '{test_case['query']}'")
            print(f"    Target: {test_case['description']}")

            results = test_weight_configuration(index, config, test_case)
            config_results[test_case["name"]] = results

            # Print results
            if results["target_found"]:
                print(f"    ✅ FOUND at rank #{results['target_rank']} (score: {results['target_score']:.3f})")
            else:
                print(f"    ❌ NOT FOUND in top-20 results")
                print(f"    Top result: {results['top_result_url'][:60]}...")

        all_results[config["name"]] = config_results

    # Print summary table
    print("\n\n" + "="*80)
    print("SUMMARY - BM25 WEIGHT TUNING RESULTS")
    print("="*80)

    print("\n{:<30} {:<25} {:<25}".format(
        "Configuration",
        "Consul (Rank/Score)",
        "Vault (Rank/Score)"
    ))
    print("-" * 80)

    best_config = None
    best_score = -1

    for config in WEIGHT_CONFIGS:
        consul_result = all_results[config["name"]]["Consul Stale Reads"]
        vault_result = all_results[config["name"]]["Vault Disk Throughput"]

        consul_str = (
            f"✅ #{consul_result['target_rank']} ({consul_result['target_score']:.2f})"
            if consul_result["target_found"]
            else "❌ Not found"
        )

        vault_str = (
            f"✅ #{vault_result['target_rank']} ({vault_result['target_score']:.2f})"
            if vault_result["target_found"]
            else "❌ Not found"
        )

        print("{:<30} {:<25} {:<25}".format(
            config["name"],
            consul_str,
            vault_str
        ))

        # Calculate score: both found = 2, one found = 1, none = 0
        # Prefer lower ranks
        score = 0
        if consul_result["target_found"]:
            score += 1.0 / consul_result["target_rank"]
        if vault_result["target_found"]:
            score += 1.0 / vault_result["target_rank"]

        if score > best_score:
            best_score = score
            best_config = config["name"]

    print("\n" + "="*80)
    print(f"RECOMMENDATION: {best_config}")
    print("="*80)

    # Check if any configuration retrieves the Vault chunk
    vault_found_in_any = any(
        all_results[config["name"]]["Vault Disk Throughput"]["target_found"]
        for config in WEIGHT_CONFIGS
    )

    if vault_found_in_any:
        print("\n✅ SUCCESS: Found a weight configuration that retrieves the Vault chunk!")
    else:
        print("\n⚠️  WARNING: No weight configuration retrieves the Vault hardware-sizing chunk.")
        print("This confirms it's a retrieval problem that requires query expansion or")
        print("multi-query generation to solve.")

    print("\n" + "="*80 + "\n")

    return 0 if vault_found_in_any else 1


if __name__ == "__main__":
    sys.exit(main())
