from medivault.ingestion.chunker import chunk_pages
from medivault.utils.text import clean_text, hard_split, merge_blocks, split_blocks


def test_clean_text_strips_page_numbers() -> None:
    text = "Page 1 of 3\nAspirin 75mg\n\nPage 2\nDaily dose"
    assert "Page 1" not in clean_text(text)
    assert "Aspirin 75mg" in clean_text(text)


def test_split_blocks_ignores_empty() -> None:
    assert split_blocks("a\n\n\n\nb") == ["a", "b"]


def test_merge_blocks_respects_chunk_size() -> None:
    blocks = ["aaa", "bbb", "ccc"]
    merged = merge_blocks(blocks, chunk_size=8)
    assert all(len(m) <= 8 for m in merged)


def test_hard_split_overlap() -> None:
    text = "x" * 100
    chunks = hard_split(text, chunk_size=40, overlap=10)
    assert len(chunks) == 3
    assert all(len(c) <= 40 for c in chunks)


def test_chunk_pages_returns_chunks_under_size() -> None:
    pages = ["Paracetamol 500mg\n\nIbuprofen 400mg\n\n" + "note " * 500]
    chunks = chunk_pages(pages, doc_type="medicine", chunk_size=200, overlap=40)
    assert chunks
    assert all(len(c) <= 200 for c in chunks)


def test_chunk_pages_empty_input() -> None:
    assert chunk_pages([""], doc_type="patient", chunk_size=100, overlap=10) == []
