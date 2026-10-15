from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def make_minimal_pdf(text: str) -> bytes:
    """Build a tiny one-page PDF containing `text` (one line per \n, for tests)."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    lines = ["BT /F1 10 Tf"]
    y = 750
    for line in text.split("\n"):
        lines.append(f"1 0 0 1 40 {y} Tm ({_escape(line)}) Tj")
        y -= 14
    lines.append("ET")
    stream = DecodedStreamObject()
    stream.set_data("\n".join(lines).encode("latin-1"))
    stream_ref = writer._add_object(stream)
    font_ref = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
    )
    page[NameObject("/Contents")] = stream_ref
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref}),
        }
    )
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
