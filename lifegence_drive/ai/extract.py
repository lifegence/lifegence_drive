# Copyright (c) 2026, Lifegence Corporation and Contributors
# See license.txt
"""Plain text out of the office files people keep in Drive, for the AI agent to read.

No Frappe import here, so the parsing can be tested on its own. Word, PowerPoint and Excel
files are zip packages of XML: they are read with zipfile + defusedxml (no python-docx /
python-pptx dependency, and no entity expansion from a hostile file). PDF goes through
PyMuPDF, which Drive already depends on for thumbnails.

The text keeps just enough structure for a model to follow: headings as `#`, list items as
`-`, table rows as `a | b | c`, one section per slide / sheet / page.
"""

from __future__ import annotations

import io
import posixpath
import re
import zipfile
from xml.etree.ElementTree import ParseError

from defusedxml import DefusedXmlException, ElementTree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PR = "{http://schemas.openxmlformats.org/package/2006/relationships}"

# A package part bigger than this is refused rather than parsed (zip bombs).
MAX_PART_BYTES = 64 * 1024 * 1024
MAX_XLSX_ROWS_PER_SHEET = 5000

TEXT_EXTENSIONS = {
    "txt",
    "md",
    "csv",
    "tsv",
    "json",
    "xml",
    "html",
    "htm",
    "log",
    "yaml",
    "yml",
}
OFFICE_EXTENSIONS = {"docx", "docm", "pptx", "pptm", "xlsx", "xlsm"}
LEGACY_EXTENSIONS = {"doc", "xls", "ppt"}


class UnsupportedFormat(Exception):
    """The file type has no text extractor here."""


def extension(file_name: str) -> str:
    return file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""


def extract_text(data: bytes, file_name: str) -> tuple[str, str]:
    """(text, format) for the file's bytes. Raises UnsupportedFormat for anything else."""
    ext = extension(file_name)
    if ext in ("docx", "docm"):
        return _docx(data), "docx"
    if ext in ("pptx", "pptm"):
        return _pptx(data), "pptx"
    if ext in ("xlsx", "xlsm"):
        return _xlsx(data), "xlsx"
    if ext == "pdf":
        return _pdf(data), "pdf"
    if ext in TEXT_EXTENSIONS:
        return _decode(data), "text"
    if ext in LEGACY_EXTENSIONS:
        raise UnsupportedFormat(
            f".{ext} is the old binary Office format; save it as .{ext}x to let the assistant read it"
        )
    raise UnsupportedFormat(f"no text extractor for .{ext or '(no extension)'} files")


# --- helpers ---------------------------------------------------------------------------------


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp932"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _read_part(z: zipfile.ZipFile, name: str):
    info = z.getinfo(name)
    if info.file_size > MAX_PART_BYTES:
        raise UnsupportedFormat(f"{name} is too large to read ({info.file_size} bytes)")
    try:
        return ElementTree.fromstring(z.read(name))
    except (ParseError, DefusedXmlException) as e:
        raise UnsupportedFormat(
            f"{name} could not be read safely ({type(e).__name__})"
        ) from e


def _open(data: bytes) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise UnsupportedFormat("the file is not a valid Office package") from e


def _rels(z: zipfile.ZipFile, part: str) -> dict[str, str]:
    """{rId: target part path} from the part's .rels file."""
    folder, base = posixpath.split(part)
    rels_name = posixpath.join(folder, "_rels", base + ".rels")
    if rels_name not in z.namelist():
        return {}
    out = {}
    for rel in _read_part(z, rels_name).iter(PR + "Relationship"):
        target = rel.get("Target") or ""
        if rel.get("TargetMode") == "External":
            continue
        path = (
            target.lstrip("/")
            if target.startswith("/")
            else posixpath.normpath(posixpath.join(folder, target))
        )
        out[rel.get("Id")] = path
    return out


def _clean(lines: list[str]) -> str:
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# --- Word ------------------------------------------------------------------------------------


def _w_runs(el) -> str:
    parts = []
    for node in el.iter():
        if node.tag == W + "t":
            parts.append(node.text or "")
        elif node.tag == W + "tab":
            parts.append("\t")
        elif node.tag in (W + "br", W + "cr"):
            parts.append("\n")
    return "".join(parts)


def _w_paragraph(p) -> str:
    text = _w_runs(p).strip()
    if not text:
        return ""
    ppr = p.find(W + "pPr")
    if ppr is not None:
        style = ppr.find(W + "pStyle")
        level = None
        if style is not None:
            m = re.match(
                r"(?:heading|見出し)\s*(\d)", (style.get(W + "val") or "").lower()
            )
            if m:
                level = int(m.group(1))
        if level is None:
            outline = ppr.find(W + "outlineLvl")
            if outline is not None and (outline.get(W + "val") or "").isdigit():
                level = int(outline.get(W + "val")) + 1
        if level:
            return "#" * min(level, 6) + " " + text
        if ppr.find(W + "numPr") is not None:
            return "- " + text
    return text


def _w_table(tbl) -> list[str]:
    rows = []
    for tr in tbl.findall(W + "tr"):
        cells = []
        for tc in tr.findall(W + "tc"):
            cell = " ".join(t for t in (_w_paragraph(p) for p in tc.iter(W + "p")) if t)
            cells.append(cell.replace("\n", " "))
        rows.append(" | ".join(cells))
    return rows


