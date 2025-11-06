# Certification Test Results Summary

## Overview

This document summarizes the results of the certification-based regression test suite across five iterations, showing progressive improvements in test accuracy through enhanced question formatting and grading logic improvements.

## Test Suite Details

- **Total Questions**: 26
- **Products**: Vault (14), Consul (7), Terraform (5)
- **Question Types**: True/False (7), Multiple Choice (12), Multiple Answer (7)
- **Source**: HashiCorp certification practice questions (Associate 003)

## Results Comparison

### Iteration 1: Unformatted Questions (Baseline)
**Date**: 2025-11-05
**Score**: 8/26 (30.8%)

Questions were sent as plain text without certification exam formatting.

**By Product**:
- Consul: 1/7 (14.3%)
- Terraform: 3/5 (60.0%)
- Vault: 4/14 (28.6%)

**By Question Type**:
- True/False: 3/7 (42.9%)
- Multiple Choice: 4/12 (33.3%)
- Multiple Answer: 1/7 (14.3%)

**Issues**:
- Ivan provided explanatory answers instead of direct responses
- Grading logic couldn't parse natural language explanations
- No clear indication of which option was selected

---

### Iteration 2: Formatted Questions
**Date**: 2025-11-05
**Score**: 19/26 (73.1%)

Questions formatted in certification exam style with instructions and checkboxes.

**Improvement**: +42.3 percentage points

**By Product**:
- Consul: 6/7 (85.7%) ⬆️ +71.4%
- Terraform: 3/5 (60.0%) → No change
- Vault: 10/14 (71.4%) ⬆️ +42.8%

**By Question Type**:
- True/False: 6/7 (85.7%) ⬆️ +42.8%
- Multiple Choice: 11/12 (91.7%) ⬆️ +58.4%
- Multiple Answer: 2/7 (28.6%) ⬆️ +14.3%

**Remaining Issues**:
- Some multiple answer questions returned unchecked boxes (⬜) instead of checked (✓)
- Punctuation handling in grading logic
- True/False questions with explanatory text after the answer

---

### Iteration 3: Improved Grading Logic
**Date**: 2025-11-05
**Score**: 21/26 (80.8%)

Enhanced grading to handle edge cases: unchecked boxes, punctuation, explanatory text.

**Improvement**: +7.7 percentage points from v2, +50.0 percentage points from v1

**By Product**:
- Consul: 6/7 (85.7%) → No change
- Terraform: 4/5 (80.0%) ⬆️ +20.0%
- Vault: 11/14 (78.6%) ⬆️ +7.2%

**By Question Type**:
- True/False: 7/7 (100.0%) ⬆️ +14.3% ✅ PERFECT SCORE
- Multiple Choice: 11/12 (91.7%) → No change
- Multiple Answer: 3/7 (42.9%) ⬆️ +14.3%

**Remaining Failures** (5 tests):
1. **Vault Q8** - Multiple choice with apostrophe punctuation issue
2. **Vault Q11** - Multiple answer with incorrect answer from LLM
3. **Vault Q14** - Multiple answer with wrong option selected
4. **Consul Q7** - Multiple answer with en-dash punctuation issue
5. **Terraform Q5** - Multiple answer with incorrect answer from LLM

---

### Iteration 4: Enhanced Apostrophe Handling
**Date**: 2025-11-05
**Score**: 22/26 (84.6%)

Improved text normalization to handle all apostrophe and quote variants (straight quotes, curly quotes, unicode characters).

**Improvement**: +3.8 percentage points from v3, +53.8 percentage points from v1

**By Product**:
- Consul: 6/7 (85.7%) → No change
- Terraform: 4/5 (80.0%) → No change
- Vault: 12/14 (85.7%) ⬆️ +7.1%

**By Question Type**:
- True/False: 7/7 (100.0%) → Still perfect ✅
- Multiple Choice: 12/12 (100.0%) ⬆️ +8.3% ✅ PERFECT SCORE
- Multiple Answer: 3/7 (42.9%) → No change

**Fixed**:
- **Vault Q8** ✅ - Enhanced normalization now handles "don't" with any apostrophe variant

**Remaining Failures** (4 tests):
1. **Vault Q11** - LLM knowledge issue
2. **Vault Q14** - LLM knowledge issue
3. **Consul Q7** - En-dash character (Read‑scalability)
4. **Terraform Q5** - LLM knowledge issue

---

### Iteration 5: Comprehensive Hyphen/Dash Handling
**Date**: 2025-11-05
**Score**: 23/26 (88.5%)

Added comprehensive hyphen/dash normalization covering all Unicode variants (regular hyphen, en-dash, em-dash, non-breaking hyphen, figure dash, etc.).

**Improvement**: +3.9 percentage points from v4, +57.7 percentage points from v1

**By Product**:
- Consul: 7/7 (100.0%) ⬆️ +14.3% ✅ PERFECT SCORE
- Terraform: 4/5 (80.0%) → No change
- Vault: 12/14 (85.7%) → No change

