"""TBX OpenScript engine.

Loads a SumTotal ToolBook TBKX export folder, or a zip of that folder, and
interprets the plain-text .script files that accompany Book.xml / Page.xml /
Background.xml.

Page keys are the XML Name attribute (P1040, P430, ...), not the folder name.
Backgrounds are loaded the same way. Page.Objects are walked for kind, Name,
Bounds, Vertices, and parent Group. Bitmap references are recorded.
Export-only pages (P440, P2920 in the 9e954d01 corpus) are flagged.

Runner covers the subset that appears in the Nida lessons:
  go to page / of book, send, assignment, get/set, put,
  if/else/end if (nested), conditions/when, increment, step, forward.
Handler lookup is case-insensitive.

report() and coverage() emit the jump graph and construct counts.
"""

from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Pages present in the TBX export of 9e954d01 but not in the raw TBK.
EXPORT_ONLY = {"P440", "P2920"}


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


@dataclass
class TbxObject:
    kind: str
    name: str = ""
    bounds: str = ""
    vertices: str = ""
    parent: str = ""
    fill: str = ""
    script_file: str | None = None
    id_number: str = ""
    text: str = ""


@dataclass
class TbxPage:
    id_number: str
    name: str
    background: str = ""
    script_file: str | None = None
    objects: list[TbxObject] = field(default_factory=list)
    export_only: bool = False


@dataclass
class TbxBook:
    path: str
    title: str = ""
    pages: dict[str, TbxPage] = field(default_factory=dict)
    backgrounds: dict[str, TbxPage] = field(default_factory=dict)
    scripts: dict[str, str] = field(default_factory=dict)
    bitmaps: dict[str, str] = field(default_factory=dict)  # id -> Source file


@dataclass
class RuntimeState:
    book: TbxBook
    page: str = ""
    variables: dict[str, Any] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)

    def note(self, msg: str) -> None:
        self.log.append(msg)


MARK = "urn:sumtotalsystems:toolbook.tbkx"
_TWIP = 15
_UNPACK_LIMIT = 512 * 1024 * 1024
_unpacked: dict[tuple, Path] = {}


