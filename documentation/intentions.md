# Intentions

## Primary goal

Make OpenScript from ToolBook books usable in a modern Python environment, without requiring the original 16-bit runtime.

The immediate consumer is Foolbook, a clean-room reader for ToolBook books. Foolbook needs to:

- Open a `.tbk` or `.sbk` and recover the page structure and the script.
- Open a TBKX export and use the plain-text scripts and the expanded geometry.
- Run the common navigation and quiz patterns (`go to page`, `send`, simple assignment, if/else).

This package is the shared place for that work so Foolbook, Foolcourse, and later tools do not each carry their own decoder.

## Secondary goals

- Keep the format surface plug-and-play. Adding a new container (FBK, JSON, PPTX, etc.) should mean a new module under `formats/`, not a change to the engine.
- Preserve enough of the original structure (page names, object kinds, Vertices/Bounds, background references) that a viewer can reconstruct the lesson without re-parsing the binary.
- Stay honest about what is implemented. The runner documents the subset it covers and does not claim to be a full OpenScript interpreter.

## Non-goals

- Bit-for-bit compatibility with TB80RTM.
- Running VBX, OLE, dBASE, network, or licensing features.
- Rendering. Geometry is exposed; drawing is the caller's job.
- Replacing the system books (`nc81base.sbk`, `nc81recs.sbk`, etc.). Those are resource containers and trainer DLLs; their logic is not OpenScript.

## Relationship to the Fool* stack

- Foolbook is the book reader. It depends on this package for `.tbk` / `.sbk` / `.tbx` script handling.
- Foolcourse sits above Foolbook and manages courses.
- Foolversity sits above Foolcourse and manages schools.

This package is the bottom of that stack for script and format concerns. It does not know about courses or schools.
