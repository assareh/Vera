#!/usr/bin/env python3
"""Test script for HashiCorp docs search tool."""

import sys
sys.path.insert(0, '.')

from tools import search_hashicorp_docs

def test_general_search():
    """Test general HashiCorp search."""
    print("=" * 60)
    print("Test 1: General Terraform search")
    print("=" * 60)
    result = search_hashicorp_docs(
        query="terraform modules",
        max_results=3
    )
    print(result)
    print("\n")

def test_product_specific_search():
    """Test product-specific search."""
    print("=" * 60)
    print("Test 2: Vault-specific search")
    print("=" * 60)
    result = search_hashicorp_docs(
        query="authentication methods",
        product="vault",
        max_results=3
    )
    print(result)
    print("\n")

def test_consul_search():
    """Test Consul search."""
    print("=" * 60)
    print("Test 3: Consul service mesh")
    print("=" * 60)
    result = search_hashicorp_docs(
        query="service mesh configuration",
        product="consul",
        max_results=3
    )
    print(result)
    print("\n")

if __name__ == "__main__":
    print("Testing HashiCorp Documentation Search Tool\n")

    try:
        test_general_search()
        test_product_specific_search()
        test_consul_search()

        print("=" * 60)
        print("All tests completed successfully!")
        print("=" * 60)
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()
