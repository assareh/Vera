#!/usr/bin/env python3
"""
Certification Question Regression Test

Tests Ivan's ability to answer HashiCorp certification practice questions
using the llm_api_server.eval framework.

Usage:
    python tests/test_certification.py
    python tests/test_certification.py --model openai/gpt-oss-20b
    python tests/test_certification.py --html report.html
    python tests/test_certification.py --json results.json

Requirements:
    - Ivan must be running on http://localhost:8000
    - Backend LLM must be available (LM Studio/Ollama)
"""

import argparse
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path

from llm_api_server.eval import (
    Evaluator,
    HTMLReporter,
    JSONReporter,
    TestCase,
    TestResult,
)

# Configuration
IVAN_API_URL = "http://localhost:8000"
DEFAULT_MODEL = "wwtfo/ivan"
QUESTIONS_FILE = Path(__file__).parent / "certification_questions.json"
REQUEST_TIMEOUT = 300  # 5 minutes - generous timeout for slow models/tool loops

# ANSI color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"
CHECK_MARK = f"{GREEN}✓{RESET}"
X_MARK = f"{RED}✗{RESET}"


# =============================================================================
# Text Normalization
# =============================================================================


def normalize_text(text: str) -> str:
    """
    Aggressively normalize text for comparison by removing all punctuation,
    extra whitespace, and converting to lowercase.

    This ensures that answers match regardless of:
    - Periods, commas, quotes, etc.
    - En-dashes, em-dashes, hyphens
    - Multiple spaces or newlines
    - Different quote styles
    """
    # Convert to lowercase
    normalized = text.lower()

    # Replace all quotation and apostrophe variants
    # Using unicode escapes for ambiguous characters to satisfy linter
    quote_chars = [
        "'", '"', "`", "\u00b4",  # acute accent
        "\u2018", "\u2019",  # left/right single quote
        "\u201a", "\u201b",  # low-9/high-reversed-9 quote
        "\u201c", "\u201d",  # left/right double quote
        "\u201e", "\u201f",  # low-9/high-reversed-9 double quote
        "\u2032", "\u2033",  # prime, double prime
        "\u02bb", "\u02bc", "\u02bd", "\u02be", "\u02bf",
    ]
    for char in quote_chars:
        normalized = normalized.replace(char, "")

    # Replace all hyphen/dash variants (intentionally matching unicode variants)
    hyphen_chars = [
        "-",        # U+002D Regular hyphen-minus
        "\u2010",   # Hyphen
        "\u2011",   # Non-breaking hyphen
        "\u2012",   # Figure dash
        "\u2013",   # En dash
        "\u2014",   # Em dash
        "\u2015",   # Horizontal bar
        "\u2212",   # Minus sign
    ]
    for char in hyphen_chars:
        normalized = normalized.replace(char, "")

    # Remove common punctuation
    punctuation_chars = [
        ".", ",", "!", "?", ";", ":", "(", ")", "[", "]",
        "{", "}", "/", "\\", "|", "*", "#", "@", "$", "%", "^", "&",
    ]
    for char in punctuation_chars:
        normalized = normalized.replace(char, " ")

    # Replace multiple spaces with single space
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized.strip()


# =============================================================================
# Custom Validators for Each Question Type
# =============================================================================


