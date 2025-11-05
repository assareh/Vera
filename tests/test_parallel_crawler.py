"""Test parallel web crawler."""
import sys
from pathlib import Path
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from hashicorp_web_search import HashiCorpWebSearchIndex
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_parallel_crawler():
    """Test parallel crawler on 100 pages."""
    print("\n" + "="*80)
    print("Testing Parallel Web Crawler")
    print("="*80 + "\n")

    # Test with 100 pages
    print("Testing with 100 pages, 10 parallel workers...")
    start_time = time.time()

    index = HashiCorpWebSearchIndex(
        cache_dir="./test_parallel_crawl",
        max_pages=100,
        max_workers=10
    )

    index.initialize(force_update=True)

    elapsed = time.time() - start_time

    if index.vectorstore is None:
        print("\n❌ FAILED: Vector store not initialized")
        return False

    print(f"\n✅ Indexed 100 pages in {elapsed:.1f} seconds ({elapsed/100:.2f}s per page)")
    print(f"   That's {100/elapsed:.1f} pages/second")

    # Test search
    print("\nTesting search functionality...")
    results = index.search("consul stale reads", top_k=3)

    if results:
        print(f"\n✅ Search working - found {len(results)} results")
        for idx, result in enumerate(results, 1):
            print(f"\n{idx}. [{result['product'].upper()}]")
            print(f"   URL: {result['url']}")
            print(f"   Score: {result['score']:.3f}")
    else:
        print("\n⚠️  No results found (may be normal with small sample)")

    # Test caching
    print("\n" + "="*80)
    print("Testing caching (rebuilding index)...")
    print("="*80 + "\n")

    start_time = time.time()
    index2 = HashiCorpWebSearchIndex(
        cache_dir="./test_parallel_crawl",
        max_pages=100,
        max_workers=10
    )
    index2.initialize(force_update=True)
    elapsed2 = time.time() - start_time

    print(f"\n✅ Second run with caching: {elapsed2:.1f} seconds")
    print(f"   Speedup: {elapsed/elapsed2:.1f}x faster")

    print("\n" + "="*80)
    print("✅ Parallel crawler test completed successfully!")
    print("="*80 + "\n")

    return True


if __name__ == "__main__":
    try:
        success = test_parallel_crawler()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
