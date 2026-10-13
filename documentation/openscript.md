# OpenScript subset

The package implements the subset that appears in the Nida Corporation ATT lessons and in the Foolbook materials. It does not claim to be a full OpenScript interpreter.

## Implemented

- `to handle NAME ... end`
- `go to page "P"` and `go to page "P" of book "B"`
- `send NAME`
- `NAME = EXPR`
- `put EXPR into NAME`
- `set PROP of TARGET to EXPR`
- `get EXPR`
- `increment NAME` / `decrement NAME`
- `if` / `else` / `end if` (nested)
- `conditions` / `when` / `else` / `end conditions`
- `step NAME from A to B`
- `name of this book` / `name of this page`
- `forward` / `break`
- simple function calls (`get name(...)`, `isObject(...)`)

System declarations are ignored. Handler names are normalized to lowercase on lookup.

## Counts from the 9e954d01 TBX

Across 302 script files:

| Construct | Count |
|---|---|
| if | 297 |
| set | 184 |
| get | 113 |
| forward | 48 |
| when | 37 |
| else | 27 |
| conditions | 26 |
| break | 22 |
| increment | 14 |
| step | 10 |
| put | 1 |
| decrement | 0 |

External book jumps: `nida81.tbk` only (15 times). No other books appear in `of book` clauses.

## Not implemented

- Full expression evaluation. Conditions are recorded; the host decides what is true.
- User properties beyond simple assignment.
- Notify handlers, media, and the trainer DLL calls (`initializebase`, `openSession`, etc.). Those are noted but not executed.
- Anything that requires the original system books or the 16-bit runtime.

The TBK path recovers source from bytecode. The TBX path uses the plain-text `.script` files directly. Both feed the same core runner.
