"""OpenScript analysis package.

Format-specific loaders live under formats/. Shared runtime is in core/.
"""

from pathlib import Path

from .core import run_handler, RuntimeState


def load(path: str | Path):
    """Load a book by extension. Returns the format's model object."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in (".tbk", ".sbk"):
        from .formats.tbk import load as load_tbk
        return load_tbk(p)
    if suffix in (".tbx",) or (p.is_dir() and (p / "Book.xml").exists()):
        from .formats.tbx.loader import load_tbx
        return load_tbx(p)
    if suffix == ".json":
        from .formats.json import load  # stub
        return load(p)
    if suffix == ".fbk":
        from .formats.fbk import load  # stub
        return load(p)
    if suffix == ".fsk":
        from .formats.fsk import load  # stub
        return load(p)
    raise ValueError(f"unsupported format: {suffix or p.name}")


__all__ = ["load", "run_handler", "RuntimeState"]
