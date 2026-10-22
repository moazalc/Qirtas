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
English comes out scrambled: every Arabic string here is Arabic only, with
the English on a line of its own.

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
BIG = ("Segoe UI", 14, "bold")


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
        self.say("status", "يفحص الملف ...\nChecking the file ...")
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
            self.say("status", "يفحص الخطوط ...\nChecking the fonts ...")
            fonts.judge(pdf, found)
            if all(m.only_style for m in found):
                left = found
                break
            self.say("fonts", fonts.message(found))
            if self.answer.get() == "go":
                left = found
                break
            fonts.rescan()
        self.say("status", "يحوّل ... قد يستغرق دقيقة أو دقيقتين لملف طويل.\n"
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


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(TITLE)
        self.geometry("560x400")
        self.minsize(480, 380)
        self.events = queue.Queue()
        self.worker = Worker(self.events)
        self.worker.start()
        self.pdf = None
        self.docx = None

        pad = {"padx": 16, "pady": 6}
        tk.Label(self, text="حوّل ملف بي دي إف عربيًا إلى ملف وورد يمكن تعديله",
                 font=BIG, anchor="e", justify="right").pack(fill="x", **pad)
        tk.Label(self, text="Turn an Arabic PDF back into a Word file you can edit",
                 font=FONT, fg="#555", anchor="e").pack(fill="x", padx=16)

        row = tk.Frame(self)
        row.pack(fill="x", **pad)
        self.pick = tk.Button(row, text="اختر الملف\nChoose a PDF", font=FONT,
                              command=self.choose)
        self.pick.pack(side="right")
        self.name = tk.Label(row, text="", font=FONT, anchor="e")
        self.name.pack(side="right", fill="x", expand=True, padx=8)

        self.go = tk.Button(self, text="حوّل\nConvert", font=BIG, state="disabled",
                            command=self.convert)
        self.go.pack(**pad)
        self.bar = ttk.Progressbar(self, mode="indeterminate")
        self.bar.pack(fill="x", **pad)
        self.status = tk.Label(self, text="", font=FONT, anchor="e", justify="right",
                               wraplength=520)
        self.status.pack(fill="x", **pad)
        self.open = tk.Button(self, text="افتح الملف\nOpen the Word file", font=FONT,
                              command=self.open_docx)
        self.after(150, self.poll)

    def choose(self):
        path = filedialog.askopenfilename(
            title="Choose a PDF",
            filetypes=[("PDF", "*.pdf"), ("All files", "*.*")])
        if not path:
            return
        self.pdf = Path(path)
        self.name.config(text=self.pdf.name)
        self.go.config(state="normal")
        self.status.config(text="")
        self.open.pack_forget()

    def convert(self):
        if not self.pdf:
            return
        self.docx = _out_path(self.pdf)
        self.busy(True)
        self.worker.jobs.put((str(self.pdf), str(self.docx)))

    def busy(self, on):
        self.go.config(state="disabled" if on else "normal")
        self.pick.config(state="disabled" if on else "normal")
        if on:
            self.open.pack_forget()
            self.bar.start(12)
        else:
            self.bar.stop()

    def poll(self):
        try:
            while True:
                self.handle(*self.events.get_nowait())
        except queue.Empty:
            pass
        self.after(150, self.poll)

    def handle(self, kind, *args):
        if kind == "status":
            self.status.config(text=args[0])
        elif kind == "refused":
            self.busy(False)
            self.status.config(text="لا يمكن تحويل هذا الملف.\nThis file cannot be converted.")
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
            self.status.config(text=f"تم.\nDone: {self.docx}")
            self.open.pack(padx=16, pady=6)
            if args[1]:
                messagebox.showinfo(TITLE, args[1])
        elif kind == "failed":
            self.busy(False)
            self.status.config(text="حدث خطأ.\nSomething went wrong.")
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
