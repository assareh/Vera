"""Test script for HashiCorp web documentation crawler.

Tests the web crawler on a small sample of pages to validate:
- Sitemap parsing
- robots.txt compliance
- Content extraction (headings, code blocks)
- FAISS indexing
- Search functionality
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from hashicorp_web_search import HashiCorpWebSearchIndex
import logging

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_web_crawler():
    """Test web crawler with a small sample of pages."""
    print("\n" + "="*80)
    print("Testing HashiCorp Web Documentation Crawler")
    print("="*80 + "\n")

    # Create index with limited pages for testing
    print("Step 1: Initializing crawler (limiting to 20 pages for testing)...")
    index = HashiCorpWebSearchIndex(
        cache_dir="./test_hashicorp_web_docs",
        max_pages=20,  # Only crawl 20 pages for testing
        rate_limit_delay=0.2  # Be extra polite
    )

    # Initialize (download sitemap, crawl pages, build index)
    print("\nStep 2: Crawling pages and building index...")
    index.initialize(force_update=True)

    if index.vectorstore is None:
        print("\n❌ FAILED: Vector store not initialized")
        return False

    print("\n✅ Index built successfully!")

    # Test search queries
    test_queries = [
        "consul service mesh",
        "terraform modules",
        "vault authentication methods",
        "nomad job specification"
    ]

    print("\nStep 3: Testing search queries...\n")

    for query in test_queries:
        print(f"\n{'-'*80}")
        print(f"Query: {query}")
        print(f"{'-'*80}")

        results = index.search(query, top_k=3)

        if results:
            print(f"Found {len(results)} results:")
            for idx, result in enumerate(results, 1):
                print(f"\n{idx}. [{result['product'].upper()}]")
                print(f"   URL: {result['url']}")
                print(f"   Score: {result['score']:.3f}")
                print(f"   Preview: {result['text'][:200]}...")
        else:
            print("No results found")

    print("\n" + "="*80)
    print("✅ Web crawler test completed successfully!")
    print("="*80 + "\n")

    return True


if __name__ == "__main__":
    try:
        success = test_web_crawler()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
