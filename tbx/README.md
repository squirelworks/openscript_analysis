# TBX OpenScript Engine

Self-contained interpreter for the plain-text `.script` files that accompany a SumTotal ToolBook TBKX export.

## Usage

```bash
python3 tbx_engine.py "/path/to/9e954d01 tbx" --list
python3 tbx_engine.py "/path/to/9e954d01 tbx" --page P900
python3 tbx_engine.py "/path/to/9e954d01 tbx" --script Book.script
```

## What it does

- Loads `Book.xml`, every `Page*/Page.xml`, and every `Background*/Background.xml`.
- Collects the external `.script` files and associates them with pages, backgrounds, and objects.
- Interprets the common OpenScript subset used by the Nida lesson books:
  - `go to page "P" [of book "B"]`
  - `send NAME`
  - assignment, `put … into`, `set … to`, `get`
  - `increment` / `decrement`
  - nested `if` / `else` / `end if`
  - `conditions` / `when` / `else` / `end conditions`
  - `step` / `end step`
  - `name of this book` / `name of this page`
  - `forward`, `break`
- Returns a list of actions (`goto`, `send`, `set`, `setprop`, `get`, `note`, …) that a host can apply.

## Current limits

- Conditionals that use `is not in`, `is object`, or other OpenScript predicates are not fully evaluated; the line is recorded as a note.
- Function calls (`initializebase`, `getSkippedCount`, …) return a stub value.
- Object property writes are recorded but not applied to a live object model.
- Loading the full 9e954d01 export takes ~20 s (XML parse of 131 pages).

This is the starting point for a TBX-native playback path. It does not replace the existing Foolbook engine used for `.tbk` / `.fbk`.
