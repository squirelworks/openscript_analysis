"""openscript_analysis diagnostics.

  python3 -m openscript_analysis --doctor
"""

from __future__ import annotations

import sys
from pathlib import Path


def run() -> int:
    print("openscript_analysis doctor")
    print(f"  python: {sys.version.split()[0]}")
    print(f"  executable: {sys.executable}")
    here = Path(__file__).resolve().parent
    print(f"  package: {here}")
    for sub in ("core", "formats"):
        p = here / sub
        print(f"  {sub}: exists={p.exists()}")
    return 0
