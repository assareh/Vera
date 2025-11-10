# Ivan - Work in Progress

Last updated: 2025-11-05 (Updated after cross-encoder implementation and retrieval analysis)

## Current Status

### Recently Completed ✅

#### Cross-Encoder Re-Ranking (2025-11-05) 🎯
- [x] **Implemented cross-encoder re-ranking** for improved result precision
- [x] Added `CrossEncoder` from sentence-transformers (`cross-encoder/ms-marco-MiniLM-L-12-v2`)
- [x] Re-ranks top-20 candidates from hybrid search before returning top-k results
- [x] Added configuration options: `enable_reranking`, `rerank_model`, `rerank_top_k`
- [x] **Result**: Fixed Consul stale reads test (0% → 100% pass rate)
- [x] Latency impact: ~0.5-1s per search (acceptable trade-off)
- [x] **Status**: Deployed and working, ready for production

#### Core Search Infrastructure
- [x] Migrated from PDF search to web crawler (hashicorp_doc_search)
- [x] Implemented hybrid search (BM25 + semantic FAISS) - 50/50 weighting
- [x] Added tool call debug logging to `ivan_tools_debug.log`
- [x] Fixed LangChain deprecation warnings (invoke vs get_relevant_documents)
- [x] Upgraded LangChain to 0.3.27 with pydantic compatibility fixes
- [x] Adjusted scoring algorithm (exponential decay: `1.0 / (1.0 + idx * 0.1)`)
- [x] Reduced validated-designs boost from 2.0x to 1.15x
- [x] Renamed hashicorp_web_search → hashicorp_doc_search for accuracy
- [x] Updated all imports and references across codebase
- [x] Deprecated old PDF search files to `deprecated/` directory
- [x] **Fixed duplicate URL bug** - Deduplication keeps top 2 sections per page

#### Token-Based Adaptive Chunking (commit 54c86c4) 🎯
- [x] **Implemented token-based chunking** using tiktoken (cl100k_base encoding)
- [x] **Adaptive chunk sizes by document type**:
  - API/CLI pages: 500 tokens (~15% overlap)
  - Configuration: 400 tokens (~20% overlap)
  - Release notes: 600 tokens (~10% overlap)
  - Tutorials/guides: 900 tokens (~15% overlap)
  - Concepts/how-to: 800 tokens (default, ~15% overlap)
- [x] **Section-aware chunking strategy**:
  - Chunks by H2/H3 boundaries instead of fixed splits
  - Preserves heading context in each chunk
  - Keeps code blocks and tables atomic
  - Intelligent overlap between sections
  - Implemented in `_split_into_sections()` method
- [x] **Section anchors for precise citations** 🎯:
  - Extracts H2/H3 section anchors during HTML parsing
  - Stores anchor IDs in chunk metadata (`section_anchor`)
  - Returns URLs with anchors: `url#section-id`
  - Enables jump-to-section links for actionable answers
  - Implemented in `_extract_main_content()` method

#### Enhanced Content Extraction
- [x] **Table extraction** - Converts HTML tables to markdown format
- [x] **URL normalization** - Removes fragments before caching to prevent duplicates
- [x] **Validated-designs discovery fixes** - Properly crawls all guide subpages

#### Index Management Improvements
- [x] Simplified index build process (inline, transparent progress)
- [x] Added `--rebuild-index` flag for fast rebuilds (uses cached pages)
- [x] Added `--force-scrape` flag for complete re-scrape
- [x] Enhanced progress indicators for all 4 build phases
- [x] Deleted obsolete scripts: build_web_index.py, web_index_manager.py, etc.

#### Test Infrastructure
- [x] **Certification test suite** (commit 3db1f43):
  - 26 certification questions (Vault, Consul, Terraform)
  - **88.5% pass rate** (23/26) with medium reasoning effort
  - Automated grading with edge case handling
  - Results: Vault 92.9%, Consul 71.4%, Terraform 100%
