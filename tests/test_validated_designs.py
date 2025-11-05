"""Test validated-designs discovery."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from hashicorp_doc_search import HashiCorpDocSearchIndex
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_validated_designs_discovery():
    """Test that we can discover validated-designs pages."""
    print("\n" + "="*80)
    print("Testing Validated-Designs Discovery")
    print("="*80 + "\n")

    index = HashiCorpDocSearchIndex(
        cache_dir="./test_validated_designs",
        max_pages=None,  # Don't limit for this test
        rate_limit_delay=0.2
    )

    # Test discovery
    print("Discovering validated-designs pages...")
    validated_designs = index._discover_validated_designs()

    if not validated_designs:
        print("\n❌ FAILED: No validated-designs pages discovered")
        return False

    print(f"\n✅ Discovered {len(validated_designs)} validated-designs pages")

    # Show some examples
    print("\nSample URLs:")
    for idx, url_info in enumerate(validated_designs[:10], 1):
        print(f"{idx}. [{url_info['product'].upper()}] {url_info['url']}")

    # Check that we have multiple products
    products = set(url_info['product'] for url_info in validated_designs)
    print(f"\nProducts found: {', '.join(sorted(products))}")

    # Test that robots.txt override works
    test_url = "https://developer.hashicorp.com/validated-designs/terraform-operating-guides-adoption"
    can_fetch = index._can_fetch(test_url)
    print(f"\nRobots.txt override test: {'✅ PASS' if can_fetch else '❌ FAIL'}")

    print("\n" + "="*80)
    print("✅ Validated-designs discovery test completed!")
    print("="*80 + "\n")

    return True


if __name__ == "__main__":
    try:
        success = test_validated_designs_discovery()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
