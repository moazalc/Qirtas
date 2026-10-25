#!/usr/bin/env python3
"""A small window: pick a PDF, get the Word file - the same conversion as
`python -m convert`, for a person who does not use a command line.

    python -m convert.app

TASKS item 2 (Moaz, 22 Oct). It says the same things the command says, in
the same order: a scan is refused (convert/scan.py); fonts the PDF uses that
this computer lacks are named, with a choice to install them and look again
or convert without them (convert/fonts.py); after converting, the pages whose
numbers the PDF stores one way and shows another (convert/digits.py).

Tk lays a line out left to right as a whole, so a line mixing Arabic and
English comes out scrambled, and so does an Arabic line with "..." or a full
stop in it: every Arabic string here is Arabic words only, with the English
on a line of its own.

Word renders every attempt (convert/fit.py) over COM, and a Word instance
belongs to the thread that started it (harness/word.py keeps one per
process), so every conversion runs on one worker thread that lives as long
as the window.
"""
import os
import queue
import sys
import tempfile
import threading
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

TITLE = "Qirtas - قرطاس"
FONT = ("Segoe UI", 11)
SMALL = ("Segoe UI", 10)
BIG = ("Segoe UI", 14, "bold")
TITLE_FONT = ("Segoe UI", 24, "bold")
# Moaz's palette (25 Oct): deep green, cream text, gold.
C = {"bg": "#07281e", "card": "#0d3127", "muted": "#12352a",
     "secondary": "#12382d", "accent": "#163e31", "fg": "#f3ead9",
     "muted_fg": "#cdc3af", "primary": "#d8b66d", "ring": "#b89a5a",
     "destructive": "#f47c6e", "success": "#7bcc98"}


def _out_path(pdf):
    """Beside the PDF, with its name; a number added rather than writing
    over a Word file that is already there."""
    pdf = Path(pdf)
    out = pdf.with_suffix(".docx")
    n = 2
    while out.exists():
        out = pdf.with_name(f"{pdf.stem} ({n}).docx")
        n += 1
    return out


class Worker(threading.Thread):
    """Runs conversions one at a time; reports back through `events`."""

    def __init__(self, events):
        super().__init__(daemon=True)
        self.jobs = queue.Queue()
        self.events = events
        self.answer = queue.Queue()     # the window's reply about fonts

    def run(self):
        while True:
            pdf, docx = self.jobs.get()
            try:
                self._convert(Path(pdf), Path(docx))
            except Exception as e:      # said to the person, kept for us
                self.events.put(("failed", f"{e}\n\n{traceback.format_exc(limit=3)}"))

    def say(self, *event):
        self.events.put(event)

    def _convert(self, pdf, docx):
        from convert import digits, fonts
        from convert.scan import Refused, refuse_scans
        self.say("status", "يفحص الملف\nChecking the file ...")
        try:
            refuse_scans(str(pdf))
        except Refused as e:
            self.say("refused", str(e))
            return
        left = []
        while True:
            found = fonts.missing(pdf)
            if not found:
                break
            self.say("status", "يفحص الخطوط\nChecking the fonts ...")
            fonts.judge(pdf, found)
            if all(m.only_style for m in found):
                left = found
                break
            self.say("fonts", fonts.message(found))
            if self.answer.get() == "go":
                left = found
                break
            fonts.rescan()
        self.say("status", "جار التحويل وقد يستغرق دقيقة أو دقيقتين لملف طويل\n"
                           "Converting - a minute or two for a long file.")
        from convert.fit import convert
        from harness.word import docx_to_pdf
        import shutil
        media = docx.parent / "media"
        made = [p for p in (media, media / docx.stem) if not p.exists()]
        with tempfile.TemporaryDirectory(prefix="qirtas-pages-") as work:
            convert(str(pdf), str(docx), render=lambda d: docx_to_pdf(d, work))
        for p in reversed(made):
            if p == media / docx.stem:
                shutil.rmtree(p, ignore_errors=True)
            elif p.exists() and not any(p.iterdir()):
                p.rmdir()
        notes = []
        for m in left:
            if m.wrong:
                notes.append(f"The text in {m.name}{' ' + m.style if m.style else ''}"
                             f"{fonts._pages(m.pages)} came out wrong. Install that "
                             f"font and convert again.")
        if digits.ON:
            from convert.glyphs import repaired
            note = digits.message(digits.scan(repaired(pdf)))
            if note:
                notes.append(note)
        self.say("done", str(docx), "\n\n".join(notes))