- [x] **Regression test framework** (commit dee4d1c):
  - Multi-test-case framework in test_comparison.py
  - Scoring system (must_contain, should_contain, must_not_contain)
  - Two test cases: Consul stale reads, Vault disk throughput

### Known Issues 🐛

#### 1. Regression Test Failures (1/2 passing) ⚠️ IN PROGRESS

**Consul Stale Reads Test** ✅ **FIXED**
- Query: "what's the consul default for stale reads"
- Expected: "max_stale value to 10 years" from Consul Adoption Guide
- **Status**: ✅ **PASS (100%)** after cross-encoder re-ranking implementation
- Cross-encoder successfully boosted correct answer from rank ~5 to rank #1

**Vault Disk Throughput Test** ❌ **RETRIEVAL PROBLEM**
- Query: "what disk throughput is needed to run vault"
- Expected: "75+ MB/s, 250+ MB/s" from `vault/tutorials/day-one-raft/raft-reference-architecture#hardware-sizing-for-vault-servers`
- **Problem**: Correct chunk with table EXISTS in index but not retrieved in top-50 candidates
- **Analysis**: Cross-encoder can only re-rank what's retrieved. This is a retrieval issue, not a ranking issue.
- **Action**: Try retrieval optimizations (see below)

#### 2. Search Quality Observations

**Current Strengths**:
- ✅ Hybrid search (50% BM25, 50% semantic) working well
- ✅ Section anchors working (URLs include `#section-id`)
- ✅ Token-based adaptive chunking by doc type
- ✅ Good score distribution (exponential decay)
- ✅ URL deduplication (max 2 sections per page)
- ✅ Product filtering working
- ✅ Table extraction working
- ✅ **88.5% accuracy on certification questions**

**Gaps Remaining**:
- ⚠️ Partial metadata (missing: version, doc_type, hcp flag)
- ⚠️ No result re-ranking (answers present but not always top-ranked)
- ⚠️ No live search fallback for freshness
- ⚠️ No incremental updates (full rebuild required)

### Upcoming Tasks 📋

#### High Priority - Retrieval Optimization (Vault Disk Throughput Fix)

**Problem**: Correct chunk with "75+ MB/s, 250+ MB/s" exists in index but not retrieved in top-50 candidates.

**Root Cause Analysis**:
- Query: "what disk throughput is needed to run vault"
- Target chunk: Contains table with "Small: 75+ MB/s, Large: 250+ MB/s"
- Semantic gap: Query uses "needed" and "run", chunk uses "requirements" and "sizing"
- BM25 gap: Limited keyword overlap between query and table content

**Three Optimization Approaches to Test** (in priority order):

1. **Query Expansion with Domain Synonyms** ⭐ **[RECOMMENDED - MOST TARGETED]**
   - Expand query with HashiCorp-specific terminology:
     - "disk throughput needed" → add "disk IO", "IOPS", "MB/s", "disk performance"
     - "requirements" → add "sizing", "recommendations", "hardware", "system requirements"
     - "run vault" → add "deploy vault", "vault server", "production vault"
   - Implementation: Create expansion dictionary, append synonyms to query
   - **Impact**: HIGH - Directly addresses semantic gap between query and chunk
   - **Effort**: LOW (~50-100 lines) - Simple dictionary + query modification
   - **Trade-off**: May retrieve more candidates but cross-encoder will filter
   - **Latency**: Negligible (~10ms)
   - **Status**: Not started
   - **Expected outcome**: Retrieve the hardware-sizing chunk in top-20 candidates

2. **BM25 Weight Tuning** (Currently 50/50)
   - Test different hybrid search weight configurations:
     - Current: 50% BM25, 50% semantic
     - Option A: 60% BM25, 40% semantic (favor exact term matching)
     - Option B: 40% BM25, 60% semantic (favor conceptual matching)
     - Option C: 70% BM25, 30% semantic (heavy keyword bias)
   - Implementation: Adjust `EnsembleRetriever` weights parameter
   - **Impact**: MEDIUM - May help if BM25 is better at finding the chunk
   - **Effort**: VERY LOW (~5 lines) - Just change weight parameter
   - **Trade-off**: May hurt other queries that rely on semantic matching
   - **Latency**: None
   - **Status**: Not started
   - **Expected outcome**: Uncertain - needs testing with regression suite

