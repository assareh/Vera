# Ivan Test Suite

This directory contains tests for the Ivan AI assistant, focused on validating HashiCorp documentation search quality.

## Test Files

### Regression Tests (Required)

#### `test_comparison.py`
**Purpose**: Comprehensive regression test suite for HashiCorp documentation search quality.

**What it tests**:
- Tests the web crawler search implementation (hashicorp_web_search.py)
- Validates search accuracy against known correct answers
- Ensures chunking and retrieval strategies work correctly
- Multiple test cases covering different products and query types

**Current test cases**:

1. **Consul Stale Reads Default**
   - Query: "what's the consul default for stale reads"
   - Expected: "By default, Consul enables stale reads and sets the max_stale value to 10 years"
   - Source: Consul Operating Guide for Adoption, section 8.3.6

2. **Vault Disk Throughput Requirements**
   - Query: "what disk throughput is needed to run vault"
   - Expected: "Small clusters: 75+ MB/s, Large clusters: 250+ MB/s"
   - Source: Vault Solution Design Guide - Validated Designs, Detailed Design section

**Pass criteria**:
- Each test case has `must_contain`, `should_contain`, and `must_not_contain` criteria
- Test passes with 75% or higher score
- All test cases must pass for overall pass

**Run**:
```bash
source venv/bin/activate
python tests/test_comparison.py
```

**Expected output**: `Overall: 2/2 tests passed`

**Adding new test cases**: Simply add a new dictionary to the `TEST_CASES` list in the file

---

### Debug & Development Tools

#### `test_debug_chunks.py`
**Purpose**: Debug tool to inspect full chunk content and understand retrieval behavior.

**What it does**:
- Runs a search query
- Shows full content of retrieved chunks (not just preview)
- Helps diagnose search quality issues
- Useful when search isn't returning expected results

**Usage**:
```bash
source venv/bin/activate
python tests/test_debug_chunks.py
```

Edit the file to change the query you want to debug.

#### `test_validated_designs.py`
**Purpose**: Test web crawler's ability to discover validated-designs pages.

**What it tests**:
- Sitemap parsing
- Validated-designs URL discovery
- robots.txt override for validated-designs
- Product categorization

**Usage**:
```bash
source venv/bin/activate
python tests/test_validated_designs.py
```

---

## Running All Tests

To run the main regression test:

```bash
source venv/bin/activate
python tests/test_comparison.py
```

To run all tests (including debug/dev tools):

```bash
source venv/bin/activate
for test in tests/test_*.py; do
    echo "Running $test..."
    python "$test" || echo "FAILED: $test"
done
```

## Adding New Regression Tests

When you discover a search quality issue or want to validate specific behavior:

1. Add a new test case to `TEST_CASES` in `test_comparison.py`:

```python
{
    "name": "Your Test Name",
    "query": "your search query",
    "product": "consul",  # or "vault", "terraform", etc.
    "source": "Documentation source",
    "expected": "What the answer should be",
    "must_contain": [
        ("critical", "keyword"),  # Both must be present
    ],
    "should_contain": [
        "important",  # Should be present
        "keyword",
    ],
    "must_not_contain": [
        "wrong info",  # Should NOT be present
    ],
}
```

2. Run the test to verify it works:
```bash
python tests/test_comparison.py
```

3. Commit the updated test case

## Test Requirements

- Tests require the search index to be built (happens automatically on first run)
- Initial index build can take a few minutes
- Subsequent runs use cached index (much faster)

## When to Run Tests

**Always run regression tests** (`test_comparison.py`) before committing changes to:
- `hashicorp_web_search.py` - Web crawler search implementation
- `tools.py` - Tool definitions (especially search-related)
- Embedding models or chunking strategies
- FAISS index configuration
- Any RAG-related code

## CI/CD Integration (Future)

These tests should be run in CI/CD:
1. Run regression tests on every PR
2. Require 100% pass rate for search-related changes
3. Update tests when intentionally changing search behavior
4. Block merge if tests fail

## Troubleshooting

**Index not found**: Run Ivan once to build the index, or run `python tests/test_comparison.py` to trigger index build.

**Tests failing**: Use `test_debug_chunks.py` to inspect what content is being returned and why it might not match expectations.

**Slow tests**: First run is slow (building index), subsequent runs are fast (using cache).
