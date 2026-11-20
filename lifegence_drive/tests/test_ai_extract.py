# Copyright (c) 2026, Lifegence Corporation and Contributors
# See license.txt
"""Text extraction for the AI agent's read_drive_file tool (no Frappe needed)."""

import io
import unittest
import zipfile

from lifegence_drive.ai import extract

W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
A_NS = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
P_NS = 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
R_NS = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
S_NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def package(parts: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, xml in parts.items():
            z.writestr(name, xml)
    return buf.getvalue()


def rels(entries: list[tuple[str, str, str]]) -> str:
    body = "".join(
        f'<Relationship Id="{i}" Type="{REL}/{t}" Target="{target}"/>'
        for i, t, target in entries
    )
    return f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{body}</Relationships>'


def wp(text, style=None, numbered=False):
    ppr = ""
    if style or numbered:
        ppr = "<w:pPr>"
        if style:
            ppr += f'<w:pStyle w:val="{style}"/>'
        if numbered:
            ppr += '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'
        ppr += "</w:pPr>"
    return f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'


class TestDocx(unittest.TestCase):
    def test_headings_lists_tables_in_order(self):
        body = (
            wp("セミナー台本", style="Heading1")
            + wp("タイムスケジュール", style="Heading2")
            + "<w:tbl>"
            + "<w:tr><w:tc>"
            + wp("12:00")
            + "</w:tc><w:tc>"
            + wp("オープニング")
            + "</w:tc></w:tr>"
            + "<w:tr><w:tc>"
            + wp("12:05")
            + "</w:tc><w:tc>"
            + wp("基調講演")
            + "</w:tc></w:tr>"
            + "</w:tbl>"
            + wp("資料を配布する", numbered=True)
            + "<w:p><w:r><w:t>前半</w:t><w:tab/><w:t>後半</w:t><w:br/><w:t>次の行</w:t></w:r></w:p>"
            + "<w:p><w:r><w:delText>削除済み</w:delText></w:r></w:p>"
        )
        data = package(
            {
                "word/document.xml": f"<w:document {W_NS}><w:body>{body}</w:body></w:document>"
            }
        )
        text, kind = extract.extract_text(data, "台本.docx")
        self.assertEqual(kind, "docx")
        self.assertEqual(
            text.splitlines(),
            [
                "# セミナー台本",
                "## タイムスケジュール",
                "",
                "12:00 | オープニング",
                "12:05 | 基調講演",
                "",
                "- 資料を配布する",
                "前半\t後半",
                "次の行",
            ],
        )
        self.assertNotIn("削除済み", text)

    def test_not_a_package(self):
        with self.assertRaises(extract.UnsupportedFormat):
            extract.extract_text(b"not a zip", "x.docx")


class TestPptx(unittest.TestCase):
    def test_slides_in_presentation_order_with_notes(self):
        def slide(*lines):
            ps = "".join(f"<a:p><a:r><a:t>{t}</a:t></a:r></a:p>" for t in lines)
            return f"<p:sld {A_NS} {P_NS}><p:cSld><p:spTree><p:sp><p:txBody>{ps}</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"

        data = package(
            {
                "ppt/presentation.xml": (
                    f"<p:presentation {P_NS} {R_NS}><p:sldIdLst>"
                    '<p:sldId id="256" r:id="rId2"/><p:sldId id="257" r:id="rId1"/>'
                    "</p:sldIdLst></p:presentation>"
                ),
                "ppt/_rels/presentation.xml.rels": rels(
                    [
                        ("rId1", "slide", "slides/slide1.xml"),
                        ("rId2", "slide", "slides/slide2.xml"),
                    ]
                ),
                "ppt/slides/slide1.xml": slide("まとめ"),
                "ppt/slides/slide2.xml": slide("表紙", "2026-11-30"),
                "ppt/slides/_rels/slide2.xml.rels": rels(
                    [("rId1", "notesSlide", "../notesSlides/notesSlide1.xml")]
                ),
                "ppt/notesSlides/notesSlide1.xml": slide("ここで自己紹介", "2"),
            }
        )
        text, kind = extract.extract_text(data, "deck.pptx")
        self.assertEqual(kind, "pptx")
        self.assertEqual(
            text.splitlines(),
            [
                "## Slide 1",
                "表紙",
                "2026-11-30",
                "Notes:",
                "ここで自己紹介",
                "",
                "## Slide 2",
                "まとめ",
            ],
        )


class TestXlsx(unittest.TestCase):
    def test_shared_inline_bool_and_gaps(self):
        data = package(
            {
                "xl/workbook.xml": (
                    f"<workbook {S_NS} {R_NS}><sheets>"
                    '<sheet name="予定" sheetId="1" r:id="rId1"/>'
                    '<sheet name="Lists" sheetId="2" state="hidden" r:id="rId2"/>'
                    "</sheets></workbook>"
                ),
                "xl/_rels/workbook.xml.rels": rels(
                    [
                        ("rId1", "worksheet", "worksheets/sheet1.xml"),
                        ("rId2", "worksheet", "worksheets/sheet2.xml"),
                    ]
                ),
                "xl/sharedStrings.xml": f"<sst {S_NS}><si><t>時刻</t></si><si><r><t>内</t></r><r><t>容</t></r></si></sst>",
                "xl/worksheets/sheet1.xml": (
                    f"<worksheet {S_NS}><sheetData>"
                    '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
                    '<row r="2"><c r="A2" t="inlineStr"><is><t>12:00</t></is></c><c r="C2" t="b"><v>1</v></c></row>'
                    '<row r="3"><c r="A3"/></row>'
                    "</sheetData></worksheet>"
                ),
                "xl/worksheets/sheet2.xml": f'<worksheet {S_NS}><sheetData><row r="1"><c r="A1"><v>42</v></c></row></sheetData></worksheet>',
            }
        )
        text, kind = extract.extract_text(data, "plan.xlsx")
        self.assertEqual(kind, "xlsx")
        self.assertEqual(
            text.splitlines(),
            [
                "## Sheet: 予定",
                "時刻\t内容",
                "12:00\t\tTRUE",
                "",
                "## Sheet: Lists (hidden)",
                "42",
            ],
        )


class TestPdfAndText(unittest.TestCase):
    def test_pdf_pages(self):
        import pymupdf

        doc = pymupdf.open()
        for line in ("Opening 12:00", "Q&A 12:40"):
            doc.new_page().insert_text((72, 72), line)
        data = doc.tobytes()
        text, kind = extract.extract_text(data, "a.pdf")
        self.assertEqual(kind, "pdf")
        self.assertIn("## Page 1", text)
        self.assertIn("Opening 12:00", text)
        self.assertIn("## Page 2", text)
        self.assertIn("Q&A 12:40", text)

    def test_pdf_without_text_layer(self):
        import pymupdf

        doc = pymupdf.open()
        doc.new_page()
        with self.assertRaises(extract.UnsupportedFormat):
            extract.extract_text(doc.tobytes(), "scan.pdf")

    def test_text_encodings(self):
        self.assertEqual(
            extract.extract_text("予定".encode("cp932"), "a.txt"), ("予定", "text")
        )
        self.assertEqual(
            extract.extract_text("﻿予定".encode(), "a.md"), ("予定", "text")
        )

    def test_legacy_and_unknown(self):
        with self.assertRaisesRegex(extract.UnsupportedFormat, "docx"):
            extract.extract_text(b"\xd0\xcf\x11\xe0", "old.doc")
        with self.assertRaises(extract.UnsupportedFormat):
            extract.extract_text(b"", "image.png")

    def test_entity_expansion_refused(self):
        bomb = (
            '<?xml version="1.0"?><!DOCTYPE w [<!ENTITY a "aaaaaaaaaa">]>'
            f"<w:document {W_NS}><w:body><w:p><w:r><w:t>&a;</w:t></w:r></w:p></w:body></w:document>"
        )
        with self.assertRaisesRegex(extract.UnsupportedFormat, "EntitiesForbidden"):
            extract.extract_text(package({"word/document.xml": bomb}), "bomb.docx")


if __name__ == "__main__":
    unittest.main()
