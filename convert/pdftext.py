"""What the glyphs on a page say, as a set of text repairs.

`convert/arabic.py` holds the repairs and knows nothing about PDFs, by design.
This is the one place that turns a pymupdf page into the character stream those
repairs need - and then, crucially, turns the result back into plain
text-to-text substitutions.

That last step is the whole point, and it was learned the hard way. The first
version of this applied the geometric repairs directly, in the reader's
geometry path and in the checker. It broke the hard gate: 100.0% -> 96.2% on
the regression set, one file's text score falling 0.998 -> 0.000, while
`page_score` did not move on a single file. The converter's output had not
changed at all. What changed was that the CHECKER now repaired the original and
the READER did not, because six of those eight files come through the tag route
- `/ActualText` strings, which carry no glyph boxes for the repair to read.

That is `PLAN.md` caveat 1 and the invariant at the top of `convert/arabic.py`:
a repair applied to one side and not the other is worse than no repair, because
our output stops matching the thing it is scored against and a genuine fix
reads as a regression.

So the repairs are derived from the glyphs ONCE, expressed as
{broken text -> repaired text} over whole words, and then applied as text by
whoever has text. Both sides derive the same map from the same file and apply
it to whatever they extracted, so neither can be repaired without the other.
"""
import difflib
import os
import re
import unicodedata

import pymupdf

from convert.arabic import _ZERO_W, repair_line

__all__ = ["fix_map", "apply_fixes", "line_items", "enabled"]


def enabled():
    """Is the geometric repair switched on? QIRTAS_ARABIC_FIX=off turns it off.

    It exists to measure the repair against its own absence on the same code,
    the same machine and the same renderer. Off is exactly the behaviour
    before the repair: `fix_map` returns nothing, and since the reader and the
    checker both get their repairs only from `fix_map`, they switch together -
    one side repaired and not the other is the failure this file was written
    around. On by default.
    """
    return os.environ.get("QIRTAS_ARABIC_FIX", "on").strip().lower()         not in ("off", "0", "false", "no")

# A fragment shorter than this is too common to replace safely: mapping ال onto
# لا everywhere would corrupt every definite article in the document. The
# geometric evidence is per-occurrence, but a text substitution is not, so the
# unit has to be big enough to be specific.
MIN_FRAGMENT = 3

# One word of context on each side of a change. Without it a neutral that
# crossed a word boundary produces a one-sided pair: the period that moves from
# the front of a line to the end gave `.طنجة،` -> `طنجة،`, which DELETES a
# character wherever it fires. With context the same change reads as a balanced
# replacement of two words by two words.
CONTEXT = 1


def line_items(line):
    """One rawdict line -> [(char, x0, x1)], repaired and ordered."""
    items = []
    for span in line.get("spans", []):
        for ch in span["chars"]:
            x0, _, x1, _ = ch["bbox"]
            items.append((ch["c"], x0, x1))
    return repair_line(items)


# A glyph layer has to be worth reading before its geometry can be trusted.
#
# The repair's whole premise is that a zero-width character is half of a
# ligature. On the six hard thesis files the glyphs barely decode at all -
# RESEARCH.md measured 0-8% recovered, the text really living in /ActualText -
# and their widths are therefore meaningless. Run on them, the repair "fixed"
# every definite article: الله came back لاله, القرشي came back لاقرشي, and a
# whole line's spaces collapsed. The hard gate fell to 0.944.
#
# Measured over the first pages of each file, non-space non-combining
# characters only:
#
#     z21358439        10,961 chars    2.14% zero width    healthy
#     z21011460        14,060 chars    1.56%               healthy
#     ödev              1,120 chars    0.00%               healthy
#     الفصل الخامس الثالث   11 chars   27.27%              degenerate
#     الفصل الخامس الأول    37 chars   67.57%              degenerate
#     مقدمة البحث          202 chars   96.04%              degenerate
#
# Two orders of magnitude between the two groups on both counts, so the
# thresholds sit in open space rather than being tuned to a boundary.
MAX_ZERO_WIDTH = 0.10
MIN_CHARS = 200


