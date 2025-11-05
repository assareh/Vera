#!/usr/bin/env python3
"""Check the status of the HashiCorp web documentation index build."""
import json
from pathlib import Path
from datetime import datetime

def format_timestamp(iso_string):
    """Format ISO timestamp for display."""
    try:
        dt = datetime.fromisoformat(iso_string)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return iso_string

def main():
    cache_dir = Path("hashicorp_web_docs")

    print("="*80)
    print("HashiCorp Web Documentation Index - Build Status")
    print("="*80)
    print()

    # Check if cache directory exists
    if not cache_dir.exists():
        print("❌ No build started yet")
        print(f"   Cache directory not found: {cache_dir}")
        return

    # Check URL list
    url_list_file = cache_dir / "url_list.json"
    if url_list_file.exists():
        try:
            url_list = json.loads(url_list_file.read_text())
            print(f"✅ URL Discovery: Complete")
            print(f"   Total URLs: {len(url_list)}")
        except:
            print("⚠️  URL list file exists but is corrupted")
    else:
        print("⏳ URL Discovery: Not started")

    print()

    # Check pages cached
    pages_dir = cache_dir / "pages"
    if pages_dir.exists():
        cached_pages = list(pages_dir.glob("*.json"))
        print(f"✅ Page Scraping: In progress or complete")
        print(f"   Cached pages: {len(cached_pages)}")
        if url_list_file.exists():
            try:
                url_list = json.loads(url_list_file.read_text())
                percent = (len(cached_pages) / len(url_list)) * 100
                print(f"   Progress: {percent:.1f}%")
            except:
                pass
    else:
        print("⏳ Page Scraping: Not started")

    print()

    # Check chunks
    chunks_file = cache_dir / "chunks.json"
    if chunks_file.exists():
        try:
            chunks = json.loads(chunks_file.read_text())
            print(f"✅ Chunking: Complete")
            print(f"   Total chunks: {len(chunks)}")
        except:
            print("⚠️  Chunks file exists but is corrupted")
    else:
        print("⏳ Chunking: Not started")

    print()

    # Check embedding progress
    progress_file = cache_dir / "embedding_progress.json"
    if progress_file.exists():
        try:
            progress = json.loads(progress_file.read_text())
            percent = (progress['completed'] / progress['total']) * 100
            print(f"🔄 Embedding Generation: In progress")
            print(f"   Completed: {progress['completed']:,}/{progress['total']:,} chunks ({percent:.1f}%)")
            print(f"   Last saved: {format_timestamp(progress['timestamp'])}")
        except:
            print("⚠️  Progress file exists but is corrupted")
    else:
        print("⏳ Embedding Generation: Not started")

    print()

    # Check final index
    index_file = cache_dir / "index" / "index.faiss"
    if index_file.exists():
        size_mb = index_file.stat().st_size / (1024 * 1024)
        print(f"✅ FAISS Index: Built")
        print(f"   Index size: {size_mb:.1f} MB")

        # Check metadata
        metadata_file = cache_dir / "metadata.json"
        if metadata_file.exists():
            try:
                metadata = json.loads(metadata_file.read_text())
                print(f"   Last update: {format_timestamp(metadata['last_update'])}")
                print(f"   Page count: {metadata.get('page_count', 'unknown')}")
                print(f"   Model: {metadata.get('model_name', 'unknown')}")
            except:
                pass
    else:
        print("⏳ FAISS Index: Not built yet")

    print()
    print("="*80)

    # Provide helpful next steps
    if not index_file.exists():
        print()
        print("Next step: Run ./run_build_index.sh to continue building the index")
        if chunks_file.exists():
            print("(Will resume from embedding generation)")
        elif pages_dir.exists() and len(list(pages_dir.glob("*.json"))) > 0:
            print("(Will use cached pages and generate chunks)")
    else:
        print()
        print("✅ Index is complete and ready to use!")

if __name__ == "__main__":
    main()
