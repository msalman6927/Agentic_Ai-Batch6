from langchain_text_splitters import RecursiveCharacterTextSplitter

from institution_rag.config import CHUNK_OVERLAP, CHUNK_SIZE


def chunk_text(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return [chunk for chunk in splitter.split_text(text) if chunk.strip()]
