# Overview

`openscript_analysis` is a Python package that loads ToolBook-related containers and runs the OpenScript they contain.

It is a clean-room analysis and playback aid, not a port of the original ToolBook runtime. The original engine is a set of 16-bit NE binaries (TB80RTM, TB80BAS, TB80CMP, and the satellite DLLs). This package does not load those binaries. It reads the files they produced or exported and interprets the script.

## What it loads

- Raw ToolBook books (`.tbk`) and system books (`.sbk`), via bytecode expand and decode.
- SumTotal TBKX XML exports (a folder with `Book.xml`, `Page.xml`, and `.script` files).
- HTML that embeds OpenScript in `<script type="openscript">` or comment blocks.
- PDF text that contains `to handle ... end` blocks (when a PDF library is present).
- Stubs for Foolbook envelopes (`.fbk`, `.fsk`), JSON lesson shells, generic XML, and PowerPoint.

Unknown or unimplemented formats fall back to the TBK loader.

## What it returns

A book model (pages, handlers, objects) that the shared runtime in `core/` can execute. Format loaders are responsible for turning a container into that model. The engine is responsible for running the source.

## What it is not

- A full OpenScript implementation. It covers the subset that appears in the Nida Corporation ATT lessons and in the Foolbook materials.
- A geometry renderer. It exposes Vertices, Bounds, and Groups from a TBX; it does not draw them.
- A replacement for Foolbook. Foolbook is the reader. This package is the script and format layer that Foolbook (and future tools) can depend on.
- A decompiler of the NE images. That work lives in other repositories and in the working papers.
