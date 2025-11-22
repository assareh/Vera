#!/usr/bin/env python3
"""Debug script to see full chunk content for search queries (using doc crawler)."""
import logging
import sys
from pathlib import Path

# Add parent directory to path to import modules from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from hashicorp_doc_search import get_doc_search_index

# Configure logging
logging.basicConfig(level=logging.WARNING)


def main():
    """Show full chunk content for debugging."""
    print("Loading doc search index...")
    index = get_doc_search_index()

    if index.vectorstore is None:
        print("Index not loaded, initializing...")
        from hashicorp_doc_search import initialize_doc_search

        initialize_doc_search()
        print("Index initialized.\n")

    query = "what's the consul default for stale reads"
    print(f"\nQuery: '{query}'\n")

    # Get raw results
    results = index.search(query, top_k=10, product_filter="consul")

    # Display full content of top results
    for idx, result in enumerate(results, 1):
        print("=" * 80)
        print(f"Result {idx}: [{result['product'].upper()}] {result.get('source', 'web')}")
        print(f"Score: {result['score']:.3f}")
        print(f"URL: {result['url']}")
        print("-" * 80)
        print("FULL CONTENT:")
        print(result["text"])
        print("=" * 80)
        print()

        # Check for keywords
        text_lower = result["text"].lower()
        has_max_stale = "max_stale" in text_lower
        has_10_years = "10 years" in text_lower or "10 year" in text_lower
        has_stale_reads = "stale reads" in text_lower or "stale read" in text_lower
        has_section = "8.3.6" in result["text"]

        print("Keywords found:")
        print(f"  - 'max_stale': {has_max_stale}")
        print(f"  - '10 years': {has_10_years}")
        print(f"  - 'stale reads': {has_stale_reads}")
        print(f"  - 'section 8.3.6': {has_section}")
        print()

        if has_max_stale and has_10_years:
            print("✅ This chunk contains the expected answer!")
            break


if __name__ == "__main__":
    main()
