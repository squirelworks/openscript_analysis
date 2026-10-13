# Formats

## tbk

Raw ToolBook books (`.tbk`) and system books (`.sbk`).

The file is a PE stub followed by a JBO signature at offset 0xC00. Pages are `80 65` records. Handlers are compressed bytecode inside the page blob. The loader:

1. Finds page records.
2. Expands the bytecode with the keyword table (back-references copy from the input stream).
3. Decodes the result into source.
4. Returns a core `Book`.

This is the default path. Unknown extensions and unimplemented stubs fall back here.

## tbx

SumTotal TBKX export. A folder containing `Book.xml`, `Page.xml` / `Background.xml`, and `.script` files.

The loader (updated from the 9e954d01 deep dive):

- Uses the XML `Name` attribute as the page key (P1040, not the folder name).
- Loads backgrounds the same way and records which background each page uses.
- Walks `Page.Objects` for kind, Name, Bounds, Vertices, and parent Group.
- Builds a bitmap id → Source map.
- Flags export-only pages (P440 and P2920 in the 9e954d01 corpus).

The runner handles the subset that appears in the Nida lessons: `go to` / `of book`, `send`, assignment, `get`/`set`, `if`/`else`, `conditions`/`when`, `increment`, `step`, `forward`. Handler lookup is case-insensitive.

`report()` and `coverage()` emit the jump graph and construct counts.

## html

Extracts OpenScript from:

- `<script type="openscript">...</script>`
- `<script language="openscript">...</script>`
- `<!-- openscript --> ... <!-- /openscript -->`

Returns a core Book. Falls back to TBK if no script is found.

## pdf

Extracts text with `pypdf` or `PyPDF2` and looks for `to handle NAME ... end` blocks. Falls back to TBK if the library is missing or no handlers are found.

## Stubs

| Module | Intended format | Status |
|---|---|---|
| `fbk/` | Foolbook `.fbk` envelope | stub; falls back to TBK |
| `fsk/` | Fool system `.fsk` | stub; falls back to TBK |
| `json/` | Plain JSON lesson shells | stub; falls back to TBK |
| `xml/` | Generic XML | stub; falls back to TBK |
| `pptx/` | PowerPoint with embedded OpenScript | future stub; falls back to TBK |

A stub should raise `NotImplementedError` until it can produce a core Book. The dispatcher treats that as a signal to fall back.