**By Question Type**:
- True/False: 7/7 (100.0%) → Still perfect ✅
- Multiple Choice: 12/12 (100.0%) → Still perfect ✅
- Multiple Answer: 4/7 (57.1%) ⬆️ +14.2%

**Fixed**:
- **Consul Q7** ✅ - Now handles en-dash in "Read‑scalability" and "Redundancy"

**Remaining Failures** (3 tests - ALL are LLM knowledge issues):
1. **Vault Q11** - LLM selected "token IDs always begin with s." instead of "core method for authentication"
2. **Vault Q14** - LLM selected "namespace" instead of "second cluster"
3. **Terraform Q5** - LLM selected "retrieves plugins" instead of "makes infrastructure changes"

---

## Key Improvements

### 1. Question Formatting (v1 → v2)
**Impact**: +42.3 percentage points

```
Before: "Which protocol(s) need to be enabled in your network..."

After:  "Multiple choice questions ask you to select one correct answer from a list.

Which protocol(s) need to be enabled in your network...

⬜ TCP and UDP
⬜ gRPC
⬜ SSL
⬜ HTTP and HTTPS
⬜ All of the above"
```

**Result**: Ivan now responds with exact option text or checkmarks instead of explanations.

### 2. Enhanced Grading Logic (v2 → v3)
**Impact**: +7.7 percentage points

**Improvements**:
- True/False: Handle "True – explanation" format (extract first word)
- Multiple Choice: Better punctuation normalization
- Multiple Answer: Parse unchecked boxes (⬜) and plain text lists
- All Types: Improved text normalization function

**Result**: 100% True/False accuracy, better handling of LLM variations.

### 3. Enhanced Apostrophe/Quote Handling (v3 → v4)
**Impact**: +3.8 percentage points

**Improvements**:
- Comprehensive Unicode apostrophe handling (straight quotes, curly quotes, etc.)
- Added support for: ' ' " " " ` ´ and all modifier letters
- Removes all quote variants entirely to avoid spacing issues
- Fixed Vault Q8: "don't" now matches "don't" regardless of apostrophe type

**Result**: 100% Multiple Choice accuracy achieved.

### 4. Comprehensive Hyphen/Dash Handling (v4 → v5)
**Impact**: +3.9 percentage points

**Improvements**:
- Added all Unicode hyphen/dash variants:
  - Regular hyphen (-), en-dash (–), em-dash (—)
  - Non-breaking hyphen (‑), figure dash (‒), horizontal bar (―)
  - Minus sign (−)
- Removes all hyphen variants entirely (no space replacement)
- Fixed Consul Q7: "Read-scalability" now matches "Read‑scalability"

**Result**: 100% Consul accuracy achieved, 100% Multiple Choice maintained.

---

## Analysis of Remaining Failures

### Multiple Answer Questions (4/7 pass rate)

**Current Status**: Only 3 out of 26 total tests fail, all in the Multiple Answer category.

**All Remaining Failures are LLM Knowledge Issues**:

1. **Vault Q11**: LLM selected "token IDs always begin with s." instead of "core method for authentication"
   - **Root Cause**: The search didn't return correct documentation about Vault tokens
   - **Issue Type**: Search quality / Documentation coverage

2. **Vault Q14**: LLM selected "Create a namespace" instead of "Deploy a second Vault cluster"
   - **Root Cause**: The LLM doesn't know that namespaces are Enterprise-only (question specifies "Vault open source")
   - **Issue Type**: Search quality / Context understanding

3. **Terraform Q5**: LLM selected "retrieves plugins" instead of "makes infrastructure changes"
   - **Root Cause**: The search didn't emphasize that `terraform apply` makes infrastructure changes
   - **Issue Type**: Search quality / Documentation relevance

**Key Insight**: All grading/formatting issues have been resolved! The remaining 3 failures (11.5% of tests) are entirely due to:
- Search not returning the most relevant documentation
- LLM not understanding product-specific context (Enterprise vs Open Source)
- Documentation chunks not emphasizing the correct information

---

## Success Metrics

| Metric | v1 | v2 | v3 | v4 | v5 | Total Improvement |
|--------|----|----|----|----|----|--------------------|
| **Overall** | 30.8% | 73.1% | 80.8% | 84.6% | **88.5%** | **+57.7%** |
| **True/False** | 42.9% | 85.7% | 100.0% | 100.0% | **100.0%** | **+57.1%** ✅ |
| **Multiple Choice** | 33.3% | 91.7% | 91.7% | 100.0% | **100.0%** | **+66.7%** ✅ |
| **Multiple Answer** | 14.3% | 28.6% | 42.9% | 42.9% | **57.1%** | **+42.8%** |
| **Consul** | 14.3% | 85.7% | 85.7% | 85.7% | **100.0%** | **+85.7%** ✅ |
| **Vault** | 28.6% | 71.4% | 78.6% | 85.7% | **85.7%** | **+57.1%** |
| **Terraform** | 60.0% | 60.0% | 80.0% | 80.0% | **80.0%** | **+20.0%** |

