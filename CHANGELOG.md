# Changelog

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
