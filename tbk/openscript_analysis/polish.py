"""Polish expanded OpenScript into readable source."""

import re

def polish(src: str) -> str:
    if not src:
        return ""
    # Collapse runs of whitespace that the expander left behind
    src = re.sub(r"[ \t]+\n", "\n", src)
    src = re.sub(r"\n{3,}", "\n\n", src)
    return src.strip()
