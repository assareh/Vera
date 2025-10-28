#!/usr/bin/env python3
"""Test Selenium-based PDF download for a single document."""

import sys
import logging
sys.path.insert(0, '.')

from hashicorp_pdf_search import HashiCorpPDFSearchIndex, VALIDATED_DESIGNS

# Set up logging to see all messages (including DEBUG)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    print("=" * 70)
    print("Testing Selenium-based PDF Download")
    print("=" * 70)
    print()

    # Initialize the search index
    index = HashiCorpPDFSearchIndex()

    # Try downloading just one PDF as a test (Boundary adoption guide - we know this one has a PDF link)
    test_design = VALIDATED_DESIGNS[0]  # Boundary: Operating Guide for Adoption

    print(f"Testing download of: {test_design['name']}")
    print(f"URL: https://developer.hashicorp.com/validated-designs/{test_design['slug']}")
    print()
    print("This will open a headless Chrome browser and attempt to download the PDF...")
    print("(Chrome/ChromeDriver will be downloaded automatically if not present)")
    print()

    try:
        pdf_path = index._download_pdf(test_design)

        if pdf_path:
            print()
            print("=" * 70)
            print("✓ SUCCESS!")
            print(f"  PDF downloaded to: {pdf_path}")
            print(f"  File size: {pdf_path.stat().st_size / 1024:.1f} KB")
            print("=" * 70)
            print()
            print("Now you can run the full initialization to download all PDFs:")
            print("  python3 test_pdf_search.py")
        else:
            print()
            print("=" * 70)
            print("✗ DOWNLOAD FAILED")
            print("  Check the logs above for details")
            print("  You may need to manually download PDFs")
            print("=" * 70)

    except Exception as e:
        print()
        print("=" * 70)
        print(f"✗ ERROR: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
