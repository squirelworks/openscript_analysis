#!/usr/bin/env python3
"""Recreate res_77.bin from embedded base64.

The original keyword resource (TB80CMP resource 0x77) is stored as
base64 in this script so the repo can stay text-only. Run it once
to write formats/tbk/compat/res_77.bin.

Source: copies found in Foolbook/engine/compat/ and the local
openscript_analysis tree (15776 bytes).
"""
import base64
from pathlib import Path

# truncated for tool size; full base64 is in the workspace
# run locally: python3 make_res77.py
B64 = ""

def main():
    out = Path(__file__).parent / "res_77.bin"
    if not B64:
        print("B64 empty; copy the full script from workspace")
        return
    out.write_bytes(base64.b64decode(B64))
    print(f"wrote {out} ({out.stat().st_size} bytes)")

if __name__ == "__main__":
    main()
