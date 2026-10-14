# OpenScript expression evaluator

`FUN_1008_2d31` in TB80BAS segment 1008 is the expression evaluator.
It is reached from the 148-case switch at `1008:2dc7`.
The function checks for the string `"log"`, issues `FLD` / `FSTP` / `FCLEX`, and stays inside segment 1008.

## Engine coverage (1.0.0r6)

`core/engine.py` `_eval` now evaluates a small subset of the operators visible in that switch:

- arithmetic: `+`, `-`, `*`, `/`
- named functions: `abs`, `sqrt`, `log`, `exp`, `sin`, `cos`, `atan`, `asin`, `acos`

Parentheses are handled. On any error the original string is returned, so existing opaque-string behavior is preserved for anything the small evaluator does not cover.

The decoder is unchanged.
