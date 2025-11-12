# Search Performance Optimization - Progress Summary

**Started**: 2025-11-11
**Status**: Phase 1 Complete → Starting Phase 2
**Goal**: Reduce search latency from 70+ seconds to < 6 seconds

---

## ✅ Phase 1: Parent-Child Chunking (COMPLETE)

### Implementation

**Created**:
- `chunking_utils.py` (975 lines) - Semantic HTML chunking with tiktoken
  - Parent chunks: 300-900 tokens (for LLM context)
  - Child chunks: 150-350 tokens (for search precision)
  - Heading hierarchy tracking
  - Rich metadata extraction (product, version, doc_type)

**Modified**:
- `hashicorp_doc_search.py`:
  - Added `parent_chunks` and `child_to_parent` storage
  - Modified `_fetch_page_content()` to include raw HTML
  - Replaced `_split_into_sections()` with semantic chunking
  - Index version: "4.0.0-parent-child"

**Test Infrastructure**:
- `test_parent_child.py` - Integration test (PASSING)
- `tests/benchmark_search.py` - Performance benchmarking

### Results

**Storage**: 2,420 parents + 940 children (test index, 228 pages)

**Performance** (test index, NO reranking):
```
Latency:      p50: 10.6ms  |  p95: 17.7ms  |  p99: 17.7ms
Throughput:   77.7 queries/sec
```

**Key Finding**: Search is extremely fast WITHOUT re-ranking. The 70+ second bottleneck is entirely from cross-encoder re-ranking 535+ candidates.

---

## 🚧 Phase 2: Hybrid Retrieval + Lightweight Reranker (IN PROGRESS)

### Current Architecture (Phase 1)

```
Query
  ↓
Ensemble Retriever (LangChain's weighted combination)
  ├─ BM25 (keyword)
  └─ FAISS (semantic)
  ↓
Retrieve 1600 candidates (for version queries)
  ↓
Filter by product → 731 candidates
  ↓
Deduplicate (2 per page) → 535 candidates
  ↓
Cross-encoder re-ranking ALL 535 candidates → 70+ SECONDS ❌
  ↓
Top 5 results
```

### Target Architecture (Phase 2)

```
Query
  ↓
Query preprocessing (extract product, version, doc_type)
  ↓
Parallel retrieval:
  ├─ BM25: 100 candidates (with metadata filters)
  └─ FAISS: 100 candidates (with metadata filters)
  ↓
RRF Fusion (proper reciprocal rank fusion) → 80 candidates
  ↓
Lightweight reranker (MiniLM-L-6) → 30 candidates
  ↓
Expand children → parents (get full context)
  ↓
MMR deduplication → top_k results
  ↓
Total time: < 6 seconds ✅
```

### What Needs to Change

**1. Implement Custom RRF Fusion**
- Current: LangChain's EnsembleRetriever uses simple weighted averaging
- New: Proper Reciprocal Rank Fusion algorithm
  ```python
  def reciprocal_rank_fusion(results_list, k=60):
      scores = {}
      for results in results_list:
          for rank, doc_id in enumerate(results):
              scores[doc_id] = scores.get(doc_id, 0) + 1/(k + rank)
      return sorted(scores.items(), key=lambda x: x[1], reverse=True)
  ```

**2. Add Query Preprocessing**
- Extract product, version, doc_type from query
- Apply metadata filters BEFORE retrieval (not after)
- Reduces initial candidates from 1600 → 200

**3. Replace Heavy Cross-Encoder**
- Current: `cross-encoder/ms-marco-MiniLM-L-12-v2` (re-ranks 535 candidates)
- New: `cross-encoder/ms-marco-MiniLM-L-6-v2` (re-ranks only 30 candidates)
- Benefit: Smaller model + fewer candidates = 100x faster

**4. Add MMR Deduplication**
- Maximal Marginal Relevance to reduce redundant results
- Applied AFTER parent expansion
- Ensures diverse results

### Implementation Plan

**Step 1**: Add RRF fusion function ✅ (ready to implement)
**Step 2**: Add query preprocessing ⏳
**Step 3**: Add lightweight reranker ⏳
**Step 4**: Rewrite `search()` method with new pipeline ⏳
**Step 5**: Add MMR deduplication ⏳
**Step 6**: Test and benchmark ⏳

