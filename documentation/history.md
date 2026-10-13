# History

This package grew out of a reverse-engineering effort on Asymetrix / SumTotal ToolBook II 8.1, focused on the Nida Corporation ATT Master_3 electronics CAI lessons (Navy rating tracks).

## The binary path

The original books are `.tbk` files: a PE stub, a JBO signature at file offset 0xC00, and page records marked `80 65`. Handlers are compressed bytecode. The keyword table lives in TB80CMP resource 0x77 and in TB80BAS. Expanding the bytecode (with back-references copying from the input stream) produced readable OpenScript for the Logic Families lesson (`9e954d01.tbk`).

That work also produced:

- An OPTLOADER unpacker for the 16-bit NE images.
- Ghidra projects and decompiles for TB80BAS, TB80RTM, TB80CMP, and the satellite DLLs.
- SoftICE traces of the paint path (GDI Polygon, Polyline, Arc) that confirmed the twip-to-screen scale (stored * 96 + 720) / 1440, which simplifies to /15 at 96 dpi.
- A clean-room runtime sketch that never claimed to be a port of the NE images.

## The TBX path

A SumTotal TBKX export of the same lesson provided plain-text `.script` files and explicit Vertices lists for every IrregularPolygon. That removed the need to reverse the binary geometry for playback. The TBX loader was written to consume the export directly, then expanded (page-by-Name, backgrounds, object tree, bitmaps, richer runner) after a full walk of the 131 pages and 302 scripts.

## The package split

The decoder and the runner were originally mixed into Foolbook's `engine/` directory. They were extracted into this repository so the format surface could grow (TBK, TBX, HTML, PDF, and stubs) without further entangling the reader. Foolbook now depends on this package; Foolcourse depends on Foolbook; Foolversity depends on Foolcourse.

## Naming

The package is named for the analysis work that produced it. It is not a general-purpose OpenScript IDE. It is the place where ToolBook script and format knowledge is kept so the rest of the Fool* stack can use it.
