#!/usr/bin/env python3
"""Generate a styled PDF from Markdown or plain text."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Sequence

from reportlab.lib import colors
from reportlab.lib.colors import Color
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, LEGAL, LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image as PlatypusImage,
    ListFlowable,
    ListItem,
    LongTable,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)


PAGE_SIZES = {"A4": A4, "LETTER": LETTER, "LEGAL": LEGAL}
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
UNORDERED_PATTERN = re.compile(r"^\s*[-+*]\s+(.+)$")
ORDERED_PATTERN = re.compile(r"^\s*\d+[.)]\s+(.+)$")
RULE_PATTERN = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
TABLE_SEPARATOR_PATTERN = re.compile(r"^:?-{3,}:?$")
IMAGE_PATTERN = re.compile(
    r"""^\s*!\[(?P<alt>[^\]]*)\]\(\s*
    (?:<(?P<angle>[^>]+)>|(?P<plain>[^\s)]+))
    (?:\s+(?:"(?P<double>[^"]*)"|'(?P<single>[^']*)'))?
    \s*\)\s*$""",
    re.VERBOSE,
)
DEFAULT_FOOTER = "Vadkerti Financial Services"
SUPPORTED_IMAGE_EXTENSIONS = {".jpeg", ".jpg", ".png", ".svg"}


@dataclass(frozen=True)
class PdfOptions:
    output: Path
    title: str = "Document"
    author: str = ""
    subject: str = ""
    keywords: str = ""
    page_size: str = "A4"
    header: str = ""
    footer: str = DEFAULT_FOOTER
    accent_color: str = "#2457A6"
    font: Path | None = None
    asset_root: Path | None = None
    overwrite: bool = False


def parse_color(value: str) -> Color:
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise ValueError("accent color must use #RRGGBB format")
    return colors.HexColor(value)


def register_font(font_path: Path | None) -> str:
    if font_path is None:
        return "Helvetica"
    if not font_path.is_file():
        raise ValueError(f"font file does not exist: {font_path}")
    if font_path.suffix.lower() not in {".ttf", ".otf"}:
        raise ValueError("font must be a .ttf or .otf file")

    font_name = f"PdfGenerator-{font_path.stem}"
    try:
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
        pdfmetrics.registerFontFamily(
            font_name,
            normal=font_name,
            bold=font_name,
            italic=font_name,
            boldItalic=font_name,
        )
    except Exception as error:
        raise ValueError(f"unable to load font '{font_path}': {error}") from error
    return font_name


def inline_markup(text: str) -> str:
    value = escape(text, quote=False)
    value = re.sub(r"`([^`\n]+)`", r'<font name="Courier">\1</font>', value)
    value = re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", value)
    return value


def make_styles(font_name: str, accent: Color) -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    body = ParagraphStyle(
        "Body",
        parent=sample["BodyText"],
        fontName=font_name,
        fontSize=10.5,
        leading=15,
        textColor=colors.HexColor("#20242A"),
        spaceAfter=3 * mm,
    )
    styles: dict[str, ParagraphStyle] = {
        "body": body,
        "quote": ParagraphStyle(
            "Quote",
            parent=body,
            leftIndent=6 * mm,
            borderWidth=1,
            borderColor=accent,
            borderPadding=(1.5 * mm, 3 * mm, 1.5 * mm, 3 * mm),
            textColor=colors.HexColor("#4A4F57"),
        ),
        "code": ParagraphStyle(
            "Code",
            parent=body,
            fontName="Courier",
            fontSize=8.5,
            leading=11,
            leftIndent=3 * mm,
            rightIndent=3 * mm,
            borderWidth=0.5,
            borderColor=colors.HexColor("#D9DEE7"),
            borderPadding=3 * mm,
            backColor=colors.HexColor("#F5F7FA"),
            spaceBefore=2 * mm,
            spaceAfter=4 * mm,
        ),
        "caption": ParagraphStyle(
            "ImageCaption",
            parent=body,
            fontSize=8.5,
            leading=11,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#69707A"),
            spaceBefore=1.5 * mm,
            spaceAfter=4 * mm,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=body,
            fontSize=8.2,
            leading=10,
            textColor=colors.white,
            spaceAfter=0,
        ),
        "table_left": ParagraphStyle(
            "TableCellLeft",
            parent=body,
            fontSize=8.2,
            leading=10.5,
            alignment=TA_LEFT,
            spaceAfter=0,
        ),
        "table_center": ParagraphStyle(
            "TableCellCenter",
            parent=body,
            fontSize=8.2,
            leading=10.5,
            alignment=TA_CENTER,
            spaceAfter=0,
        ),
        "table_right": ParagraphStyle(
            "TableCellRight",
            parent=body,
            fontSize=8.2,
            leading=10.5,
            alignment=TA_RIGHT,
            spaceAfter=0,
        ),
    }
    heading_sizes = (24, 19, 16, 13.5, 12, 11)
    for level, size in enumerate(heading_sizes, start=1):
        styles[f"h{level}"] = ParagraphStyle(
            f"Heading{level}",
            parent=body,
            fontName=font_name,
            fontSize=size,
            leading=size * 1.2,
            textColor=accent if level <= 2 else colors.HexColor("#20242A"),
            spaceBefore=(7 if level == 1 else 5) * mm,
            spaceAfter=(4 if level <= 2 else 2.5) * mm,
            keepWithNext=True,
        )
    return styles


def resolve_image_path(target: str, asset_root: Path) -> Path:
    if "://" in target or target.lower().startswith("data:"):
        raise ValueError(f"image source must be a local file: {target}")

    path = Path(target)
    if not path.is_absolute():
        path = asset_root / path
    path = path.resolve()
    if not path.is_file():
        raise ValueError(f"image file does not exist: {path}")
    if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_IMAGE_EXTENSIONS))
        raise ValueError(
            f"unsupported image format '{path.suffix or '(none)'}'; "
            f"choose from {supported}"
        )
    return path


def image_flowable(path: Path, max_width: float, max_height: float) -> object:
    try:
        if path.suffix.lower() == ".svg":
            try:
                from svglib.svglib import svg2rlg
            except ImportError as error:
                raise ValueError(
                    "SVG support requires svglib; install the skill requirements"
                ) from error

            image = svg2rlg(str(path))
            if image is None or image.width <= 0 or image.height <= 0:
                raise ValueError(f"unable to read SVG dimensions: {path}")
            scale = min(max_width / image.width, max_height / image.height, 1)
            image.scale(scale, scale)
            image.width *= scale
            image.height *= scale
        else:
            image = PlatypusImage(str(path))
            if image.drawWidth <= 0 or image.drawHeight <= 0:
                raise ValueError(f"unable to read image dimensions: {path}")
            scale = min(
                max_width / image.drawWidth,
                max_height / image.drawHeight,
                1,
            )
            image.drawWidth *= scale
            image.drawHeight *= scale
    except ValueError:
        raise
    except Exception as error:
        raise ValueError(f"unable to load image '{path}': {error}") from error

    image.hAlign = "CENTER"
    return image


def split_markdown_table_row(line: str) -> list[str]:
    value = line.strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|") and not value.endswith(r"\|"):
        value = value[:-1]
    return [
        cell.replace(r"\|", "|").strip()
        for cell in re.split(r"(?<!\\)\|", value)
    ]


def table_alignments(separator_line: str) -> list[str] | None:
    cells = split_markdown_table_row(separator_line)
    if len(cells) < 2 or not all(TABLE_SEPARATOR_PATTERN.fullmatch(cell) for cell in cells):
        return None
    return [
        "center" if cell.startswith(":") and cell.endswith(":")
        else "right" if cell.endswith(":")
        else "left"
        for cell in cells
    ]


def table_column_widths(rows: list[list[str]], max_width: float) -> list[float]:
    column_count = len(rows[0])
    scores = [
        max(8, min(40, max(len(row[index]) for row in rows)))
        for index in range(column_count)
    ]
    minimum = min(22 * mm, max_width / column_count * 0.65)
    distributable = max_width - (minimum * column_count)
    score_total = sum(scores)
    return [
        minimum + distributable * (score / score_total)
        for score in scores
    ]


def table_flowable(
    rows: list[list[str]],
    alignments: list[str],
    styles: dict[str, ParagraphStyle],
    accent: Color,
    max_width: float,
) -> LongTable:
    header = [
        Paragraph(f"<b>{inline_markup(cell)}</b>", styles["table_header"])
        for cell in rows[0]
    ]
    body = [
        [
            Paragraph(inline_markup(cell), styles[f"table_{alignments[index]}"])
            for index, cell in enumerate(row)
        ]
        for row in rows[1:]
    ]
    table = LongTable(
        [header, *body],
        colWidths=table_column_widths(rows, max_width),
        repeatRows=1,
        hAlign="LEFT",
        splitByRow=1,
        spaceBefore=2 * mm,
        spaceAfter=5 * mm,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), accent),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CCD3DD")),
                ("BOX", (0, 0), (-1, -1), 0.7, accent),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                    colors.white,
                    colors.HexColor("#F5F7FA"),
                ]),
                ("LEFTPADDING", (0, 0), (-1, -1), 2.2 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2.2 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 1.8 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8 * mm),
            ]
        )
    )
    return table


def markdown_story(
    content: str,
    styles: dict[str, ParagraphStyle],
    accent: Color,
    asset_root: Path,
    max_image_width: float,
    max_image_height: float,
) -> list[object]:
    story: list[object] = []
    paragraph_lines: list[str] = []
    list_items: list[str] = []
    list_kind: str | None = None
    code_lines: list[str] = []
    in_code = False

    def flush_paragraph() -> None:
        if paragraph_lines:
            text = " ".join(line.strip() for line in paragraph_lines)
            story.append(Paragraph(inline_markup(text), styles["body"]))
            paragraph_lines.clear()

    def flush_list() -> None:
        nonlocal list_kind
        if list_items:
            bullet_type = "bullet" if list_kind == "unordered" else "1"
            items = [
                ListItem(Paragraph(inline_markup(item), styles["body"]))
                for item in list_items
            ]
            story.append(
                ListFlowable(
                    items,
                    bulletType=bullet_type,
                    leftIndent=7 * mm,
                    bulletFontName=styles["body"].fontName,
                    bulletFontSize=9,
                    spaceAfter=3 * mm,
                )
            )
            list_items.clear()
        list_kind = None

    lines = content.split("\n")
    skip_until = 0
    for line_index, raw_line in enumerate(lines):
        if line_index < skip_until:
            continue
        line = raw_line.rstrip("\r")
        if line.strip().startswith("```"):
            flush_paragraph()
            flush_list()
            if in_code:
                story.append(Preformatted("\n".join(code_lines), styles["code"]))
                code_lines.clear()
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line)
            continue
        if line_index + 1 < len(lines):
            alignments = table_alignments(lines[line_index + 1].rstrip("\r"))
            header = split_markdown_table_row(line)
            if alignments and len(header) == len(alignments):
                flush_paragraph()
                flush_list()
                rows = [header]
                row_index = line_index + 2
                while row_index < len(lines) and "|" in lines[row_index]:
                    row = split_markdown_table_row(lines[row_index].rstrip("\r"))
                    if len(row) != len(header):
                        raise ValueError(
                            f"Markdown table row {row_index + 1} has {len(row)} "
                            f"columns; expected {len(header)}"
                        )
                    rows.append(row)
                    row_index += 1
                story.append(
                    table_flowable(
                        rows,
                        alignments,
                        styles,
                        accent,
                        max_image_width,
                    )
                )
                skip_until = row_index
                continue
        if "\f" in line:
            parts = line.split("\f")
            for index, part in enumerate(parts):
                if part.strip():
                    paragraph_lines.append(part)
                    flush_paragraph()
                if index < len(parts) - 1:
                    flush_list()
                    story.append(PageBreak())
            continue
        if not line.strip():
            flush_paragraph()
            flush_list()
            continue

        heading = HEADING_PATTERN.match(line)
        unordered = UNORDERED_PATTERN.match(line)
        ordered = ORDERED_PATTERN.match(line)
        image = IMAGE_PATTERN.match(line)
        if image:
            flush_paragraph()
            flush_list()
            target = image.group("angle") or image.group("plain")
            assert target is not None
            path = resolve_image_path(target, asset_root)
            story.append(Spacer(1, 2 * mm))
            story.append(image_flowable(path, max_image_width, max_image_height))
            caption = image.group("double") or image.group("single")
            if caption:
                story.append(Paragraph(inline_markup(caption), styles["caption"]))
            else:
                story.append(Spacer(1, 4 * mm))
        elif heading:
            flush_paragraph()
            flush_list()
            level = len(heading.group(1))
            story.append(Paragraph(inline_markup(heading.group(2)), styles[f"h{level}"]))
        elif RULE_PATTERN.match(line):
            flush_paragraph()
            flush_list()
            story.append(
                HRFlowable(
                    width="100%",
                    thickness=0.7,
                    color=accent,
                    spaceBefore=2 * mm,
                    spaceAfter=4 * mm,
                )
            )
        elif unordered or ordered:
            flush_paragraph()
            current_kind = "unordered" if unordered else "ordered"
            if list_kind and list_kind != current_kind:
                flush_list()
            list_kind = current_kind
            match = unordered or ordered
            assert match is not None
            list_items.append(match.group(1))
        elif line.lstrip().startswith(">"):
            flush_paragraph()
            flush_list()
            quote = line.lstrip()[1:].lstrip()
            story.append(Paragraph(inline_markup(quote), styles["quote"]))
        else:
            if list_items:
                flush_list()
            paragraph_lines.append(line)

    if in_code:
        raise ValueError("unclosed fenced code block")
    flush_paragraph()
    flush_list()
    return story


def footer_labels(footer: str) -> tuple[str, str]:
    custom = footer.strip()
    if custom == DEFAULT_FOOTER:
        custom = ""
    return DEFAULT_FOOTER, custom


def text_story(content: str, styles: dict[str, ParagraphStyle]) -> list[object]:
    story: list[object] = []
    for block in re.split(r"\n\s*\n", content.strip()):
        if "\f" in block:
            parts = block.split("\f")
            for index, part in enumerate(parts):
                if part.strip():
                    story.append(
                        Paragraph(
                            "<br/>".join(escape(line) for line in part.splitlines()),
                            styles["body"],
                        )
                    )
                if index < len(parts) - 1:
                    story.append(PageBreak())
        elif block.strip():
            story.append(
                Paragraph(
                    "<br/>".join(escape(line) for line in block.splitlines()),
                    styles["body"],
                )
            )
    return story


def generate_pdf(content: str, input_format: str, options: PdfOptions) -> dict[str, object]:
    if not content.strip():
        raise ValueError("source content is empty")
    if input_format not in {"markdown", "text"}:
        raise ValueError("format must be 'markdown' or 'text'")
    if options.output.exists() and not options.overwrite:
        raise FileExistsError(
            f"output already exists: {options.output}; pass --overwrite to replace it"
        )

    try:
        page_size = PAGE_SIZES[options.page_size]
    except KeyError as error:
        raise ValueError(
            f"unsupported page size '{options.page_size}'; "
            f"choose from {', '.join(PAGE_SIZES)}"
        ) from error

    accent = parse_color(options.accent_color)
    font_name = register_font(options.font)
    styles = make_styles(font_name, accent)
    top_margin = 22 * mm if options.header else 18 * mm
    bottom_margin = 22 * mm
    asset_root = (options.asset_root or Path.cwd()).resolve()
    story = (
        markdown_story(
            content,
            styles,
            accent,
            asset_root,
            page_size[0] - 36 * mm,
            (page_size[1] - top_margin - bottom_margin) * 0.75,
        )
        if input_format == "markdown"
        else text_story(content, styles)
    )
    if not story:
        raise ValueError("source content produced no PDF elements")

    options.output.parent.mkdir(parents=True, exist_ok=True)
    page_count = 0
    doc = SimpleDocTemplate(
        str(options.output),
        pagesize=page_size,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=top_margin,
        bottomMargin=bottom_margin,
        title=options.title,
        author=options.author,
        subject=options.subject,
        keywords=options.keywords,
    )

    def decorate_page(canvas: object, document: object) -> None:
        nonlocal page_count
        page_count += 1
        width, height = page_size
        canvas.saveState()
        canvas.setTitle(options.title)
        canvas.setAuthor(options.author)
        canvas.setSubject(options.subject)
        canvas.setKeywords(options.keywords)
        canvas.setFont(font_name, 8)
        canvas.setFillColor(colors.HexColor("#69707A"))
        if options.header:
            canvas.drawString(18 * mm, height - 12 * mm, options.header)
        brand, custom_footer = footer_labels(options.footer)
        canvas.setStrokeColor(accent)
        canvas.setLineWidth(0.4)
        canvas.line(18 * mm, 16 * mm, width - 18 * mm, 16 * mm)
        brand_font = "Helvetica-Bold" if font_name == "Helvetica" else font_name
        canvas.setFont(brand_font, 8)
        canvas.setFillColor(colors.HexColor("#303640"))
        canvas.drawString(18 * mm, 11 * mm, brand)
        canvas.drawRightString(width - 18 * mm, 11 * mm, str(document.page))
        if custom_footer:
            canvas.setFont(font_name, 7)
            canvas.setFillColor(colors.HexColor("#69707A"))
            canvas.drawString(18 * mm, 7.5 * mm, custom_footer)
        canvas.restoreState()

    try:
        doc.build(story, onFirstPage=decorate_page, onLaterPages=decorate_page)
    except Exception:
        if options.output.exists():
            options.output.unlink()
        raise

    return {
        "output": str(options.output.resolve()),
        "pages": page_count,
        "bytes": options.output.stat().st_size,
        "format": input_format,
    }


def resolve_format(requested: str, input_path: Path | None) -> str:
    if requested != "auto":
        return requested
    if input_path and input_path.suffix.lower() in {".md", ".markdown"}:
        return "markdown"
    return "text"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a styled PDF from Markdown or plain text."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="UTF-8 source file")
    source.add_argument("--text", help="inline source text")
    parser.add_argument("--output", type=Path, required=True, help="destination PDF")
    parser.add_argument(
        "--format",
        choices=("auto", "markdown", "text"),
        default="auto",
        help="input format; auto uses Markdown for .md and .markdown files",
    )
    parser.add_argument("--page-size", choices=tuple(PAGE_SIZES), default="A4")
    parser.add_argument("--title", help="PDF title (defaults to the input file name)")
    parser.add_argument("--author", default="")
    parser.add_argument("--subject", default="")
    parser.add_argument("--keywords", default="")
    parser.add_argument("--header", default="")
    parser.add_argument(
        "--footer",
        default=DEFAULT_FOOTER,
        help="optional secondary footer text; company branding is always shown",
    )
    parser.add_argument("--accent-color", default="#2457A6")
    parser.add_argument("--font", type=Path, help="optional TrueType/OpenType font")
    parser.add_argument(
        "--asset-root",
        type=Path,
        help="base directory for relative Markdown image paths",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.input:
            if not args.input.is_file():
                raise ValueError(f"input file does not exist: {args.input}")
            content = args.input.read_text(encoding="utf-8")
        else:
            content = args.text
        title = args.title or (args.input.stem if args.input else "Document")
        result = generate_pdf(
            content,
            resolve_format(args.format, args.input),
            PdfOptions(
                output=args.output,
                title=title,
                author=args.author,
                subject=args.subject,
                keywords=args.keywords,
                page_size=args.page_size,
                header=args.header,
                footer=args.footer,
                accent_color=args.accent_color,
                font=args.font,
                asset_root=args.asset_root or (args.input.parent if args.input else None),
                overwrite=args.overwrite,
            ),
        )
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
