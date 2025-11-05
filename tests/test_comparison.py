#!/usr/bin/env python3
"""Comprehensive search quality regression test.

This test validates that the HashiCorp documentation search returns correct
answers for known queries. Add new test cases as you discover search quality
issues or want to validate specific behaviors.
"""
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Test cases: Each test case defines a query and validation criteria
TEST_CASES = [
    {
        "name": "Consul Stale Reads Default",
        "query": "what's the consul default for stale reads",
        "product": "consul",
        "source": "Consul Operating Guide for Adoption, section 8.3.6",
        "expected": "By default, Consul enables stale reads and sets the max_stale value to 10 years",
        "must_contain": [
            ("max_stale", "10 years"),  # Both must be present
        ],
        "should_contain": [
            "adoption",  # Should reference the Adoption guide
            "enables stale reads",  # Should indicate it's enabled by default
        ],
        "must_not_contain": [
            "defaults to false",  # Common incorrect answer
            "stale = false",
        ],
    },
    {
        "name": "Vault Disk Throughput Requirements",
        "query": "what disk throughput is needed to run vault",
        "product": "vault",
        "source": "Vault Solution Design Guides - Validated Designs, Detailed Design section",
        "expected": "Small clusters: 75+ MB/s, Large clusters: 250+ MB/s",
        "must_contain": [
            ("75", "mb/s"),  # Small cluster requirement
        ],
        "should_contain": [
            "250",  # Large cluster requirement
            "throughput",
            "disk",
        ],
        "must_not_contain": [
            "iops only",  # Should mention throughput, not just IOPS
        ],
    },
]


def validate_test_case(test_case, results):
    """Validate search results against test case criteria.

    Returns:
        tuple: (passed, score, max_score, details)
    """
    details = []
    score = 0
    max_score = 0
    results_lower = results.lower()

    # Check must_contain (critical - worth 2 points each)
    for items in test_case["must_contain"]:
        max_score += 2
        if isinstance(items, tuple):
            # All items in tuple must be present
            if all(item.lower() in results_lower for item in items):
                details.append(f"   ✅ CRITICAL: Found all of {items}")
                score += 2
            elif any(item.lower() in results_lower for item in items):
                details.append(f"   ⚠️  PARTIAL: Found some of {items}")
                score += 1
            else:
                details.append(f"   ❌ CRITICAL: Missing {items}")
        else:
            if items.lower() in results_lower:
                details.append(f"   ✅ CRITICAL: Found '{items}'")
                score += 2
            else:
                details.append(f"   ❌ CRITICAL: Missing '{items}'")

    # Check should_contain (important - worth 1 point each)
    for item in test_case["should_contain"]:
        max_score += 1
        if item.lower() in results_lower:
            details.append(f"   ✅ Found '{item}'")
            score += 1
        else:
            details.append(f"   ⚠️  Missing '{item}'")

    # Check must_not_contain (critical - deducts 2 points)
    for item in test_case["must_not_contain"]:
        if item.lower() in results_lower:
            details.append(f"   ❌ FAIL: Contains incorrect info '{item}'")
            score -= 2

    passed = score >= (max_score * 0.75)  # Pass if 75% or better

    return passed, score, max_score, details


def run_test_case(test_case, search_func):
    """Run a single test case.

    Returns:
        bool: True if test passed, False otherwise
    """
    print(f"\n{'='*80}")
    print(f"TEST: {test_case['name']}")
    print(f"{'='*80}")

    print(f"\nQuery: '{test_case['query']}'")
    print(f"Expected: {test_case['expected']}")
    print(f"Source: {test_case['source']}")

    try:
        # Search
        print(f"\nSearching...")
        results = search_func(
            test_case['query'],
            top_k=5,
            product=test_case.get('product')
        )

        print(f"\nResults Preview (first 500 chars):")
        print("-" * 80)
        print(results[:500] + "..." if len(results) > 500 else results)
        print("-" * 80)

        # Validate
        passed, score, max_score, details = validate_test_case(test_case, results)

        print(f"\nValidation:")
        for detail in details:
            print(detail)
        print(f"\n   Score: {score}/{max_score} ({score/max_score*100:.1f}%)")
        print(f"   Result: {'✅ PASS' if passed else '❌ FAIL'}")

        return passed

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all search quality tests."""
    print("\n" + "="*80)
    print("HASHICORP SEARCH QUALITY - REGRESSION TEST SUITE")
    print("="*80)
    print(f"\nRunning {len(TEST_CASES)} test cases...")

    # Initialize search
    try:
        from hashicorp_pdf_search import initialize_pdf_search, search_pdfs
        print("\nInitializing search index...")
        initialize_pdf_search()
        search_func = search_pdfs
    except Exception as e:
        print(f"\n❌ Failed to initialize search: {e}")
        return 1

    # Run all test cases
    results = {}
    for test_case in TEST_CASES:
        passed = run_test_case(test_case, search_func)
        results[test_case['name']] = passed

    # Summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")

    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    passed_count = sum(1 for p in results.values() if p)
    total_count = len(results)

    print(f"\nOverall: {passed_count}/{total_count} tests passed")
    print("="*80)

    # Return 0 if all passed, 1 otherwise
    return 0 if passed_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())