def create_true_false_validator(correct_answer: str) -> Callable[[str], tuple[bool, list[str]]]:
    """Create a validator for True/False questions."""

    def validator(response: str) -> tuple[bool, list[str]]:
        if not response:
            return False, ["No response received"]

        response_lower = response.lower()
        correct_lower = correct_answer.lower()

        # Look for checkmark/selection indicators
        if "☑" in response or "✓" in response or "✔" in response:
            if correct_lower == "true":
                if any(f"{mark} true" in response_lower for mark in ["☑", "✓", "✔"]):
                    return True, []
            else:
                if any(f"{mark} false" in response_lower for mark in ["☑", "✓", "✔"]):
                    return True, []

        # Look for "**Answer:**" pattern (markdown bold) - common LLM response format
        # Matches: "**Answer:** ⬜ True", "**Answer:** True", "**answer**: false"
        answer_pattern = re.search(r"\*\*answer:?\*\*:?\s*(?:⬜\s*)?(\w+)", response_lower)
        if answer_pattern:
            answer_word = answer_pattern.group(1)
            if answer_word == correct_lower:
                return True, []

        # Look for explicit answer in first line
        first_line = response_lower.split("\n")[0] if "\n" in response_lower else response_lower
        first_word = first_line.strip().split()[0] if first_line.strip() else ""

        # Look for "⬜ **True**" or "⬜ **False**" pattern (bold markdown answer)
        bold_answer_pattern = re.search(r"⬜\s*\*\*(\w+)\*\*", response_lower)
        if bold_answer_pattern:
            bold_answer = bold_answer_pattern.group(1)
            if bold_answer == correct_lower:
                return True, []

        # Look for standalone "**True**" or "**False**" (bold markdown without checkbox)
        standalone_bold_pattern = re.search(r"\*\*(true|false)\*\*", response_lower)
        if standalone_bold_pattern:
            bold_answer = standalone_bold_pattern.group(1)
            if bold_answer == correct_lower:
                return True, []

        if correct_lower == "true":
            # Check for explicit "true" as first word (including en-dash/em-dash variants and markdown bold)
            if first_word in ["true", "true.", "true,", "true\u2013", "true\u2014", "**true**"]:
                return True, []
            # Check for affirmative statements
            affirmative_phrases = ["answer is true", "answer: true", "is true", "true."]
            negative_phrases = ["not true", "is false", "answer is false"]
            if any(phrase in response_lower for phrase in affirmative_phrases) and not any(
                phrase in response_lower[:100] for phrase in negative_phrases
            ):
                return True, []
            # Check for "⬜ true" pattern (unchecked box used as label for chosen answer)
            if "⬜ true" in response_lower and "⬜ false" not in response_lower:
                return True, []
        else:
            # Check for explicit "false" as first word (including en-dash/em-dash variants and markdown bold)
            if first_word in ["false", "false.", "false,", "false\u2013", "false\u2014", "**false**"]:
                return True, []
            # Check for negative statements
            if any(phrase in response_lower for phrase in ["answer is false", "answer: false", "is false", "false."]):
                return True, []
            # Check for "⬜ false" pattern (unchecked box used as label for chosen answer)
            if "⬜ false" in response_lower and "⬜ true" not in response_lower:
                return True, []

        return False, [f"Expected '{correct_answer}', could not find clear answer in response"]

    return validator


def create_multiple_choice_validator(correct_answer: str, correct_letter: str | None = None) -> Callable[[str], tuple[bool, list[str]]]:
    """Create a validator for Multiple Choice questions."""

    def validator(response: str) -> tuple[bool, list[str]]:
        if not response:
            return False, ["No response received"]

        response_lower = response.lower()
        correct_lower = correct_answer.lower()

        # Check for letter answer (A, B, C, D) if we know the correct letter
        if correct_letter:
            # Look for standalone letter at start of response
            first_word = response_lower.strip().split()[0] if response_lower.strip() else ""
            if first_word.rstrip(".),:") == correct_letter.lower():
                return True, []
            # Look for "answer is D" or "answer: D" patterns
            letter_patterns = [
                f"answer is {correct_letter.lower()}",
                f"answer: {correct_letter.lower()}",
                f"answer is **{correct_letter.lower()}**",
                f"**{correct_letter.lower()}**",
            ]
            if any(pattern in response_lower for pattern in letter_patterns):
                return True, []

        # Look for checkmark next to correct answer
        if "☑" in response or "✓" in response or "✔" in response:
            lines = response_lower.split("\n")
            for line in lines:
                if "☑" in line or "✓" in line or "✔" in line:
                    line_clean = line.replace("☑", "").replace("✓", "").replace("✔", "").replace("⬜", "")
                    line_normalized = normalize_text(line_clean)
                    correct_normalized = normalize_text(correct_lower)

                    if line_normalized == correct_normalized or correct_normalized in line_normalized:
                        return True, []

        # Look for explicit answer statement
        if "answer:" in response_lower or "answer is" in response_lower or "correct answer" in response_lower:
            for phrase in ["answer:", "answer is", "correct answer is", "correct answer:"]:
                if phrase in response_lower:
                    answer_part = response_lower.split(phrase)[1].split("\n")[0]
                    answer_normalized = normalize_text(answer_part)
                    correct_normalized = normalize_text(correct_lower)
                    if correct_normalized in answer_normalized:
                        return True, []

        # Check normalized text containment
        correct_normalized = normalize_text(correct_lower)
        response_normalized = normalize_text(response_lower)

        if correct_normalized == response_normalized or correct_normalized in response_normalized:
            return True, []

        # Check first line specifically
        first_line = response_lower.split("\n")[0] if "\n" in response_lower else response_lower
        first_line_normalized = normalize_text(first_line)
        if correct_normalized == first_line_normalized or correct_normalized in first_line_normalized:
            return True, []

        # Fuzzy match for longer answers
        if len(correct_normalized) > 10:
            correct_words = set(correct_normalized.split())
            response_words = set(response_normalized.split())
            if correct_words and len(correct_words & response_words) >= len(correct_words) * 0.9:
                return True, []

        return False, [f"Expected '{correct_answer}', not found in response"]

    return validator