def _is_zip(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.suffix.lower() not in {".zip", ".tbkx"} and not path.name.lower().endswith(".tbkx.zip"):
        return False
    return zipfile.is_zipfile(path)


def _unsafe_member(name: str) -> bool:
    name = name.replace("\\", "/")
    if name.startswith("/") or (len(name) >= 2 and name[1] == ":"):
        return True
    return ".." in Path(name).parts


def _zip_book_member(path: Path) -> str | None:
    """Archive member of Book.xml, if this zip is a TBX export."""
    try:
        with zipfile.ZipFile(path) as zf:
            names = []
            for info in zf.infolist():
                name = info.filename.replace("\\", "/")
                if info.is_dir() or _unsafe_member(name):
                    continue
                if not name.rstrip("/").lower().endswith("book.xml"):
                    continue
                names.append(name)
            names.sort(key=lambda n: (n.count("/"), len(n)))
            for name in names:
                head = zf.read(name)[:4096].decode("utf-8", errors="replace")
                if MARK in head:
                    return name
    except (zipfile.BadZipFile, OSError, ValueError):
        return None
    return None


def _materialize(path: Path) -> Path:
    """Unpack a zipped TBX once and return the folder that holds Book.xml."""
    member = _zip_book_member(path)
    if member is None:
        raise FileNotFoundError(f"No Book.xml in {path}")
    st = path.stat()
    key = (str(path.resolve()), st.st_mtime_ns, st.st_size)
    cached = _unpacked.get(key)
    if cached is not None and (cached / "Book.xml").is_file():
        return cached
    dest = Path(tempfile.mkdtemp(prefix="tbx-"))
    dest_resolved = dest.resolve()
    with zipfile.ZipFile(path) as zf:
        total = 0
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if not name or name.endswith("/") or info.is_dir():
                continue
            if _unsafe_member(name):
                raise ValueError(f"unsafe path in {path.name}: {info.filename}")
            # A Unix symlink is mode 0120000 in the high half of external_attr.
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                continue
            total += info.file_size
            if total > _UNPACK_LIMIT:
                raise ValueError(f"{path.name} is too large to unpack")
            target = (dest / name).resolve()
            if dest_resolved != target and dest_resolved not in target.parents:
                raise ValueError(f"unsafe path in {path.name}: {info.filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
    book = dest / Path(member).parent
    if not (book / "Book.xml").is_file():
        raise FileNotFoundError(f"No Book.xml in {path}")
    _unpacked[key] = book
    return book


def is_tbx(path: str | Path) -> bool:
    """True for a TBX folder, an XML file inside one, or a zip of that folder."""
    path = Path(path)
    if _is_zip(path):
        return _zip_book_member(path) is not None
    if path.is_dir():
        path = path / "Book.xml"
    if path.suffix.lower() != ".xml" or not path.is_file():
        return False
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:4096]
    except OSError:
        return False
    return MARK in head


def book_root(path: str | Path) -> Path:
    """Folder that holds Book.xml, walking up from the file that was opened.

    A zipped export is unpacked into a temporary folder first. The folder
    itself is unchanged.
    """
    path = Path(path)
    if _is_zip(path) and _zip_book_member(path) is not None:
        return _materialize(path)
    cur = path if path.is_dir() else path.parent
    for _ in range(6):
        if (cur / "Book.xml").is_file():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return path if path.is_dir() else path.parent


def load_tbx(folder: str | Path) -> TbxBook:
    """Load a TBKX export folder, or an XML file inside one."""
    root = book_root(folder) if not Path(folder).is_dir() else Path(folder)
    if (root / "Book.xml").is_file() or not root.is_dir():
        root = book_root(folder)
    book = TbxBook(path=str(root))
    book_xml = root / "Book.xml"
    if book_xml.exists():
        tree = ET.parse(book_xml)
        root_el = tree.getroot()
        book.title = root_el.get("Caption") or root_el.get("Title") or ""
        for el in root_el.iter():
            if _local(el.tag) == "Bitmap":
                bid = el.get("IdNumber") or el.get("Id") or ""
                src = el.get("Source") or ""
                if bid and src:
                    book.bitmaps[bid] = src
    for page_xml in sorted(root.rglob("Page.xml"), key=lambda p: str(p.parent).lower()):
        page = _load_page(page_xml)
        if page:
            book.pages[page.name] = page
    for bg_xml in sorted(root.rglob("Background.xml"), key=lambda p: str(p.parent).lower()):
        bg = _load_page(bg_xml)
        if bg:
            book.backgrounds[bg.name or bg.id_number] = bg
    for script in root.rglob("*.script"):
        book.scripts[script.name] = script.read_text(encoding="utf-8", errors="replace")
    return book


def _load_page(xml_path: Path) -> TbxPage | None:
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError:
        return None
    el = tree.getroot()
    name = el.get("Name") or xml_path.parent.name
    page = TbxPage(
        id_number=el.get("IdNumber") or "",
        name=name,
        background=el.get("Background") or "",
        script_file=el.get("Script") or None,
        export_only=name in EXPORT_ONLY,
    )
    objs = el.find(".//{urn:sumtotalsystems:toolbook.tbkx}Page.Objects")
    if objs is None:
        objs = el.find(".//{urn:sumtotalsystems:toolbook.tbkx}Background.Objects")
    if objs is None:
        objs = el
    page.objects = _walk_objects(objs, parent="")
    if not page.script_file:
        for script in sorted(xml_path.parent.glob("*.script")):
            if not script.name.lower().startswith("button"):
                page.script_file = script.name
                break
    return page


def _walk_objects(el: ET.Element, parent: str) -> list[TbxObject]:
    out: list[TbxObject] = []
    for child in el:
        tag = _local(child.tag)
        if tag in ("Page.Objects", "Background.Objects", "Group.Objects", "UserProperties"):
            continue
        name = child.get("Name") or ""
        obj = TbxObject(
            kind=tag,
            name=name,
            bounds=child.get("Bounds") or "",
            vertices=child.get("Vertices") or "",
            parent=parent,
            fill=child.get("FillColor") or child.get("Fill") or "",
            script_file=child.get("Script") or None,
            id_number=child.get("IdNumber") or "",
            text=_object_text(child) if tag == "Field" else "",
        )
        out.append(obj)
        # recurse into groups
        for sub in child:
            if _local(sub.tag) in ("Group.Objects", "Objects"):
                out.extend(_walk_objects(sub, parent=name or tag))
    return out


def _object_text(el: ET.Element) -> str:
    for key in ("Text", "RichText", "Caption"):
        if el.get(key):
            return _plain(el.get(key) or "")
    chunks = []
    for child in list(el):
        if _local(child.tag).lower() in ("text", "richtext", "para", "paragraph"):
            chunks.append(_plain("".join(child.itertext())))
    if chunks:
        return " ".join(part for part in chunks if part)
    return _plain("".join(el.itertext()))


def _plain(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", value).strip()


def _px(value: str) -> list[int]:
    out = []
    for part in (value or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(float(part) / _TWIP))
        except ValueError:
            return []
    return out


def _color(value: str) -> str:
    parts = [p.strip() for p in (value or "").split(",")]
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        r, g, b = (max(0, min(255, int(p))) for p in parts)
        return f"#{r:02x}{g:02x}{b:02x}"
    return value if value.startswith("#") else ""


def _shape(obj: TbxObject) -> dict | None:
    kind = obj.kind.lower()
    bounds = _px(obj.bounds)
    nums = _px(obj.vertices)
    points = [[nums[i], nums[i + 1]] for i in range(0, len(nums) - 1, 2)]
    fill = _color(obj.fill)
    if kind in ("rectangle", "roundrect") and len(bounds) >= 4:
        left, top, right, bottom = bounds[:4]
        return {"kind": "rect", "x": min(left, right), "y": min(top, bottom), "w": abs(right - left), "h": abs(bottom - top), "fill": fill, "outline": fill}
    if kind in ("ellipse", "oval") and len(bounds) >= 4:
        left, top, right, bottom = bounds[:4]
        return {"kind": "ellipse", "x": min(left, right), "y": min(top, bottom), "w": abs(right - left), "h": abs(bottom - top), "fill": fill, "outline": fill}
    if kind in ("line", "angledline") and len(points) >= 2:
        return {"kind": "line", "points": points, "outline": "#000000"}
    if kind in ("irregularpolygon", "polygon") and len(points) >= 3:
        return {"kind": "polygon", "points": points, "fill": fill, "outline": fill}
    return None


def _handlers(source: str) -> list[dict]:
    found = []
    for part in re.split(r"(?im)^[ \t]*to handle[ \t]+", source or "")[1:]:
        name = part.split(None, 1)[0].strip() if part.split() else ""
        if name:
            found.append({"name": name, "source": "to handle " + part.strip()})
    return found


def _button(obj: TbxObject, script: str) -> dict | None:
    low = (script or "").lower()
    match = re.search(r'go\s+to\s+page\s+"([^"]+)"(?:\s+of\s+book\s+"([^"]+)")?', script or "", re.I)
    target = match.group(1) if match else ""
    other = match.group(2) if match and match.group(2) else ""
    if "go to next page" in low or (not target and "send next" in low):
        label = "Next"
    elif "go to previous" in low or "send previous" in low or "send back" in low:
        label = "Back"
    else:
        label = obj.name or target
    if not label:
        return None
    return {"label": label, "page": target, "book": other, "script": script}


def to_book_dict(book: TbxBook) -> dict:
    """The TBX as the page dict Foolbook already displays."""
    pages = []
    for page in book.pages.values():
        text = [obj.text for obj in page.objects if obj.kind == "Field" and obj.text]
        shapes = [s for obj in page.objects if (s := _shape(obj))]
        items = []
        for obj in page.objects:
            if obj.kind != "Button":
                continue
            script = ""
            if obj.script_file:
                script = book.scripts.get(Path(obj.script_file).name, "")
            if not script and obj.id_number:
                script = book.scripts.get(f"Button{obj.id_number}.script", "")
            item = _button(obj, script)
            if item:
                items.append(item)
        source = book.scripts.get(Path(page.script_file).name, "") if page.script_file else ""
        pages.append({
            "id": page.name,
            "text": text,
            "items": items,
            "shapes": shapes,
            "handlers": _handlers(source),
        })
    ids = [p["id"] for p in pages]
    for i, page in enumerate(pages):
        for item in page["items"]:
            if item.get("page"):
                item.pop("script", None)
                continue
            low = (item.get("script") or "").lower()
            if ("send next" in low or "go to next page" in low) and i + 1 < len(ids):
                item["page"] = ids[i + 1]
            elif ("send previous" in low or "go to previous" in low or "send back" in low) and i > 0:
                item["page"] = ids[i - 1]
            item.pop("script", None)
    return {"title": book.title, "pages": pages}


def run_script(state: RuntimeState, source: str) -> list[dict]:
    """Interpret a plain-text OpenScript handler."""
    actions: list[dict] = []
    if not source:
        return actions
    lines = _normalize(source)
    _run_block(state, lines, 0, len(lines), actions)
    return actions


def _normalize(source: str) -> list[str]:
    out = []
    for raw in source.replace("\r", "").split("\n"):
        line = raw.strip()
        if not line or line.startswith("--"):
            continue
        low = line.lower()
        if low.startswith("to handle") or low.startswith("system "):
            continue
        if low in ("end", "end handler", "end if", "end conditions"):
            out.append(line)  # keep structural ends for the runner
            if low in ("end", "end handler"):
                break
            continue
        out.append(line)
    return out


def _run_block(state: RuntimeState, lines: list[str], start: int, end: int, actions: list[dict]) -> int:
    i = start
    while i < end:
        line = lines[i]
        low = line.lower()
        if low.startswith("go to page"):
            m = re.search(r'"([^"]+)"', line)
            if m:
                book_m = re.search(r'of book "([^"]+)"', line, re.I)
                actions.append({
                    "kind": "goto",
                    "page": m.group(1),
                    "book": book_m.group(1) if book_m else None,
                })
            i += 1
            continue
        if low.startswith("send "):
            actions.append({"kind": "send", "name": line.split(None, 1)[1].lower()})
            i += 1
            continue
        if low.startswith("forward"):
            actions.append({"kind": "forward"})
            i += 1
            continue
        if low.startswith("get "):
            actions.append({"kind": "get", "expr": line[4:].strip()})
            i += 1
            continue
        if low.startswith("set "):
            actions.append({"kind": "set", "expr": line[4:].strip()})
            i += 1
            continue
        if low.startswith("increment "):
            name = line.split(None, 1)[1].strip()
            actions.append({"kind": "increment", "name": name})
            i += 1
            continue
        if low.startswith("step "):
            actions.append({"kind": "step", "expr": line[5:].strip()})
            i += 1
            continue
        if low.startswith("if "):
            i = _run_if(state, lines, i, end, actions)
            continue
        if low.startswith("conditions"):
            i = _run_conditions(state, lines, i, end, actions)
            continue
        if " = " in line and not low.startswith("if "):
            name, expr = line.split("=", 1)
            state.variables[name.strip()] = expr.strip()
            i += 1
            continue
        state.note(f"skip: {line}")
        i += 1
    return i


def _run_if(state: RuntimeState, lines: list[str], start: int, end: int, actions: list[dict]) -> int:
    """Handle if / else / end if. Condition is recorded, not evaluated."""
    actions.append({"kind": "if", "cond": lines[start][3:].strip()})
    i = start + 1
    depth = 1
    while i < end and depth > 0:
        low = lines[i].lower()
        if low.startswith("if "):
            depth += 1
        elif low == "end if":
            depth -= 1
            if depth == 0:
                i += 1
                break
        elif low == "else" and depth == 1:
            actions.append({"kind": "else"})
            i += 1
            continue
        else:
            i = _run_block(state, lines, i, i + 1, actions)
            continue
        i += 1
    actions.append({"kind": "end if"})
    return i


def _run_conditions(state: RuntimeState, lines: list[str], start: int, end: int, actions: list[dict]) -> int:
    actions.append({"kind": "conditions"})
    i = start + 1
    while i < end:
        low = lines[i].lower()
        if low == "end conditions":
            actions.append({"kind": "end conditions"})
            return i + 1
        if low.startswith("when "):
            actions.append({"kind": "when", "cond": lines[i][5:].strip()})
            i += 1
            continue
        i = _run_block(state, lines, i, i + 1, actions)
    return i


def report(book: TbxBook) -> dict:
    """Jump graph and handler counts from a loaded book."""
    handlers: Counter = Counter()
    gotos: Counter = Counter()
    books: Counter = Counter()
    for name, src in book.scripts.items():
        for m in re.finditer(r"to handle (\w+)", src, re.I):
            handlers[m.group(1).lower()] += 1
        for m in re.finditer(r'go to page "([^"]+)"(?: of book "([^"]+)")?', src, re.I):
            gotos[m.group(1)] += 1
            if m.group(2):
                books[m.group(2)] += 1
    return {
        "pages": len(book.pages),
        "backgrounds": len(book.backgrounds),
        "bitmaps": len(book.bitmaps),
        "handlers": handlers.most_common(),
        "goto_targets": gotos.most_common(20),
        "external_books": dict(books),
        "export_only": [p.name for p in book.pages.values() if p.export_only],
    }


def coverage(book: TbxBook) -> dict:
    """Construct counts across all scripts. Useful as a regression check."""
    counts: Counter = Counter()
    pats = {
        "if": r"\bif\b",
        "else": r"\belse\b",
        "conditions": r"\bconditions\b",
        "when": r"\bwhen\b",
        "step": r"\bstep\b",
        "increment": r"\bincrement\b",
        "set": r"\bset\b",
        "get": r"\bget\b",
        "forward": r"\bforward\b",
        "put": r"\bput\b",
    }
    for src in book.scripts.values():
        low = src.lower()
        for name, pat in pats.items():
            counts[name] += len(re.findall(pat, low))
    return dict(counts.most_common())


def main():
    import argparse, json
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--page")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--coverage", action="store_true")
    args = ap.parse_args()
    book = load_tbx(args.folder)
    if args.list:
        for name in sorted(book.pages):
            flag = " *" if book.pages[name].export_only else ""
            print(f"{name}{flag}")
        return
    if args.report:
        print(json.dumps(report(book), indent=2))
        return
    if args.coverage:
        print(json.dumps(coverage(book), indent=2))
        return
    if args.page:
        page = book.pages.get(args.page)
        if not page or not page.script_file:
            print(f"no script for {args.page}")
            return
        src = book.scripts.get(page.script_file, "")
        state = RuntimeState(book=book, page=args.page)
        actions = run_script(state, src)
        print(json.dumps(actions, indent=2))
    else:
        print("Use --page P900, --list, --report, or --coverage")


if __name__ == "__main__":
    main()
