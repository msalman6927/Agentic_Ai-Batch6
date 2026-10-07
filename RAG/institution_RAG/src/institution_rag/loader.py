from pathlib import Path

from pypdf import PdfReader


def load_pdf(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {path}")
    reader = PdfReader(path)
    pages = [(page.extract_text() or "") for page in reader.pages]
    text = "\n\n".join(pages)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    text = text.strip()
    if not text:
        raise ValueError(f"No extractable text in {path.name} (scanned/image PDF?)")
    return text