def create_multiple_answer_validator(correct_answers: list[str]) -> Callable[[str], tuple[bool, list[str]]]:
    """Create a validator for Multiple Answer questions."""

    def validator(response: str) -> tuple[bool, list[str]]:
        if not response:
            return False, ["No response received"]

        response_lower = response.lower()
        found_correct = set()

        # Look for checkmark indicators
        if "☑" in response or "✓" in response or "✔" in response:
            lines = response_lower.split("\n")
            for line in lines:
                if "☑" in line or "✓" in line or "✔" in line:
                    line_clean = line.replace("☑", "").replace("✓", "").replace("✔", "").replace("⬜", "")
                    line_normalized = normalize_text(line_clean)
                    for correct in correct_answers:
                        correct_normalized = normalize_text(correct.lower())
                        if correct_normalized in line_normalized or line_normalized in correct_normalized:
                            found_correct.add(correct)

            if found_correct:
                if len(found_correct) == len(correct_answers):
                    return True, []
                missing = set(correct_answers) - found_correct
                return False, [f"Missing answers: {', '.join(missing)}"]

        # Look for listed items
        lines = response.split("\n")
        for line in lines:
            line_clean = line.strip()
            if not line_clean or len(line_clean) > 200:
                continue

            line_clean = line_clean.lstrip("⬜☑✓✔-•*123456789. ")
            line_normalized = normalize_text(line_clean.lower())

            for correct in correct_answers:
                correct_normalized = normalize_text(correct.lower())

                if correct_normalized in line_normalized or line_normalized in correct_normalized:
                    found_correct.add(correct)
                elif len(correct_normalized) > 20:
                    words_in_correct = set(correct_normalized.split())
                    words_in_line = set(line_normalized.split())
                    if len(words_in_correct & words_in_line) >= len(words_in_correct) * 0.8:
                        found_correct.add(correct)
                elif len(correct_normalized) <= 20:
                    words_in_correct = set(correct_normalized.split())
                    words_in_line = set(line_normalized.split())
                    if words_in_correct and len(words_in_correct & words_in_line) >= len(words_in_correct) * 0.9:
                        found_correct.add(correct)

        if len(found_correct) == len(correct_answers):
            return True, []

        missing = set(correct_answers) - found_correct
        return False, [f"Missing answers: {', '.join(missing)}"]

    return validator


# =============================================================================
# Question Formatting
# =============================================================================


def format_question(question_data: dict) -> str:
    """Format question in certification exam style with explicit answer-only instructions."""
    question_type = question_data["type"]
    question_text = question_data["question"]
    options = question_data.get("options", [])

    if question_type == "true_false":
        formatted = (
            f"{question_text}\n\n"
            "⬜ True\n"
            "⬜ False\n\n"
            "Answer with ONLY 'True' or 'False'. Do not include any explanation or other text."
        )
    elif question_type == "multiple_choice":
        formatted = f"{question_text}\n\n"
        for option in options:
            formatted += f"⬜ {option}\n"
        formatted += (
            "\nSelect exactly ONE answer. Respond with ONLY the answer text, nothing else. "
            "Do not include any explanation, reasoning, or additional text."
        )
    elif question_type == "multiple_answer":
        num_answers = len(question_data.get("correct_answers", []))
        formatted = f"{question_text.replace('(Select 2)', '').strip()}\n\n"
        for option in options:
            formatted += f"⬜ {option}\n"
        formatted += (
            f"\nSelect exactly {num_answers} answers. Respond with ONLY the {num_answers} answer texts, "
            "one per line. Do not include any explanation, reasoning, or additional text."
        )
    else:
        formatted = question_text

    return formatted.strip()


# =============================================================================
# Load and Convert Questions to TestCases
# =============================================================================