def _w_block(container, out: list[str]) -> None:
    for child in container:
        if child.tag == W + "p":
            text = _w_paragraph(child)
            if text:
                out.append(text)
        elif child.tag == W + "tbl":
            out.append("")
            out.extend(_w_table(child))
            out.append("")
        elif child.tag in (W + "sdt", W + "sdtContent", W + "customXml"):
            _w_block(
                child.find(W + "sdtContent") if child.tag == W + "sdt" else child, out
            )


def _docx(data: bytes) -> str:
    z = _open(data)
    if "word/document.xml" not in z.namelist():
        raise UnsupportedFormat("word/document.xml is missing")
    body = _read_part(z, "word/document.xml").find(W + "body")
    out: list[str] = []
    if body is not None:
        _w_block(body, out)
    return _clean(out)


# --- PowerPoint ------------------------------------------------------------------------------


def _a_text(root) -> list[str]:
    lines = []
    for p in root.iter(A + "p"):
        text = "".join(
            (n.text or "") if n.tag == A + "t" else "\n"
            for n in p.iter()
            if n.tag in (A + "t", A + "br")
        ).strip()
        if text:
            lines.append(text)
    return lines


def _slide_order(z: zipfile.ZipFile) -> list[str]:
    names = z.namelist()
    if "ppt/presentation.xml" in names:
        rels = _rels(z, "ppt/presentation.xml")
        pres = _read_part(z, "ppt/presentation.xml")
        lst = pres.find(P + "sldIdLst")
        if lst is not None:
            order = [rels.get(s.get(R + "id")) for s in lst.findall(P + "sldId")]
            order = [o for o in order if o in names]
            if order:
                return order
    slides = [n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
    return sorted(slides, key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))


def _pptx(data: bytes) -> str:
    z = _open(data)
    out: list[str] = []
    for number, slide in enumerate(_slide_order(z), start=1):
        out.append(f"## Slide {number}")
        out.extend(_a_text(_read_part(z, slide)))
        notes = [
            t
            for t in _rels(z, slide).values()
            if "notesSlide" in t and t in z.namelist()
        ]
        if notes:
            # The notes page repeats the slide's placeholder text as an empty shape; keep its body.
            note_lines = _a_text(_read_part(z, notes[0]))
            note_lines = [line for line in note_lines if not re.fullmatch(r"\d+", line)]
            if note_lines:
                out.append("Notes:")
                out.extend(note_lines)
        out.append("")
    return _clean(out)


# --- Excel -----------------------------------------------------------------------------------


def _col_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref or "")
    if not letters:
        return 0
    n = 0
    for ch in letters.group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    return [
        "".join(t.text or "" for t in si.iter(S + "t"))
        for si in _read_part(z, "xl/sharedStrings.xml").findall(S + "si")
    ]


def _xlsx(data: bytes) -> str:
    z = _open(data)
    if "xl/workbook.xml" not in z.namelist():
        raise UnsupportedFormat("xl/workbook.xml is missing")
    strings = _shared_strings(z)
    rels = _rels(z, "xl/workbook.xml")
    sheets = _read_part(z, "xl/workbook.xml").find(S + "sheets")
    out: list[str] = []
    for sheet in sheets if sheets is not None else []:
        part = rels.get(sheet.get(R + "id"))
        if not part or part not in z.namelist():
            continue
        hidden = sheet.get("state") in ("hidden", "veryHidden")
        out.append(f"## Sheet: {sheet.get('name')}" + (" (hidden)" if hidden else ""))
        rows = 0
        for row in _read_part(z, part).iter(S + "row"):
            values: list[str] = []
            for c in row.findall(S + "c"):
                kind = c.get("t")
                if kind == "inlineStr":
                    value = "".join(t.text or "" for t in c.iter(S + "t"))
                else:
                    v = c.find(S + "v")
                    value = v.text if v is not None and v.text is not None else ""
                    if kind == "s" and value.isdigit() and int(value) < len(strings):
                        value = strings[int(value)]
                    elif kind == "b":
                        value = "TRUE" if value == "1" else "FALSE"
                idx = _col_index(c.get("r"))
                while len(values) < idx:
                    values.append("")
                values.append(value.replace("\n", " ").replace("\t", " "))
            while values and not values[-1]:
                values.pop()
            if values:
                out.append("\t".join(values))
                rows += 1
                if rows >= MAX_XLSX_ROWS_PER_SHEET:
                    out.append(f"(rows after {MAX_XLSX_ROWS_PER_SHEET} are not shown)")
                    break
        out.append("")
    return _clean(out)


# --- PDF -------------------------------------------------------------------------------------


def _pdf(data: bytes) -> str:
    import pymupdf

    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as e:
        raise UnsupportedFormat("the file is not a readable PDF") from e
    out = []
    with doc:
        if doc.needs_pass:
            raise UnsupportedFormat("the PDF is password protected")
        for number, page in enumerate(doc, start=1):
            out.append(f"## Page {number}")
            out.append(page.get_text().strip())
            out.append("")
    text = _clean(out)
    if not re.sub(r"## Page \d+|\s", "", text):
        raise UnsupportedFormat("the PDF has no text layer (scanned images need OCR)")
    return text
