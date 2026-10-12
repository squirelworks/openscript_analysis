"""OpenScript: expand bytecode, polish the source, run the handler."""

from .decode import decode
from .engine import run_handler
from .expand import decompress
from .loader import load
from .polish import polish

__all__ = ["decode", "decompress", "polish", "load", "run_handler"]
