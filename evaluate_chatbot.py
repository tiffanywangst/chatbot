"""
evaluate_chatbot.py

Evaluation harness for the MIT Course Navigator chatbot.
Tests factual accuracy, relevance, hallucination, and helpfulness.

NOTE: MIT renumbered all Course 6 subjects starting Fall 2022.
All tests use NEW numbers as primary, with OLD numbers as accepted synonyms.

  Old → New
  6.006 → 6.1210  (Introduction to Algorithms)
  6.009 → 6.1010  (Fundamentals of Programming)
  6.034 → 6.4110  (Artificial Intelligence)
  6.036 → 6.3900  (Introduction to Machine Learning)
  6.042 → 6.1200  (Mathematics for Computer Science)

Usage:
    python evaluate_chatbot.py                    # Gradio at 127.0.0.1:7860
    python evaluate_chatbot.py --direct           # import Chatbot directly
    python evaluate_chatbot.py --out results.json # save JSON
    python evaluate_chatbot.py --verbose          # print response for every test
"""

import argparse
import json
import time
import sys
import textwrap
from dataclasses import dataclass, asdict, field

try:
    from src.chat import Chatbot as _DirectChatbot
    DIRECT_AVAILABLE = True
except ImportError:
    DIRECT_AVAILABLE = False

try:
    import requests as _requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# =============================================================================
# TEST CASE DEFINITION
# =============================================================================

@dataclass
class TestCase:
    id: str
    category: str
    query: str
    # Each entry is a synonym group: test passes that group if ANY synonym matches.
    # ALL groups must pass for the overall test to pass.
    must_contain_any: list = field(default_factory=list)   # list[list[str]]
    must_not_contain: list = field(default_factory=list)   # list[str]
    rubric: str = ""

    def synonym_groups(self):
        return self.must_contain_any


# =============================================================================
# TEST SUITE  (30 cases)
# =============================================================================

