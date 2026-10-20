# openscript_analysis

Version 1.0.0r9. Dependency of Foolbook for ToolBook script compatibility.

OpenScript tools for ToolBook and related formats.

Shared runtime lives in `core/`. Format-specific loaders live under `formats/`.
Unimplemented format stubs fall back to the TBK loader.

Full project context (intentions, architecture, history, future) is in [documentation/](documentation/README.md).

| Directory | Format |
|---|---|
| `formats/tbk/` | Raw `.tbk` / `.sbk` (bytecode expand + decode). Keyword resource in `formats/tbk/compat/res_77.bin`. Default for unknown or unimplemented formats. |
| `formats/tbx/` | TBKX XML export folder + plain-text `.script` files. |
| `formats/html/` | HTML with `<script type="openscript">` or `<!-- openscript -->` blocks. Falls back to TBK if none found. |
| `formats/pdf/` | PDF text extract (needs pypdf or PyPDF2). Looks for `to handle ... end` blocks. Falls back to TBK if none found or library missing. |
| `formats/fbk/` | Foolbook `.fbk` envelope (stub; falls back to TBK). |
| `formats/fsk/` | Fool system `.fsk` (stub; falls back to TBK). |
| `formats/json/` | Plain JSON lesson shells (stub; falls back to TBK). |
| `formats/xml/` | Generic XML (stub; falls back to TBK). |
| `formats/pptx/` | PowerPoint OpenScript (future stub; falls back to TBK). |

## Usage

```python
from openscript_analysis import load, run_handler

book = load("lesson.tbk")
book = load("export.tbx")   # directory with Book.xml
book = load("page.html")    # extracts <script type="openscript">
book = load("notes.pdf")    # extracts to handle ... end (needs pypdf)
book = load("unknown.xyz")  # falls back to TBK loader
```

## CLI

```
python3 -m openscript_analysis formats/tbk book.tbk
python3 formats/tbx/loader.py "/path/to/book tbx" --page P900
```

Keyword table for the TBK path is `formats/tbk/compat/res_77.bin` (resource 0x77 from TB80CMP). The package falls back to `core/keywords.py` if the binary is absent.
