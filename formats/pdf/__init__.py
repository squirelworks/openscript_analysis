"""PDF OpenScript loader.

Extracts text from a PDF and looks for OpenScript handlers.
Requires pypdf or PyPDF2 if available; otherwise raises NotImplementedError
so the dispatcher falls back to the TBK loader.
"""

from __future__ import annotations

import re
from pathlib import Path

from ...core.model import Book, Page, Handler


_HANDLER = re.compile(
    r'to\s+handle\s+(\w+).*?end(?:\s+handler)?',
    re.IGNORECASE | re.DOTALL,
)


def _extract_text(path: Path) -> str:
    """Best-effort text extract. Prefers pypdf, then PyPDF2."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        pass
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        raise NotImplementedError("PDF text extract needs pypdf or PyPDF2")


def load(path: str | Path) -> Book:
    """Load OpenScript handlers found in a PDF into the core Book model."""
    p = Path(path)
    text = _extract_text(p)
    book = Book(path=str(p), title=p.stem)
    page = Page(id="P0")
    for m in _HANDLER.finditer(text):
        page.handlers.append(Handler(name=m.group(1), source=m.group(0).strip()))
    if not page.handlers:
        raise NotImplementedError("no OpenScript handlers found in PDF")
    book.pages.append(page)
    return book
