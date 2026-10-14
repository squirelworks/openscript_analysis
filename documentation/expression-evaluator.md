# Expression evaluator

The OpenScript math path is not in the decoder. It is in TB80BAS segment 1008.

- `FUN_1008_2d31` (called from the 148-case switch at `1008:2dc7`) is the expression evaluator.
- It checks for the string `"log"`, issues `FLD` / `FSTP` / `FCLEX`, and stays inside segment 1008.
- This is the path for arithmetic and transcendental expressions, not for page records or widget bounds.

The current engine (`tbk/openscript_analysis/engine.py`) treats the right-hand side of an assignment as an opaque string. A future cut can hand that string to a small evaluator that mirrors the 1008 switch, starting with the operators already visible in the decompile (`+`, `-`, `*`, `/`, and the named functions that reach `FUN_1008_2d31`).

ScaleTwipsToScreen (`FUN_1008_01dd`) is a separate helper in the same segment. It is not part of the script expression path.
