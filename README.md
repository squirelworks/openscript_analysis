# openscript_analysis

One package. Expand bytecode, polish the source, and run the handler.

| Module | What it does |
|---|---|
| `expand` | `COMPILEREXPANDTEXT`. Reads the whole book, so a back-reference can land in an earlier handler. |
| `decode` | Calls `expand`. Also compiles source and reads constant pools. |
| `polish` | Turns CRLF into LF and trims noise. |
| `engine` | Runs a handler: `go to`, `send`, `set`, `if`, `step`. |
| `loader` | Opens `.tbk`, `.sbk`, `.fbk`, `.fsk`, and `.json`. |

```
python3 -m openscript_analysis book.sbk handlers.json
```

The keyword table is `openscript_analysis/compat/res_77.bin`, resource 0x77 from TB80CMP.
