#!/usr/bin/env python3
"""
Certification Question Regression Test

Tests Ivan's ability to answer HashiCorp certification practice questions
by querying the Ivan API directly and grading responses against official answers.

Usage:
    python tests/test_certification.py

Requirements:
    - Ivan must be running on http://localhost:8000
    - Backend LLM must be available (LM Studio/Ollama)
"""

import json
import requests
import sys
import time
from typing import Dict, List, Optional

# Configuration
IVAN_ENDPOINT = "http://localhost:8000/v1/chat/completions"
QUESTIONS_FILE = "tests/certification_questions.json"
REQUEST_TIMEOUT = 90  # seconds
REQUEST_DELAY = 1  # seconds between requests to avoid overwhelming the backend


class CertificationTester:
    """Test Ivan with certification questions"""

    def __init__(self, endpoint: str, questions_file: str):
        self.endpoint = endpoint
        self.questions_file = questions_file
        self.questions = []
        self.results = []

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Aggressively normalize text for comparison by removing all punctuation,
        extra whitespace, and converting to lowercase.

        This ensures that answers match regardless of:
        - Periods, commas, quotes, etc.
        - En-dashes (–), em-dashes (—), hyphens (-)
        - Multiple spaces or newlines
        - Different quote styles (' " ' " " ')
        """
        import re
        import unicodedata

        # Convert to lowercase
        normalized = text.lower()

        # Replace all quotation and apostrophe variants with space
        # This includes: ' ' " " " ` ´ ʻ ʼ ʽ ʾ ʿ ˈ ˊ ˋ etc.
        quote_chars = [
            "'", '"', '`', '´',  # ASCII quotes
            '\u2018', '\u2019',  # ' '  (left and right single quote)
            '\u201A', '\u201B',  # ‚ ‛  (single low-9 quote, single high-reversed-9 quote)
            '\u201C', '\u201D',  # " "  (left and right double quote)
            '\u201E', '\u201F',  # „ ‟  (double low-9 quote, double high-reversed-9 quote)
            '\u2032', '\u2033',  # ′ ″  (prime, double prime)
            '\u02BB', '\u02BC', '\u02BD', '\u02BE', '\u02BF',  # Various modifier letters
        ]
        for char in quote_chars:
            normalized = normalized.replace(char, '')

        # Replace all hyphen/dash variants with space
        # This includes regular hyphen, en-dash, em-dash, non-breaking hyphen, etc.
        hyphen_chars = [
            '-',         # U+002D - Regular hyphen-minus
            '‐',         # U+2010 - Hyphen
            '‑',         # U+2011 - Non-breaking hyphen
            '‒',         # U+2012 - Figure dash
            '–',         # U+2013 - En dash
            '—',         # U+2014 - Em dash
            '―',         # U+2015 - Horizontal bar
            '−',         # U+2212 - Minus sign
        ]
        for char in hyphen_chars:
            normalized = normalized.replace(char, '')  # Remove entirely (don't add space)

        # Remove all other common punctuation and special characters
        punctuation_chars = [
            '.', ',', '!', '?', ';', ':',
            '(', ')', '[', ']', '{', '}',
            '/', '\\', '|',
            '*', '#', '@', '$', '%', '^', '&',
        ]
        for char in punctuation_chars:
            normalized = normalized.replace(char, ' ')

        # Replace multiple spaces with single space
        normalized = re.sub(r'\s+', ' ', normalized)

        return normalized.strip()

    def load_questions(self) -> bool:
        """Load questions from JSON file"""
        try:
            with open(self.questions_file, 'r') as f:
                data = json.load(f)
                # Load all question sets
                vault_q = data.get('vault_associate_003', [])
                consul_q = data.get('consul_associate_003', [])
                terraform_q = data.get('terraform_associate_003', [])

                # Tag each question with its product
                for q in vault_q:
                    q['product'] = 'Vault'
                for q in consul_q:
                    q['product'] = 'Consul'
                for q in terraform_q:
                    q['product'] = 'Terraform'

                # Combine all questions
                self.questions = vault_q + consul_q + terraform_q

            print(f"✅ Loaded {len(self.questions)} questions (Vault: {len(vault_q)}, Consul: {len(consul_q)}, Terraform: {len(terraform_q)})")
            return True
        except Exception as e:
            print(f"❌ Failed to load questions: {e}")
            return False

    def format_question(self, question_data: Dict) -> str:
        """Format question in certification exam style"""
        question_type = question_data['type']
        question_text = question_data['question']
        options = question_data.get('options', [])

        if question_type == 'true_false':
            formatted = (
                "True or false questions present you with a statement and ask you to choose whether it is true or false.\n\n"
                f"{question_text}\n\n"
                "⬜ True\n"
                "⬜ False"
            )
        elif question_type == 'multiple_choice':
            formatted = (
                "Multiple choice questions ask you to select one correct answer from a list.\n\n"
                f"{question_text}\n\n"
            )
            for option in options:
                formatted += f"⬜ {option}\n"
        elif question_type == 'multiple_answer':
            num_answers = len(question_data.get('correct_answers', []))
            formatted = (
                "Multiple answer questions ask you to select multiple correct answers from a list. "
                "The question indicates how many answers you must choose.\n\n"
                f"{question_text.replace('(Select 2)', '').strip()} "
                f"Pick the {num_answers} correct responses below\n\n"
            )
            for option in options:
                formatted += f"⬜ {option}\n"
        else:
            formatted = question_text

        return formatted.strip()

    def check_ivan_health(self) -> bool:
        """Check if Ivan is running"""
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                print("✅ Ivan is running")
                return True
        except Exception as e:
            print(f"❌ Cannot connect to Ivan: {e}")
            print(f"   Make sure Ivan is running: python ivan.py")
            return False

    def query_ivan(self, question: str) -> Optional[str]:
        """Send question to Ivan API"""
        try:
            payload = {
                "model": "wwtfo/ivan",
                "messages": [
                    {"role": "user", "content": question}
                ],
                "temperature": 0
            }

            response = requests.post(
                self.endpoint,
                json=payload,
                timeout=REQUEST_TIMEOUT
            )

            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content']
            else:
                print(f"   ⚠️  API returned status {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            print(f"   ⚠️  Request timeout after {REQUEST_TIMEOUT}s")
            return None
        except Exception as e:
            print(f"   ⚠️  Request failed: {e}")
            return None

    def grade_true_false(self, response: str, correct_answer: str) -> bool:
        """Grade True/False question"""
        if not response:
            return False

        response_lower = response.lower()
        correct_lower = correct_answer.lower()

        # Look for checkmark/selection indicators
        if '☑' in response or '✓' in response or '✔' in response:
            # Look for marked checkboxes
            if correct_lower == "true":
                return '☑ true' in response_lower or '✓ true' in response_lower or '✔ true' in response_lower
            else:
                return '☑ false' in response_lower or '✓ false' in response_lower or '✔ false' in response_lower

        # Look for explicit answer in first few lines
        first_line = response_lower.split('\n')[0] if '\n' in response_lower else response_lower
        first_word = first_line.strip().split()[0] if first_line.strip() else ""

        if correct_lower == "true":
            # Check for explicit "true" as first word (handles "True – explanation" format)
            if first_word in ["true", "true.", "true,", "true–", "true—"]:
                return True
            # Check for affirmative statements
            if any(phrase in response_lower for phrase in ["answer is true", "answer: true", "is true", "true."]):
                # Make sure it's not negated
                if not any(phrase in response_lower[:100] for phrase in ["not true", "is false", "answer is false"]):
                    return True
        else:  # False
            # Check for explicit "false" as first word (handles "False – explanation" format)
            if first_word in ["false", "false.", "false,", "false–", "false—"]:
                return True
            # Check for negative statements
            if any(phrase in response_lower for phrase in ["answer is false", "answer: false", "is false", "false."]):
                return True

        return False

    def grade_multiple_choice(self, response: str, correct_answer: str) -> bool:
        """Grade multiple choice question"""
        if not response:
            return False

        response_lower = response.lower()
        correct_lower = correct_answer.lower()

        # Look for checkmark/selection indicators next to the correct answer
        if '☑' in response or '✓' in response or '✔' in response:
            lines = response_lower.split('\n')
            for line in lines:
                if ('☑' in line or '✓' in line or '✔' in line):
                    # Normalize the line using our robust normalization
                    line_clean = line.replace("☑", "").replace("✓", "").replace("✔", "").replace("⬜", "")
                    line_normalized = self.normalize_text(line_clean)
                    correct_normalized = self.normalize_text(correct_lower)

                    # Check if normalized texts match
                    if line_normalized == correct_normalized or correct_normalized in line_normalized:
                        return True

        # Look for explicit answer statement
        if "answer:" in response_lower or "answer is" in response_lower or "correct answer" in response_lower:
            # Extract the part after "answer:"
            for phrase in ["answer:", "answer is", "correct answer is", "correct answer:"]:
                if phrase in response_lower:
                    answer_part = response_lower.split(phrase)[1].split('\n')[0]
                    answer_normalized = self.normalize_text(answer_part)
                    correct_normalized = self.normalize_text(correct_lower)
                    if correct_normalized in answer_normalized:
                        return True

        # Check if the correct answer text appears in the response
        correct_normalized = self.normalize_text(correct_lower)
        response_normalized = self.normalize_text(response_lower)

        # Debug output (uncomment to troubleshoot)
        # print(f"\n[DEBUG] Correct normalized: '{correct_normalized}'")
        # print(f"[DEBUG] Response normalized: '{response_normalized}'")

        # Check for exact match or containment
        if correct_normalized == response_normalized:
            return True
        if correct_normalized in response_normalized:
            return True

        # Check first line specifically (often the direct answer)
        first_line = response_lower.split('\n')[0] if '\n' in response_lower else response_lower
        first_line_normalized = self.normalize_text(first_line)
        if correct_normalized == first_line_normalized or correct_normalized in first_line_normalized:
            return True

        # As a last resort, check if the normalized texts are very similar (fuzzy match)
        # This handles edge cases with special unicode characters
        if len(correct_normalized) > 10 and len(response_normalized) > 0:
            # Split into words and check if most words match
            correct_words = set(correct_normalized.split())
            response_words = set(response_normalized.split())
            if correct_words and len(correct_words & response_words) >= len(correct_words) * 0.9:
                return True

        return False

    def grade_multiple_answer(self, response: str, correct_answers: List[str]) -> bool:
        """Grade multiple answer question (must include all correct answers)"""
        if not response:
            return False

        response_lower = response.lower()
        found_correct = set()

        # Look for checkmark/selection indicators (checked boxes)
        if '☑' in response or '✓' in response or '✔' in response:
            lines = response_lower.split('\n')
            for line in lines:
                if ('☑' in line or '✓' in line or '✔' in line):
                    line_clean = line.replace("☑", "").replace("✓", "").replace("✔", "").replace("⬜", "")
                    line_normalized = self.normalize_text(line_clean)
                    # Check if this line matches any correct answer
                    for correct in correct_answers:
                        correct_normalized = self.normalize_text(correct.lower())
                        if correct_normalized in line_normalized or line_normalized in correct_normalized:
                            found_correct.add(correct)

            # If we found checkmarks, only count those
            if found_correct:
                return len(found_correct) == len(correct_answers)

        # Look for listed items (bullet points, dashes, or just plain text lines)
        # Some models return the answers as a simple list
        lines = response.split('\n')
        for line in lines:
            line_clean = line.strip()
            # Skip empty lines and lines that are too long (likely explanations)
            if not line_clean or len(line_clean) > 200:
                continue

            # Remove common list indicators
            line_clean = line_clean.lstrip('⬜☑✓✔-•*123456789. ')
            line_normalized = self.normalize_text(line_clean.lower())

            # Check if this line matches any correct answer
            for correct in correct_answers:
                correct_normalized = self.normalize_text(correct.lower())
                # Check for substantial match (at least 80% of the correct answer text)
                if correct_normalized in line_normalized or line_normalized in correct_normalized:
                    found_correct.add(correct)
                elif len(correct_normalized) > 20:  # For longer answers, check partial match
                    words_in_correct = set(correct_normalized.split())
                    words_in_line = set(line_normalized.split())
                    if len(words_in_correct & words_in_line) >= len(words_in_correct) * 0.8:
                        found_correct.add(correct)
                elif len(correct_normalized) <= 20:  # For short answers, check word match
                    words_in_correct = set(correct_normalized.split())
                    words_in_line = set(line_normalized.split())
                    # If most words match (90%+), consider it a match
                    if words_in_correct and len(words_in_correct & words_in_line) >= len(words_in_correct) * 0.9:
                        found_correct.add(correct)

        # Must find all correct answers
        return len(found_correct) == len(correct_answers)

    def grade_response(self, question_data: Dict, response: str) -> bool:
        """Grade response based on question type"""
        question_type = question_data['type']

        if question_type == 'true_false':
            return self.grade_true_false(response, question_data['correct_answer'])
        elif question_type == 'multiple_choice':
            return self.grade_multiple_choice(response, question_data['correct_answer'])
        elif question_type == 'multiple_answer':
            return self.grade_multiple_answer(response, question_data['correct_answers'])
        else:
            print(f"   ⚠️  Unknown question type: {question_type}")
            return False

    def run_test(self, question_data: Dict) -> Dict:
        """Run a single test"""
        import time
        start_time = time.time()

        question_id = question_data['id']
        question_type = question_data['type']
        question_text = question_data['question']
        product = question_data.get('product', 'Unknown')

        print(f"\n{'='*80}")
        print(f"TEST: {product} {question_id.upper()} ({question_type})")
        print(f"{'='*80}")

        # Format question in certification exam style
        formatted_question = self.format_question(question_data)

        # Print the FULL formatted question that will be sent to Ivan
        print(formatted_question)
        print()

        # Get correct answer for display
        if question_type == 'multiple_answer':
            correct = question_data['correct_answers']
            print(f"Expected Answers: {', '.join(correct)}")
        else:
            correct = question_data.get('correct_answer', 'N/A')
            print(f"Expected Answer: {correct}")

        # Query Ivan
        print("\nQuerying Ivan...")
        response = self.query_ivan(formatted_question)

        if response is None:
            print("❌ No response from Ivan")
            return {
                'id': question_id,
                'type': question_type,
                'product': product,
                'passed': False,
                'response': None,
                'error': 'No response'
            }

        # Show response (full for short responses, preview for long ones)
        if len(response) <= 500:
            print(f"\nIvan's Response:\n{response}")
        else:
            print(f"\nIvan's Response (first 500 chars):\n{response[:500]}...")

        # Grade the response
        passed = self.grade_response(question_data, response)

        # Calculate elapsed time
        elapsed_time = time.time() - start_time

        result_icon = "✅ PASS" if passed else "❌ FAIL"
        print(f"\nResult: {result_icon}")
        print(f"Time: {elapsed_time:.2f}s")

        return {
            'id': question_id,
            'type': question_type,
            'product': product,
            'passed': passed,
            'response': response,
            'time': elapsed_time
        }

    def run_all_tests(self):
        """Run all certification tests"""
        import time
        overall_start_time = time.time()

        print("\n" + "="*80)
        print("HASHICORP CERTIFICATION - REGRESSION TEST SUITE")
        print("="*80)
        print(f"\nTesting with {len(self.questions)} questions from multiple certifications")
        print(f"Endpoint: {self.endpoint}\n")

        for i, question in enumerate(self.questions, 1):
            print(f"\n[{i}/{len(self.questions)}]")
            result = self.run_test(question)
            self.results.append(result)

            # Add delay between requests
            if i < len(self.questions):
                time.sleep(REQUEST_DELAY)

        overall_elapsed_time = time.time() - overall_start_time
        self.print_summary(overall_elapsed_time)

    def print_summary(self, overall_elapsed_time: float):
        """Print test summary"""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)

        # Overall stats
        total = len(self.results)
        passed = sum(1 for r in self.results if r['passed'])
        failed = total - passed
        pass_rate = (passed / total * 100) if total > 0 else 0

        print(f"\nOverall: {passed}/{total} tests passed ({pass_rate:.1f}%)")

        # Timing stats
        total_test_time = sum(r.get('time', 0) for r in self.results)
        avg_time = total_test_time / total if total > 0 else 0
        print(f"\nTiming:")
        print(f"  Total elapsed: {overall_elapsed_time:.2f}s ({overall_elapsed_time/60:.1f}m)")
        print(f"  Total test time: {total_test_time:.2f}s")
        print(f"  Average per test: {avg_time:.2f}s")
        print(f"  Overhead (delays, setup): {(overall_elapsed_time - total_test_time):.2f}s")

        # By product
        print("\nBy product:")
        products = set(r.get('product', 'Unknown') for r in self.results)
        for product in sorted(products):
            prod_results = [r for r in self.results if r.get('product') == product]
            prod_passed = sum(1 for r in prod_results if r['passed'])
            prod_total = len(prod_results)
            prod_rate = (prod_passed / prod_total * 100) if prod_total > 0 else 0
            prod_avg_time = sum(r.get('time', 0) for r in prod_results) / prod_total if prod_total > 0 else 0
            print(f"  {product:15s}: {prod_passed:2d}/{prod_total:2d} ({prod_rate:5.1f}%) - avg {prod_avg_time:.2f}s/test")

        # By question type
        print("\nBy question type:")
        types = set(r['type'] for r in self.results)
        for qtype in sorted(types):
            type_results = [r for r in self.results if r['type'] == qtype]
            type_passed = sum(1 for r in type_results if r['passed'])
            type_total = len(type_results)
            type_rate = (type_passed / type_total * 100) if type_total > 0 else 0
            type_avg_time = sum(r.get('time', 0) for r in type_results) / type_total if type_total > 0 else 0
            print(f"  {qtype:20s}: {type_passed:2d}/{type_total:2d} ({type_rate:5.1f}%) - avg {type_avg_time:.2f}s/test")

        # Slowest tests
        slowest_tests = sorted(self.results, key=lambda r: r.get('time', 0), reverse=True)[:5]
        if slowest_tests:
            print(f"\nSlowest tests:")
            for r in slowest_tests:
                product = r.get('product', 'Unknown')
                test_time = r.get('time', 0)
                status = "✅" if r['passed'] else "❌"
                print(f"  {status} {product} {r['id']}: {test_time:.2f}s")

        # Failed tests
        failed_tests = [r for r in self.results if not r['passed']]
        if failed_tests:
            print(f"\nFailed tests ({len(failed_tests)}):")
            for r in failed_tests:
                product = r.get('product', 'Unknown')
                test_time = r.get('time', 0)
                print(f"  ❌ {product} {r['id']} ({test_time:.2f}s)")

        print("="*80)

        # Exit code
        sys.exit(0 if failed == 0 else 1)


def main():
    """Main entry point"""
    tester = CertificationTester(IVAN_ENDPOINT, QUESTIONS_FILE)

    # Load questions
    if not tester.load_questions():
        sys.exit(1)

    # Check Ivan health
    if not tester.check_ivan_health():
        sys.exit(1)

    # Run tests
    tester.run_all_tests()


if __name__ == "__main__":
    main()