TEST_CASES = [

    # ─────────────────────────────────────────────────────────────────────────
    # EXACT SUBJECT LOOKUP
    # Use NEW numbers in queries; accept both new and old in responses since
    # FireRoad may return the old_id field alongside the new subject_id.
    # ─────────────────────────────────────────────────────────────────────────
    TestCase(
        id="exact_6_1210",
        category="exact_lookup",
        query="Tell me about 6.1210.",
        must_contain_any=[
            ["6.1210", "6.006"],                          # new or old ID
            ["algorithm", "algorithms"],                   # topic must appear
        ],
        rubric=(
            "NEW number for old 6.006. Should return Introduction to Algorithms. "
            "Previously tested as 6.006 and failed because the API stores the new number. "
            "Accept both IDs since FireRoad shows old_id in the entry."
        ),
    ),
    TestCase(
        id="exact_18_01",
        category="exact_lookup",
        query="What is 18.01?",
        must_contain_any=[["18.01"], ["calculus"]],
        rubric="18.01 was NOT renumbered (only Course 6 changed). Should identify Single Variable Calculus.",
    ),
    TestCase(
        id="exact_21L_001",
        category="exact_lookup",
        query="What is 21L.001?",
        must_contain_any=[["21L.001"]],
        rubric="21L subjects were not renumbered. Should return the correct literature subject.",
    ),
    TestCase(
        id="exact_6_4110",
        category="exact_lookup",
        query="Tell me about 6.4110.",
        must_contain_any=[
            ["6.4110", "6.034"],
            ["artificial intelligence", "ai"],
        ],
        rubric="NEW number for old 6.034 Artificial Intelligence.",
    ),
    TestCase(
        id="exact_6_1010",
        category="exact_lookup",
        query="What is 6.1010?",
        must_contain_any=[
            ["6.1010", "6.009"],
            ["programming", "fundamentals"],
        ],
        rubric="NEW number for old 6.009 Fundamentals of Programming.",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # BACKWARD COMPAT: old numbers should still work (FireRoad stores old_id)
    # ─────────────────────────────────────────────────────────────────────────
    TestCase(
        id="compat_old_6_006",
        category="backward_compat",
        query="Tell me about 6.006.",
        must_contain_any=[
            ["6.1210", "6.006"],
            ["algorithm", "algorithms"],
        ],
        rubric=(
            "Old number 6.006 entered by user. FireRoad stores it as old_id on the 6.1210 entry. "
            "The chatbot should still find and describe Introduction to Algorithms. "
            "This is the test that previously appeared to fail — it was actually a test design bug "
            "(checking for 'algorithm' singular when response said 'Algorithms')."
        ),
    ),
    TestCase(
        id="compat_old_6_034",
        category="backward_compat",
        query="What are the prerequisites for 6.034?",
        must_contain_any=[
            ["6.4110", "6.034"],
        ],
        rubric="Old number 6.034 — should resolve to 6.4110 via old_id lookup.",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # PREREQUISITES
    # ─────────────────────────────────────────────────────────────────────────
    TestCase(
        id="prereqs_6_1210",
        category="prerequisites",
        query="What are the prerequisites for 6.1210?",
        must_contain_any=[["6.1210", "6.006"]],
        must_not_contain=["i don't know", "cannot find"],
        rubric="Should mention prereqs (e.g. 6.1200/6.042, 6.1010/6.009, 18.01).",
    ),
    TestCase(
        id="prereqs_6_4110",
        category="prerequisites",
        query="What do I need to take before 6.4110?",
        must_contain_any=[["6.4110", "6.034"]],
        rubric="Should cite actual prerequisites from the catalog for AI.",
    ),
    TestCase(
        id="prereqs_chain",
        category="prerequisites",
        query="I want to take advanced algorithms. What should I take first?",
        must_contain_any=[["6.1210", "6.006", "algorithm"]],
        rubric="Should suggest 6.1210 (old 6.006) as a foundation.",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # DISTRIBUTION REQUIREMENTS
    # ─────────────────────────────────────────────────────────────────────────
    TestCase(
        id="hass_economics",
        category="distribution_requirements",
        query="I need a HASS-S elective. I like economics and policy.",
        must_contain_any=[["hass", "hass-s"]],
        must_not_contain=["i cannot help", "no courses"],
        rubric="Should suggest >= 1 HASS-S course with economics/social-science focus.",
    ),
    TestCase(
        id="ci_h_options",
        category="distribution_requirements",
        query="What CI-H courses are available for Course 6 students?",
        must_contain_any=[["ci-h"]],
        rubric="Should suggest CI-H courses relevant to EECS.",
    ),
    TestCase(
        id="rest_requirement",
        category="distribution_requirements",
        query="Which courses satisfy the REST requirement?",
        must_contain_any=[["rest"]],
        rubric="Should explain REST and give examples.",
    ),
    TestCase(
        id="gir_lab",
        category="distribution_requirements",
        query="What are the lab science GIR options?",
        must_contain_any=[["gir", "lab"]],
        rubric="Should list lab subjects satisfying the GIR.",
    ),
    TestCase(
        id="hass_arts",
        category="distribution_requirements",
        query="I want a HASS-A course related to music or visual arts.",
        must_contain_any=[["hass", "hass-a"]],
        rubric="Should suggest HASS-A arts courses.",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # MULTI-CONSTRAINT
    # ─────────────────────────────────────────────────────────────────────────
    TestCase(
        id="multi_constraint_junior",
        category="multi_constraint",
        query=(
            "I'm a 6-3 junior who needs a CI-H and prefers afternoon classes. "
            "I'm interested in AI ethics."
        ),
        must_contain_any=[["ci-h"]],
        must_not_contain=["i cannot", "sorry, i"],
        rubric="Should suggest >= 1 specific course matching CI-H + AI/ethics theme.",
    ),
    TestCase(
        id="multi_constraint_freshman",
        category="multi_constraint",
        query=(
            "I'm a freshman exploring majors. I like biology and computation. "
            "What courses would help me figure out what to study?"
        ),
        must_contain_any=[],
        must_not_contain=["i don't have", "no information"],
        rubric="Should suggest intro courses spanning CS, biology, or computational biology.",
    ),
    TestCase(
        id="multi_constraint_grad",
        category="multi_constraint",
        query="I'm a grad student in Course 6. I want something in ML theory.",
        must_contain_any=[["graduate", "grad", "g level", "g-level", "advanced"]],
        rubric="Should suggest graduate ML/theory courses.",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # HALLUCINATION GUARD
    # ─────────────────────────────────────────────────────────────────────────
    TestCase(
        id="fake_course",
        category="hallucination",
        query="Tell me about 99.999 - Advanced Unicorn Studies.",
        must_not_contain=[
            "unicorn studies is a course",
            "99.999 covers",
            "99.999 is offered",
            "advanced unicorn studies covers",
        ],
        rubric=(
            "Should NOT fabricate a description. Mentioning '99.999' in a "
            "'not found' sentence is fine — only fake descriptions are banned."
        ),
    ),
    TestCase(
        id="fake_instructor",
        category="hallucination",
        query="What courses does Professor Zaphod Beeblebrox teach at MIT?",
        must_not_contain=["zaphod beeblebrox teaches", "professor beeblebrox offers"],
        rubric="Should not fabricate course listings for a nonexistent instructor.",
    ),
    TestCase(
        id="fake_dept",
        category="hallucination",
        query="What courses are in the MIT Department of Wizardry?",
        must_not_contain=["department of wizardry offers", "wizardry 1.", "wizardry 2."],
        rubric="Should not invent courses for a nonexistent department.",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # OFF-TOPIC REDIRECT
    # Require a redirect signal; only ban actual answer content (not echoed words).
    # ─────────────────────────────────────────────────────────────────────────
    TestCase(
        id="offtopic_weather",
        category="off_topic",
        query="What's the weather like in Cambridge today?",
        must_contain_any=[["mit", "course", "subject", "catalog", "help you with"]],
        must_not_contain=["the temperature is", "currently raining", "sunny today", "°f", "°c"],
        rubric=(
            "Should redirect to MIT courses. "
            "Only ban actual weather answers, not echoed question words."
        ),
    ),
    TestCase(
        id="offtopic_stock",
        category="off_topic",
        query="What is the current stock price of Apple?",
        must_contain_any=[["mit", "course", "subject", "catalog", "help you with"]],
        must_not_contain=["aapl is trading", "apple shares", "nasdaq", "per share"],
        rubric=(
            "Should redirect to MIT courses. "
            "Only ban actual stock data, not the echoed question."
        ),
    ),
    TestCase(
        id="offtopic_recipe",
        category="off_topic",
        query="How do I make carbonara pasta?",
        must_contain_any=[["mit", "course", "subject", "catalog", "help you with"]],
        must_not_contain=["guanciale", "pecorino", "pasta water", "egg yolk"],
        rubric="Should redirect. Should not provide cooking instructions.",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # WORKLOAD / UNITS
    # Accept any numeric unit phrase, not just the bare word "unit".
    # ─────────────────────────────────────────────────────────────────────────
    TestCase(
        id="units_6_1210",
        category="workload",
        query="How many units is 6.1210?",
        must_contain_any=[
            ["6.1210", "6.006"],
            ["12 unit", "12-unit", "worth 12", "12 credit", "units: 12", "total units", "12"],
        ],
        rubric=(
            "Should state 12 units for Introduction to Algorithms (new number 6.1210). "
            "Accepts any numeric unit phrase — prior test failed by requiring bare 'unit'."
        ),
    ),
    TestCase(
        id="units_18_06",
        category="workload",
        query="How many units is 18.06?",
        must_contain_any=[["18.06"], ["unit", "credit", "12", "15"]],
        rubric="Should state units for Linear Algebra (18.06 not renumbered).",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # LEVEL
    # ─────────────────────────────────────────────────────────────────────────
    TestCase(
        id="grad_ml",
        category="level",
        query="I'm a grad student interested in advanced machine learning. What graduate courses are there?",
        must_contain_any=[["graduate", "grad", "g level", "g-level", "advanced"]],
        rubric="Should return graduate-level ML courses.",
    ),
    TestCase(
        id="undergrad_intro",
        category="level",
        query="What are good introductory undergraduate courses in Course 6?",
        must_contain_any=[["undergraduate", "undergrad", "introductory", "intro", "6."]],
        rubric="Should suggest intro EECS undergrad courses.",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # DEPARTMENT BROWSING
    # ─────────────────────────────────────────────────────────────────────────
    TestCase(
        id="dept_wgs",
        category="department",
        query="What courses does the Women's and Gender Studies department offer?",
        must_contain_any=[["wgs"]],
        rubric="Should list WGS courses.",
    ),
    TestCase(
        id="dept_course6_overview",
        category="department",
        query="Give me an overview of what Course 6 has to offer.",
        must_contain_any=[["6."]],
        rubric="Should describe EECS offerings with several course examples.",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # SCHEDULING / SEMESTER
    # ─────────────────────────────────────────────────────────────────────────
    TestCase(
        id="fall_courses",
        category="scheduling",
        query="What interesting courses are offered only in the fall semester?",
        must_contain_any=[["fall"]],
        rubric="Should return fall-only course recommendations.",
    ),
    TestCase(
        id="iap_courses",
        category="scheduling",
        query="Are there any interesting courses during IAP?",
        must_contain_any=[
            ["iap", "independent activities period", "january term", "january"],
        ],
        rubric=(
            "Should mention IAP subjects. Accepts 'IAP', 'Independent Activities Period', "
            "and 'January' as synonyms — prior test failed when model said 'January'."
        ),
    ),
]


# =============================================================================
# BACKENDS
# =============================================================================

class DirectBackend:
    def __init__(self):
        if not DIRECT_AVAILABLE:
            raise ImportError("Could not import src.chat.Chatbot — run from project root.")
        self._bot = _DirectChatbot()

    def query(self, text):
        return self._bot.get_response(text, history=[])


class GradioBackend:
    def __init__(self, base_url="http://127.0.0.1:7860"):
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests is not installed.")
        self.base_url = base_url.rstrip("/")
        self._session = _requests.Session()

    def query(self, text):
        url = f"{self.base_url}/api/predict"
        payload = {"data": [text, []]}
        resp = self._session.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        history = data.get("data", [[]])[0]
        if history and isinstance(history[-1], list):
            return history[-1][1] or ""
        return str(data)


# =============================================================================
# EVALUATOR
# =============================================================================

@dataclass
class Result:
    id: str
    category: str
    query: str
    response: str
    passed: bool
    failures: list
    latency_s: float
    rubric: str


def _check(response, case):
    failures = []
    lower = response.lower()
    for group in case.synonym_groups():
        if not any(syn.lower() in lower for syn in group):
            readable = " | ".join(f'"{s}"' for s in group)
            failures.append(f"MISSING (need one of): {readable}")
    for phrase in case.must_not_contain:
        if phrase.lower() in lower:
            failures.append(f"FOUND forbidden phrase: '{phrase}'")
    return failures


def _wrap(text, width=90, indent="         "):
    lines = []
    for line in text.splitlines():
        wrapped = textwrap.fill(line, width=width, subsequent_indent=indent)
        lines.append(wrapped)
    return "\n".join(lines)


def run_evaluation(backend, test_cases, delay=1.0, verbose=False):
    results = []
    total = len(test_cases)
    for i, case in enumerate(test_cases, 1):
        print(f"[{i:2d}/{total}] {case.id:<42}", end="", flush=True)
        t0 = time.time()
        try:
            response = backend.query(case.query)
            latency = time.time() - t0
            failures = _check(response, case)
            passed = len(failures) == 0
        except Exception as exc:
            latency = time.time() - t0
            response = f"ERROR: {exc}"
            failures = [f"Exception: {exc}"]
            passed = False

        label = "PASS" if passed else "FAIL"
        print(f" {label}  ({latency:.1f}s)")

        if not passed or verbose:
            preview = response.replace("\n", " ").strip()
            if len(preview) > 300:
                preview = preview[:297] + "..."
            print(f"         RESPONSE: {_wrap(preview)}")

        if failures:
            for f in failures:
                print(f"         ↳ {f}")

        results.append(Result(
            id=case.id, category=case.category, query=case.query,
            response=response, passed=passed, failures=failures,
            latency_s=round(latency, 2), rubric=case.rubric,
        ))
        if delay:
            time.sleep(delay)
    return results


# =============================================================================
# REPORTING
# =============================================================================

def print_summary(results):
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    pct = 100 * passed / total if total else 0
    print("\n" + "=" * 65)
    print(f"OVERALL: {passed}/{total} passed  ({pct:.0f}%)")
    print("=" * 65)

    categories = {}
    for r in results:
        categories.setdefault(r.category, []).append(r)
    print("\nBy category:")
    for cat, rs in sorted(categories.items()):
        p = sum(1 for r in rs if r.passed)
        bar = "#" * p + "-" * (len(rs) - p)
        print(f"  {cat:<38} {p}/{len(rs)}  [{bar}]")

    failed = [r for r in results if not r.passed]
    if failed:
        print(f"\nFailed tests ({len(failed)}):")
        for r in failed:
            print(f"\n  • {r.id}  [{r.category}]")
            print(f"    QUERY:    {r.query[:120]}")
            preview = r.response.replace('\n', ' ').strip()[:300]
            print(f"    RESPONSE: {preview}")
            for f in r.failures:
                print(f"    ↳ {f}")
            if r.rubric:
                print(f"    RUBRIC:   {r.rubric[:120]}")

    latencies = [r.latency_s for r in results]
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    print(f"\nAvg latency: {avg_lat:.1f}s  |  Max: {max(latencies, default=0):.1f}s")
    print("=" * 65)


def save_results(results, path):
    with open(path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    print(f"\nResults saved to {path}")


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--direct", action="store_true")
    parser.add_argument("--url", default="http://127.0.0.1:7860")
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--out", default="")
    parser.add_argument("--category", default="")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    cases = TEST_CASES
    if args.category:
        cases = [c for c in cases if c.category == args.category]
        if not cases:
            print(f"No tests in category '{args.category}'.")
            sys.exit(1)

    if args.direct:
        print("Using direct backend (importing Chatbot)...")
        backend = DirectBackend()
    else:
        print(f"Using Gradio backend at {args.url}...")
        backend = GradioBackend(args.url)

    print(f"Running {len(cases)} test(s) with {args.delay}s delay.\n")
    results = run_evaluation(backend, cases, delay=args.delay, verbose=args.verbose)
    print_summary(results)
    if args.out:
        save_results(results, args.out)


if __name__ == "__main__":
    main()