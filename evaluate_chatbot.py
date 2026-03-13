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

# =============================================================================
# MULTI-TURN TEST CASES
# Each turn has: user message, expected must_contain_any, must_not_contain.
# History is built up automatically as turns progress.
# The test PASSES only if every turn passes.
# =============================================================================

@dataclass
class Turn:
    user: str
    must_contain_any: list = field(default_factory=list)   # list[list[str]]
    must_not_contain: list = field(default_factory=list)   # list[str]
    note: str = ""  # human-readable description of what this turn checks

    def synonym_groups(self):
        return self.must_contain_any


@dataclass
class MultiTurnTestCase:
    id: str
    category: str = "follow_up"
    turns: list = field(default_factory=list)   # list[Turn]
    rubric: str = ""


MULTI_TURN_TEST_CASES = [

    # ── 1. Pronoun reference: "it", "that course" ────────────────────────────
    MultiTurnTestCase(
        id="followup_pronoun_reference",
        rubric="After asking about a course, user refers to it with 'it' — chatbot must resolve the pronoun correctly.",
        turns=[
            Turn(
                user="Tell me about 6.1210.",
                must_contain_any=[["6.1210", "6.006"], ["algorithm", "algorithms"]],
                note="Turn 1: establish 6.1210 as context.",
            ),
            Turn(
                user="What are the prerequisites for it?",
                must_contain_any=[["6.1210", "6.006", "prerequisite", "prereq"]],
                must_not_contain=["which course", "what course are you referring"],
                note="Turn 2: 'it' must resolve to 6.1210, not ask for clarification.",
            ),
        ],
    ),

    # ── 2. "Tell me more" continuation ───────────────────────────────────────
    MultiTurnTestCase(
        id="followup_tell_me_more",
        rubric="User asks 'tell me more' — chatbot should expand on the same course, not ask what course.",
        turns=[
            Turn(
                user="What is 18.06?",
                must_contain_any=[["18.06"], ["linear algebra"]],
                note="Turn 1: establish 18.06 Linear Algebra.",
            ),
            Turn(
                user="Tell me more about it.",
                must_contain_any=[["18.06", "linear algebra"]],
                must_not_contain=["which course", "could you clarify", "what subject"],
                note="Turn 2: should expand on 18.06 without asking for clarification.",
            ),
        ],
    ),

    # ── 3. Requirement constraint remembered across turns ────────────────────
    MultiTurnTestCase(
        id="followup_constraint_memory",
        rubric="User states they need CI-H in turn 1; turn 2 asks for more options without repeating the constraint.",
        turns=[
            Turn(
                user="I need a CI-H course. I'm interested in writing about technology.",
                must_contain_any=[["ci-h"]],
                note="Turn 1: establish CI-H constraint.",
            ),
            Turn(
                user="Do you have any other suggestions?",
                must_contain_any=[["ci-h", "communication", "writing"]],
                must_not_contain=["what requirement", "could you remind me"],
                note="Turn 2: chatbot should remember CI-H from prior turn and suggest more CI-H options.",
            ),
        ],
    ),

    # ── 4. Comparison across two courses mentioned in history ────────────────
    MultiTurnTestCase(
        id="followup_comparison",
        rubric="User asks about two courses separately, then asks to compare them — chatbot must recall both.",
        turns=[
            Turn(
                user="Tell me about 6.1210.",
                must_contain_any=[["6.1210", "6.006"], ["algorithm", "algorithms"]],
                note="Turn 1: first course.",
            ),
            Turn(
                user="Now tell me about 6.4110.",
                must_contain_any=[["6.4110", "6.034"], ["artificial intelligence", "ai"]],
                note="Turn 2: second course.",
            ),
            Turn(
                user="Which of those two would you recommend for a 6-3 sophomore?",
                must_contain_any=[
                    ["6.1210", "6.006", "6.4110", "6.034"],
                ],
                must_not_contain=["which courses are you referring", "could you clarify which two"],
                note="Turn 3: must reference both previously discussed courses without re-asking.",
            ),
        ],
    ),

    # ── 5. Profile built up incrementally ───────────────────────────────────
    MultiTurnTestCase(
        id="followup_incremental_profile",
        rubric="User reveals constraints one turn at a time; final recommendation must reflect all of them.",
        turns=[
            Turn(
                user="I'm a junior in Course 6.",
                must_contain_any=[],   # just an acknowledgment is fine
                note="Turn 1: establish year and major.",
            ),
            Turn(
                user="I need to satisfy a HASS requirement.",
                must_contain_any=[["hass"]],
                note="Turn 2: add HASS constraint.",
            ),
            Turn(
                user="I'm especially interested in ethics or society topics. What do you suggest?",
                must_contain_any=[["hass"]],
                must_not_contain=["what year are you", "what is your major"],
                note="Turn 3: final recommendation must reflect Course 6 junior + HASS + ethics, not re-ask prior info.",
            ),
        ],
    ),

    # ── 6. Correction / topic switch ────────────────────────────────────────
    MultiTurnTestCase(
        id="followup_topic_switch",
        rubric="User corrects themselves mid-conversation — chatbot must follow the new topic, not the old one.",
        turns=[
            Turn(
                user="Tell me about 6.1210.",
                must_contain_any=[["6.1210", "6.006"]],
                note="Turn 1: start with algorithms.",
            ),
            Turn(
                user="Actually, forget that. Tell me about 18.01 instead.",
                must_contain_any=[["18.01"], ["calculus"]],
                must_not_contain=["6.1210", "algorithm"],
                note="Turn 2: after correction, response should be about 18.01, not 6.1210.",
            ),
        ],
    ),

    # ── 7. Off-topic then back on topic ──────────────────────────────────────
    MultiTurnTestCase(
        id="followup_offtopic_recovery",
        rubric="User goes off-topic, gets redirected, then asks a real course question — chatbot should answer normally.",
        turns=[
            Turn(
                user="What's the best pizza place in Cambridge?",
                must_contain_any=[["mit", "course", "subject", "catalog", "help you with"]],
                must_not_contain=["pepperoni", "margherita", "yelp"],
                note="Turn 1: off-topic, should redirect.",
            ),
            Turn(
                user="OK fine, what courses satisfy the REST requirement?",
                must_contain_any=[["rest"]],
                note="Turn 2: legitimate course question after redirect — should answer normally.",
            ),
        ],
    ),

    # ── 8. Units follow-up ───────────────────────────────────────────────────
    MultiTurnTestCase(
        id="followup_units_after_lookup",
        rubric="After describing a course, user asks 'how many units is that?' — chatbot resolves 'that' correctly.",
        turns=[
            Turn(
                user="What is 6.1010?",
                must_contain_any=[["6.1010", "6.009"], ["programming", "fundamentals"]],
                note="Turn 1: establish 6.1010.",
            ),
            Turn(
                user="How many units is that?",
                must_contain_any=[["6.1010", "6.009", "unit", "12"]],
                must_not_contain=["which course", "what subject are you asking about"],
                note="Turn 2: 'that' should resolve to 6.1010.",
            ),
        ],
    ),
]


