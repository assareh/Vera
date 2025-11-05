# Ivan Test Suite

This directory contains tests for the Ivan AI assistant, particularly focused on HashiCorp documentation search quality.

## Test Files

### Regression Tests (Required)

#### `test_comparison.py`
**Purpose**: Primary regression test for HashiCorp PDF search quality.

**What it tests**:
- Tests the LangChain-based FAISS implementation
- Validates search accuracy against known correct answers
- Ensures chunking and retrieval strategies work correctly

**Key test case**:
- Query: "what's the consul default for stale reads"
- Expected: Finds "By default, Consul enables stale reads and sets the max_stale value to 10 years"
- Source: Consul Operating Guide for Adoption, section 8.3.6

**Pass criteria**:
- ✅ Must find 'max_stale' AND '10 years'
- ✅ Must reference Adoption guide
- ✅ Must indicate stale reads are enabled by default
- ❌ Must NOT contain incorrect information (e.g., "defaults to false")

**Run**:
```bash
source venv/bin/activate
python tests/test_comparison.py
```

**Expected output**: `V2 (LangChain): ✅ PASS`

---

### Debug & Development Tests

#### `test_debug_chunks.py`
**Purpose**: Debug tool to inspect full chunk content and understand retrieval behavior.

**Usage**:
```bash
source venv/bin/activate
python tests/test_debug_chunks.py
```

Shows full chunk content for top 10 results to help diagnose search quality issues.

#### `test_consul_stale_reads.py`
**Purpose**: Focused test for the specific Consul stale reads regression case.

**Usage**:
```bash
source venv/bin/activate
python tests/test_consul_stale_reads.py
```

#### `test_hashicorp_search.py`
**Purpose**: Legacy test for HashiCorp search functionality.

**Usage**:
```bash
source venv/bin/activate
python tests/test_hashicorp_search.py
```

#### `test_pdf_search.py`
**Purpose**: Test PDF semantic search functionality.

**Usage**:
```bash
source venv/bin/activate
python tests/test_pdf_search.py
```

#### `test_selenium_download.py`
**Purpose**: Test PDF download automation using Selenium.

**Usage**:
```bash
source venv/bin/activate
python tests/test_selenium_download.py
```

## Running All Tests

To run all tests:

```bash
source venv/bin/activate
for test in tests/test_*.py; do
    echo "Running $test..."
    python "$test" || echo "FAILED: $test"
done
```

## Adding New Regression Tests

When adding features or fixing bugs in the search implementation:

1. Create a test case with a specific query and expected answer
2. Add it to `test_comparison.py` or create a new test file
3. Document the expected behavior
4. Run the test to verify it passes
5. Add it to this README

## Known Issues

- `test_selenium_download.py` may fail if Chrome/ChromeDriver versions don't match
- Tests require the PDF index to be built (happens automatically on first run)
- Initial index build can take 2-3 minutes

## CI/CD Integration (Future)

These tests should be run in CI/CD before deploying changes to:
- `hashicorp_pdf_search.py`
- `tools.py` (search-related functions)
- Embedding models or chunking strategies

Recommended workflow:
1. Run regression tests on every PR
2. Require 100% pass rate for search-related changes
3. Update tests when intentionally changing search behavior
