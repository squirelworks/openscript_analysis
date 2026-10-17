# Changelog

## 1.0.0r7

- A TBX is settled before it is shown. `Book.Pages` is the page list. Each page is the background's objects with the page's objects on top. Text, graphics, and buttons keep the bounds, caption, and bitmap the book stored.
- A quiz page is graded from its Answer property.
- A TBK is read to the end first. A later record for the same page replaces the earlier one.
- A written `.tbx` includes `Book.Pages` and bounds on fields and buttons.

## 1.0.0r6

- Small expression evaluator in `core/engine.py`. Covers `+ - * /` and the named functions that reach `FUN_1008_2d31`. Falls back to the original string on error. Decoder unchanged.

## 1.0.0r5

- Expression evaluator note: `FUN_1008_2d31` in TB80BAS segment 1008 (switch at `1008:2dc7`) is the OpenScript math path. Recorded in `documentation/expression-evaluator.md`.

## 1.0.0r4

- The install now provides the `openscript_analysis` module. 1.0.0r3 installed `formats` and `core` at the top level, so Foolbook could not import it.

## 1.0.0r3

- A TBX XML file is loaded as a TBX folder, not as a `.tbk`.
- `write_tbx` writes the expanded directory: `Book.xml`, `PageN/Page.xml`, and `.script` files.
- `write_tbk` and `write_sbk` write the shell Foolbook already knows how to read.

## 1.0.0r1


## 1.0.0

OpenScript tools for ToolBook compatibility.

- `formats/tbk/`: bytecode path for raw `.tbk` / `.sbk`.
- `formats/tbx/`: plain-text path for TBKX XML exports.
- Keyword table from TB80CMP resource 0x77.

Dependency of Foolbook for `.tbk` / `.sbk` / `.tbx` script handling.

## 1.0.0r1

- --freshstart and --doctor
- _debug/ dumps diagnostics

## Unreleased

TBX loader and runner updates from the 9e954d01 deep dive:

- Page key is the XML Name attribute (P1040), not the folder name.
- Backgrounds loaded the same way; page records which background it uses.
- Page.Objects walked for kind, Name, Bounds, Vertices, and parent Group.
- Bitmap id to Source map.
- Export-only pages (P440, P2920) flagged.
- Runner handles if/else, conditions/when, increment, step, get/set, forward.
- Handler lookup is case-insensitive.
- report() and coverage() for jump graph and construct counts.
