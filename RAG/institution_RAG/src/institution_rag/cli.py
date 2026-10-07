import argparse
import sys
from pathlib import Path

from institution_rag.config import EMBEDDING_DIMS, PROJECT_ROOT, require_gemini_api_key
from institution_rag.pipeline import ingest


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="institution-rag",
        description="Ingest a PDF into Neon Postgres with Gemini embeddings.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=str(PROJECT_ROOT / "salman_company.pdf"),
        help="PDF to ingest (default: salman_company.pdf)",
    )
    parser.add_argument(
        "--reingest",
        action="store_true",
        help="Delete any existing copy of this file's chunks and re-ingest.",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Embed one string to verify the Gemini API key, then exit.",
    )
    args = parser.parse_args()

    if args.smoke:
        require_gemini_api_key()
        from institution_rag.embedder import smoke_test

        dims = smoke_test()
        status = "OK" if dims == EMBEDDING_DIMS else "UNEXPECTED"
        print(f"SMOKE   gemini embed -> {dims} dims [{status}]")
        return

    path = Path(args.path)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    try:
        ingest(path, reingest=args.reingest)
    except Exception as exc:
        print(f"ERROR   {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
