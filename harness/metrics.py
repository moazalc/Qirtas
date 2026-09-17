"""Scoring for extracted text. No ground truth required."""
import re

AR_BASE   = lambda c: 0x0600 <= ord(c) <= 0x06FF
# U+FD3E/FD3F are ornate parentheses ﴾ ﴿ - legitimate Quranic quotation marks,
# not glyph corruption, despite living in the Presentation Forms A block.
LEGIT_PRES = {0xFD3E, 0xFD3F}
AR_PRESA  = lambda c: 0xFB50 <= ord(c) <= 0xFDFF and ord(c) not in LEGIT_PRES
AR_PRESB  = lambda c: 0xFE70 <= ord(c) <= 0xFEFF
PUA       = lambda c: 0xE000 <= ord(c) <= 0xF8FF   # private use (Wingdings etc.)

WORD_RE = re.compile(r"[؀-ۿ]{2,}")


def score(text: str) -> dict:
    t = text or ""
    base = sum(1 for c in t if AR_BASE(c))
    pres = sum(1 for c in t if AR_PRESA(c) or AR_PRESB(c))
    pua  = sum(1 for c in t if PUA(c))
    words = WORD_RE.findall(t)
    return {
        "chars": len(t.strip()),
        "arabic": base,
        "presentation_forms": pres,   # >0 means glyph corruption
        "pua": pua,                   # symbol-font junk
        "words": len(words),
        "uniq_words": len(set(words)),
    }


def recovery(s: dict, best_arabic: int) -> float:
    """Fraction of the best route's Arabic character count this route recovered."""
    return (s["arabic"] / best_arabic) if best_arabic else 0.0
