#!/usr/bin/env python3
"""Tests for text_score.

    python -m harness.test_text_score

PLAN.md item 1 claims text_score was "Validated: identical 100%". That
validation never used a document containing a REPEATED sentence, which is what
classical Arabic is full of - honorifics like صلى الله عليه وسلم, repeated
citations. On those, a document scored against itself did not reach 100%.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.compare import text_score

A, B, C, D = "A" * 14, "B" * 14, "C" * 14, "D" * 14
FAILED = []


def check(name, got, want, tol=1e-6):
    ok = abs(got - want) <= tol
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<46} got {got:.1%}  want {want:.1%}")
    if not ok:
        FAILED.append(name)


def main():
    print("identical documents must score 100%")
    check("no repeats", text_score(f"{A}.{B}.{C}.", f"{A}.{B}.{C}."), 1.0)
    # The regression: the same sentence three times, output identical to input.
    check("repeated sentence", text_score(f"{A}.{B}.{A}.{C}.{A}.",
                                          f"{A}.{B}.{A}.{C}.{A}."), 1.0)
    check("all sentences identical", text_score(f"{A}.{A}.{A}.{A}.",
                                                f"{A}.{A}.{A}.{A}."), 1.0)
    real = "قال صلى الله عليه وسلم كذا. وروى الراوي خبرا طويلا هنا. " \
           "وقال صلى الله عليه وسلم كذا. ثم ذكر المؤلف مسألة أخرى. " \
           "وقال صلى الله عليه وسلم كذا."
    check("repeated Arabic honorific", text_score(real, real), 1.0)

    print("\nreordering must still be caught")
    check("reversed order", text_score(f"{A}.{B}.{C}.{D}.", f"{D}.{C}.{B}.{A}."), 0.25)
    check("unrelated text", text_score(f"{A}.{B}.{C}.", f"{D}.{D}.{D}."), 0.0)
    # One sentence genuinely moved to the end: the other three still hold.
    check("one sentence moved", text_score(f"{A}.{B}.{C}.{D}.", f"{B}.{C}.{D}.{A}."), 0.75)

    print("\npartial output must score partially")
    check("half the document", text_score(f"{A}.{B}.{C}.{D}.", f"{A}.{B}."), 0.5)
    check("empty output", text_score(f"{A}.{B}.", ""), 0.0)
    check("empty original", text_score("", f"{A}.{B}."), 0.0)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
