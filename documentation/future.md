# Future

## Near term

- Finish the TBX object tree so a viewer can consume Vertices, Bounds, and Groups without a second parser. The loader already walks them; the next step is a stable export (JSON or a small helper) that Foolbook can call.
- Implement the remaining stubs that have a clear source format:
  - `fbk` / `fsk` — the Foolbook envelope (FBK1/FSK1 magic, optional zlib, JSON payload). These already have source; they should not fall back to the TBK bytecode path.
  - `json` — the plain lesson shells used by earlier runtimes.
- Add a regression check that runs `coverage()` against the 9e954d01 TBX and fails if the construct counts drift. The current numbers (if 297, set 184, get 113, …) are the baseline.
- 1.0.1 is the published release. The interim `v1.0.0rN` tags are not releases.

## Medium term

- HTML and PDF loaders are minimal. HTML should also accept a whole lesson directory (one HTML file per page). PDF should note page boundaries so handlers can be attributed.
- PPTX is a stub. If OpenScript is ever embedded in PowerPoint notes or a custom XML part, the loader should extract it the same way the HTML loader does. No design work has been done.
- Background scripts are loaded but not composed with page scripts. A page that inherits a background handler should see both. The 9e954d01 export has 14 backgrounds; id 2 and id 3 cover most pages.
- External book jumps are recorded (`nida81.tbk` only, in this corpus). Resolving them requires the host to supply the other book. The package should define the hook, not implement the lookup.

## Longer term

- The TBK bytecode path and the TBX plain-text path should converge on the same model. Today the TBX loader has richer objects; the TBK loader has only pages and handlers. Geometry from a TBK is still a research topic (the binary stores many shapes as bounds-only records).
- System-book behavior (`initializebase`, `openSession`, `gotoPageList`) is currently a note in the script, not a call. A future host can supply those; this package should not grow a trainer.
- If the package is ever used outside the Fool* stack, the fallback-to-TBK rule should become configurable. It is convenient while stubs are unfinished; it is surprising once a format is real.

## Explicitly not planned

- A full OpenScript language. The corpus does not need it.
- Rendering. Geometry stays data.
- Any dependency on the original 16-bit binaries.
