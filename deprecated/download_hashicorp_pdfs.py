#!/usr/bin/env python3
"""Helper script to download HashiCorp Validated Design PDFs.

Since HashiCorp's PDF downloads require clicking a button on their website,
this script provides instructions and URLs for manual downloads.

For automation, you can use this with Selenium or Playwright.
"""

from pathlib import Path
from hashicorp_pdf_search import VALIDATED_DESIGNS

def main():
    print("=" * 80)
    print("HashiCorp Validated Designs PDF Download Helper")
    print("=" * 80)
    print()
    print("The PDFs need to be manually downloaded from HashiCorp's website.")
    print("For each document below:")
    print("  1. Visit the URL")
    print("  2. Click 'Download as PDF' in the left navigation")
    print("  3. Save to: ./hashicorp_pdfs/pdfs/")
    print()
    print("=" * 80)
    print()

    # Create directory if it doesn't exist
    pdfs_dir = Path("./hashicorp_pdfs/pdfs")
    pdfs_dir.mkdir(parents=True, exist_ok=True)
    print(f"✓ PDF directory created: {pdfs_dir.absolute()}")
    print()

    # List all documents
    for idx, design in enumerate(VALIDATED_DESIGNS, 1):
        print(f"{idx}. {design['name']}")
        print(f"   Product: {design['product']}")
        print(f"   URL: https://developer.hashicorp.com/validated-designs/{design['slug']}")
        print(f"   Save as: {design['slug']}.pdf")
        print()

    print("=" * 80)
    print()
    print("Alternative: Automated download with Selenium")
    print()
    print("If you want to automate downloads, you can use Selenium:")
    print()
    print("  pip install selenium webdriver-manager")
    print()
    print("Then modify the _download_pdf() method in hashicorp_pdf_search.py")
    print("to use Selenium to click the 'Download as PDF' button.")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