3. **Multi-Query Generation with LLM** (Most sophisticated)
   - Generate 3-5 query variations using LLM:
     - Original: "what disk throughput is needed to run vault"
     - Variation 1: "vault disk performance requirements"
     - Variation 2: "vault server IOPS and MB/s specifications"
     - Variation 3: "vault hardware sizing disk throughput"
   - Search with all variations, merge and deduplicate results
   - Re-rank combined candidate pool with cross-encoder
   - **Impact**: HIGH - Multiple angles increase retrieval probability
   - **Effort**: MEDIUM (~150-200 lines) - LLM call + result merging
   - **Trade-off**: Adds 1-2s latency for LLM query generation
   - **Latency**: HIGH (~1-2s for LLM call + multiple searches)
   - **Status**: Not started
   - **Expected outcome**: High success rate but significant latency cost

**Comparison Matrix**:

| Approach | Impact | Effort | Latency | Risk | Recommendation |
|----------|--------|--------|---------|------|----------------|
| Query Expansion | HIGH | LOW | ~10ms | LOW | ⭐ **TRY FIRST** |
| BM25 Tuning | MEDIUM | VERY LOW | 0ms | MEDIUM (may hurt other queries) | Try second |
| Multi-Query LLM | HIGH | MEDIUM | ~1-2s | LOW | Try if others fail |

**Implementation Plan**:
1. Implement query expansion first (lowest effort, high impact)
2. Run regression tests to validate improvement
3. If still failing, try BM25 weight tuning
4. If both fail, implement multi-query generation

**Success Criteria**:
- Vault disk throughput test passes (retrieves hardware-sizing chunk in top-20)
- Consul stale reads test still passes (no regression)
- Certification test suite maintains ≥85% pass rate

1. ~~**Cross-Encoder Re-Ranking**~~ ✅ **COMPLETED (2025-11-05)**
   - Added `cross-encoder/ms-marco-MiniLM-L-12-v2` model
   - Re-scores top-20 results for better precision
   - **Result**: Fixed Consul test (0% → 100%), improved ranking significantly
   - **Latency**: Adds ~0.5-1s per search (acceptable)
   - **Status**: ✅ Deployed and working

#### Medium Priority - Extended Features

2. **Enhanced Metadata Schema** (Partial completion)
   - ✅ Already have: product, source, section_heading, section_anchor, lastmod
   - ❌ Missing:
     - Extract version info from URLs or page content
     - Classify doc_type: `howto | concept | api | release-notes | tutorial`
     - Add `hcp` boolean flag (cloud.hashicorp vs developer.hashicorp)
   - **Impact**: Better filtering, more precise answers
   - **Effort**: Medium (update crawler + metadata extraction)
   - **Status**: 50% complete

3. **Confidence-Based Live Search Fallback**
   - Integrate Ollama Web Search as secondary retriever
   - Detect low-confidence scenarios:
     - Top result score < threshold (e.g., 0.6)
     - Empty result set
     - Query contains "latest", "new", "GA", "RC", version numbers
   - Route to live search when confidence low
   - Cache and optionally index live search results
   - **Impact**: Freshness + edge case coverage
   - **Effort**: High (new integration + routing logic)
   - **Status**: Not started

#### Lower Priority - Extended Coverage

4. **HCP Changelog Indexing**
   - Add crawler for `cloud.hashicorp.com/changelog`
   - Tag with doc_type: "release-notes" and hcp: true
   - Update daily (managed offerings move on own cadence)
   - **Impact**: Coverage of HCP-specific changes
   - **Effort**: Low (similar to existing crawler)

5. **GitHub Releases Integration**
   - Add GitHub API integration for each product
   - Index release notes from GitHub (markdown format)
   - Tag with version + release date
   - Update daily
   - **Impact**: Covers pre-docs.hashicorp.com content
   - **Effort**: Medium (GitHub API integration)