def load_test_cases(questions_file: Path) -> list[TestCase]:
    """Load questions from JSON and convert to TestCase objects."""
    with open(questions_file) as f:
        data = json.load(f)

    test_cases = []

    # Process each product's questions
    products = [
        ("vault_associate_003", "Vault"),
        ("consul_associate_003", "Consul"),
        ("terraform_associate_003", "Terraform"),
    ]

    for key, product_name in products:
        questions = data.get(key, [])

        for q in questions:
            question_id = q["id"]
            question_type = q["type"]

            # Create the appropriate validator
            if question_type == "true_false":
                validator = create_true_false_validator(q["correct_answer"])
                correct_display = q["correct_answer"]
            elif question_type == "multiple_choice":
                # Compute correct letter (A, B, C, D) from options
                options = q.get("options", [])
                correct_letter = None
                if options and q["correct_answer"] in options:
                    idx = options.index(q["correct_answer"])
                    correct_letter = chr(ord("A") + idx)  # A, B, C, D...
                validator = create_multiple_choice_validator(q["correct_answer"], correct_letter)
                correct_display = q["correct_answer"]
            elif question_type == "multiple_answer":
                validator = create_multiple_answer_validator(q["correct_answers"])
                correct_display = ", ".join(q["correct_answers"])
            else:
                continue

            # Format the question
            formatted_question = format_question(q)

            # Create TestCase
            test_case = TestCase(
                question=formatted_question,
                description=f"{product_name} {question_id.upper()} ({question_type})",
                expected_keywords=[],  # We use custom validator instead
                min_response_length=1,  # Allow single-letter answers like "D"
                timeout=REQUEST_TIMEOUT,
                custom_validator=validator,
                metadata={
                    "product": product_name,
                    "cert_key": key,
                    "question_id": question_id,
                    "question_type": question_type,
                    "correct_answer": correct_display,
                    "original_question": q["question"],
                },
            )
            test_cases.append(test_case)

    return test_cases


# =============================================================================
# Custom Console Reporter with Product Breakdown
# =============================================================================


def print_detailed_summary(results: list[TestResult]):
    """Print detailed summary with product and type breakdowns."""
    print("\n" + "=" * 80)
    print("DETAILED SUMMARY")
    print("=" * 80)

    # Overall stats
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    pass_rate = (passed / total * 100) if total > 0 else 0

    print(f"\nOverall: {passed}/{total} tests passed ({pass_rate:.1f}%)")

    # Timing stats
    total_time = sum(r.response_time for r in results)
    avg_time = total_time / total if total > 0 else 0
    print("\nTiming:")
    print(f"  Total time: {total_time:.2f}s ({total_time/60:.1f}m)")
    print(f"  Average per test: {avg_time:.2f}s")

    # By product
    print("\nBy product:")
    products = {r.test_case.metadata.get("product", "Unknown") for r in results}
    for product in sorted(products):
        prod_results = [r for r in results if r.test_case.metadata.get("product") == product]
        prod_passed = sum(1 for r in prod_results if r.passed)
        prod_total = len(prod_results)
        prod_rate = (prod_passed / prod_total * 100) if prod_total > 0 else 0
        prod_avg_time = sum(r.response_time for r in prod_results) / prod_total if prod_total > 0 else 0
        print(f"  {product:15s}: {prod_passed:2d}/{prod_total:2d} ({prod_rate:5.1f}%) - avg {prod_avg_time:.2f}s/test")

    # By question type
    print("\nBy question type:")
    types = {r.test_case.metadata.get("question_type", "unknown") for r in results}
    for qtype in sorted(types):
        type_results = [r for r in results if r.test_case.metadata.get("question_type") == qtype]
        type_passed = sum(1 for r in type_results if r.passed)
        type_total = len(type_results)
        type_rate = (type_passed / type_total * 100) if type_total > 0 else 0
        type_avg_time = sum(r.response_time for r in type_results) / type_total if type_total > 0 else 0
        print(f"  {qtype:20s}: {type_passed:2d}/{type_total:2d} ({type_rate:5.1f}%) - avg {type_avg_time:.2f}s/test")

    # Slowest tests
    slowest_tests = sorted(results, key=lambda r: r.response_time, reverse=True)[:5]
    if slowest_tests:
        print("\nSlowest tests:")
        for r in slowest_tests:
            product = r.test_case.metadata.get("product", "Unknown")
            status = CHECK_MARK if r.passed else X_MARK
            print(f"  [{status}] {product} {r.test_case.metadata.get('question_id', '?')}: {r.response_time:.2f}s")

    # Failed tests
    failed_tests = [r for r in results if not r.passed]
    if failed_tests:
        print(f"\nFailed tests ({len(failed_tests)}):")
        for r in failed_tests:
            product = r.test_case.metadata.get("product", "Unknown")
            qid = r.test_case.metadata.get("question_id", "?")
            correct = r.test_case.metadata.get("correct_answer", "?")
            print(f"  {X_MARK} {product} {qid}: expected '{correct}'")
            if r.issues:
                for issue in r.issues:
                    print(f"      {issue}")

    print("=" * 80)


