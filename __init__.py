"""OpenScript analysis package.

Format-specific loaders live under formats/. Shared runtime is in core/.
If a format stub is not implemented, load() falls back to the TBK loader.
"""

from pathlib import Path

from .core import run_handler, RuntimeState


def _load_tbk(path: Path):
    from .formats.tbk import load as load_tbk
    return load_tbk(path)


def load(path: str | Path):
    """Load a book by extension. Returns the format's model object.

    Unimplemented format stubs and unknown suffixes fall back to the TBK loader.
    """
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix in (".tbk", ".sbk"):
        return _load_tbk(p)

    if suffix in (".tbx",) or (p.is_dir() and (p / "Book.xml").exists()):
        try:
            from .formats.tbx.loader import load_tbx
            return load_tbx(p)
        except (ImportError, NotImplementedError):
            return _load_tbk(p)

    # stubs: try the format module; fall back to tbk if not implemented
    stub_map = {
        ".json": "json",
        ".fbk": "fbk",
        ".fsk": "fsk",
        ".xml": "xml",
        ".pptx": "pptx",
    }
    mod_name = stub_map.get(suffix)
    if mod_name:
        try:
            mod = __import__(f"openscript_analysis.formats.{mod_name}", fromlist=["load"])
            if hasattr(mod, "load"):
                return mod.load(p)
        except (ImportError, NotImplementedError, AttributeError):
            pass
        return _load_tbk(p)

    # unknown extension — default to tbk
    return _load_tbk(p)


__all__ = ["load", "run_handler", "RuntimeState"]