class Button(tk.Label):
    """A flat button in the palette's colours. Tk's own button keeps the
    system's grey on Windows whatever colour it is given."""

    def __init__(self, master, text, command, primary=False, **kw):
        self.colours = ((C["primary"], C["bg"], C["ring"]) if primary else
                        (C["secondary"], C["fg"], C["accent"]))
        super().__init__(master, text=text, cursor="hand2", padx=22, pady=8,
                         justify="center", font=kw.pop("font", FONT),
                         highlightthickness=1, takefocus=1, **kw)
        self.command, self.enabled = command, True
        self._paint()
        self.bind("<Button-1>", lambda e: self._press())
        self.bind("<Return>", lambda e: self._press())
        self.bind("<space>", lambda e: self._press())
        self.bind("<Enter>", lambda e: self._paint(hover=True))
        self.bind("<Leave>", lambda e: self._paint())

    def _paint(self, hover=False):
        bg, fg, over = self.colours
        if not self.enabled:
            bg, fg = C["muted"], C["muted_fg"]
        elif hover:
            bg = over
        self.config(bg=bg, fg=fg, highlightbackground=bg,
                    highlightcolor=C["ring"],
                    cursor="hand2" if self.enabled else "arrow")

    def _press(self):
        if self.enabled:
            self.command()

    def set_enabled(self, on):
        self.enabled = on
        self._paint()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(TITLE)
        self.geometry("600x540")
        self.minsize(520, 520)
        self.configure(bg=C["bg"])
        self.events = queue.Queue()
        self.worker = Worker(self.events)
        self.worker.start()
        self.pdf = None
        self.docx = None

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Gold.Horizontal.TProgressbar", troughcolor=C["muted"],
                        background=C["primary"], bordercolor=C["card"],
                        lightcolor=C["primary"], darkcolor=C["primary"], thickness=6)

        head = tk.Frame(self, bg=C["bg"])
        head.pack(fill="x", padx=28, pady=(22, 10))
        tk.Label(head, text="قرطاس", font=TITLE_FONT, bg=C["bg"], fg=C["primary"],
                 anchor="e").pack(fill="x")
        tk.Label(head, text="حوّل ملف بي دي إف عربيًا إلى ملف وورد يمكن تعديله",
                 font=FONT, bg=C["bg"], fg=C["fg"], anchor="e").pack(fill="x")
        tk.Label(head, text="Turn an Arabic PDF back into a Word file you can edit",
                 font=SMALL, bg=C["bg"], fg=C["muted_fg"], anchor="e").pack(fill="x")

        card = tk.Frame(self, bg=C["card"], highlightthickness=1,
                        highlightbackground=C["secondary"])
        card.pack(fill="both", expand=True, padx=28, pady=(6, 24))
        inner = tk.Frame(card, bg=C["card"])
        inner.pack(fill="both", expand=True, padx=22, pady=20)

        row = tk.Frame(inner, bg=C["card"])
        row.pack(fill="x")
        self.pick = Button(row, "اختر الملف\nChoose a PDF", self.choose)
        self.pick.pack(side="right")
        self.name = tk.Label(row, text="لم يُختر ملف بعد\nNo file chosen yet",
                             font=FONT, bg=C["card"], fg=C["muted_fg"],
                             anchor="e", justify="right")
        self.name.pack(side="right", fill="x", expand=True, padx=(0, 14))

        self.go = Button(inner, "حوّل\nConvert", self.convert, primary=True,
                         font=BIG)
        self.go.pack(pady=(22, 16))
        self.go.set_enabled(False)

        self.bar = ttk.Progressbar(inner, mode="indeterminate",
                                   style="Gold.Horizontal.TProgressbar")
        self.status = tk.Label(inner, text="", font=FONT, bg=C["card"], fg=C["fg"],
                               anchor="e", justify="right", wraplength=480)
        self.status.pack(fill="x", pady=(10, 0))
        self.open = Button(inner, "افتح الملف\nOpen the Word file", self.open_docx)
        self.after(150, self.poll)

    def choose(self):
        path = filedialog.askopenfilename(
            title="Choose a PDF",
            filetypes=[("PDF", "*.pdf"), ("All files", "*.*")])
        if not path:
            return
        self.pdf = Path(path)
        self.name.config(text=self.pdf.name, fg=C["fg"])
        self.go.set_enabled(True)
        self.say("")
        self.open.pack_forget()

    def convert(self):
        if not self.pdf:
            return
        self.docx = _out_path(self.pdf)
        self.busy(True)
        self.worker.jobs.put((str(self.pdf), str(self.docx)))

    def busy(self, on):
        self.go.set_enabled(not on)
        self.pick.set_enabled(not on)
        if on:
            self.open.pack_forget()
            self.bar.pack(fill="x", before=self.status)
            self.bar.start(12)
        else:
            self.bar.stop()
            self.bar.pack_forget()

    def say(self, text, colour="fg"):
        self.status.config(text=text, fg=C[colour])

    def poll(self):
        try:
            while True:
                self.handle(*self.events.get_nowait())
        except queue.Empty:
            pass
        self.after(150, self.poll)

    def handle(self, kind, *args):
        if kind == "status":
            self.say(args[0])
        elif kind == "refused":
            self.busy(False)
            self.say("لا يمكن تحويل هذا الملف\nThis file cannot be converted.",
                     "destructive")
            messagebox.showwarning(TITLE, args[0])
        elif kind == "fonts":
            again = messagebox.askyesno(
                TITLE, args[0] + "\n\n"
                "Yes: I have installed them - look again.\n"
                "No: convert without them.")
            self.worker.answer.put("again" if again else "go")
        elif kind == "done":
            self.busy(False)
            self.docx = Path(args[0])
            self.say(f"تم\nDone: {self.docx.name}", "success")
            self.open.pack(pady=(14, 0))
            if args[1]:
                messagebox.showinfo(TITLE, args[1])
        elif kind == "failed":
            self.busy(False)
            self.say("حدث خطأ\nSomething went wrong.", "destructive")
            messagebox.showerror(TITLE, args[0])

    def open_docx(self):
        if self.docx and self.docx.exists():
            os.startfile(str(self.docx))


def selftest(pdf, report):
    """`--selftest in.pdf report.txt`: one conversion without the window,
    every message written to `report` - to check a frozen build works
    without anyone clicking (the installed program has no console)."""
    events = queue.Queue()
    w = Worker(events)
    w.start()
    w.jobs.put((pdf, str(_out_path(pdf))))
    with open(report, "w", encoding="utf-8") as out:
        while True:
            kind, *args = events.get()
            out.write(f"{kind}: {args}\n")
            out.flush()
            if kind == "fonts":
                w.answer.put("go")
            if kind in ("done", "refused", "failed"):
                return kind == "done"


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--selftest":
        sys.exit(0 if selftest(sys.argv[2], sys.argv[3]) else 1)
    App().mainloop()


if __name__ == "__main__":
    main()
