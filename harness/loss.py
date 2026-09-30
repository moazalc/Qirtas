#!/usr/bin/env python3
"""The loss check: did we drop anything?

The only question here is whether text went missing. Order is deliberately
ignored - that is the look score's job. This is the hard gate: nothing ships
while a word is being lost.

    python -m harness.loss corpus/*.pdf
"""
import argparse, collections, difflib, os, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.compare import text_of, text_of_docx
from convert.v1 import convert

# Zero-width joiners count as space. z21850164 stores one (U+200C) between
# every pair of words instead of a space, so a sentence was one "word" and
# no word of it could be looked for on its own (FLAGS 29).
WS = re.compile(r"[\s\u200b-\u200d\u2060\ufeff]+")
TASHKEEL = re.compile(r"[ً-ْٰـ]")
BOLD, DIM, GRN, YEL, RED, OFF = "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m"


def norm(t, marks=True):
    t = WS.sub("", t or "")
    return t if marks else TASHKEEL.sub("", t)


SENT_SPLIT = re.compile(r"[.؟!؛:\n]+|،")
MIN_SENT = 40


def sentences(t):
    """Split into sentences, normalised so spacing differences don't matter."""
    return [s for s in (norm(x) for x in SENT_SPLIT.split(t or ""))
            if len(s) >= MIN_SENT]


# Text written in short pieces - a reference entry ("مطر، أميرة حلمي. (1994).
# جمهورية أفلاطون. دط. القاهرة: ..."), a contents line, a caption - cuts
# into pieces under MIN_SENT, and none of it was checked: a change dropped
# 93 words of `z18037898`'s references and the gate read 100% (FLAGS 34).
# Neighbouring short pieces are taken together, as the stretch of the
# original they make with the marks between them, once it reaches MIN_SENT.
SHORT_ON = os.environ.get("QIRTAS_GATE_SHORT", "1") != "0"


class Short(str):
    """A stretch of short pieces taken together (SHORT_ON)."""


# Such a stretch is asked for its words' letters only: numbers and marks in
# it are note numbers our Word file draws as notes ("(626)" beside a
# hadith, `z14065750`), numbers glued to a word (التالية1) or a formula's
# brackets - all read as lost the first time this ran, on 11 of 27 files.
# A dropped reference entry is its names and titles, and those are letters.
LETTER_WORD = re.compile(r"[ء-يA-Za-z]{3,}")
ALL_LETTERS = re.compile(r"[ء-يA-Za-z]+")


def letters_survive(raw, b_letters):
    return not letters_lacking(raw, b_letters)


def letters_lacking(raw, b_letters):
    """Every word of 3+ letters in ours - or, where the reference stores it
    backwards (`z22058810`: ةعماج for جامعة), turned round, as sentences are
    excused in judge(). A stretch with no such word - a broken title page's
    letters one by one, a formula in maths italic - has nothing to lose."""
    words = LETTER_WORD.findall(TASHKEEL.sub("", raw))

    def turned(w):
        return w[::-1] in b_letters or \
            (len(w) >= 5 and "".join(sorted(w)) in b_letters.bags)

    straight = [w for w in words if w in b_letters]
    back = [w for w in words if w not in b_letters and turned(w)]
    rest = [w for w in words if w not in b_letters and not turned(w)]
    if not rest:
        return []
    # A stretch the reference stores backwards, in whole or in part (a word
    # of it ours only turned round), cuts its pieces a letter off: بةيربخملا
    # for بروتوكولات and المخبرية, تيبوبنألابيكترلا for two words run
    # together; its alef with a hamza lands at the other end (أعرس for
    # أسرع, إراط for إطار) and its لا inside a word turns (تفصالي). There,
    # as the backfill asks (reader._backfill), a word is also ours in those
    # shapes. Never for a stretch the right way round: a dropped entry is its
    # words gone, none of them ours turned round.
    if not back:
        return rest

    def known(w):
        w = FOLD_ALEF.sub("ا", w)
        return w in b_letters.folded or w[::-1] in b_letters.folded or \
            (len(w) >= 5 and "".join(sorted(w)) in b_letters.bags)

    def shapes(w):
        w = FOLD_ALEF.sub("ا", w)
        yield w
        if len(w) >= 4:
            yield w[1:] + w[0]           # the alef at the other end
            yield w[-1] + w[:-1]
        if "لا" in w or "ال" in w:
            yield w.replace("لا", "\0").replace("ال", "لا").replace("\0", "ال")

    def loose(w):
        if any(known(s) for s in shapes(w)):
            return True
        return (len(w) >= 5 and (known(w[1:]) or known(w[:-1]))) or any(
            known(w[:k]) and known(w[k:]) for k in range(4, len(w) - 3))
    return [w for w in rest if not loose(w)]


