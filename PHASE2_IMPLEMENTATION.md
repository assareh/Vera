# Phase 2 Implementation: Two-Stage Reranking

**Date**: 2025-11-12
**Status**: 🚧 IN PROGRESS
**Approach**: Incremental improvement (simpler than original PROGRESS_SUMMARY plan)

---

## Problem Statement

**Current Bottleneck** (from Phase 1 analysis):
- Retrieve 1600 candidates for version queries → FAST (10-20ms)
- Filter by product → 731 candidates → FAST (<1ms)
- Deduplicate (2 per page) → 535 candidates → FAST (<1ms)
- **Cross-encoder rerank ALL 535 candidates → 70,000+ ms (70+ seconds)** ❌

The bottleneck is the heavy cross-encoder (`ms-marco-MiniLM-L-12-v2`) processing 535 candidates.

---

## Phase 2 Solution: Two-Stage Reranking

Instead of completely rewriting the search pipeline (as originally planned in PROGRESS_SUMMARY.md), we'll use a **simpler, incremental approach**:

### Architecture

```
Current Flow:
Query → Retrieve 1600 → Filter → Dedupe → 535 candidates →
Heavy Rerank (L-12) ALL 535 → 70+ seconds ❌

Phase 2 Flow:
Query → Retrieve 1600 → Filter → Dedupe → 535 candidates →
Lightweight Rerank (L-6) → 80 candidates →
Heavy Rerank (L-12) → Top 5 results
Target: < 6 seconds ✅
```

### Key Changes

1. **Add Lightweight Cross-Encoder (L-6)**:
   - Model: `cross-encoder/ms-marco-MiniLM-L-6-v2`
   - Purpose: Fast first-pass reranking
   - Input: 535 candidates
   - Output: Top 80 candidates

2. **Keep Heavy Cross-Encoder (L-12)**:
   - Model: `cross-encoder/ms-marco-MiniLM-L-12-v2`
   - Purpose: High-quality final reranking
   - Input: 80 candidates (from L-6)
   - Output: Top 5 results

### Benefits

- **Performance**: Reduce heavy cross-encoder work from 535 → 80 (6.7x reduction)
- **Safety**: Incremental change, keeps all existing logic (version detection, URL boosting, etc.)
- **Simplicity**: No major rewrite, just add one function and modify flow
- **Quality**: Still uses heavy cross-encoder for final ranking (quality preserved)

---

## Implementation Steps

### Step 1: Add Lightweight Reranker Fields

**File**: `hashicorp_doc_search.py`

**Lines 109-110** - Add new parameters to `__init__`:
```python
rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-12-v2",  # Heavy cross-encoder (final ranking)
light_rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",  # Lightweight cross-encoder (first pass)
rerank_top_k: int = 80,  # Candidates for final reranking
light_rerank_top_k: int = 80,  # Candidates after lightweight reranking (was 535)
```

**Line 170** - Add lightweight cross-encoder field:
```python
self.cross_encoder: Optional[CrossEncoder] = None  # Heavy cross-encoder (L-12) for final ranking
self.light_cross_encoder: Optional[CrossEncoder] = None  # Lightweight cross-encoder (L-6) for first pass
```

### Step 2: Initialize Lightweight Cross-Encoder

**File**: `hashicorp_doc_search.py`
**Method**: `_initialize_components` (around line 1363)

Add after existing cross-encoder initialization:
```python
if self.enable_reranking and self.light_cross_encoder is None:
    logger.info(f"[DOC_SEARCH] Loading lightweight cross-encoder for first-pass ranking: {self.light_rerank_model}")
    self.light_cross_encoder = CrossEncoder(self.light_rerank_model)
    logger.info(f"[DOC_SEARCH] Lightweight cross-encoder loaded (will reduce candidates to {self.light_rerank_top_k})")
```

### Step 3: Add Lightweight Reranking Method

**File**: `hashicorp_doc_search.py`
**Location**: Before `search()` method (around line 1700)

