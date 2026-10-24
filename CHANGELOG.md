# Changelog

## 1.0.0r29 — 2026-10-25

- The first indent word is the first line, and the second is every line after it. P1's title is 0 then 650, which is what ToolBook's paragraph dialog shows. Every other field in this book has the two words equal.

## 1.0.0r28 — 2026-10-25

- A field's font is the entry `+0x22` points at. The face is the first 32 bytes, the height at +32 is twips (12 point is -240), and bit 0 of the flag at +36 is bold. Bit 1 is italic. A style run that names its own entry replaces that font. A face dword of 1 is a colour change, not a name.

## 1.0.0r27 — 2026-10-25

- The four paragraph words are first-line indent `+0x28`, left indent `+0x2A`, right indent `+0x2C`, and tab spacing `+0x2E`. On the P400 body field those are 360, 360, 310 and 720, which is what ToolBook's paragraph dialog shows. The tab is not an inset.
- A field with no style runs takes its face from the name pointer at `+0x22`. That field's face is Arial. The bold flag and the 12-point size are not in these words.

## 1.0.0r26 — 2026-10-25

- A field keeps the left and right margin words at `+0x28` and `+0x2A`. On the Logic Families book those are 720 for the copyright and 360 for the body panels.
- `write_store` writes an object store: directory, segments, one field per page, text in a trailer. `splice_text` replaces a string of the same length inside a book that already opens. Neither one writes a script. A script ToolBook runs is still TB80CMP bytecode.

## 1.0.0r25 — 2026-10-24

- A group's buttonClick is not written into a child that already has a script. On P300 the field Selection1 keeps its mouse handlers. The button, which had none, keeps the jump.

## 1.0.0r24 — 2026-10-24

- A background object is marked `layer: background`. A page object is marked `layer: page`. The two lists used to be one list with nothing saying which was which.

## 1.0.0r23 — 2026-10-24

- Background scripts that are tokenized, including the Test background, are read. That script is `get handleQuizClick(target)`.
- A quiz page's Answer, QuestionNo and TestNo are read from the property block just after the segment.

## 1.0.0r22 — 2026-10-24

- A paint object is the bitmap it points at. The full-page picture on P450 was being drawn as a white rectangle.

## 1.0.0r21 — 2026-10-24

- A group's buttonClick is kept on the children that do not have their own. A menu picture jumps to the page the group names.
- A page and its background keep their own scripts. A click on P0 or P1 can send next.

## 1.0.0r20 — 2026-10-22

- A field's style run points at the face name. Wingdings `w` is a bullet. An Arial `w` stays a letter.

## 1.0.0r19 — 2026-10-22

- An arc has no pattern byte. The endpoints are the two points at `+0x25`, on the ellipse at `+0x2D`. Mapped onto the bounds they match the exported vertices. `drawDirect` is bit `0x20` of `+0x1F`.

## 1.0.0r18 — 2026-10-22

- Class `0x11` is an arc. The two ray words are at `+0x26` and `+0x2A`. The pattern byte at `+0x25` is kept.

## 1.0.0r17 — 2026-10-22

- A button records whether it is transparent. The header faces are.

## 1.0.0r16 — 2026-10-22

- A field keeps the fill at `+0x1B` unless it is transparent or has no pattern. The frame is the byte at `+0x36`: none, rectangle, scrolling, shadowed, raised, or inset. The stroke stays the text colour.

## 1.0.0r15 — 2026-10-22

- A button's face follows `+0x26`. Bit `0x01` clear is the disabled face, bit `0x04` is the down face, and bit `0x10` on a check box or radio button is the checked face. Anything else is the up face.
- A bitmap with bit 0 set at resource `+0x08` is a row of the table at header `+0x104`. The word at resource `+0x09` is the row, and the row's file offset is the same 8-byte prefix as an inline bitmap. All 67 bitmaps in `9e954d01.tbk` open.

## 1.0.0r14 — 2026-10-22

- A field's horizontal alignment is the byte at `+0x26`. 0 is the left, 1 the right, 2 the centre.

## 1.0.0r13 — 2026-10-22

- `read_store` walks a ToolBook 8 object store. The page list is book `+0x10`. Field text is the trailer handle in word 1 of object `+0x24`. Class `0x10` points are the block at `+0x32`, mapped onto the bounds. A bitmap directory id is the fourth word of the 8-byte entry.

## 1.0.0r12 — 2026-10-21

- A 1,275 by 300 twip box at 0,30 does not replace the real field. On P1085 the definition keeps the 8,205 by 1,890 box.

## 1.0.0r11 — 2026-10-21

- `find_streams` walks the whole book. A handler may start with the plain words `to handle`, `to get`, or `to set`, or with those words compressed. A stream inside a page belongs to that page. A stream outside every page is the book script.

## 1.0.0r10 — 2026-10-21

- A TBKX zip is read the same way as the unpacked folder. The archive is unpacked once, and a member that escapes the folder is rejected.
- The settled book keeps the book script and each page script. A page with no name uses its folder name. A button keeps its script.

## 1.0.0r9 — 2026-10-20

- The TBK expander reads resource 0x77 the way FUN_1040_0970 does. The count is the word at byte 0. Keywords are indexed by id (`to`, `handle`, `end`, `system` at 564). A back-reference copies from the input stream. `0xFF` repeats the next byte, count plus one. The fallback list is that same 994-word table, because `res_77.bin` is not in the tree.
- A back-reference that lands on another back-reference is not followed. The `EnterPage` handler in `9e954d01.tbk` does not need that chase.

## 1.0.0r8

- A TBK page is replayed before it is drawn. A later copy of the same object id replaces the earlier one. What remains has the bounds the record stored, in twips.
- Field text and button names come from the property key on that record. A button script between that widget and the next one is returned for the viewer to run.
- A quiz answer is the page's Answer property. Grading it is still `core.quiz`.

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
