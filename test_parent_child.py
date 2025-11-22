#!/usr/bin/env python3
"""
Quick test of parent-child chunking integration.
Tests with a small number of pages to verify the implementation.
"""

import sys

from hashicorp_doc_search import HashiCorpDocSearchIndex


def test_parent_child_integration():
    """Test parent-child chunking with a small index."""
    print("=" * 80)
    print("PARENT-CHILD CHUNKING INTEGRATION TEST")
    print("=" * 80)

    # Create index with small page limit for testing
    print("\n📦 Creating search index with max_pages=10...")
    index = HashiCorpDocSearchIndex(
        cache_dir="./hashicorp_web_docs_test",
        max_pages=10,  # Only process 10 pages for quick test
        enable_reranking=False,  # Disable reranking for faster test
    )

    # Build or load index
    print("\n🔨 Building index...")
    index.initialize()

    # Check parent-child storage
    print("\n" + "=" * 80)
    print("PARENT-CHILD STORAGE VERIFICATION")
    print("=" * 80)

    num_parents = len(index.parent_chunks)
    num_children = len(index.child_to_parent)

    print(f"\n✅ Parent chunks stored: {num_parents}")
    print(f"✅ Child chunks stored: {num_children}")
    print(f"✅ Child-to-parent mappings: {len(index.child_to_parent)}")

    if num_parents == 0:
        print("\n❌ ERROR: No parent chunks were created!")
        return False

    if num_children == 0:
        print("\n❌ ERROR: No child chunks were created!")
        return False

    # Show sample parent chunk
    print("\n" + "-" * 80)
    print("SAMPLE PARENT CHUNK")
    print("-" * 80)

    parent_id = list(index.parent_chunks.keys())[0]
    parent = index.parent_chunks[parent_id]

    print(f"\nParent ID: {parent_id[:50]}...")
    print(f"URL: {parent.get('url', 'N/A')}")
    print(f"Product: {parent.get('product', 'N/A')}")
    print(f"Content length: {len(parent.get('content', ''))} chars")
    print(f"Preview: {parent.get('content', '')[:200]}...")

    # Show sample child chunk
    print("\n" + "-" * 80)
    print("SAMPLE CHILD CHUNK")
    print("-" * 80)

    child_id = list(index.child_to_parent.keys())[0]
    parent_id = index.child_to_parent[child_id]

    print(f"\nChild ID: {child_id[:50]}...")
    print(f"Parent ID: {parent_id[:50]}...")
    print(f"✅ Parent exists: {parent_id in index.parent_chunks}")

    # Test a simple search
    print("\n" + "=" * 80)
    print("SEARCH TEST")
    print("=" * 80)

    query = "installation"
    print(f"\nQuery: '{query}'")

    try:
        results = index.search(query, top_k=3)
        print(f"\n✅ Search completed: {len(results)} results")

        for i, result in enumerate(results, 1):
            print(f"\nResult #{i}:")
            print(f"  URL: {result.get('url', 'N/A')}")
            print(f"  Product: {result.get('product', 'N/A')}")
            print(f"  Score: {result.get('score', 0):.3f}")
            print(f"  Preview: {result.get('text', '')[:100]}...")

    except Exception as e:
        print(f"\n❌ Search failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    print("\n" + "=" * 80)
    print("✅ PARENT-CHILD INTEGRATION TEST PASSED!")
    print("=" * 80)

    return True


if __name__ == "__main__":
    success = test_parent_child_integration()
    sys.exit(0 if success else 1)