# =============================================================================
# Main Entry Point
# =============================================================================


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run HashiCorp certification tests against Ivan")
    parser.add_argument("--html", type=str, help="Generate HTML report to specified path")
    parser.add_argument("--json", type=str, help="Generate JSON report to specified path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full responses")
    parser.add_argument("--limit", "-n", type=int, help="Limit number of tests to run")
    parser.add_argument("--model", "-m", type=str, default=DEFAULT_MODEL, help=f"Model to test (default: {DEFAULT_MODEL})")
    parser.add_argument("--test", "-t", type=str, help="Run specific test(s). Format: 'terraform_associate_003' or 'terraform_associate_003:q15'")
    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("HASHICORP CERTIFICATION - REGRESSION TEST SUITE")
    print("Using llm_api_server.eval framework")
    print("=" * 80)
    print(f"Model: {args.model}")

    # Load test cases
    print(f"\nLoading questions from {QUESTIONS_FILE}...")
    test_cases = load_test_cases(QUESTIONS_FILE)
    print(f"Loaded {len(test_cases)} test cases")

    # Create evaluator
    evaluator = Evaluator(
        api_url=IVAN_API_URL,
        model=args.model,
        stream=False,
        extra_params={"temperature": 0},
    )

    # Check health
    print(f"\nChecking Ivan at {IVAN_API_URL}...")
    if not evaluator.check_health():
        print("ERROR: Ivan is not running or not healthy")
        print("Make sure Ivan is running: python ivan.py")
        sys.exit(1)
    print("Ivan is healthy")

    # Apply test filter if specified
    if args.test:
        if ":" in args.test:
            # Format: cert_key:question_id (e.g., terraform_associate_003:q15)
            cert_key, question_id = args.test.split(":", 1)
            test_cases = [
                tc for tc in test_cases
                if tc.metadata.get("cert_key") == cert_key and tc.metadata.get("question_id") == question_id
            ]
        else:
            # Format: cert_key only (e.g., terraform_associate_003)
            test_cases = [tc for tc in test_cases if tc.metadata.get("cert_key") == args.test]

        if not test_cases:
            print(f"ERROR: No tests found matching '{args.test}'")
            print("Available cert keys: vault_associate_003, consul_associate_003, terraform_associate_003")
            sys.exit(1)
        print(f"Filtered to {len(test_cases)} test(s) matching '{args.test}'")

    # Apply limit if specified
    if args.limit:
        test_cases = test_cases[: args.limit]

    # Run tests
    print(f"\nRunning {len(test_cases)} tests...\n")
    results = []

    for i, test_case in enumerate(test_cases, 1):
        product = test_case.metadata.get("product", "?")
        qid = test_case.metadata.get("question_id", "?")
        qtype = test_case.metadata.get("question_type", "?")
        correct = test_case.metadata.get("correct_answer", "?")

        print(f"[{i}/{len(test_cases)}] {product} {qid.upper()} ({qtype})")
        print(f"  Expected: {correct[:60]}{'...' if len(correct) > 60 else ''}")

        result = evaluator.run_test(test_case)
        results.append(result)

        status = f"{CHECK_MARK} PASS" if result.passed else f"{X_MARK} FAIL"
        print(f"  Result: {status} ({result.response_time:.2f}s)")

        if not result.passed and result.issues:
            for issue in result.issues:
                print(f"  Issue: {issue}")

        if args.verbose and result.response:
            print(f"  Response preview: {result.response[:200]}...")

        print()

    # Print detailed summary
    print_detailed_summary(results)

    # Generate reports
    if args.html:
        print(f"\nGenerating HTML report: {args.html}")
        html_reporter = HTMLReporter()
        html_reporter.generate(results, args.html, title="HashiCorp Certification Test Results")
        print(f"HTML report saved to {args.html}")

    if args.json:
        print(f"\nGenerating JSON report: {args.json}")
        json_reporter = JSONReporter()
        json_reporter.generate(results, args.json)
        print(f"JSON report saved to {args.json}")

    # Exit code
    failed = sum(1 for r in results if not r.passed)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
