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
import math
import os
import queue
import sys
import tempfile
import threading
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tkinter as tk
from tkinter import filedialog, ttk
from tkinter import font as tkfont

TITLE = "Qirtas - قرطاس"
FONT = ("Segoe UI", 11)
SMALL = ("Segoe UI", 9)
BIG = ("Segoe UI", 13, "bold")
TITLE_FONT = ("Segoe UI", 18, "bold")
LOGO = Path(__file__).resolve().parent / "data" / "logo.png"   # 180 px square
# Moaz's palette (25 Oct): deep green, cream text, gold.
C = {"bg": "#07281e", "card": "#0d3127", "muted": "#12352a",
     "secondary": "#12382d", "accent": "#163e31", "fg": "#f3ead9",
     "muted_fg": "#cdc3af", "primary": "#d8b66d", "ring": "#b89a5a",
     "destructive": "#f47c6e", "success": "#7bcc98",
     "edge": "#54603f"}     # the site's outline: gold at 35% over the card


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
    """A flat square button in the palette's colours, as on the website: gold,
    or dark with a thin gold outline. Tk's own button keeps the system's grey
    on Windows whatever colour it is given."""

    def __init__(self, master, text, command, primary=False, **kw):
        self.colours = ((C["primary"], C["bg"], C["ring"], C["primary"]) if primary
                        else (C["card"], C["fg"], C["accent"], C["edge"]))
        super().__init__(master, text=text, cursor="hand2", padx=18, pady=6,
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
        bg, fg, over, edge = self.colours
        if not self.enabled:
            bg, fg, edge = C["muted"], C["muted_fg"], C["muted"]
        elif hover:
            bg = over
        self.config(bg=bg, fg=fg, highlightbackground=edge,
                    highlightcolor=C["ring"],
                    cursor="hand2" if self.enabled else "arrow")

    def _press(self):
        if self.enabled:
            self.command()

    def set_enabled(self, on):
        self.enabled = on
        self._paint()


class Dialog(tk.Toplevel):
    """A message in the window's colours, in place of Windows' grey box.
    `buttons`: [(Arabic, English, value)], the first gold; the window waits
    and `.value` is the one pressed (None if closed)."""

    def __init__(self, master, arabic, english, body, colour, buttons):
        super().__init__(master)
        self.title(TITLE)
        self.configure(bg=C["card"])
        self.transient(master)
        self.resizable(False, False)
        self.value = None
        tk.Frame(self, bg=C[colour], height=4).pack(fill="x")
        inner = tk.Frame(self, bg=C["card"])
        inner.pack(fill="both", expand=True, padx=24, pady=(16, 20))
        tk.Label(inner, text=arabic, font=BIG, bg=C["card"], fg=C[colour],
                 anchor="e").pack(fill="x")
        tk.Label(inner, text=english, font=SMALL, bg=C["card"], fg=C["muted_fg"],
                 anchor="e").pack(fill="x", pady=(0, 10))
        if body:
            # The converter's own words: English, left to right, and as long
            # as a list of fonts can be - scrolled past ten lines.
            frame = tk.Frame(inner, bg=C["muted"])
            frame.pack(fill="both", expand=True)
            box = tk.Text(frame, width=64, height=3, wrap="word", font=SMALL,
                          bg=C["muted"], fg=C["fg"], relief="flat", padx=12,
                          pady=10, highlightthickness=0,
                          insertbackground=C["fg"], selectbackground=C["accent"])
            box.insert("1.0", body)
            box.pack(side="left", fill="both", expand=True)
            # As tall as the text once wrapped, measured with the font (the
            # box cannot say before it is drawn); past that, scrolled.
            face = tkfont.Font(font=SMALL)
            wide = 64 * face.measure("0") * 0.95
            shown = sum(max(1, math.ceil(face.measure(ln) / wide))
                        for ln in body.split("\n"))
            box.config(height=min(MAX_LINES, max(3, shown)))
            if shown > MAX_LINES:
                bar = ttk.Scrollbar(frame, orient="vertical", command=box.yview,
                                    style="Card.Vertical.TScrollbar")
                bar.pack(side="right", fill="y")
                box.config(yscrollcommand=bar.set)
            box.config(state="disabled")
        row = tk.Frame(inner, bg=C["card"])
        row.pack(fill="x", pady=(16, 0))
        first = None
        for k, (ar, en, value) in enumerate(buttons):
            b = Button(row, f"{ar}\n{en}", lambda v=value: self._close(v),
                       primary=(k == 0))
            b.pack(side="right", padx=(10, 0))
            first = first or b
        self.protocol("WM_DELETE_WINDOW", lambda: self._close(None))
        self.bind("<Escape>", lambda e: self._close(None))
        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.grab_set()
        first.focus_set()

    def _close(self, value):
        self.value = value
        self.grab_release()
        self.destroy()

    def ask(self):
        self.wait_window()
        return self.value


OK = [("حسنًا", "OK", True)]
MAX_LINES = 16


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(TITLE)
        # No fixed height: the window is as tall as what it shows, and grows
        # when the progress bar, the status and the open button appear.
        self.minsize(520, 1)
        self.configure(bg=C["bg"])
        self.logo = None
        if LOGO.exists():
            self.logo = tk.PhotoImage(file=str(LOGO))
            self.iconphoto(True, self.logo)
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
        style.configure("Card.Vertical.TScrollbar", troughcolor=C["muted"],
                        background=C["accent"], bordercolor=C["muted"],
                        arrowcolor=C["muted_fg"], lightcolor=C["accent"],
                        darkcolor=C["accent"])

        # One header row, right to left: the logo, then the name and what it does.
        head = tk.Frame(self, bg=C["bg"])
        head.pack(fill="x", padx=18, pady=(14, 10))
        if self.logo:
            self.mark = self.logo.subsample(4)          # 45 px
            tk.Label(head, image=self.mark, bg=C["bg"]).pack(side="right")
        words = tk.Frame(head, bg=C["bg"])
        words.pack(side="right", fill="x", expand=True, padx=(0, 12))
        # The website's heading face where this computer has it
        title = (("Amiri", 22, "bold") if "Amiri" in tkfont.families(self)
                 else TITLE_FONT)
        tk.Label(words, text="قرطاس", font=title, bg=C["bg"], fg=C["primary"],
                 anchor="e").pack(fill="x")
        tk.Label(words, text="Arabic PDF to editable Word", font=SMALL, bg=C["bg"],
                 fg=C["muted_fg"], anchor="e").pack(fill="x")

        card = tk.Frame(self, bg=C["card"], highlightthickness=1,
                        highlightbackground=C["secondary"])
        card.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        inner = tk.Frame(card, bg=C["card"])
        inner.pack(fill="both", expand=True, padx=16, pady=14)

        # The file: a sunken strip with its name, the choose button at its end.
        row = tk.Frame(inner, bg=C["muted"])
        row.pack(fill="x")
        self.pick = Button(row, "اختر الملف\nChoose a PDF", self.choose)
        self.pick.pack(side="right")
        self.name = tk.Label(row, text="لم يُختر ملف بعد\nNo file chosen yet",
                             font=SMALL, bg=C["muted"], fg=C["muted_fg"],
                             anchor="e", justify="right")
        self.name.pack(side="right", fill="x", expand=True, padx=12)

        self.go = Button(inner, "حوّل\nConvert", self.convert, primary=True,
                         font=BIG)
        self.go.pack(fill="x", pady=(12, 0))
        self.go.set_enabled(False)

        self.bar = ttk.Progressbar(inner, mode="indeterminate",
                                   style="Gold.Horizontal.TProgressbar")
        self.status = tk.Label(inner, text="", font=SMALL, bg=C["card"], fg=C["fg"],
                               anchor="e", justify="right", wraplength=440)
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
            self.bar.pack(fill="x", pady=(12, 0), after=self.go)
            self.bar.start(12)
        else:
            self.bar.stop()
            self.bar.pack_forget()

    def say(self, text, colour="fg"):
        self.status.config(text=text, fg=C[colour])
        if text:
            above = self.bar if self.bar.winfo_manager() else self.go
            self.status.pack(fill="x", pady=(8, 0), after=above)
        else:
            self.status.pack_forget()

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
            Dialog(self, "لا يمكن تحويل هذا الملف", "This file cannot be converted",
                   args[0], "destructive", OK).ask()
        elif kind == "fonts":
            again = Dialog(self, "خطوط غير مثبتة", "Fonts missing on this computer",
                           args[0], "primary",
                           [("ثبّتها ثم افحص", "Installed - check again", True),
                            ("حوّل بدونها", "Convert without them", False)]).ask()
            self.worker.answer.put("again" if again else "go")
        elif kind == "done":
            self.busy(False)
            self.docx = Path(args[0])
            self.say(f"تم\nDone: {self.docx.name}", "success")
            self.open.pack(fill="x", pady=(8, 0))
            if args[1]:
                Dialog(self, "راجع هذه الملاحظات", "Please check these notes",
                       args[1], "primary", OK).ask()
        elif kind == "failed":
            self.busy(False)
            self.say("حدث خطأ\nSomething went wrong.", "destructive")
            Dialog(self, "حدث خطأ", "Something went wrong", args[0],
                   "destructive", OK).ask()

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