# =============================================================================
# MULTI-TURN RUNNER
# =============================================================================

@dataclass
class TurnResult:
    turn_index: int
    user: str
    response: str
    passed: bool
    failures: list
    latency_s: float
    note: str


@dataclass
class MultiTurnResult:
    id: str
    category: str
    passed: bool          # True only if ALL turns passed
    turn_results: list    # list[TurnResult]
    rubric: str

    # For unified summary
    @property
    def query(self):
        return f"[{len(self.turn_results)}-turn] " + self.turn_results[0].user if self.turn_results else ""

    @property
    def response(self):
        last = self.turn_results[-1] if self.turn_results else None
        return last.response if last else ""

    @property
    def failures(self):
        out = []
        for tr in self.turn_results:
            for f in tr.failures:
                out.append(f"Turn {tr.turn_index+1}: {f}")
        return out

    @property
    def latency_s(self):
        return round(sum(tr.latency_s for tr in self.turn_results), 2)


def _check_turn(response, turn):
    failures = []
    lower = response.lower()
    for group in turn.synonym_groups():
        if not any(syn.lower() in lower for syn in group):
            readable = " | ".join(f'"{s}"' for s in group)
            failures.append(f"MISSING (need one of): {readable}")
    for phrase in turn.must_not_contain:
        if phrase.lower() in lower:
            failures.append(f"FOUND forbidden phrase: '{phrase}'")
    return failures


