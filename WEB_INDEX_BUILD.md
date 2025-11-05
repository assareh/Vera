# HashiCorp Web Documentation Index - Build Process

## Overview

The web documentation indexing system is **fully automatic and resilient to interruptions**. When you start Ivan, it automatically:

1. ✅ Checks if the index exists
2. ✅ Builds the index in the background if needed (non-blocking)
3. ✅ Updates the index automatically every 7 days
4. ✅ Resumes from interruptions automatically
5. ✅ Saves progress incrementally at each stage

**You don't need to manually manage the index** - it just works!

## Build Stages

The build process consists of 4 main stages:

### 1. URL Discovery
- Downloads sitemap from developer.hashicorp.com
- Parses all URLs from the sitemap
- Discovers validated-designs pages (not in sitemap)
- **Saved to:** `hashicorp_web_docs/url_list.json`

### 2. Page Scraping
- Fetches content from all discovered URLs
- Extracts main documentation content from HTML
- **Saved to:** `hashicorp_web_docs/pages/*.json` (one file per page)
- **Resume capability:** Already-cached pages are skipped

### 3. Chunking
- Splits documents into 1000-character chunks with 200-char overlap
- Creates LangChain Document objects with metadata
- **Saved to:** `hashicorp_web_docs/chunks.json`
- **Resume capability:** If chunks.json exists, scraping is skipped

### 4. Embedding Generation & Index Build
- Generates semantic embeddings for each chunk using all-MiniLM-L6-v2
- Builds FAISS vector index
- **Saved to:** `hashicorp_web_docs/index/` (every 10,000 chunks)
- **Progress tracked in:** `hashicorp_web_docs/embedding_progress.json`
- **Resume capability:** Builds in batches with incremental saves

## Automatic Management

### Normal Usage (Recommended)

Simply start Ivan - the index is managed automatically:

```bash
python3 ivan.py
```

On startup, Ivan will:
- Check if the index exists
- Build it in the background if needed (without blocking startup)
- Show you the current status
- Continue to serve requests immediately

The index builds in the background and becomes available when ready.

### Check Index Status

While Ivan is running:
```bash
./index_status
```

Or via API:
```bash
curl http://localhost:8000/index/status
```

When Ivan is NOT running:
```bash
python3 check_index_status.py
```

### Manual Build (Optional)

If you prefer to build the index manually before starting Ivan:

```bash
./run_build_index.sh
```

This is useful if you want to:
- Build the index before first use
- Monitor build progress interactively
- Build on one machine and transfer to another

### Force Rebuild

To force a complete rebuild:
```bash
rm -rf hashicorp_web_docs/
python3 ivan.py  # Will rebuild automatically
```

Or manually:
```bash
rm -rf hashicorp_web_docs/
./run_build_index.sh
```

## Expected Timeline

### Fresh build:
- **URL Discovery:** ~30 seconds
- **Page Scraping:** ~15-20 minutes (7,000+ pages, parallel fetching)
- **Chunking:** ~5 seconds (in-memory processing)
- **Embedding Generation:** ~90-120 minutes (97,000+ chunks)
- **Total:** ~2 hours

### Resume from interruption:
- **If interrupted during scraping:** Continues from last cached page
- **If interrupted after scraping:** Jumps directly to embedding generation (~90 min)
- **If interrupted during embedding:** Resumes from last saved batch

## Cache Files

All cache files are stored in `hashicorp_web_docs/`:

```
hashicorp_web_docs/
├── sitemap.xml                  # Downloaded sitemap
├── url_list.json                # All discovered URLs
├── pages/                       # Individual page caches
│   └── <hash>.json              # One file per URL
├── chunks.json                  # All chunks (97k+ objects, ~500MB)
├── embedding_progress.json      # Current embedding batch
├── index/                       # FAISS vector store
│   ├── index.faiss              # Vector index
│   └── index.pkl                # Document metadata
└── metadata.json                # Build metadata & timestamps
```

## Transferring to Another Machine

### To run embedding generation on a faster machine:

1. **On the original machine** (after scraping completes):
```bash
# Wait for chunks.json to be created
python3 check_index_status.py

# Once you see "✅ Chunking: Complete", transfer the cache
tar -czf hashicorp_web_cache.tar.gz hashicorp_web_docs/
scp hashicorp_web_cache.tar.gz other-machine:/path/to/Ivan/
```

2. **On the faster machine**:
```bash
cd /path/to/Ivan/
tar -xzf hashicorp_web_cache.tar.gz
./run_build_index.sh  # Will skip scraping, jump to embedding generation
```

3. **Transfer back the completed index**:
```bash
# On faster machine
tar -czf hashicorp_index_only.tar.gz hashicorp_web_docs/index/ hashicorp_web_docs/metadata.json

# On original machine
scp other-machine:/path/to/Ivan/hashicorp_index_only.tar.gz .
tar -xzf hashicorp_index_only.tar.gz
```

## Troubleshooting

### Process appears stuck
Check the latest log file:
```bash
tail -f build_index_*.log
```

### Out of memory during embedding
The script processes in 10k-chunk batches. If you still run out of memory:
1. Edit `hashicorp_web_search.py`
2. Find `batch_size = 10000` in `_build_index()` method
3. Reduce to `5000` or `2000`

### Corrupted cache files
Remove specific cache files and re-run:
```bash
# Re-do chunking and embedding
rm hashicorp_web_docs/chunks.json
rm -rf hashicorp_web_docs/index/
./run_build_index.sh

# Re-scrape everything
rm -rf hashicorp_web_docs/pages/
./run_build_index.sh
```

### Want to update just the index (not re-scrape)
The index is automatically rebuilt from cached pages if:
- Cache is older than 7 days, OR
- You run with `force_update=True`

To force index rebuild without re-scraping:
```python
from hashicorp_web_search import initialize_web_search
initialize_web_search(force_update=True)
```

## Implementation Details

### Batch Size Strategy
- **Page fetching:** 10 parallel workers
- **Embedding generation:** 10,000 chunks per batch
- **Progress saves:** After every batch

### Why incremental saves matter
- **Embedding generation** is the slowest step (~1.9s per 32-chunk batch)
- **97,277 chunks** = ~3,040 batches = ~95 minutes of compute
- **Saving every 10k chunks** means ~6 save points during the process
- If interrupted at 50% (48k chunks), you save ~45 minutes on resume

### Memory usage
- **During scraping:** Low (~500MB), pages processed individually
- **During chunking:** Medium (~1GB), all documents in memory briefly
- **During embedding:** High (2-3GB), model + batch of embeddings in memory

## Future Enhancements

Possible improvements for even better resilience:
- [ ] Stream chunks to disk during creation (avoid loading all into memory)
- [ ] Smaller embedding batches with more frequent saves
- [ ] Parallel embedding generation across multiple machines
- [ ] Delta updates (only re-index changed pages)
- [ ] Compression of chunks.json (currently ~500MB uncompressed)
