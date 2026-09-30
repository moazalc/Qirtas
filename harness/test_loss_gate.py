#!/usr/bin/env python3
"""Tests for the hard gate: it must catch loss and ignore order.

    python -m harness.test_loss_gate

loss.py's docstring has always said "order is deliberately ignored - that is
the look score's job". The implementation did not do that. It looked for each
sentence as one contiguous run (`s in b`), so moving a phrase within a sentence
made the whole sentence read as lost.

That is not hypothetical. It is what three holdout files were reporting:

    z21762343.pdf  gate said 95.83% kept - the worst file in the corpus.
                   Every word present; a French keyword list on the title page
                   had two phrases swapped. Nothing was lost at all. With only
                   24 scoreable sentences, one false flag cost 4.17%.
    z20251974.pdf  gate said 99.19%. A two-character fragment.
    z21312494.pdf  gate said 99.80%. This one is real - nine words genuinely
                   absent - and it was the best-looking of the three.

So the file that looked worst had lost nothing and the file that looked best
was the only one actually dropping text. A gate that inverts the ranking of its
own failures cannot be used to decide what to fix.

Diagnosing it took three instruments, the first two of which failed the same
way - they measured contiguity and called it presence. Fixed-size chunks
straddle the seam where order changed; sliding n-grams lose N-1 grams per seam,
which on a short sentence is a third of them. Word presence has no such
dependence, which is why the fix is built on it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.loss import coverage

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<54} got {got!r}  want {want!r}")
    if not ok:
        FAILED.append(name)


# Long enough to clear MIN_SENT (40 characters once spaces are stripped).
A = "دور الفهم القرائي في تطوير التفكير الناقد لدى تلاميذ المرحلة الابتدائية"
B = "العدالة التعليمية وتكافؤ الفرص في العراق التحديات وآليات المعالجة الشاملة"


def main():
    print("text that is all present must score 100%, however it is arranged")
    check("identical", coverage(A, A)[0], 1.0)
    # The real z21762343 case: same words, two phrases swapped.
    swapped = " ".join(A.split()[:4][::-1] + A.split()[4:])
    check("phrases swapped inside a sentence", coverage(A, swapped)[0], 1.0)
    check("whole sentences in a different order",
          coverage(f"{A}. {B}", f"{B}. {A}")[0], 1.0)

    print("\nand text that is genuinely gone must still be caught")
    check("one sentence of two deleted", coverage(f"{A}. {B}", A)[0], 0.5)
    check("everything deleted", coverage(A, "")[0], 0.0)

    print("\na sentence missing a word is loss, not reordering")
    # This is the z21312494 case: most of the sentence survives, one word does
    # not. The lenient path must not wave it through.
    dropped = A.replace(" الابتدائية", "")
    check("one word removed", coverage(A, dropped)[0], 0.0)
    two_gone = B.replace(" العراق", "").replace(" الشاملة", "")
    check("two words removed", coverage(B, two_gone)[0], 0.0)

    print("\nand the gate must not be fooled by the words turning up elsewhere")
    # Every word of A exists in the output, but scattered through other text
    # rather than as a sentence. That IS acceptable - the gate's question is
    # whether text survived, not where it went. Stated as a test so the
    # leniency is deliberate and visible rather than accidental.
    scattered = " ... ".join(A.split())
    check("words present but spread out", coverage(A, scattered)[0], 1.0)

    print("\na sentence the reference stores backwards (judge, 2026-09-28)")
    from harness.loss import _together, LETTERS, TASHKEEL
    # `z21145041`: excused only where its words, turned round, stand
    # together in ours - a thesis's common words are everywhere else.
    ref = "تراطإ ةحورطألا هذه مدختساًً يليلحتاًً يدصراًً"
    ours = ("في الفصل الثالث تستخدم هذه الأطروحة إطاراً تحليلياً رصدياً "
            "لمحاكاة ظروف دراسة مستقبلية")
    elsewhere = ("الأطروحة في مقدمتها. ثم إطار عام. " + "كلام آخر " * 40 +
                 "وتستخدم الدراسة منهجا تحليليا. " + "كلام آخر " * 40 +
                 "هذه نتائج رصدية.")

    def bare(t):
        return LETTERS.sub("", TASHKEEL.sub("", t))
    check("in ours, together: excused", _together(ref, bare(ours)), True)
    check("its words only scattered through ours: not",
          _together(ref, bare(elsewhere)), False)

    print("\ntext in short pieces is checked too (FLAGS 34, 2026-09-30)")
    # A reference list: every piece under 40 letters, so none was checked,
    # and a change dropped 93 words of `z18037898`'s and scored 100%.
    refs = ("مطر، أميرة حلمي. (1994). جمهورية أفلاطون. دط. القاهرة: الهيئة "
            "المصرية العامة للتأليف والنشر.\nالنووي، يحيى بن شرف. (1991). "
            "روضة الطالبين. ط 3. بيروت: المكتب الإسلامي.")
    first, second = refs.split("\n")
    check("all there", coverage(refs, refs)[0], 1.0)
    check("an entry dropped is caught", coverage(refs, first)[0] < 1.0, True)
    check("the old gate saw nothing to check", len(__import__(
        "harness.loss", fromlist=["x"]).sentences(refs)), 0)
    # Its numbers are note numbers ours draws as notes, glued numbers, or
    # a formula's marks: asked by letters only.
    check("a note number our Word file draws as a note",
          coverage("قال رسول الله (\n626\n) . وعن جبير بن مطعم قال سمعت",
                   "قال رسول الله . وعن جبير بن مطعم قال سمعت")[0], 1.0)
    # The reference storing a word backwards, its لا turned too.
    check("backwards, لا turned: السكري as ايركسل",
          coverage("مرضى ايركسل. في هذه الدراسة التطبيقية المهمة جدا",
                   "مرضى السكري في هذه الدراسة التطبيقية المهمة جدا")[0], 1.0)
    check("nothing but letters one by one: nothing to lose",
          coverage("\n".join(["1440 هـ - 2018م."] + [x + "." for x in
                   "خ بن مخ ة لإ تم خ مح غ لآ لج ر لح 54 خ بن مخ".split()]),
                   "")[0], 1.0)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
