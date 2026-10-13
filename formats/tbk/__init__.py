"""ToolBook .tbk / .sbk bytecode loader.

Expands compressed OpenScript, polishes the source, and returns a Book
the core engine can run.
"""

from .loader import load, find_book, set_keyword_bin, set_keep_decoded
from .expand import decompress
from .decode import decode

__all__ = ["load", "find_book", "set_keyword_bin", "set_keep_decoded", "decompress", "decode"]
