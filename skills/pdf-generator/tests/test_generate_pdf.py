from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

from PIL import Image as PillowImage
from reportlab.platypus import LongTable


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "pdf-generator"
    / "scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))

from generate_pdf import (
    DEFAULT_FOOTER,
    PdfOptions,
    build_parser,
    footer_labels,
    generate_pdf,
    make_styles,
    markdown_story,
    parse_color,
    resolve_format,
)


class GeneratePdfTests(unittest.TestCase):
    def test_uses_professional_company_footer_by_default(self) -> None:
        self.assertEqual(PdfOptions(output=Path("document.pdf")).footer, DEFAULT_FOOTER)
        args = build_parser().parse_args(
            ["--text", "Content", "--output", "document.pdf"]
        )
        self.assertEqual(args.footer, DEFAULT_FOOTER)
        self.assertEqual(
            footer_labels("PortfolioManager — Negotiation Summary"),
            (DEFAULT_FOOTER, "PortfolioManager — Negotiation Summary"),
        )
        self.assertEqual(footer_labels(""), (DEFAULT_FOOTER, ""))

    def test_renders_styled_markdown_table(self) -> None:
        styles = make_styles("Helvetica", parse_color("#2457A6"))
        story = markdown_story(
            "| Asset class | Current | Target |\n"
            "|:------------|--------:|-------:|\n"
            "| Equities | 56.84% | 47.60% |\n"
            "| Bonds | 9.69% | 26.40% |",
            styles,
            parse_color("#2457A6"),
            Path.cwd(),
            160 * 2.83465,
            200 * 2.83465,
        )

        tables = [flowable for flowable in story if isinstance(flowable, LongTable)]
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0].repeatRows, 1)
        self.assertEqual(len(tables[0]._cellvalues), 3)

    def test_renders_generated_table_with_two_dash_separators(self) -> None:
        styles = make_styles("Helvetica", parse_color("#2457A6"))
        story = markdown_story(
            "| Item | Result |\n"
            "|:--|:--|\n"
            "| Closest model | **Dynamic** |\n"
            "| Confidence | **Low** |",
            styles,
            parse_color("#2457A6"),
            Path.cwd(),
            160 * 2.83465,
            200 * 2.83465,
        )

        tables = [flowable for flowable in story if isinstance(flowable, LongTable)]
        self.assertEqual(len(tables), 1)
        self.assertEqual(len(tables[0]._cellvalues), 3)

    def test_rejects_inconsistent_markdown_table_rows(self) -> None:
        styles = make_styles("Helvetica", parse_color("#2457A6"))
        with self.assertRaisesRegex(ValueError, "expected 2"):
            markdown_story(
                "| Asset | Weight |\n"
                "|:------|-------:|\n"
                "| Equities | 56.84% | Extra |",
                styles,
                parse_color("#2457A6"),
                Path.cwd(),
                160 * 2.83465,
                200 * 2.83465,
            )

    def test_generates_markdown_pdf_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "nested" / "report.pdf"
            result = generate_pdf(
                "# Report\n\nIntro with **bold** text.\n\n- One\n- Two\n\n```python\nprint('ok')\n```",
                "markdown",
                PdfOptions(
                    output=output,
                    title="Test Report",
                    header="Header",
                    footer="Footer",
                ),
            )

            self.assertTrue(output.is_file())
            self.assertEqual(output.read_bytes()[:5], b"%PDF-")
            self.assertEqual(result["pages"], 1)
            self.assertGreater(result["bytes"], 500)

    def test_embeds_png_jpeg_and_svg_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            asset_root = Path(temp_dir)
            PillowImage.new("RGB", (320, 180), "#2457A6").save(
                asset_root / "chart.png"
            )
            PillowImage.new("RGB", (160, 240), "#D9DEE7").save(
                asset_root / "diagram.jpg"
            )
            (asset_root / "scenario.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">'
                '<rect width="400" height="200" fill="#F5F7FA"/>'
                '<circle cx="200" cy="100" r="70" fill="#2457A6"/>'
                "</svg>",
                encoding="utf-8",
            )
            output = asset_root / "visual-report.pdf"

            result = generate_pdf(
                "# Visual report\n\n"
                '![Allocation](chart.png "Portfolio allocation")\n\n'
                "![Structure](diagram.jpg)\n\n"
                '![Scenario](scenario.svg "Scenario analysis")',
                "markdown",
                PdfOptions(output=output, asset_root=asset_root),
            )

            self.assertTrue(output.is_file())
            self.assertEqual(result["pages"], 2)
            self.assertGreater(result["bytes"], 1500)

    def test_rejects_missing_and_unsupported_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            asset_root = Path(temp_dir)
            output = asset_root / "report.pdf"

            with self.assertRaisesRegex(ValueError, "does not exist"):
                generate_pdf(
                    "![Missing](missing.png)",
                    "markdown",
                    PdfOptions(output=output, asset_root=asset_root),
                )

            unsupported = asset_root / "chart.gif"
            unsupported.write_bytes(b"GIF89a")
            with self.assertRaisesRegex(ValueError, "unsupported image format"):
                generate_pdf(
                    "![Unsupported](chart.gif)",
                    "markdown",
                    PdfOptions(output=output, asset_root=asset_root),
                )

    def test_generates_plain_text_with_explicit_page_break(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "notes.pdf"
            result = generate_pdf(
                "First page\fSecond page",
                "text",
                PdfOptions(output=output),
            )

            self.assertEqual(result["pages"], 2)

    def test_generates_markdown_with_explicit_page_break(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.pdf"
            result = generate_pdf(
                "# First page\n\nContent\f# Second page\n\nMore content",
                "markdown",
                PdfOptions(output=output),
            )

            self.assertEqual(result["pages"], 2)

    def test_refuses_to_overwrite_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "existing.pdf"
            output.write_bytes(b"existing")

            with self.assertRaises(FileExistsError):
                generate_pdf("Content", "text", PdfOptions(output=output))

            self.assertEqual(output.read_bytes(), b"existing")

    def test_rejects_empty_content_and_invalid_color(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "document.pdf"
            with self.assertRaisesRegex(ValueError, "empty"):
                generate_pdf(" \n", "text", PdfOptions(output=output))
            with self.assertRaisesRegex(ValueError, "#RRGGBB"):
                generate_pdf(
                    "Content",
                    "text",
                    PdfOptions(output=output, accent_color="blue"),
                )

    def test_resolves_format_from_extension(self) -> None:
        self.assertEqual(resolve_format("auto", Path("report.md")), "markdown")
        self.assertEqual(resolve_format("auto", Path("notes.txt")), "text")
        self.assertEqual(resolve_format("markdown", Path("notes.txt")), "markdown")

    def test_rejects_unsupported_programmatic_page_size(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "document.pdf"
            with self.assertRaisesRegex(ValueError, "unsupported page size"):
                generate_pdf(
                    "Content",
                    "text",
                    PdfOptions(output=output, page_size="TABLOID"),
                )



if __name__ == "__main__":
    unittest.main()
