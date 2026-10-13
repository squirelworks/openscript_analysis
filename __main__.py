"""openscript_analysis entry.

  python3 -m openscript_analysis --freshstart
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if "--freshstart" in argv:
        return _freshstart()
    if "--doctor" in argv:
        from openscript_analysis._debug import run
        return run()
    print("openscript_analysis")
    print("  python3 -m openscript_analysis --freshstart")
    return 0


def _freshstart() -> int:
    """Force-reinstall this package."""
    import subprocess
    cmd = [
        sys.executable, "-m", "pip", "install", "--force-reinstall",
        "git+https://github.com/squirelworks/openscript_analysis.git@v1.0.0",
    ]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
