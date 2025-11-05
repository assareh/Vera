# Deprecated Files

This directory contains deprecated code that is no longer used in production but kept for historical reference.

## PDF Search Implementation (Deprecated)

**Replaced by:** Web crawler search (`hashicorp_web_search.py`)

The following files implemented the old PDF-based documentation search:

- `hashicorp_pdf_search.py` - Final version of PDF search using LangChain FAISS
- `hashicorp_pdf_search_v1_backup.py` - Earlier version (backup)
- `download_hashicorp_pdfs.py` - PDF download automation using Selenium
- `validate_semantic_search.py` - Validation script for PDF search

**Why deprecated:**
- PDF search only covered validated design documents
- Web crawler indexes the entire developer.hashicorp.com site (much more comprehensive)
- Web crawler includes validated designs + all product docs + guides
- Better maintenance: automatically updates when HashiCorp publishes new docs

## Unified Search (Deprecated)

- `hashicorp_unified_search.py` - Attempted to combine PDF and web search

**Why deprecated:**
- Web crawler made this unnecessary
- All content now in single index

## Migration Date

November 5, 2025

## If You Need These Files

These files are kept for reference only. If you need to understand how the old PDF search worked or want to reference the implementation, you can find the code here.

**Do not import these modules in production code.**
