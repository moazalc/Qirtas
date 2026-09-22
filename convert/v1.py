"""v1: lines joined into real paragraphs."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from convert.reader import read
from convert.scan import refuse_scans
from convert.writer import write


def convert(pdf_path, out_path, scale=None):
    # Before anything is written: a scan has no text of its own, and what
    # OCR laid over it converts to a Word file nobody can read (FLAGS.md 1).
    refuse_scans(pdf_path)
    img_dir = Path(out_path).parent / "media" / Path(out_path).stem
    model = read(str(pdf_path), image_dir=img_dir)
    write(model, out_path, scale)
    return model.source_route


if __name__ == "__main__":
    print("route:", convert(sys.argv[1], sys.argv[2]))
