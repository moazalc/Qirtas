"""v1: lines joined into real paragraphs."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from convert.reader import read
from convert.writer import write


def convert(pdf_path, out_path, scale=None):
    img_dir = Path(out_path).parent / "media" / Path(out_path).stem
    model = read(str(pdf_path), image_dir=img_dir)
    write(model, out_path, scale)
    return model.source_route


if __name__ == "__main__":
    print("route:", convert(sys.argv[1], sys.argv[2]))
