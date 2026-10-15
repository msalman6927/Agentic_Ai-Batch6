from medivault.utils.text import clean_text, hard_split, merge_blocks, split_blocks


def chunk_pages(
    pages: list[str],
    *,
    doc_type: str,  # noqa: ARG001 - doc_type reserved for type-aware strategies
    chunk_size: int,
    overlap: int,
) -> list[str]:
    """Type-aware chunking: block-merge first (keeps medicine/patient entries whole),
    then hard-split anything still oversized."""
    text = clean_text("\n\n".join(pages))
    if not text:
        return []
    blocks = split_blocks(text)
    merged = merge_blocks(blocks, chunk_size)
    chunks: list[str] = []
    for block in merged:
        if len(block) <= chunk_size:
            chunks.append(block)
        else:
            chunks.extend(hard_split(block, chunk_size, overlap))
    return chunks
