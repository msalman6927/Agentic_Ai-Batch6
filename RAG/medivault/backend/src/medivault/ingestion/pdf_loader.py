from io import BytesIO

from pypdf import PdfReader

from medivault.utils.errors import IngestError


def load_pdf_pages(data: bytes) -> list[str]:
    try:
        reader = PdfReader(BytesIO(data))
        return [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:  # noqa: BLE001
        raise IngestError(f"could not read PDF: {type(exc).__name__}: {exc}") from exc
