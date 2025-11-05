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

### In Progress 🔄
- [ ] **Rewrite regression tests** (test_comparison.py)
  - Current tests expect PDF content that doesn't exist in web-crawled docs
  - Need to identify what content is actually available in the web index
  - Update test cases with realistic expectations
  - Add new test cases for search quality validation

### Known Issues 🐛

#### 1. Regression Test Failures (0/2 passing)

**Consul Stale Reads Test**
- Query: "what's the consul default for stale reads"
- Expected: "max_stale value to 10 years" from Consul Adoption Guide
- Problem: Web crawler may not have this specific content
- Need to: Verify if this content exists, or update test expectations

**Vault Disk Throughput Test**
- Query: "what disk throughput is needed to run vault"
- Expected: "75+ MB/s" from Validated Designs
- Problem: Search returns general performance tuning docs, not specific requirements
- Need to: Check if validated-designs content is properly indexed

#### 2. Search Quality

**Current Performance**
- Hybrid search (50% BM25, 50% semantic) working
- Score distribution good (1.00, 0.909, 0.833, 0.769, 0.714)
- No score compression issues

**Areas for Improvement**
- May need to adjust BM25/semantic weighting for different query types
- Consider adding product-specific boosting
- Evaluate chunk size (currently 1000 chars, 200 overlap)

### Upcoming Tasks 📋

#### High Priority
1. **Rewrite regression tests**
   - Create new test cases based on actual web index content
   - Test both keyword-heavy and semantic queries
   - Add tests for product filtering
   - Ensure tests validate search quality, not just presence of content

2. **Validate web index completeness**
   - Verify validated-designs pages are properly indexed
   - Check if important technical content is present
   - Review chunking strategy for technical documents

3. **Search quality tuning**
   - Analyze debug logs to understand search behavior
   - Consider query-specific retrieval strategies
   - Test with real user queries

#### Medium Priority
4. **Documentation updates**
   - Update README.md with hybrid search details
   - Document search algorithm and scoring
   - Add troubleshooting guide for common search issues

5. **Testing infrastructure**
   - Add more comprehensive test suite
   - Create test queries covering different use cases
   - Add performance benchmarks

#### Low Priority
6. **Optimization**
   - Consider caching BM25 retriever initialization
   - Evaluate if chunk size needs adjustment
   - Profile search performance

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
