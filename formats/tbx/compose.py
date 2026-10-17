"""Settle a TBX before anyone sees it.

ToolBook reads the whole file, then applies what the book itself says.
Book.Pages is that settled list. A page folder that is not in the list
is not part of the book the viewer gets.

Each page the viewer gets is one surface: the background's objects, then
the page's objects on top. Text, graphics, and buttons all have bounds.
A button's caption and its NormalGraphic are what the book stored.
"""

from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree as ET

from ...core.quiz import answer_of, is_quiz

NS = "urn:sumtotalsystems:toolbook.tbkx"
TWIP = 15


def settle(path: str | Path) -> dict:
    root = _book_root(Path(path))
    book_xml = root / "Book.xml"
    if not book_xml.is_file():
        raise FileNotFoundError(f"No Book.xml in {root}")
    book_el = ET.parse(book_xml).getroot()
    title = book_el.get("Caption") or book_el.get("Title") or root.name
    page_w, page_h = _size(book_el.get("Size") or "")
    bitmaps = _bitmaps(book_el, root)
    scripts = _scripts(root)
    backgrounds = {}
    for bg_path in root.rglob("Background.xml"):
        el = ET.parse(bg_path).getroot()
        made = _unit(el, bg_path.parent, scripts, bitmaps)
        if made["id"]:
            backgrounds[made["id"]] = made
        if made["name"]:
            backgrounds[made["name"]] = made
    pages_by_source = {}
    for page_path in root.rglob("Page.xml"):
        rel = page_path.relative_to(root).as_posix()
        pages_by_source[rel.lower()] = page_path
    order = _locators(book_el)
    if not order:
        order = sorted(pages_by_source)
    pages = []
    for source in order:
        page_path = pages_by_source.get(source.lower())
        if page_path is None:
            continue
        el = ET.parse(page_path).getroot()
        page = _unit(el, page_path.parent, scripts, bitmaps)
        bg_key = _bg_key(el.get("Background") or "")
        bg = backgrounds.get(bg_key) or backgrounds.get(el.get("Background") or "")
        objects = list(bg["objects"]) if bg else []
        objects.extend(page["objects"])
        props = page["props"]
        quiz = None
        if is_quiz(props):
            quiz = {"answer": answer_of(props), "prompt": _prompt(objects)}
        pages.append({
            "id": page["name"] or page["id"] or page_path.parent.name,
            "text": [obj["text"] for obj in objects if obj["kind"] == "text" and obj.get("text")],
            "items": [obj["item"] for obj in objects if obj.get("item")],
            "shapes": objects,
            "objects": objects,
            "quiz": quiz,
            "settled": True,
            "size": [page_w, page_h],
        })
    _bind(pages)
    return {
        "title": title,
        "size": [page_w, page_h],
        "pages": pages,
        "settled": True,
    }


def _book_root(path: Path) -> Path:
    cur = path if path.is_dir() else path.parent
    for _ in range(6):
        if (cur / "Book.xml").is_file():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return path if path.is_dir() else path.parent


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _size(value: str) -> tuple[int, int]:
    parts = _px(value)
    if len(parts) >= 2:
        return parts[0], parts[1]
    return 624, 442


def _px(value: str) -> list[int]:
    out = []
    for part in (value or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(round(float(part) / TWIP)))
        except ValueError:
            return []
    return out


def _box(bounds: str) -> dict | None:
    nums = _px(bounds)
    if len(nums) < 4:
        return None
    left, top, right, bottom = nums[:4]
    return {
        "x": min(left, right),
        "y": min(top, bottom),
        "w": abs(right - left),
        "h": abs(bottom - top),
    }


def _color(value: str) -> str:
    parts = [p.strip() for p in (value or "").split(",")]
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        r, g, b = (max(0, min(255, int(p))) for p in parts)
        return f"#{r:02x}{g:02x}{b:02x}"
    return ""


def _words(value: str) -> str:
    text = (value or "").replace("{CRLF}", "\n")
    text = re.sub(r"\{[^{}]*\}", "", text)
    return text.strip()


def _bitmaps(book_el: ET.Element, root: Path) -> dict[str, str]:
    found = {}
    for el in book_el.iter():
        if _local(el.tag) != "Bitmap":
            continue
        bid = el.get("IdNumber") or ""
        src = el.get("Source") or ""
        if not bid or not src:
            continue
        path = root / src
        found[bid] = str(path if path.is_file() else src)
    return found


def _scripts(root: Path) -> dict[str, str]:
    found = {}
    for path in root.rglob("*.script"):
        found[path.name.lower()] = path.read_text(encoding="utf-8", errors="replace")
    return found


def _locators(book_el: ET.Element) -> list[str]:
    order = []
    for el in book_el.iter():
        if _local(el.tag) != "PageLocator":
            continue
        source = (el.get("Source") or "").replace("\\", "/")
        if source:
            order.append(source)
    return order


def _bg_key(value: str) -> str:
    match = re.search(r"(\d+)\s*$", value or "")
    return match.group(1) if match else value