6. **Incremental Updates**
   - Track ETags or last-modified dates for pages
   - Implement differential crawling logic
   - Handle deletions and moves
   - Only re-index changed pages instead of full rebuild
   - **Impact**: Faster daily/weekly refreshes
   - **Effort**: High (~500+ lines of code)
   - **Trade-off**: More complex state management
   - **Status**: Not started

7. **Automated Refresh Cadence**
   - Daily: release notes + HCP changelog + GitHub releases
   - Weekly: all product docs
   - On-demand: when query misses or confidence low
   - Add CLI flags: `--refresh=daily|weekly|all`
   - **Impact**: Keeps index fresh
   - **Effort**: Low (scheduling + incremental update logic)

8. **Documentation updates**
   - Update README.md with cross-encoder re-ranking details
   - Update CLAUDE.md with retrieval optimization strategies
   - Document query expansion dictionary
   - Add troubleshooting guide for common search issues

9. **Performance optimization**
    - Consider caching BM25 retriever initialization
    - Profile search performance with cross-encoder overhead
    - Optimize embedding generation (batching)
    - **Status**: Performance is acceptable, deprioritized

### Notes

**Search Implementation Details**
- **Hybrid Search**: LangChain EnsembleRetriever (50% BM25, 50% semantic)
- **BM25**: Keyword matching using rank-bm25 library
- **Semantic**: FAISS with all-MiniLM-L6-v2 embeddings (384 dimensions)
- **Re-Ranking**: Cross-encoder (`ms-marco-MiniLM-L-12-v2`) re-scores top-20 candidates ✨ NEW
- **Chunking**: Token-based adaptive chunking (400-900 tokens depending on doc type)
- **Chunking Strategy**: Section-aware (chunks by H2/H3 boundaries, preserves headings)
- **Scoring**: Cross-encoder scores (when enabled) or exponential rank decay
- **Boosting**: Validated-designs URLs get 1.15x boost (applied before re-ranking)
- **Deduplication**: Max 2 sections per page in results
- **Anchors**: URLs include section anchors (e.g., `url#section-id`)
- **Tables**: Converted to markdown format for better indexing

**Token-Based Chunking Configuration** (hashicorp_doc_search.py:391-413)
```python
def _get_chunk_config(url):
    if '/api/' in url or '/commands/' in url:
        return {'size': 500, 'overlap': 75}  # API/CLI: smaller chunks
    elif '/configuration/' in url:
        return {'size': 400, 'overlap': 80}  # Config: smallest chunks
    elif '/release-notes' in url or '/changelog' in url:
        return {'size': 600, 'overlap': 60}  # Release notes: medium
    elif '/tutorials/' in url or '/guides/' in url:
        return {'size': 900, 'overlap': 135}  # Tutorials: largest
    else:
        return {'size': 800, 'overlap': 120}  # Concept/how-to: default
```

**Debug Logging**
- Enable with: `IVAN_DEBUG_TOOLS=true` in .env
- Log file: `ivan_tools_debug.log`
- Shows query, results, scores, and content previews

**Test Commands**
```bash
source venv/bin/activate

# Run regression tests (currently 0/2 passing)
python tests/test_comparison.py

# Run certification tests (88.5% passing, 23/26)
python tests/test_certification.py --reasoning-effort medium

# Debug chunk content
python tests/test_debug_chunks.py
```

---

## Implementation Notes

### What's Been Accomplished (Recent Commits)

**Commit 54c86c4** - Token-based adaptive chunking (MAJOR):
- Replaced character-based chunking with token-based (tiktoken)
- Implemented adaptive chunk sizes by document type
- Section-aware chunking by H2/H3 boundaries
- Section anchor extraction and URL generation
- URL normalization fixes
- Deleted 1,422 lines of obsolete code

**Commit 3db1f43** - Certification test suite:
- 26 certification questions across 3 products
- 88.5% pass rate (23/26 correct)
- Table extraction for comparison matrices
- Enhanced system prompt for technical questions

