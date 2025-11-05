# Ivan - Work in Progress

Last updated: 2025-11-05

## Current Status

### Recently Completed ✅
- [x] Migrated from PDF search to web crawler (hashicorp_doc_search)
- [x] Implemented hybrid search (BM25 + semantic FAISS)
- [x] Added tool call debug logging to `ivan_tools_debug.log`
- [x] Fixed LangChain deprecation warnings (invoke vs get_relevant_documents)
- [x] Adjusted scoring algorithm (exponential decay instead of linear)
- [x] Reduced validated-designs boost from 2.0x to 1.15x
- [x] Renamed hashicorp_web_search → hashicorp_doc_search for accuracy
- [x] Updated all imports and references across codebase
- [x] Deprecated old PDF search files to `deprecated/` directory
- [x] **Fixed duplicate URL bug** - Same URL appearing multiple times in search results
  - Added deduplication logic to keep highest-scoring chunk per URL
  - Applies to both hybrid and semantic-only search paths

### In Progress 🔄
- [ ] **Section Anchors Implementation** (Quick Win - Task #1)
  - Modify _extract_main_content to capture heading IDs
  - Store anchor in chunk metadata
  - Update search results to include anchors in URLs
  - Target: Make citations actionable for SE demos/customer conversations

### Known Issues 🐛

#### 1. Regression Test Failures (0/2 passing)

**Note**: Tests are based on old expectations. Deprioritized in favor of search quality improvements.

**Consul Stale Reads Test**
- Query: "what's the consul default for stale reads"
- Expected: "max_stale value to 10 years" from Consul Adoption Guide
- Status: Answer IS in results (rank #5), just not top result
- Action: Will be addressed by section-aware chunking + enhanced metadata

**Vault Disk Throughput Test**
- Query: "what disk throughput is needed to run vault"
- Expected: "75+ MB/s" from Validated Designs
- Status: Returns general performance docs instead of specific numbers
- Action: May be improved by validated-designs boosting + metadata

#### 2. Search Quality Gaps

**Missing Features** (being addressed - see Upcoming Tasks):
- No section anchors (can't cite specific sections)
- Fixed-size chunking (misses section boundaries)
- Limited metadata (no version, doc_type, hcp flag)
- No live search fallback for freshness

**Current Strengths**:
- ✅ Hybrid search (50% BM25, 50% semantic) working well
- ✅ Good score distribution (1.00, 0.909, 0.833, 0.769, 0.714)
- ✅ No score compression issues
- ✅ URL deduplication working
- ✅ Product filtering working

### Upcoming Tasks 📋

Based on expert guidance for hybrid RAG architecture (see notes below).

#### High Priority - Search Quality Improvements

1. **Section Anchors for Precise Citations** 🎯 **[QUICK WIN]**
   - Extract and preserve H2/H3 section anchors during crawling
   - Store anchor IDs in chunk metadata
   - Return URLs with anchors: `developer.hashicorp.com/vault/docs/auth/approle#pull-secret-id`
   - **Impact**: Makes answers actionable for SE demos/POCs/customer emails
   - **Effort**: Low (modify _extract_main_content to capture heading IDs)

2. **Section-Aware Chunking Strategy**
   - Chunk by H2/H3 boundaries instead of fixed 1000-char splits
   - Keep heading text as context for each chunk
   - Preserve code blocks separately
   - Add overlap between sections intelligently
   - **Impact**: Better relevance, enables anchor links
   - **Effort**: Medium (rewrite text splitting logic)

3. **Enhanced Metadata Schema**
   - Extract version info from URLs or page content
   - Classify doc_type: `howto | concept | api | release-notes | tutorial`
   - Add `hcp` boolean flag (cloud.hashicorp vs developer.hashicorp)
   - Store section hierarchy (e.g., "auth/approle")
   - **Impact**: Better filtering, more precise answers
   - **Effort**: Medium (update crawler + metadata extraction)

4. **Confidence-Based Live Search Fallback**
   - Integrate Ollama Web Search as secondary retriever
   - Detect low-confidence scenarios:
     - Top result score < threshold (e.g., 0.6)
     - Empty result set
     - Query contains "latest", "new", "GA", "RC", version numbers
   - Route to live search when confidence low
   - Cache and optionally index live search results
   - **Impact**: Freshness + edge case coverage
   - **Effort**: High (new integration + routing logic)

#### Medium Priority - Extended Coverage

5. **HCP Changelog Indexing**
   - Add crawler for `cloud.hashicorp.com/changelog`
   - Tag with doc_type: "release-notes" and hcp: true
   - Update daily (managed offerings move on own cadence)
   - **Impact**: Coverage of HCP-specific changes
   - **Effort**: Low (similar to existing crawler)

6. **GitHub Releases Integration**
   - Add GitHub API integration for each product
   - Index release notes from GitHub (markdown format)
   - Tag with version + release date
   - Update daily
   - **Impact**: Covers pre-docs.hashicorp.com content
   - **Effort**: Medium (GitHub API integration)

7. **Automated Refresh Cadence**
   - Daily: release notes + HCP changelog + GitHub releases
   - Weekly: all product docs
   - On-demand: when query misses or confidence low
   - Add CLI flags: `--refresh=daily|weekly|all`
   - **Impact**: Keeps index fresh
   - **Effort**: Low (scheduling + incremental update logic)

#### Lower Priority - Testing & Documentation

8. **Rewrite regression tests**
   - Create new test cases based on actual web index content
   - Test both keyword-heavy and semantic queries
   - Add tests for product filtering and metadata
   - Ensure tests validate search quality, not just presence of content
   - **Note**: Deprioritized vs search quality improvements

9. **Documentation updates**
   - Update README.md with hybrid search details
   - Document search algorithm and scoring
   - Add troubleshooting guide for common search issues
   - Document the hybrid RAG architecture

10. **Performance optimization**
    - Consider caching BM25 retriever initialization
    - Profile search performance
    - Optimize embedding generation (batching)

### Notes

**Search Implementation Details**
- Uses LangChain EnsembleRetriever
- BM25 for keyword matching (rank-bm25 library)
- FAISS for semantic search (all-MiniLM-L6-v2 embeddings)
- Exponential rank scoring: `1.0 / (1.0 + idx * 0.1)`
- Validated-designs boost: 1.15x
- Scores capped at 1.0

**Debug Logging**
- Enable with: `IVAN_DEBUG_TOOLS=true` in .env
- Log file: `ivan_tools_debug.log`
- Shows query, results, scores, and content previews

**Test Command**
```bash
source venv/bin/activate
python tests/test_comparison.py
```

---

## Task Details

### Rewrite Regression Tests

**Goal**: Create realistic regression tests that validate search quality against web-crawled content

**Approach**:
1. Run exploratory queries against current index
2. Identify queries with good/bad results
3. Create test cases with achievable expectations
4. Focus on validating search behavior, not specific content
5. Add multiple test cases covering different query types

**Example test categories**:
- Conceptual queries ("what is vault")
- Technical configuration ("consul retry join")
- Specific features ("vault auto-unseal")
- Product comparison queries
- Troubleshooting queries

**Success criteria**:
- At least 5 diverse test cases
- 80%+ pass rate on first run
- Tests are maintainable and not brittle
- Tests validate actual search quality metrics

---

## Questions / Decisions Needed

- [ ] Should we keep the old test cases as "stretch goals" or replace entirely?
- [ ] What pass threshold should we use (75%, 80%, 90%)?
- [ ] Do we need separate test suites for different query types?
- [ ] Should we test the PDF search in deprecated/ for comparison?

---

## Resources

- Debug logs: `ivan_tools_debug.log`
- Test output: `test_results.txt`
- Main search implementation: `hashicorp_doc_search.py`
- Test suite: `tests/test_comparison.py`
- Documentation: `tests/README.md`, `CLAUDE.md`

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
