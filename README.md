# openscript_analysis

OpenScript tools for ToolBook and related formats.

Shared runtime lives in `core/`. Format-specific loaders live under `formats/`.

| Directory | Format |
|---|---|
| `formats/tbk/` | Raw `.tbk` / `.sbk` (bytecode expand + decode). Keyword resource in `formats/tbk/compat/res_77.bin`. |
| `formats/tbx/` | TBKX XML export folder + plain-text `.script` files. |
| `formats/fbk/` | Foolbook `.fbk` envelope (stub). |
| `formats/fsk/` | Fool system `.fsk` (stub). |
| `formats/json/` | Plain JSON lesson shells (stub). |
| `formats/xml/` | Generic XML (stub). |
| `formats/pptx/` | PowerPoint OpenScript (future stub). |

## Usage

```python
from openscript_analysis import load, run_handler

book = load("lesson.tbk")
# or
book = load("export.tbx")   # directory with Book.xml
```

## CLI

```
python3 -m openscript_analysis formats/tbk book.tbk
python3 formats/tbx/loader.py "/path/to/book tbx" --page P900
```

Keyword table for the TBK path is `formats/tbk/compat/res_77.bin` (resource 0x77 from TB80CMP). The package falls back to `core/keywords.py` if the binary is absent.