def trustworthy(doc):
    """Can this PDF's glyph widths be believed? -> (bool, share, chars)

    Computed from the file alone, so the reader and the checker reach the same
    verdict without either knowing what the other did.
    """
    total = zero = 0
    for page in list(doc)[:8]:
        for block in page.get_text("rawdict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    for ch in span["chars"]:
                        c = ch["c"]
                        if c.isspace() or unicodedata.combining(c):
                            continue
                        total += 1
                        x0, _, x1, _ = ch["bbox"]
                        if (x1 - x0) < _ZERO_W:
                            zero += 1
    if total < MIN_CHARS:
        return False, 0.0, total
    share = zero / total
    return share <= MAX_ZERO_WIDTH, share, total


def _line_pairs(page, all_lines=None):
    """-> [(stored line, repaired line)] for every line that CHANGED.

    Lines that did not change are appended to `all_lines` when one is given:
    they are the evidence that a fragment is not universally broken, which is
    what `fix_map` needs to decide whether a substitution is safe.
    """
    out = []
    for block in page.get_text("rawdict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            stored = "".join(c["c"] for s in line.get("spans", [])
                             for c in s["chars"])
            repaired = "".join(t[0] for t in line_items(line))
            if stored != repaired:
                out.append((stored, repaired))
            elif all_lines is not None:
                all_lines.append(stored)
    return out


def _fragments(stored, repaired):
    """Minimal word-level (before, after) pairs between two versions of a line.

    Words rather than characters, because a character-level diff of a line
    whose spaces moved produces fragments like " " -> "" that are meaningless
    out of context and dangerous to apply globally.
    """
    # split() rather than split(" "): runs of whitespace collapse, so a
    # fragment is a sequence of WORDS and never carries an empty token or a
    # stray leading space. apply_fixes matches it back against any spacing,
    # which is what makes this survive the two extraction modes disagreeing
    # about where spaces fall - PLAN.md caveat 1.
    a, b = stored.split(), repaired.split()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            continue
        i1, j1 = max(0, i1 - CONTEXT), max(0, j1 - CONTEXT)
        i2, j2 = min(len(a), i2 + CONTEXT), min(len(b), j2 + CONTEXT)
        before, after = " ".join(a[i1:i2]), " ".join(b[j1:j2])
        # Never yield a pair that removes text. The hard gate exists to stop
        # words going missing, and a repair that can delete one is a worse
        # failure than the defect it fixes. `.strip()`, not truthiness: the
        # first version of this test passed `' '` as a target and would have
        # deleted a whole heading.
        if not before.strip() or not after.strip():
            continue
        # A repair REORDERS characters; it never adds or removes one. Whole
        # lines always satisfy that - both repairs are permutations - but a
        # fragment of a line need not, because a character can move from one
        # end of the line to the other. The full stop stored at the front of a
        # line gave `.طنجة، المملكة` -> `طنجة، المملكة` and
        # `المملكة المغربية` -> `المملكة المغربية.`, a matched pair that only
        # balances if BOTH fire. Applied singly either one changes the text
        # length, and 72 characters went missing from one file that way.
        #
        # So the fragment must be a permutation on its own, ignoring spaces
        # (a displaced space is exactly what `ت بدأ` -> `تبدأ` removes). The
        # cost is that a punctuation mark stored at the wrong end of its line
        # stays there. That is the right side to err on: it is legible, and
        # losing a character is not.
        if sorted(before.split()) and \
                sorted(c for c in before if not c.isspace()) != \
                sorted(c for c in after if not c.isspace()):
            continue
        if before != after and len(before) >= MIN_FRAGMENT:
            yield before, after


def fix_map(path):
    """-> {broken fragment: repaired fragment} for this PDF.

    Derived from glyph geometry, so it says only what the page itself shows:
    which alef-lam pairs came out of a single ligature glyph, and which spaces
    and punctuation marks are stored away from where they are drawn.

    Two fragments are dropped rather than trusted:

      - one that maps to two different repairs. The same broken text is then
        genuinely ambiguous, and guessing is how a repair starts corrupting
        text instead of fixing it;
      - one whose `before` still appears somewhere the page did NOT repair.
        `المغربية` -> `المغربية.` is right on the line whose full stop was
        stored at the front, and wrong on every other line that ends the same
        word without one. A substitution is global even when the evidence for
        it is local, so it is only kept when every occurrence agrees.
    """
    if not enabled():
        return {}
    seen, bad = {}, set()
    stored_all, repaired_all = [], []
    with pymupdf.open(path) as d:
        ok, _, _ = trustworthy(d)
        if not ok:
            return {}
        for page in d:
            for stored, repaired in _line_pairs(page, all_lines=stored_all):
                repaired_all.append(repaired)
                for before, after in _fragments(stored, repaired):
                    if before in seen and seen[before] != after:
                        bad.add(before)
                    seen[before] = after

    # Everything the document holds, after the geometric pass. If a fragment
    # survives in there, some occurrence of it was left alone and the
    # substitution would not be safe to apply everywhere.
    settled = "\n".join(repaired_all) + "\n" + "\n".join(
        s for s in stored_all if s not in ("",))
    out = {}
    for k, v in seen.items():
        if k in bad:
            continue
        if _pattern(k).search(settled):
            continue
        out[k] = v
    return out


def _pattern(fragment):
    """A fragment as a regex: whole words, any whitespace between them.

    The two readers and the checker extract through different pymupdf modes,
    and those disagree about where spaces fall. Matching `\\s+` between words
    rather than a literal space is what lets one map repair all of them.
    """
    words = [re.escape(w) for w in fragment.split()]
    return re.compile(r"(?<!\S)" + r"\s+".join(words) + r"(?!\S)")


def _compile(fixes):
    return [(_pattern(k), v) for k, v in
            sorted(fixes.items(), key=lambda kv: len(kv[0]), reverse=True)]


def apply_fixes(text, fixes):
    """Apply a fix map to text, longest fragment first.

    Bounded by whitespace or the ends of the string, so a fragment can only
    replace whole words - `حامال` must not fire inside a longer word that
    happens to contain it.
    """
    if not text or not fixes:
        return text
    for pat, after in _compile(fixes):
        text = pat.sub(lambda _, a=after: a, text)
    return text