FOLD_ALEF = re.compile("[آأإٱ]")


class Letters(str):
    """Ours as letter-words run together, and each word's letters sorted:
    a backwards word also has its لا turned (ايركسل for السكري,
    `z21145041`), so turned round it is still not ours. Five letters or
    more only - three-letter roots share their letters (علم, عمل)."""
    def __new__(cls, text):
        words = LETTER_WORD.findall(TASHKEEL.sub("", text))
        # Every letter, short words too: ما and يحتاج run together is how
        # the reference stores them backwards (جاتحيام).
        self = super().__new__(cls, "".join(ALL_LETTERS.findall(TASHKEEL.sub("", text))))
        self.folded = FOLD_ALEF.sub("ا", self)
        self.bags = {"".join(sorted(FOLD_ALEF.sub("ا", w))) for w in words if len(w) >= 5}
        return self


def sentence_pairs(t):
    """(normalised, as written) per sentence. The raw form keeps the spaces,
    which is the only place word boundaries still exist after norm()."""
    t = t or ""
    out, run = [], None          # run: (start, end) of short pieces so far
    at = 0
    for m in list(SENT_SPLIT.finditer(t)) + [None]:
        end = m.start() if m else len(t)
        piece = t[at:end]
        n = norm(piece)
        if len(n) >= MIN_SENT:
            out.append((n, piece))
            run = None
        elif SHORT_ON and n:
            run = (run[0] if run else at, end)
            if len(norm(t[run[0]:run[1]])) >= MIN_SENT:
                out.append((norm(t[run[0]:run[1]]), Short(t[run[0]:run[1]])))
                run = None
        if m:
            at = m.end()
    return out


MIN_WORD = 3


def words_survive(raw, b, marks=True):
    """Is every substantial word of this sentence somewhere in the output?

    This is what "order is deliberately ignored" has to mean in practice. A
    sentence found as one contiguous run is present; a sentence whose words all
    survive but changed places is ALSO present, because the gate's question is
    whether text was dropped, not where it ended up. Putting it anywhere else
    is the page score's business.

    Words under three characters are skipped. They turn up by coincidence far
    too easily to be evidence in either direction, and requiring them would
    reintroduce the false alarms this exists to remove.
    """
    words = [w for w in (norm(x, marks) for x in WS.split(raw))
             if len(w) >= MIN_WORD]
    if not words:
        return False
    return all(w in b for w in words)


