#!/usr/bin/env python3
"""Compare v1 (raw FAISS) vs v2 (LangChain FAISS) implementations.

Test case: Consul stale reads default configuration.
Expected answer: "By default, Consul enables stale reads and sets the max_stale value to 10 years."
Source: Consul Operating Guide for Adoption, section 8.3.6
"""
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_v2():
    """Test the new LangChain-based implementation."""
    print("\n" + "=" * 80)
    print("TESTING V2 (LangChain FAISS Implementation)")
    print("=" * 80)

    try:
        # Add parent directory to path to import modules from project root
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))

        from hashicorp_pdf_search import initialize_pdf_search, search_pdfs

        print("\n1. Initializing V2 index...")
        initialize_pdf_search()

        query = "what's the consul default for stale reads"
        print(f"\n2. Query: '{query}'")

        print("\n3. Searching...")
        results = search_pdfs(query, top_k=5, product="consul")

        print("\n4. Results:")
        print("-" * 80)
        print(results)
        print("-" * 80)

        # Analysis
        print("\n5. Analysis:")
        success_count = 0

        if "max_stale" in results.lower() and "10 years" in results.lower():
            print("   ✅ PASS: Found both 'max_stale' and '10 years'")
            success_count += 1
        elif "max_stale" in results.lower() or "10 years" in results.lower():
            print("   ⚠️  PARTIAL: Found one of 'max_stale' or '10 years'")
            success_count += 0.5
        else:
            print("   ❌ FAIL: Did not find 'max_stale' or '10 years'")

        if "adoption" in results.lower():
            print("   ✅ PASS: Found reference to Adoption guide")
            success_count += 1
        else:
            print("   ⚠️  WARNING: No reference to Adoption guide")

        if "enables stale reads" in results.lower() or "allow_stale = true" in results.lower():
            print("   ✅ PASS: Found evidence that stale reads are enabled by default")
            success_count += 1
        else:
            print("   ⚠️  WARNING: Unclear about default enabled status")

        # Check for wrong information
        if "stale" in results.lower() and "false" in results.lower() and "default" in results.lower():
            print("   ❌ FAIL: Contains incorrect 'defaults to false' information")
            success_count -= 1

        print(f"\n   Overall: {success_count}/3 checks passed")

        return success_count >= 2.5  # Require at least 2.5/3 to pass

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run comparison tests."""
    print("\n" + "=" * 80)
    print("CONSUL STALE READS TEST - V2 Implementation")
    print("=" * 80)
    print("\nExpected Answer:")
    print("  'By default, Consul enables stale reads and sets the max_stale value to 10 years.'")
    print("  Source: Consul Operating Guide for Adoption, section 8.3.6")
    print("\n" + "=" * 80)

    # Test V2
    v2_passed = test_v2()

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"V2 (LangChain): {'✅ PASS' if v2_passed else '❌ FAIL'}")
    print("=" * 80)

    return 0 if v2_passed else 1


if __name__ == "__main__":
    sys.exit(main())
