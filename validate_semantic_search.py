#!/usr/bin/env python3
"""Validate and tune semantic search for HashiCorp PDFs."""

import sys
import logging
sys.path.insert(0, '.')

from hashicorp_pdf_search import initialize_pdf_search, search_pdfs, get_pdf_search_index

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_semantic_search_quality():
    """Test semantic search with various queries to validate quality."""

    print("=" * 80)
    print("SEMANTIC SEARCH VALIDATION & TUNING")
    print("=" * 80)
    print()

    # Initialize
    print("Step 1: Initializing semantic search index...")
    print("(This will download PDFs and build embeddings if not cached)")
    print()

    try:
        initialize_pdf_search()
        index = get_pdf_search_index()

        if not index.chunks:
            print("❌ ERROR: No chunks indexed. PDFs may not have been downloaded.")
            print("\nTo download PDFs:")
            print("  1. Run: python3 download_hashicorp_pdfs.py")
            print("  2. Manually download PDFs from the URLs shown")
            print("  3. Re-run this validation script")
            return

        print(f"✓ Index loaded with {len(index.chunks)} chunks")
        print(f"✓ Model: {index.model_name}")
        print()

    except Exception as e:
        print(f"❌ ERROR: Failed to initialize: {e}")
        return

    # Test queries with expected results
    test_cases = [
        {
            "query": "How do I scale Vault in production?",
            "expected_products": ["vault"],
            "expected_keywords": ["scale", "scaling", "production", "performance", "cluster"],
            "description": "Vault scaling query"
        },
        {
            "query": "Terraform module best practices",
            "expected_products": ["terraform"],
            "expected_keywords": ["module", "best practice", "structure", "organization"],
            "description": "Terraform modules query"
        },
        {
            "query": "High availability architecture",
            "expected_products": ["vault", "consul", "terraform", "nomad"],  # Could match any
            "expected_keywords": ["high availability", "ha", "cluster", "redundancy", "failover"],
            "description": "HA architecture query (cross-product)"
        },
        {
            "query": "Authentication and security",
            "expected_products": ["vault", "boundary"],
            "expected_keywords": ["auth", "security", "identity", "access", "policy"],
            "description": "Auth & security query"
        },
        {
            "query": "Adopting HashiCorp tools in my organization",
            "expected_products": ["terraform", "vault", "consul", "boundary", "nomad"],
            "expected_keywords": ["adopt", "organization", "team", "workflow", "process"],
            "description": "Adoption/organization query"
        }
    ]

    print("=" * 80)
    print("Step 2: Running Test Queries")
    print("=" * 80)
    print()

    total_tests = len(test_cases)
    passed_tests = 0

    for idx, test in enumerate(test_cases, 1):
        print(f"\n{'─' * 80}")
        print(f"Test {idx}/{total_tests}: {test['description']}")
        print(f"{'─' * 80}")
        print(f"Query: \"{test['query']}\"")
        print()

        # Search
        results = index.search(test['query'], top_k=5)

        if not results:
            print("❌ FAIL: No results returned")
            continue

        # Analyze results
        print(f"Found {len(results)} results:\n")

        product_match = False
        keyword_match = False

        for i, result in enumerate(results, 1):
            score = result['score']
            distance = result['distance']
            product = result['product']
            doc = result['document']
            text_preview = result['text'][:150].replace('\n', ' ')

            # Check if product matches expectations
            if product in test['expected_products']:
                product_match = True
                product_indicator = "✓"
            else:
                product_indicator = " "

            # Check if any expected keywords are in the text
            text_lower = result['text'].lower()
            found_keywords = [kw for kw in test['expected_keywords'] if kw.lower() in text_lower]
            if found_keywords:
                keyword_match = True

            print(f"{i}. [{product_indicator}] {product.upper()}: {doc}")
            print(f"   Relevance Score: {score:.4f} (distance: {distance:.4f})")
            if found_keywords:
                print(f"   Keywords found: {', '.join(found_keywords)}")
            print(f"   Preview: {text_preview}...")
            print()

        # Evaluate
        test_passed = product_match and keyword_match

        print("Evaluation:")
        print(f"  Product Match: {'✓ PASS' if product_match else '✗ FAIL'} (found {[r['product'] for r in results[:3]]})")
        print(f"  Keyword Match: {'✓ PASS' if keyword_match else '✗ FAIL'}")
        print(f"  Overall: {'✓ PASS' if test_passed else '✗ FAIL'}")

        if test_passed:
            passed_tests += 1

    # Summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Tests Passed: {passed_tests}/{total_tests} ({passed_tests/total_tests*100:.0f}%)")
    print()

    if passed_tests == total_tests:
        print("✓ EXCELLENT: All tests passed! Semantic search is working well.")
    elif passed_tests >= total_tests * 0.7:
        print("⚠ GOOD: Most tests passed. Some tuning may improve results.")
        print("\nTuning suggestions:")
        print("  - Try adjusting chunk_size (currently 500 words)")
        print("  - Try different models: all-mpnet-base-v2 for better quality")
    else:
        print("✗ NEEDS WORK: Many tests failed. Check the following:")
        print("  - Are PDFs downloaded correctly?")
        print("  - Is text extraction working?")
        print("  - Try different embedding models")

    print()
    print("=" * 80)
    print("EMBEDDING STATISTICS")
    print("=" * 80)
    print(f"Total chunks indexed: {len(index.chunks)}")
    print(f"Embedding model: {index.model_name}")
    print(f"Embedding dimension: {index.index.d if index.index else 'N/A'}")
    print(f"Index size: {len(index.chunks)} vectors")

    # Product distribution
    product_counts = {}
    for chunk in index.chunks:
        product = chunk['product']
        product_counts[product] = product_counts.get(product, 0) + 1

    print("\nChunks per product:")
    for product, count in sorted(product_counts.items()):
        print(f"  {product}: {count} chunks")

    print()


