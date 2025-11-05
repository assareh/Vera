#!/usr/bin/env python3
"""Test script to validate Consul stale reads query.

Expected answer (from Consul Operating Guide for Adoption, section 8.3.6):
"By default, Consul enables stale reads and sets the max_stale value to 10 years."

This test will help us validate the RAG implementation returns the correct information.
"""
import logging
from hashicorp_pdf_search import initialize_pdf_search, search_pdfs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_consul_stale_reads():
    """Test the Consul stale reads default configuration query."""

    print("=" * 80)
    print("TEST: Consul Stale Reads Default Configuration")
    print("=" * 80)

    # Initialize the PDF search index
    print("\n1. Initializing PDF search index...")
    initialize_pdf_search()

    # Test query
    query = "what's the consul default for stale reads"

    print(f"\n2. Query: '{query}'")
    print("\n3. Expected answer:")
    print("   'By default, Consul enables stale reads and sets the max_stale value to 10 years.'")
    print("   Source: Consul Operating Guide for Adoption, section 8.3.6")

    # Search
    print("\n4. Searching PDF index...")
    results = search_pdfs(query, top_k=5, product="consul")

    print("\n5. Results:")
    print("-" * 80)
    print(results)
    print("-" * 80)

    # Analysis
    print("\n6. Analysis:")
    if "10 years" in results.lower() or "max_stale" in results.lower():
        print("   ✅ PASS: Found correct information about max_stale = 10 years")
    else:
        print("   ❌ FAIL: Did not find correct information about max_stale = 10 years")

    if "adoption" in results.lower():
        print("   ✅ PASS: Found information in Adoption guide")
    else:
        print("   ⚠️  WARNING: Did not find information in Adoption guide")

    if "stale" in results.lower() and "false" in results.lower():
        print("   ❌ FAIL: Incorrectly mentions stale flag defaults to false")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    test_consul_stale_reads()