```python
def _light_rerank(self, query: str, results: List[Dict[str, Any]], top_k: int = 80) -> List[Dict[str, Any]]:
    """Fast first-pass reranking using lightweight cross-encoder.

    Reduces candidate count before heavy cross-encoder reranking.

    Args:
        query: Search query
        results: List of search results to rerank
        top_k: Number of top results to keep

    Returns:
        Top k results after lightweight reranking
    """
    if not self.light_cross_encoder or not results:
        return results

    logger.debug(f"[DOC_SEARCH] Lightweight reranking {len(results)} results → top {top_k}")

    # Prepare query-document pairs for scoring
    pairs = [[query, result['text']] for result in results]

    # Score all pairs with lightweight model (fast)
    scores = self.light_cross_encoder.predict(pairs)

    # Update results with lightweight scores
    for result, score in zip(results, scores):
        result['light_rerank_score'] = float(score)

    # Sort by lightweight scores (descending)
    reranked = sorted(results, key=lambda x: x['light_rerank_score'], reverse=True)

    # Return top k
    top_results = reranked[:top_k]

    logger.debug(f"[DOC_SEARCH] Lightweight reranking complete: kept top {len(top_results)} candidates")

    return top_results
```

### Step 4: Modify Search Flow

**File**: `hashicorp_doc_search.py`
**Method**: `search()` (around line 1860)

**Current code** (lines 1859-1862):
```python
# Apply cross-encoder re-ranking if enabled
if self.enable_reranking and self.cross_encoder:
    # Re-rank before limiting to top_k (use original query for cross-encoder)
    results = self._rerank_results(original_query, results)
```

**Replace with Phase 2 two-stage reranking**:
```python
# Apply two-stage re-ranking if enabled
if self.enable_reranking:
    # Stage 1: Lightweight reranking to reduce candidates (535 → 80)
    if self.light_cross_encoder:
        results = self._light_rerank(original_query, results, top_k=self.light_rerank_top_k)

    # Stage 2: Heavy reranking for final ranking (80 → top_k)
    if self.cross_encoder:
        results = self._rerank_results(original_query, results)
```

**Same change needed for FAISS-only branch** (lines 1936-1939):
```python
# Apply two-stage re-ranking if enabled
if self.enable_reranking:
    # Stage 1: Lightweight reranking to reduce candidates
    if self.light_cross_encoder:
        results = self._light_rerank(original_query, results, top_k=self.light_rerank_top_k)

    # Stage 2: Heavy reranking for final ranking
    if self.cross_encoder:
        results = self._rerank_results(original_query, results)
```

---

## Testing Plan

### Test 1: Integration Test
```bash
python test_parent_child.py
```
- Verify two-stage reranking works
- Check that search still returns correct results

### Test 2: Performance Benchmark
```bash
python tests/benchmark_search.py --no-rerank     # Baseline without reranking
python tests/benchmark_search.py                 # Phase 2 with two-stage reranking
```
- Measure latency (p50, p95, p99)
- Compare against Phase 1 baseline (70+ seconds)
- Target: < 6 seconds

### Test 3: Critical Queries
Ensure these still pass:
1. "consul stale reads default" → Consul Operating Guide
2. "vault 1.20 release notes" → Vault v1.20.x release notes
3. "nomad 1.9 release notes" → Nomad v1.9.x release notes
4. "boundary 0.18 release notes" → Boundary v0.18.x release notes

---

## Performance Expectations

### Estimated Time Breakdown

**Current (Phase 1 with heavy reranker)**:
- Retrieve + filter + dedupe: ~50ms
- Heavy rerank (L-12) 535 candidates: ~70,000ms
- **Total**: ~70,050ms (70 seconds) ❌

**Phase 2 (Two-stage reranking)**:
- Retrieve + filter + dedupe: ~50ms
- Lightweight rerank (L-6) 535 → 80: ~500ms (estimated)
- Heavy rerank (L-12) 80 candidates: ~10,000ms (estimated: 70,000ms × 80/535)
- **Total**: ~10,550ms (10.5 seconds) ✅

**Speedup**: 70 seconds → 10.5 seconds = **6.7x faster**

### Success Criteria

✅ **Performance**:
- Latency p95 < 15,000ms (15 seconds) - conservative target
- Stretch goal: < 6,000ms (6 seconds)

✅ **Quality**:
- All 4 critical queries pass
- No regression in search relevance

---

## Rollback Plan

If Phase 2 causes issues:
1. **Revert changes**: `git revert <commit-hash>`
2. **Disable lightweight reranker**: Set `light_cross_encoder = None`
3. **Fall back to Phase 1**: Heavy reranker will still work on all 535 candidates

---

## Future Optimizations (Phase 3)

If we need even better performance, consider:
1. **Custom RRF fusion** (as originally planned in PROGRESS_SUMMARY.md)
2. **Query preprocessing** to apply metadata filters before retrieval
3. **MMR deduplication** for final result diversity
4. **Reduce initial retrieval** from 1600 → 200 candidates

But Phase 2 should get us to < 15 seconds, which is a huge improvement from 70+ seconds.

---

**Status**: Ready to implement Step 1