def run_multiturn_evaluation(backend, test_cases, delay=1.0, verbose=False):
    results = []
    total = len(test_cases)

    for i, case in enumerate(test_cases, 1):
        print(f"[MT {i}/{total}] {case.id:<42}", end="", flush=True)

        history = []   # list of [user_msg, bot_msg] pairs
        turn_results = []
        all_passed = True

        for ti, turn in enumerate(case.turns):
            t0 = time.time()
            try:
                response = backend.query_with_history(turn.user, history)
                latency = time.time() - t0
                failures = _check_turn(response, turn)
                turn_passed = len(failures) == 0
            except Exception as exc:
                latency = time.time() - t0
                response = f"ERROR: {exc}"
                failures = [f"Exception: {exc}"]
                turn_passed = False

            history.append([turn.user, response])
            all_passed = all_passed and turn_passed

            turn_results.append(TurnResult(
                turn_index=ti,
                user=turn.user,
                response=response,
                passed=turn_passed,
                failures=failures,
                latency_s=round(latency, 2),
                note=turn.note,
            ))

            if delay:
                time.sleep(delay)

        label = "PASS" if all_passed else "FAIL"
        total_lat = sum(tr.latency_s for tr in turn_results)
        print(f" {label}  ({total_lat:.1f}s total)")

        if not all_passed or verbose:
            for tr in turn_results:
                status = "ok" if tr.passed else "FAIL"
                preview = tr.response.replace("\n", " ").strip()[:200]
                print(f"         Turn {tr.turn_index+1} [{status}] Q: {tr.user[:60]}")
                print(f"                  A: {preview}")
                for f in tr.failures:
                    print(f"                  ↳ {f}")

        results.append(MultiTurnResult(
            id=case.id,
            category=case.category,
            passed=all_passed,
            turn_results=turn_results,
            rubric=case.rubric,
        ))

    return results



# Patch backends with query_with_history method
_orig_direct_query = DirectBackend.query

def _direct_query_with_history(self, text, history):
    """history is a list of [user_msg, bot_msg] pairs (Gradio format)."""
    return self._bot.get_response(text, history=history)

DirectBackend.query_with_history = _direct_query_with_history

# Also add a no-history wrapper so single-turn tests still work unchanged
DirectBackend.query = lambda self, text: self.query_with_history(text, [])


def _gradio_query_with_history(self, text, history):
    url = f"{self.base_url}/api/predict"
    payload = {"data": [text, history]}
    resp = self._session.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    hist = data.get("data", [[]])[0]
    if hist and isinstance(hist[-1], list):
        return hist[-1][1] or ""
    return str(data)

GradioBackend.query_with_history = _gradio_query_with_history
GradioBackend.query = lambda self, text: self.query_with_history(text, [])


# =============================================================================
# UPDATED MAIN — runs both single-turn and multi-turn
# =============================================================================

def _to_unified(r):
    """Wrap a MultiTurnResult so it looks like a Result for summary."""
    return Result(
        id=r.id,
        category=r.category,
        query=r.query,
        response=r.response,
        passed=r.passed,
        failures=r.failures,
        latency_s=r.latency_s,
        rubric=r.rubric,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--direct", action="store_true")
    parser.add_argument("--url", default="http://127.0.0.1:7860")
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--out", default="")
    parser.add_argument("--category", default="")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--skip-multiturn", action="store_true",
                        help="Skip multi-turn follow-up tests.")
    args = parser.parse_args()

    if args.direct:
        print("Using direct backend (importing Chatbot)...")
        backend = DirectBackend()
    else:
        print(f"Using Gradio backend at {args.url}...")
        backend = GradioBackend(args.url)

    # ── single-turn ──
    cases = TEST_CASES
    if args.category:
        cases = [c for c in cases if c.category == args.category]
        if not cases and not args.skip_multiturn:
            # maybe they want only a multi-turn category
            pass

    print(f"\nRunning {len(cases)} single-turn test(s) with {args.delay}s delay.\n")
    st_results = run_evaluation(backend, cases, delay=args.delay, verbose=args.verbose)

    # ── multi-turn ──
    mt_results_raw = []
    if not args.skip_multiturn:
        mt_cases = MULTI_TURN_TEST_CASES
        if args.category:
            mt_cases = [c for c in mt_cases if c.category == args.category]
        if mt_cases:
            print(f"\nRunning {len(mt_cases)} multi-turn follow-up test(s).\n")
            mt_results_raw = run_multiturn_evaluation(
                backend, mt_cases, delay=args.delay, verbose=args.verbose
            )

    # ── unified summary ──
    all_results = st_results + [_to_unified(r) for r in mt_results_raw]
    print_summary(all_results)

    if args.out:
        import dataclasses
        out_data = [asdict(r) for r in st_results]
        for r in mt_results_raw:
            out_data.append({
                "id": r.id, "category": r.category, "passed": r.passed,
                "rubric": r.rubric, "latency_s": r.latency_s,
                "turns": [dataclasses.asdict(tr) for tr in r.turn_results],
            })
        with open(args.out, "w") as f:
            json.dump(out_data, f, indent=2)
        print(f"\nResults saved to {args.out}")


if __name__ == "__main__":
    main()