def _unit(el: ET.Element, folder: Path, scripts: dict[str, str], bitmaps: dict[str, str]) -> dict:
    props = {}
    for child in el.iter():
        if _local(child.tag) == "UserProperty" and child.get("Name"):
            props[child.get("Name") or ""] = child.get("Value") or ""
    objects = []
    for child in el.iter():
        tag = _local(child.tag)
        if tag in ("UserProperty", "Page", "Background", "Book"):
            continue
        obj = _object(tag, child, folder, scripts, bitmaps)
        if obj:
            objects.append(obj)
    return {
        "id": el.get("IdNumber") or "",
        "name": el.get("Name") or "",
        "props": props,
        "objects": objects,
    }


def _object(tag: str, el: ET.Element, folder: Path, scripts: dict[str, str], bitmaps: dict[str, str]) -> dict | None:
    kind = tag.lower()
    if kind in ("userproperties", "page.objects", "background.objects", "page.userproperties", "background.userproperties"):
        return None
    box = _box(el.get("Bounds") or "")
    if box is None and kind not in ("field", "button", "rectangle", "ellipse", "polygon", "line", "recordfield", "roundrect"):
        return None
    if box is None:
        return None
    visible = (el.get("Visible") or "true").lower() != "false"
    fill = _color(el.get("RgbFill") or el.get("FillColor") or "")
    outline = _color(el.get("RgbStroke") or el.get("LineColor") or "")
    base = {
        **box,
        "name": el.get("Name") or "",
        "visible": visible,
        "fill": fill,
        "outline": outline,
        "font": el.get("FontFace") or "",
        "size": _font_size(el.get("FontSize") or ""),
        "bold": "bold" in (el.get("FontStyle") or "").lower(),
    }
    if kind in ("field", "recordfield"):
        return {**base, "kind": "text", "text": _words(el.get("Text") or "")}
    if kind == "button":
        caption = _words(el.get("Caption") or "")
        graphic = _graphic(el.get("NormalGraphic") or "", bitmaps)
        script = _script_of(el, folder, scripts)
        item = _jump(base["name"] or caption, script)
        return {
            **base,
            "kind": "button",
            "text": caption or base["name"],
            "src": graphic,
            "item": item,
        }
    if kind in ("rectangle", "roundrect"):
        return {**base, "kind": "rect"}
    if kind in ("ellipse", "oval"):
        return {**base, "kind": "ellipse"}
    if kind in ("line", "angledline"):
        pts = _pairs(el.get("Vertices") or "")
        if len(pts) < 2:
            return None
        return {**base, "kind": "line", "points": pts, "outline": outline or "#000000"}
    if kind in ("polygon", "irregularpolygon"):
        pts = _pairs(el.get("Vertices") or "")
        if len(pts) < 3:
            return None
        return {**base, "kind": "polygon", "points": pts}
    return None


def _font_size(value: str) -> int:
    try:
        return max(8, int(float(value)))
    except ValueError:
        return 12


def _graphic(value: str, bitmaps: dict[str, str]) -> str:
    match = re.search(r"(\d+)\s*$", value or "")
    if not match:
        return ""
    return bitmaps.get(match.group(1), "")


def _pairs(value: str) -> list[list[int]]:
    nums = _px(value)
    return [[nums[i], nums[i + 1]] for i in range(0, len(nums) - 1, 2)]


def _script_of(el: ET.Element, folder: Path, scripts: dict[str, str]) -> str:
    name = (el.get("Script") or "").replace("\\", "/").split("/")[-1]
    if name:
        direct = folder / name
        if direct.is_file():
            return direct.read_text(encoding="utf-8", errors="replace")
        return scripts.get(name.lower(), "")
    shared = el.get("SharedScript") or ""
    match = re.search(r"(\d+)\s*$", shared)
    if match:
        return scripts.get(f"sharedscript{match.group(1)}.script", "")
    return ""


def _jump(label: str, script: str) -> dict | None:
    if not script:
        return None
    match = re.search(r'go\s+to\s+page\s+"([^"]+)"(?:\s+of\s+book\s+"([^"]+)")?', script, re.I)
    if not match and not re.search(r"send\s+(next|previous|back)", script, re.I):
        return None
    item = {"label": label or (match.group(1) if match else "Go"), "page": match.group(1) if match else ""}
    if match and match.group(2):
        item["book"] = match.group(2)
    low = script.lower()
    if not item["page"] and "send next" in low:
        item["label"] = "Next"
    if not item["page"] and ("send previous" in low or "send back" in low):
        item["label"] = "Back"
    return item


def _bind(pages: list[dict]) -> None:
    ids = [page["id"] for page in pages]
    for i, page in enumerate(pages):
        for item in page["items"]:
            if item.get("page"):
                continue
            label = (item.get("label") or "").lower()
            if label == "next" and i + 1 < len(ids):
                item["page"] = ids[i + 1]
            elif label in ("back", "previous") and i > 0:
                item["page"] = ids[i - 1]


def _prompt(objects: list[dict]) -> str:
    for obj in objects:
        if obj.get("kind") == "text" and obj.get("name", "").lower() in ("stem", "question", "prompt"):
            return obj.get("text") or ""
    for obj in objects:
        if obj.get("kind") == "text" and obj.get("text"):
            return obj["text"]
    return ""
