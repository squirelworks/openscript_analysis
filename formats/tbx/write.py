"""Write a book dict as an expanded TBX folder.

The result is a directory, not a zip. Book.xml is the entry.
Each page is PageN/Page.xml plus the .script files beside it.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape


NS = "urn:sumtotalsystems:toolbook.tbkx"
_TWIP = 15


def write_tbx(path: str | Path, book: dict) -> Path:
    """Write the expanded directory. A path ending in .tbx becomes that folder."""
    folder = Path(path)
    if folder.suffix.lower() == ".tbx":
        folder.mkdir(parents=True, exist_ok=True)
    else:
        folder.mkdir(parents=True, exist_ok=True)
    title = escape(str(book.get("title") or folder.name))
    (folder / "Book.xml").write_text(
        f'<?xml version="1.0" encoding="utf-8"?>\n'
        f'<Book xmlns="{NS}" Caption="{title}"/>\n',
        encoding="utf-8",
    )
    for n, page in enumerate(book.get("pages") or [], start=1):
        _write_page(folder / f"Page{n}", page, n)
    return folder


def _write_page(directory: Path, page: dict, number: int) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    name = escape(str(page.get("id") or f"P{number}"))
    parts = [
        '<?xml version="1.0" encoding="utf-8"?>',
        f'<Page xmlns="{NS}" Name="{name}" IdNumber="{number}">',
    ]
    oid = 1
    for block in page.get("text") or []:
        parts.append(
            f'  <Field Name="Text" IdNumber="{oid}"><Text>{escape(str(block))}</Text></Field>'
        )
        oid += 1
    for shape in page.get("shapes") or []:
        piece = _shape_xml(shape, oid)
        if piece:
            parts.append("  " + piece)
            oid += 1
    scripts: list[tuple[str, str]] = []
    for item in page.get("items") or []:
        label = escape(str(item.get("label") or "Go"))
        filename = f"Button{oid}.script"
        parts.append(
            f'  <Button Name="{label}" IdNumber="{oid}" Script="{filename}"/>'
        )
        scripts.append((filename, _button_script(item)))
        oid += 1
    parts.append("</Page>")
    (directory / "Page.xml").write_text("\n".join(parts) + "\n", encoding="utf-8")
    for filename, source in scripts:
        (directory / filename).write_text(source, encoding="utf-8")
    handlers = page.get("handlers") or []
    if page.get("script"):
        handlers = [{"name": "script", "source": page["script"]}]
    if handlers:
        body = "\n\n".join(h.get("source") or "" for h in handlers if h.get("source"))
        if body.strip():
            (directory / "Page.script").write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")


def _button_script(item: dict) -> str:
    target = item.get("page") or ""
    book = item.get("book") or ""
    lines = ["to handle buttonClick"]
    if target and book:
        lines.append(f'  go to page "{target}" of book "{book}"')
    elif target:
        lines.append(f'  go to page "{target}"')
    else:
        lines.append("  -- no target")
    lines.append("end")
    return "\n".join(lines) + "\n"


def _shape_xml(shape: dict, oid: int) -> str:
    kind = (shape.get("kind") or "").lower()
    fill = _fill(shape.get("fill") or "")
    fill_attr = f' FillColor="{fill}"' if fill else ""
    if kind in ("rect", "rectangle", "ellipse", "oval"):
        tag = "Rectangle" if kind in ("rect", "rectangle") else "Ellipse"
        x, y = int(shape.get("x") or 0), int(shape.get("y") or 0)
        w, h = int(shape.get("w") or 0), int(shape.get("h") or 0)
        bounds = f"{x * _TWIP},{y * _TWIP},{(x + w) * _TWIP},{(y + h) * _TWIP}"
        return f'<{tag} IdNumber="{oid}" Bounds="{bounds}"{fill_attr}/>'
    if kind in ("line", "polygon"):
        pts = shape.get("points") or []
        flat = []
        for pt in pts:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                flat.append(str(int(pt[0]) * _TWIP))
                flat.append(str(int(pt[1]) * _TWIP))
        if len(flat) < 4:
            return ""
        tag = "Line" if kind == "line" else "Polygon"
        return f'<{tag} IdNumber="{oid}" Vertices="{",".join(flat)}"{fill_attr}/>'
    return ""


def _fill(value: str) -> str:
    value = value.strip()
    if len(value) == 7 and value.startswith("#"):
        r = int(value[1:3], 16)
        g = int(value[3:5], 16)
        b = int(value[5:7], 16)
        return f"{r},{g},{b}"
    return ""