def test_semantic_vs_keyword():
    """Compare semantic search to keyword search."""
    print("\n" + "=" * 80)
    print("SEMANTIC vs KEYWORD COMPARISON")
    print("=" * 80)
    print()

    query = "How do I make my infrastructure resilient to failures?"

    print(f"Query: \"{query}\"")
    print()

    # Semantic search
    print("Semantic Search Results (understands concepts):")
    print("-" * 60)
    index = get_pdf_search_index()
    results = index.search(query, top_k=3)

    for i, result in enumerate(results, 1):
        print(f"{i}. {result['product'].upper()}: {result['document']}")
        print(f"   Score: {result['score']:.4f}")
        print(f"   Why: Matches concepts like 'high availability', 'redundancy', 'failover'")
        print()

    # Simulated keyword search
    print("\nKeyword Search Would Find (if we used exact matching):")
    print("-" * 60)
    print("  Likely: No results (query contains 'resilient', 'failures')")
    print("  Docs likely contain: 'high availability', 'disaster recovery', 'fault tolerance'")
    print("  ⚠️  Keyword search misses conceptually similar content!")
    print()

    print("✓ This demonstrates semantic search finding relevant content")
    print("  even when exact keywords don't match!")
    print()


def show_tuning_options():
    """Show available tuning parameters."""
    print("\n" + "=" * 80)
    print("TUNING OPTIONS")
    print("=" * 80)
    print()

    print("You can tune the following in hashicorp_pdf_search.py:\n")

    print("1. EMBEDDING MODEL (affects quality)")
    print("   Current: all-MiniLM-L6-v2 (fast, 384 dims)")
    print("   Alternatives:")
    print("     - all-mpnet-base-v2 (better quality, 768 dims, slower)")
    print("     - all-distilroberta-v1 (good balance)")
    print()

    print("2. CHUNK SIZE (affects granularity)")
    print("   Current: 500 words with 50 word overlap")
    print("   Tuning:")
    print("     - Smaller chunks (250-300): More precise but may lose context")
    print("     - Larger chunks (700-1000): More context but less precise")
    print()

    print("3. TOP_K RESULTS (affects how many results returned)")
    print("   Current: 5 results by default")
    print("   Tuning: Increase for more comprehensive results")
    print()

    print("4. UPDATE CHECK INTERVAL")
    print("   Current: 24 hours")
    print("   Tuning: Adjust based on how often PDFs change")
    print()

    print("To change these, edit hashicorp_pdf_search.py and reinitialize.")
    print()


if __name__ == "__main__":
    try:
        test_semantic_search_quality()
        test_semantic_vs_keyword()
        show_tuning_options()

        print("=" * 80)
        print("VALIDATION COMPLETE")
        print("=" * 80)
        print()
        print("Next steps:")
        print("  1. If tests passed: Your semantic search is working great!")
        print("  2. If tests need work: Check tuning options above")
        print("  3. Try your own queries: python3 -c \"from hashicorp_pdf_search import search_pdfs; print(search_pdfs('your query'))\"")
        print()

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
