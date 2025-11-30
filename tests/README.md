# Ivan Test Suite

This directory contains tests for the Ivan AI assistant, focused on validating HashiCorp documentation search quality and LLM reasoning.

## Test Files

### `test_certification.py` - Primary Regression Test

**Purpose**: End-to-end regression test using HashiCorp certification practice questions.

**What it tests**:
- Full Ivan pipeline: API → RAG search → LLM → response
- Uses real HashiCorp certification questions as test cases
- Tests Ivan's ability to answer technical questions correctly
- Validates search quality + LLM reasoning together

**Requirements**:
- **Ivan must be running**: `uv run python ivan.py` in a separate terminal
- Backend LLM must be available (LM Studio/Ollama)

**Test data**:
- Questions: `tests/certification_questions.json`
- Sources: HashiCorp certification practice exams
  - [Vault Associate (003)](https://developer.hashicorp.com/vault/tutorials/associate-cert-003/associate-questions-003)
  - [Consul Associate (003)](https://developer.hashicorp.com/consul/tutorials/associate-cert-003/associate-questions-003)
  - [Terraform Associate (003)](https://developer.hashicorp.com/terraform/tutorials/certification-003/associate-questions-003)
- Question types: True/False, Multiple Choice, Multiple Answer

**Run**:
```bash
# Terminal 1: Start Ivan
uv run python ivan.py

# Terminal 2: Run tests
uv run python tests/test_certification.py

# With HTML report
uv run python tests/test_certification.py --html tests/certification_report.html

# With JSON output
uv run python tests/test_certification.py --json tests/results.json

# Verbose mode (show response previews)
uv run python tests/test_certification.py -v

# Run limited tests
uv run python tests/test_certification.py -n 10
```

**Expected output**: Pass rate depends on LLM quality. Aim for 80%+ pass rate.

---

## Test Data

### `certification_questions.json`

JSON file containing HashiCorp certification practice questions. Each question has:

```json
{
  "id": "vault-003-001",
  "product": "vault",
  "type": "true_false",
  "question": "The question text...",
  "options": ["A. True", "B. False"],
  "correct_answer": "A",
  "explanation": "Why this answer is correct..."
}
```

**Question types**:
- `true_false` - True/False questions
- `multiple_choice` - Single correct answer
- `multiple_answer` - Multiple correct answers (e.g., "A, C")

**Adding new questions**: Add entries to `certification_questions.json` following the schema above.

---

## When to Run Tests

Run certification tests before committing changes to:
- `ivan.py` - Main application
- `tools.py` - Tool definitions
- RAG configuration in `.env`
- Any search or LLM-related code

---

## CI/CD Integration (Future)

These tests should be run in CI/CD:
1. Run regression tests on every PR
2. Require 80%+ pass rate for changes
3. Block merge if tests fail significantly

---

## Troubleshooting

**Ivan not running**: Start Ivan first with `uv run python ivan.py`

**Connection refused**: Check Ivan is running on the expected port (default: 8000)

**Low pass rate**:
- Check LLM model is loaded correctly
- Verify RAG index is built (`hashicorp_docs_index/` exists)
- Try with a different/larger model

**Slow tests**: First run may be slow if RAG index needs to be built (~15-30 min)
