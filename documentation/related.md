# Related projects

## Foolbook

https://github.com/squirelworks/Foolbook

Clean-room reader for ToolBook books. Depends on this package for `.tbk` / `.sbk` / `.tbx` script handling. Carries its own `engine/` copy from before the split; the submodule pointer and the `pyproject.toml` dependency are pinned to older tags of this repository. Updating that pin is a separate change.

Foolbook also defines the `.fbk` / `.fsk` envelope (FBK1/FSK1 magic, optional zlib, JSON payload). Those formats are stubs here until the envelope loader is moved across.

## Foolcourse

https://github.com/squirelworks/Foolcourse

Course layer above Foolbook. Depends on Foolbook as a submodule. Does not import this package directly.

## Foolversity

https://github.com/squirelworks/Foolversity

School layer above Foolcourse. Depends on Foolcourse as a submodule. Does not import this package directly.

## toolbookunpacker

https://github.com/squirelworks/toolbookunpacker

OPTLOADER unpacker for the 16-bit NE images (TB80BAS, TB80RTM, TB80CMP, and the satellites). Produces honest NE files for Ghidra. Not a runtime dependency of this package.

## TBpipeline

https://github.com/squirelworks/TBpipeline

Earlier pipeline that opened a `.tbk` and emitted an HTML reader. Superseded for script work by this package and by Foolbook.

## Working papers

The reverse-engineering notes, SoftICE traces, polygon renders, and the TBX analysis dumps live outside this repository. They are the source of the numbers cited in `openscript.md` and `history.md` (page counts, construct counts, the P440/P2920 extras, the twip scale). This package keeps the code; the papers keep the evidence.
