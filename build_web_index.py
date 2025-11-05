#!/usr/bin/env python3
"""Standalone script to build the HashiCorp web documentation index with full debug logging."""
import logging
import sys

# Configure root logger for DEBUG output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout
)

from hashicorp_web_search import initialize_web_search

def main():
    print("="*80)
    print("Building HashiCorp Web Documentation Search Index")
    print("="*80)
    print()
    print("This will:")
    print("1. Download the sitemap from developer.hashicorp.com")
    print("2. Parse all URLs from the sitemap")
    print("3. Discover validated-designs pages (not in sitemap)")
    print("4. Fetch content from all pages (cached incrementally)")
    print("5. Split into chunks and save to disk")
    print("6. Generate embeddings and build FAISS index (batched)")
    print()
    print("RESUME CAPABILITY:")
    print("- Progress is saved incrementally at each step")
    print("- If interrupted, re-run this script to resume")
    print("- Pages are cached as they're fetched")
    print("- Chunks are saved before embedding generation")
    print("- Index is saved after every 10,000 chunks")
    print()
    print("This may take 30-60 minutes on first run.")
    print("Subsequent runs will resume from where you left off.")
    print("="*80)
    print()

    try:
        # Force rebuild to see all steps
        initialize_web_search(force_update=True)
        print()
        print("="*80)
        print("✓ SUCCESS! Index built and saved.")
        print("="*80)
    except KeyboardInterrupt:
        print("\n")
        print("="*80)
        print("⚠ INTERRUPTED BY USER")
        print("="*80)
        print()
        print("Progress has been saved! You can resume by running:")
        print("  ./run_build_index.sh")
        print()
        print("The script will automatically resume from where it stopped.")
        print("="*80)
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