---

## Performance Targets

### Current (Phase 1 Baseline)
- **Without reranking**: 10.6ms p50 (77.7 queries/sec)
- **With heavy reranking**: 70,000ms+ (0.014 queries/sec)

### Target (Phase 2)
- **p95 latency**: < 6,000ms (6 seconds)
- **Stretch goal**: < 3,000ms (3 seconds)
- **Quality**: ≥ baseline (no regression on critical queries)

### Critical Queries (Must Pass)
1. "consul stale reads default" → Consul Operating Guide
2. "vault 1.20 release notes" → Vault v1.20.x release notes
3. "nomad 1.9 release notes" → Nomad v1.9.x release notes
4. "boundary 0.18 release notes" → Boundary v0.18.x release notes

---

## Detailed Changes Needed

### File: hashicorp_doc_search.py

**Add Helper Functions** (new):
```python
def _reciprocal_rank_fusion(self, bm25_results, faiss_results, k=60):
    """Combine BM25 and FAISS results using RRF."""
    ...

def _preprocess_query(self, query):
    """Extract product, version, doc_type from query."""
    ...

def _light_rerank(self, query, candidates, top_k=30):
    """Re-rank with lightweight cross-encoder."""
    ...

def _expand_to_parents(self, child_docs):
    """Expand child chunks to parent chunks for LLM context."""
    ...

def _mmr_deduplicate(self, parents, lambda_param=0.3, top_k=5):
    """Apply MMR for diversity."""
    ...
```

**Modify `_initialize_components()`**:
- Add lightweight cross-encoder initialization
- Keep heavy cross-encoder for comparison (optional)

**Rewrite `search()` method**:
- Replace ensemble retriever logic with custom RRF
- Add query preprocessing step
- Reduce candidate counts at each stage:
  - Retrieve: 100 BM25 + 100 FAISS = 200 total
  - RRF fusion: 200 → 80 candidates
  - Light rerank: 80 → 30 candidates
  - Expand to parents: 30 child chunks → 30 parent contexts
  - MMR: 30 → top_k (typically 5)

### File: requirements.txt

Already has `rank-bm25>=0.2.2` ✅

---

## Testing Strategy

1. **Integration test**: Verify new pipeline works end-to-end
2. **Benchmark comparison**: Phase 1 vs Phase 2 performance
3. **Quality regression**: Ensure critical queries still pass
4. **Ablation study**: Measure impact of each component
   - Baseline (Phase 1 with heavy reranker)
   - Phase 1 without reranker (10ms)
   - Phase 2 with RRF only
   - Phase 2 with RRF + light reranker
   - Phase 2 complete (RRF + light reranker + MMR)

---

## Risk Mitigation

**Risk**: Lightweight reranker may reduce quality
**Mitigation**: Run critical query tests, compare nDCG scores

**Risk**: Custom RRF may perform worse than ensemble
**Mitigation**: Benchmark both, keep ensemble as fallback

**Risk**: Parent expansion may lose precision
**Mitigation**: Children are used for matching, parents only for context

**Risk**: Index rebuild required
**Mitigation**: Already handled in Phase 1 (version bump)

---

## Next Actions (Phase 2 Implementation)

1. ✅ Create progress summary (this document)
2. ⏳ Implement RRF fusion function
3. ⏳ Add query preprocessing
4. ⏳ Add lightweight reranker initialization
5. ⏳ Implement parent expansion
6. ⏳ Implement MMR deduplication
7. ⏳ Rewrite search() method
8. ⏳ Test with benchmark script
9. ⏳ Compare Phase 1 vs Phase 2 performance
10. ⏳ Document Phase 2 results

**Estimated Time**: 2-3 hours of implementation + 1 hour testing

---

## Success Criteria

✅ **Phase 1 Success Criteria** (ACHIEVED):
- Parent-child chunking works correctly
- Storage and mappings are correct
- Search still functions (baseline: 10.6ms without reranking)
- Test infrastructure in place

🎯 **Phase 2 Success Criteria**:
- Search latency < 6 seconds (vs 70+ seconds)
- Critical queries pass (4/4)
- Quality maintained (nDCG ≥ baseline)
- Code is clean and well-tested

---

**Status**: Phase 1 ✅ Complete | Phase 2 🚧 Starting Implementation