**Commit dee4d1c** - Regression test framework:
- Multi-test-case framework with scoring
- Two test cases (both currently failing due to ranking issues)

### Cross-Encoder Re-Ranking Implementation ✅ COMPLETED

**Implementation completed 2025-11-05**:

1. ✅ Added `CrossEncoder` from sentence-transformers package
2. ✅ Loaded cross-encoder model (`cross-encoder/ms-marco-MiniLM-L-12-v2`) in `_initialize_components()`
3. ✅ Implemented `_rerank_results()` method:
   - Creates query-document pairs
   - Scores with cross-encoder
   - Re-sorts by cross-encoder scores
   - Preserves original scores in metadata
4. ✅ Updated `search()` to use re-ranking when enabled
5. ✅ Added configuration options:
   - `enable_reranking=True` (default enabled)
   - `rerank_model='cross-encoder/ms-marco-MiniLM-L-12-v2'`
   - `rerank_top_k=20` (number of candidates to re-rank)

**Actual outcome**:
- ✅ Consul stale reads test: 0% → 100% pass (answer moved to rank #1)
- ⚠️ Vault disk throughput test: Still failing (retrieval problem, not ranking)
- ✨ Significant improvement in answer precision overall

---

## Resources

- Main search implementation: `hashicorp_doc_search.py` (1,581 lines)
- Test suite: `tests/test_comparison.py` (regression), `tests/test_certification.py` (26 questions)
- Certification results: `tests/CERTIFICATION_TEST_RESULTS_SUMMARY.md`
- Debug logs: `ivan_tools_debug.log`
- Documentation: `tests/README.md`, `CLAUDE.md`, `README.md`

---

## Expert Guidance - Hybrid RAG Architecture

**Date**: 2025-11-05
**Context**: Recommendations for SE assistant using both curated index + live web search

### When to Use Each Approach

**Use Live Web Search (Ollama Web Search) when:**
- Freshness needed: new releases, breaking changes, HCP changelog, GitHub releases
- Cross-site answers spanning docs + blog + GitHub issues/PRs
- Edge cases or long-tail queries not in index

**Use Curated Index when:**
- Verifiability & stable references for demos/POCs/SOWs
- Low latency + consistency for common questions
- Structured filters (product/version/cloud) that search alone won't provide

### What to Index

**Current (✅ Done)**:
- Product docs at developer.hashicorp.com (Terraform, Vault, Consul, Nomad, Boundary, Packer, Vagrant, HCP)
- API refs
- Sitemap-seeded crawler

**To Add**:
- Release notes pages for each product
- HCP changelog (cloud.hashicorp.com/changelog)
- GitHub releases (via API)

### Recommended Metadata Schema

```json
{
  "product": "vault",
  "topic": "auth/approle",
  "doc_type": "howto|concept|api|release-notes",
  "version": "1.21",
  "hcp": false,
  "url": "https://developer.hashicorp.com/vault/docs/auth/approle#pull-secret-id",
  "anchor": "pull-secret-id",
  "updated_at": "2025-10-22"
}
```

### Answer Flow Strategy

1. **Route each query**:
   - Version/release queries → index first, then live search for post-crawl content
   - Broad/comparative queries → index first, optionally enrich with live search

2. **Always cite**:
   - Specific section URLs from index
   - Include live search citations if used

3. **Confidence threshold**:
   - If index confidence < threshold → fall back to Ollama Web Search
   - Cache and optionally add results back to index

### Refresh Cadence

- **Daily**: release notes + HCP changelog + GitHub releases
- **Weekly**: all product docs
- **On-demand**: when query misses or low confidence

### Why This Hybrid Approach?

**Why not web search alone?**
- Inconsistent ranking across queries
- Occasional stale snippets
- Slower responses
- SE workflow needs repeatable, citable answers

**Why not index everything?**
- Diminishing returns and more noise
- Better with high-signal official sources + live search escape hatch

### Implementation Notes

- Treat Ollama Web Search as secondary retriever
- Use when index confidence < threshold or query asks for "latest"
- Cache live search results + sources
- Validate and add to index after light validation pass
