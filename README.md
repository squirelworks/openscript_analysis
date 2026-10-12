# openscript_analysis

OpenScript tools for ToolBook books.

| Directory | What it covers |
|---|---|
| `tbk/` | Bytecode path. Expand, polish, and run handlers from raw `.tbk` / `.sbk` (and the Foolbook `.fbk` / `.fsk` envelope). |
| `tbx/` | TBKX path. Load a SumTotal XML export folder and interpret the plain-text `.script` files. |

## tbk

The original package. Expand compressed OpenScript, polish the source, and run the handler.

```
python3 -m openscript_analysis.tbk.openscript_analysis book.tbk handlers.json
```

Keyword table is `tbk/openscript_analysis/compat/res_77.bin` (resource 0x77 from TB80CMP).

## tbx

Plain-text OpenScript engine for a TBKX export.

```
python3 tbx/tbx_engine.py "/path/to/book tbx" --list
python3 tbx/tbx_engine.py "/path/to/book tbx" --page P900
```
