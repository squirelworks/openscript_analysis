"""HTML OpenScript loader.

Extracts OpenScript from an HTML file and returns a core Book.
Looks for:
  <script type="openscript"> ... </script>
  <script language="openscript"> ... </script>
  or plain text blocks between <!-- openscript --> and <!-- /openscript -->
Falls back to the TBK loader if no script is found.
"""

from __future__ import annotations

import re
from pathlib import Path

from ...core.model import Book, Page, Handler


_SCRIPT = re.compile(
    r'<script[^>]*(?:type|language)=["\']openscript["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
_COMMENT = re.compile(
    r'<!--\s*openscript\s*-->(.*?)<!--\s*/openscript\s*-->',
    re.IGNORECASE | re.DOTALL,
)


def load(path: str | Path) -> Book:
    """Load OpenScript from an HTML file into the core Book model."""
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    chunks = _SCRIPT.findall(text) + _COMMENT.findall(text)
    book = Book(path=str(p), title=p.stem)
    if not chunks:
        # no embedded script; let the dispatcher fall back
        raise NotImplementedError("no OpenScript found in HTML")
    page = Page(id="P0")
    for i, src in enumerate(chunks):
        page.handlers.append(Handler(name=f"script{i}", source=src.strip()))
    book.pages.append(page)
    return book
