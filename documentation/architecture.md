# Architecture

## Layout

```
openscript_analysis/
  core/            shared runtime and model
  formats/         one module per container
    tbk/           raw .tbk / .sbk bytecode path
    tbx/           TBKX XML + .script path
    html/          HTML embedded script
    pdf/           PDF text extract
    fbk/ fsk/ json/ xml/ pptx/   stubs
  documentation/   this directory
```

## core/

Shared pieces that every format uses:

- `engine.py` — `run_handler`, `follow`, `open_book`. Executes source that a loader has already turned into text.
- `model.py` — `Book`, `Page`, `Handler`, `RuntimeState`.
- `keywords.py` — clean transcription of the OpenScript keyword table. Fallback when `res_77.bin` is absent.
- `polish.py`, `formats.py` — helpers for the Foolbook envelope and for source cleanup.

Format loaders must not reimplement the engine. They produce a model; `core` runs it.

## formats/

Each subdirectory is a loader. The top-level `load()` in `__init__.py` dispatches by extension:

- `.tbk` / `.sbk` → `formats.tbk`
- `.tbx` or a directory containing `Book.xml` → `formats.tbx`
- `.html` / `.htm` → `formats.html`
- `.pdf` → `formats.pdf`
- `.json`, `.fbk`, `.fsk`, `.xml`, `.pptx` → the matching stub

If a stub raises `ImportError` or `NotImplementedError`, or if the extension is unknown, `load()` falls back to the TBK loader. That keeps a single entry point while formats are unfinished.

## Model

The shared model is deliberately small:

- A `Book` has pages and optional shells.
- A `Page` has an id, text, items, jumps, an optional quiz, and handlers.
- A `Handler` has a name and source.

TBX extends this with objects (kind, Bounds, Vertices, parent Group) and background references, but the core engine only needs the source text.

## Keyword table

The TBK bytecode path needs a keyword table to expand the compressed handler streams. The original table is NE resource type 0x2d1 / id 0x2d0 in TB80BAS, also present as resource 0x77 in TB80CMP. The package prefers the clean transcription in `core/keywords.py`. `formats/tbk/compat/res_77.bin` is the original binary and is only used when the clean table is missing.