**Legend**:
- v1: Unformatted questions (baseline)
- v2: Formatted questions with certification exam style
- v3: Enhanced grading logic (unchecked boxes, explanatory text)
- v4: Enhanced apostrophe/quote handling
- v5: Comprehensive hyphen/dash handling

---

## Recommendations

### ✅ Completed Improvements

1. **~~Fix Grading Logic for Plain Text Lists~~** ✅ DONE
   - Fixed in v3-v5: Enhanced grading now handles plain text, unchecked boxes, and various formats

2. **~~Add Punctuation Handling~~** ✅ DONE
   - Fixed in v4: All apostrophe/quote variants handled
   - Fixed in v5: All hyphen/dash variants handled
   - Result: 100% True/False and 100% Multiple Choice accuracy

### Search Quality Improvements (Primary Focus)

The remaining 3 failures are all due to search quality issues. Priority improvements:

1. **Improve Documentation Search for Multiple Answer Questions**
   - **Vault Q11** (Vault tokens): Search should return core token documentation
   - **Vault Q14** (Open Source vs Enterprise): Search should distinguish feature availability
   - **Terraform Q5** (apply behavior): Search should emphasize primary actions
   - Consider:
     - Increasing search result count (top_k) for multiple answer questions
     - Improving chunking to include feature availability context
     - Adding product edition context (Enterprise vs Open Source)
     - Query expansion to include synonyms

2. **Add Product Context to Questions**
   - Prepend product name and edition to questions: "For HashiCorp Vault Open Source: ..."
   - Helps LLM distinguish between Enterprise and Open Source features
   - Reduces ambiguity for product-specific terminology

### Future Enhancements

3. **Expand Question Bank**
   - Add more certification question pages
   - Cover more products (Nomad, Boundary, Waypoint, etc.)
   - Include more edge cases and question types

4. **Add Confidence Scoring**
   - Have LLM indicate confidence level
   - Flag low-confidence answers for review
   - Could help identify search quality issues

5. **Track Test Stability**
   - Run tests multiple times to measure consistency
   - Identify flaky tests or non-deterministic behavior
   - Establish baseline for acceptable variation

---

## Conclusion

The certification-based test suite successfully validates Ivan's ability to answer HashiCorp technical questions. Through five iterations of improvements, the test suite achieved:

### Final Results (v5)
- **88.5% overall pass rate** (23/26 tests)
- **100% accuracy on True/False questions** ✅
- **100% accuracy on Multiple Choice questions** ✅
- **100% accuracy on Consul questions** ✅
- **57.1% accuracy on Multiple Answer questions** (improving)

### Key Achievements

1. **Question Formatting** (+42.3%): Certification exam-style formatting dramatically improved response quality
2. **Grading Logic** (+15.4%): Comprehensive punctuation handling eliminated all formatting-related failures
3. **All Remaining Failures are Search-Related**: 100% of failures traced to documentation search quality

### What We Learned

**What Works**:
- Proper question formatting is critical for reliable testing
- Comprehensive Unicode normalization handles real-world text variations
- Ivan performs excellently on direct factual questions (True/False, Multiple Choice)

**What Needs Improvement**:
- Search quality for multiple answer questions (3 failures)
- Product edition context (Enterprise vs Open Source)
- Documentation chunking to preserve important distinctions

### Value as Regression Test

This test suite provides:
- **Reliable baseline**: 88.5% pass rate with only 3 LLM knowledge failures
- **Fast feedback**: ~1-2 minutes to run all 26 questions
- **Clear failure attribution**: Can distinguish grading vs search vs LLM issues
- **Easy expansion**: Simple to add more certification question pages

The test suite successfully validates Ivan's core capabilities and provides a solid foundation for ongoing regression testing.

---

## Test Files

- **Test Script**: `tests/test_certification.py`
- **Question Bank**: `tests/certification_questions.json` (26 questions across 3 products)
- **Test Results**:
  - v1: `certification_test_results.txt` (30.8% - unformatted baseline)
  - v2: `certification_test_results_v2.txt` (73.1% - formatted questions)
  - v3: `certification_test_results_v3.txt` (80.8% - enhanced grading)
  - v4: `certification_test_results_improved.txt` (84.6% - apostrophe handling)
  - v5: `certification_test_results_final_v2.txt` (88.5% - hyphen handling) ✅ **CURRENT**
- **This Summary**: `tests/CERTIFICATION_TEST_RESULTS_SUMMARY.md`

---

**Last Updated**: 2025-11-05
**Test Version**: v5
**Backend**: LM Studio (wwtfo/ivan)
**Final Score**: 23/26 (88.5%)
