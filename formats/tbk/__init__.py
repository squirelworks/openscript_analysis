"""ToolBook .tbk / .sbk bytecode loader.

Expands compressed OpenScript, polishes the source, and returns a Book
the core engine can run.
"""

from .loader import load, find_book, set_keyword_bin, set_keep_decoded
from .expand import decompress, read_handlers
from .decode import decode
from .settle import settle_pages
from .surface import read_surface
from .write import write_sbk, write_tbk

__all__ = [
    "load", "find_book", "set_keyword_bin", "set_keep_decoded",
    "decompress", "decode", "read_handlers", "write_tbk", "write_sbk", "settle_pages", "read_surface",
]