def coverage(orig, out, marks=True):
    """Is every sentence of the original present somewhere in our output?

    Sentences, not characters or fixed-size chunks. Characters were too lenient
    (a dropped sentence shares its letters with the rest of the text). Fixed
    chunks were too harsh: a chunk straddling a point where order differs - a
    page number moving, say - is reported missing though both halves are there.
    A sentence is a real unit that reordering keeps intact.

    A sentence not found whole is retried with 8% trimmed off each end, so a
    page number glued onto its start does not condemn it.
    """
    b = norm(out, marks)
    b_letters = Letters(out)
    pairs = sentence_pairs(orig)
    if not pairs:
        return 1.0, []
    gone = []
    for s, raw in pairs:
        if s in b:
            continue
        if isinstance(raw, Short):
            if not letters_survive(raw, b_letters):
                gone.append(s)
            continue
        pad = max(2, len(s) * 8 // 100)
        if s[pad:-pad] in b:
            continue
        # Not found as one run. Before calling it lost, check whether its words
        # are simply somewhere else - see words_survive(). Three holdout files
        # were being reported as losing text when between them they had lost a
        # two-character fragment.
        if words_survive(raw, b, marks):
            continue
        gone.append(s)
    return 1 - len(gone) / len(pairs), gone


# A flagged sentence is judged by the page only where the OCR plainly read
# that part of it: at least this share of the sentence's other words.
PAGE_READ = 0.5
# Share of a backwards-stored sentence's words that must be in ours turned
# round before the page is asked about it.
TURNED = 0.8
# A word in one script: Arabic letters, or Latin letters and digits.
SCRIPTS = re.compile(r"[\u0621-\u064A]+|[A-Za-z0-9]+")
ARABIC_RUN = re.compile(r"[\u0621-\u064A]+")


def _turn_round(w):
    """A backwards-stored word the way round ours has it. Where English is
    glued to it, only the Arabic is turned: the reference's `\u0629\u0633\u064A\u0627\u0642\u0645(ELISA)`
    is \u0645\u0642\u0627\u064A\u0633\u0629 and ELISA in ours, not ASILE (`z21145041` - once brackets were
    read where the page draws them, the page's own `\u0645\u0642\u0627\u064A\u0633\u0629(ELISA)`, with no
    space, read as lost)."""
    if ARABIC_RUN.search(w) and re.search(r"[A-Za-z]", w):
        return ARABIC_RUN.sub(lambda m: m.group(0)[::-1], w)
    return w[::-1]


LETTERS = re.compile(r"[^ء-يA-Za-z0-9]+")
RUN_AT = 0.8         # share of a backwards sentence's words found together


def _together(raw, ours_bare):
    """Are a backwards-stored sentence's words in ours close together - each
    as it stands or turned round - not only each somewhere? Each somewhere
    was too little: a thesis's common words are everywhere, and a paragraph
    cut out of ours on purpose was still excused (`z21145041`, 2026-09-28).
    Not the sentence turned whole: the reference turns some of its lines and
    not others (وقد أفيد بأن مساحة تحت منحنى التشغيل لقبلتسملل). `raw`: the
    sentence as written, spaces kept."""
    # Split at punctuation too: (غلم/درتليسي)لوبلا is three words.
    words = [w for w in LETTERS.split(TASHKEEL.sub("", raw)) if len(w) >= MIN_WORD]
    if len(words) < 3:
        return True                   # too short to ask; as before
    span = 2 * sum(len(w) for w in words)
    places = []
    for w in words:
        at = set()
        t = _turn_round(w)
        # A stray letter off either end, as in judge() - only where four
        # letters are left: الب and غال are everywhere, and filled the
        # places looked at before the right one was reached.
        for f in {w, t} | {f for f in (w[1:], w[:-1], t[1:], t[:-1])
                           if len(f) >= 4}:
            k = ours_bare.find(f)
            while k >= 0 and len(at) < 2000:
                at.add(k)
                k = ours_bare.find(f, k + 1)
        places.append(sorted(at))
    import bisect
    for p in {x for at in places for x in at}:
        got = 0
        for at in places:
            i = bisect.bisect_left(at, p - span)
            if i < len(at) and at[i] <= p + span:
                got += 1
        if got >= RUN_AT * len(words):
            return True
    return False


def judge(pdf, out, marks=True):
    """Nothing lost, with the original's page as the tie-breaker (FLAGS 25).

    The reference is the PDF's hidden text, and where that text is wrong a
    sentence we wrote right reads as lost: `z21763864` has الٕ with no alef
    where the page shows الإ, and fell to 81.5% the day we stopped writing a
    misspelled second copy that matched it. So each sentence coverage()
    flags is taken to its page, read by OCR, and the words it says we lack
    are looked for there. If the page shows any of them, the loss is real.
    If it shows none - while plainly reading the rest of the sentence - the
    reference was wrong there: the sentence is excused, and listed.

    -> (kept, kept before the page was asked, [excused sentence])
    """
    import hashlib
    import pymupdf
    from convert.witness import _norm, _ocr
    from harness.compare import text_of
    pages = text_of(pdf, pages=True)
    orig = "\n".join(pages)
    cov, gone = coverage(orig, out, marks)
    if not gone:
        return cov, cov, []
    pairs = sentence_pairs(orig)
    raw_of = dict(pairs)
    by_page = [norm(t, marks) for t in pages]
    with open(pdf, "rb") as f:
        key = hashlib.sha1(f.read()).hexdigest()[:16]
    doc = pymupdf.open(pdf)
    ours = {_norm(w) for w in WS.split(out)}
    # Ours with the spaces out: a word the reference glues to the next one
    # (هداعايلع, الاصليan) is there when ours keeps them apart. The gate
    # ignores spacing everywhere else (norm) - here too.
    ours_run = "".join(_norm(w) for w in WS.split(out))
    ours_bare = LETTERS.sub("", TASHKEEL.sub("", out))
    b_letters = Letters(out)
    excused = []
    for s in gone:
        page = next((i for i, t in enumerate(by_page) if s[5:45] in t), None)
        if page is None:
            continue
        seen = _ocr(doc, [page], Path("out/work/truth/cache") / key).get(page)
        if not seen:
            continue
        seq = [w for w, _ in seen]
        joined = "".join(seq)
        # Whether the page shows a word we lack is asked of whole words: a
        # word the OCR cut in two is there as two or three side by side.
        # Searching all the page's words run together found الطرقص in الطرق
        # followed by صيانة, and held a sentence we wrote right as lost
        # (z20397518). How well the OCR read the rest stays the looser
        # question - on a page read badly (z21763864) it cuts words anywhere.
        shown = set(seq) | {"".join(seq[i:i + k]) for k in (2, 3)
                            for i in range(len(seq) - k + 1)}
        raw = raw_of.get(s, "")
        if isinstance(raw, Short):
            # A stretch of short pieces, asked the same way by its letters:
            # the words ours lacks (letters_lacking) against the page. The
            # reference's أعرس for أسرع is not what the page shows, while the
            # page plainly reads the rest - either way round, as a backwards
            # stretch's other words are stored.
            lack = letters_lacking(raw, b_letters)
            rest = [w for w in LETTER_WORD.findall(TASHKEEL.sub("", raw)) if w not in lack]

            def seen_on_page(w):
                return any(f in shown or f in joined for f in (_norm(w), _norm(w[::-1])))
            if rest and sum(1 for w in rest if seen_on_page(w)) >= PAGE_READ * len(rest) \
                    and not any(_norm(w) in shown for w in lack):
                excused.append(s)
            continue
        words = [w for w in (_norm(x) for x in WS.split(raw_of.get(s, "")))
                 if len(w) >= MIN_WORD]
        # A word as written, cut where marks stand inside it (see flip).
        PUNCT_PARTS = {_norm(x): ARABIC_RUN.findall(x)
                       for x in WS.split(raw_of.get(s, ""))
                       if len(ARABIC_RUN.findall(x)) > 1}

        def there(w):
            if w in ours or w in ours_run:
                return True
            # Glued where Arabic meets English (الاصلي“an): both halves.
            parts = SCRIPTS.findall(w)
            return len(parts) > 1 and all(p in ours or p in ours_run for p in parts)

        def forms(f):
            # A backwards-stored word carries a stray letter or digit of its
            # neighbour at one end (هباصاداهجا0, اهيجولويبلا, تراطإ for إطار).
            return [f] + ([f[1:], f[:-1]] if len(f) >= 4 else [])

        def turned_round(f):
            return f in split or any(there(g) for g in forms(f))

        def on_page(f):
            # Asked of the page the same way: the OCR reads إطار, not the
            # stray-lettered اطارت (`z21145041`, once our backwards second
            # copy of its paragraph was gone).
            return all(any(g in shown or g in joined for g in forms(p))
                       for p in split.get(f, [f]))

        split = {}

        def flip(w):
            # Words run together behind a slash or bracket, each backwards:
            # (غلم/درتليسي)لوبلا is ملغ, ديسيلتر, البول - turned whole, the
            # three come out in the wrong order. Each turned in place - only
            # where the reference itself has the marks between them.
            f = _turn_round(w)
            if turned_round(f):
                return f
            parts = [_norm(x)[::-1] for x in PUNCT_PARTS.get(w, ())]
            if len(parts) > 1 and all(turned_round(x) for x in parts):
                split["".join(parts)] = parts
                return "".join(parts)
            return f

        lacking = [w for w in words if not there(w)]
        present = [w for w in words if w not in lacking]
        # The reference stores the sentence backwards, letter by letter
        # (يمازلإلا for الإلزامي; z22058810, z21145041), so none of its words
        # match ours and nothing is left to judge the page by. Turned round,
        # nearly every word is in ours - a number, an English term or two
        # words run together aside: excused if the page shows them that way
        # and shows none of the rest. A sentence we dropped is in ours
        # neither way round.
        flipped = [flip(w) for w in lacking]
        turned = [f for f in flipped if turned_round(f)]
        if lacking and len(turned) >= TURNED * len(lacking):
            rest = [w for w, f in zip(lacking, flipped) if f not in turned]
            if sum(1 for f in turned if on_page(f)) \
                    >= PAGE_READ * len(turned) \
                    and not any(w in shown for w in rest) \
                    and _together(raw_of.get(s, ""), ours_bare):
                excused.append(s)
            continue
        if not lacking:
            # Every word there and the sentence still not found whole: the
            # difference is punctuation - الأصلي: “an where the reference has
            # الأصلي“an (z21850164). Excused only if the short words are
            # there as well; a dropped في or لا is a real loss.
            every = [w for w in (_norm(x) for x in WS.split(raw_of.get(s, ""))) if w]
            if every and all(there(w) for w in every):
                excused.append(s)
            continue
        if not present:
            continue
        read = sum(1 for w in present if w in shown or w in joined)
        if read < PAGE_READ * len(present):
            continue                  # the OCR did not read this part well
        if any(w in shown for w in lacking):
            continue                  # the page shows what we lack: a loss
        excused.append(s)
    kept = 1 - (len(gone) - len(excused)) / max(1, len(pairs))
    return kept, cov, excused


def missing_chunks(orig, out, marks=True, limit=8):
    """The actual runs of text that were dropped, so we can see WHAT is gone."""
    a, b = norm(orig, marks), norm(out, marks)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    gone = [a[i1:i2] for tag, i1, i2, _, _ in sm.get_opcodes()
            if tag in ("delete", "replace") and i2 - i1 >= 4]
    gone.sort(key=len, reverse=True)
    return gone[:limit], sum(len(g) for g in gone)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdfs", nargs="+")
    ap.add_argument("--work", default="out/work/loss")
    ap.add_argument("--show", type=int, default=3, help="missing chunks to print per file")
    a = ap.parse_args()

    worst = 1.0
    print(f"{DIM}{'file':<42}{'kept':>8}{'missing chars':>15}{OFF}")
    for pdf in a.pdfs:
        docx = Path(a.work) / (Path(pdf).stem[:40] + ".docx")
        try:
            convert(pdf, docx)
            orig, out = text_of(pdf), text_of_docx(docx)
        except Exception as e:
            print(f"{Path(pdf).name[:40]:<42} {RED}FAILED{OFF} {e}"[:140])
            continue
        cov, gone = coverage(orig, out)
        lost = sum(len(g) for g in gone)
        worst = min(worst, cov)
        col = GRN if cov >= 0.999 else (YEL if cov >= 0.99 else RED)
        print(f"{Path(pdf).name[:40]:<42}{col}{cov:>8.2%}{OFF}{lost:>15,}")
        for c in gone[:a.show]:
            print(f"    {DIM}missing:{OFF} {c[:78]}")

    print(f"\n{BOLD}worst file: {GRN if worst>=0.999 else RED}{worst:.2%}{OFF}")
    sys.exit(0 if worst >= 0.999 else 1)


if __name__ == "__main__":
    main()
