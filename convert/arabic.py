"""Repairs for Arabic text the source PDF hands over incorrectly.

Nothing here knows about PDFs or about Word. It takes text and returns text.

Both the converter and the checker import this, and they must: if only the
converter repaired its text, our output would no longer match the (still
mangled) original it is scored against, and fixing a real defect would show up
as the score getting worse. Correcting both sides compares what each document
MEANT to say, which is the only comparison worth making.
"""
import re

# لا is a ligature - one glyph in the PDF, mapped back to two letters by the
# font's ToUnicode table. Across much of this corpus that table lists them in
# the wrong order, so لا arrives as a standalone alef-lam.
#
# Safe to repair because a standalone ال is not Arabic: the definite article is
# a prefix and must attach to the word it defines. Bounded by non-word on both
# sides, an ال can only be a broken لا. Measured over 25 corpus files: 773
# occurrences, no legitimate ones.
LAM, ALEF = "ل", "ا"
_STANDALONE_AL = re.compile(rf"(?<!\w){ALEF}{LAM}(?!\w)")

# لا is not the only lam-alef ligature: لأ لإ لآ are ligatures too, and the same
# reversed ToUnicode turns them into أل إل آل. After the definite article that
# leaves األ اإل اآل - two alef forms side by side, which Arabic orthography
# does not allow - so those trigrams can only be the reversal.
#
# Deliberately anchored to the preceding ALEF. A bare أل is ordinary: ألف is a
# thousand, ألم is pain, ألوان is colours. Only alef + hamza-alef + lam is
# repaired, never أل on its own.
# Plain ALEF belongs in this class too: الاستثمار arrives as االستثمار, the
# same reversal with the plain-alef ligature. Two alefs in a row are no more
# possible than an alef beside a hamza-alef, so it is the same safe trigram.
HAMZA_ALEFS = "أإآا"
_AL_HAMZA = re.compile(rf"{ALEF}([{HAMZA_ALEFS}]){LAM}")


def repair_lam_alef(text):
    """Put reversed lam-alef ligatures back in their written order.

    Two cases, both unambiguous:
      ال standing alone     -> لا    (the definite article cannot stand alone)
      ا + أإآ + ل           -> ا ل + أإآ  (two alef forms cannot sit together)

    Prefixed forms (وال, بال, فال) are deliberately left alone: some are real
    words - بال is mind or condition, فأل is an omen - and they are an order of
    magnitude rarer, so repairing them would risk corrupting valid text to fix
    far fewer cases. See harness/test_arabic.py.
    """
    if not text:
        return text
    text = _STANDALONE_AL.sub(LAM + ALEF, text)
    return _AL_HAMZA.sub(rf"{ALEF}{LAM}\1", text)
