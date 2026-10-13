# tbx

Plain-text OpenScript engine for a SumTotal ToolBook TBKX export.

The engine loads `Book.xml`, `Page.xml`, and `Background.xml`, associates the
accompanying `.script` files, and interprets the subset of OpenScript used by
the Nida lesson corpus.

```
python3 tbx_engine.py "/path/to/book tbx" --list
python3 tbx_engine.py "/path/to/book tbx" --page P900
python3 tbx_engine.py "/path/to/book tbx" --book
```

Supported constructs: `to handle` / `end`, `go to page`, `send`, assignment,
`put into`, `set ... to`, `get`, `increment` / `decrement`, nested `if` / `else`,
`conditions` / `when`, `step ... from ... to`, `name of this book/page`,
`system` declarations, `forward` / `break`.
