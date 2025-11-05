#!/usr/bin/env python3
"""Test script for HashiCorp PDF search functionality."""

import sys
sys.path.insert(0, '.')

from hashicorp_pdf_search import initialize_pdf_search, search_pdfs

def main():
    print("=" * 70)
    print("HashiCorp PDF Search Test")
    print("=" * 70)
    print()

    # Initialize the search index
    print("Step 1: Initializing PDF search index...")
    print("(This will download PDFs if available, or use cached ones)")
    print()

    try:
        initialize_pdf_search()
        print("✓ Index initialized successfully!")
        print()
    except Exception as e:
        print(f"✗ Error initializing index: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test search queries
    test_queries = [
        ("terraform module best practices", "terraform"),
        ("vault scaling", "vault"),
        ("consul service mesh", "consul"),
        ("high availability", ""),  # No product filter
    ]

    for query, product in test_queries:
        print("=" * 70)
        if product:
            print(f"Test Query: '{query}' (product: {product})")
        else:
            print(f"Test Query: '{query}' (all products)")
        print("=" * 70)

        try:
            results = search_pdfs(query, top_k=3, product=product)
            print(results)
        except Exception as e:
            print(f"✗ Error during search: {e}")
            import traceback
            traceback.print_exc()

        print()


if __name__ == "__main__":
    main()
