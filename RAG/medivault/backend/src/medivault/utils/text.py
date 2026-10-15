import re

_PAGE_NUMBER_RE = re.compile(r"^\s*page\s+\d+\s*(of\s+\d+)?\s*$", re.IGNORECASE)
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_TRAILING_WS_RE = re.compile(r"[ \t]+")


def clean_text(text: str) -> str:
    lines = [_TRAILING_WS_RE.sub(" ", line).rstrip() for line in text.splitlines()]
    kept = [line for line in lines if not _PAGE_NUMBER_RE.match(line)]
    cleaned = "\n".join(kept)
    return _MULTI_NEWLINE_RE.sub("\n\n", cleaned).strip()


def split_blocks(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text)
    return [part.strip() for part in parts if part.strip()]


def hard_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    step = max(chunk_size - overlap, 1)
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start += step
    return chunks


def merge_blocks(blocks: list[str], chunk_size: int) -> list[str]:
    merged: list[str] = []
    current = ""
    for block in blocks:
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            merged.append(current)
        current = block
    if current:
        merged.append(current)
    return merged
