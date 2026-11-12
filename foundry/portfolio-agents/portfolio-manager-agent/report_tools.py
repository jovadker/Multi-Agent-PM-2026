# Copyright (c) Microsoft. All rights reserved.
"""Function tools that wrap the portfolio-complexity and pdf-generator skills."""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Literal

from agent_framework import tool

HERE = Path(__file__).parent
CLASSIFY_SCRIPT = HERE / "skills" / "portfolio-complexity" / "scripts" / "classify_portfolio.py"
PDF_SCRIPT = HERE / "skills" / "pdf-generator" / "scripts" / "generate_pdf.py"

ATTACHMENT_PLACEHOLDER = "__PDF_BYTES__"

PALETTE = ["#2457A6", "#1B998B", "#F4A259", "#BC4B51", "#8E7DBE", "#5B8E7D", "#F25F5C", "#247BA0"]


def reports_dir() -> Path:
    # $HOME is persisted by the hosted-agent platform across turns.
    base = Path(os.environ.get("REPORTS_DIR") or (Path(os.environ.get("HOME") or Path.home()) / "reports"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def safe_name(name: str, suffix: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(name).stem).strip("-.") or "file"
    return f"{stem}{suffix}"


def _run(command: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


@tool(name="classify_portfolio", approval_mode="never_require")
def classify_portfolio(allocation_json: str) -> str:
    """Classify a portfolio as Stable, Conservative, Balanced or Dynamic (portfolio-complexity skill).

    allocation_json: JSON object with percentages for the seven asset classes
    absolute_return, real_estate, commodities, investment_grade_bonds, high_yield_bonds, cash, equities
    (they must add up to about 100). Returns the deterministic classifier output (type, confidence,
    normalized allocation, closest and second-closest model with RMS distances).
    """
    try:
        json.loads(allocation_json)
    except json.JSONDecodeError as error:
        return f"error: allocation_json is not valid JSON: {error}"
    result = _run([sys.executable, str(CLASSIFY_SCRIPT), "--allocation-json", allocation_json], 60)
    if result.returncode != 0:
        return f"error: {(result.stderr or result.stdout).strip()}"
    return result.stdout.strip()


def _style():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


@tool(name="render_chart", approval_mode="never_require")
def render_chart(
    chart_type: Literal["pie", "bar", "diagram"],
    title: str,
    filename: str,
    labels: list[str] | None = None,
    values: list[float] | None = None,
    series_json: str = "",
) -> str:
    """Render a PNG chart for the PDF report and return its file name (use it in Markdown as ![alt](file)).

    chart_type 'pie': labels + values (for example current or proposed allocation by holding or sector).
    chart_type 'bar': labels + values for one series, or series_json like
      {"Current": [..], "Proposed": [..]} (same length as labels) for grouped bars, for example the
      expected 52-week outcome per stock.
    chart_type 'diagram': series_json like {"moves": [{"from": "Sell: PepsiCo", "to": "Buy: Eli Lilly",
      "label": "USD 1,300"}], "hold": ["Microsoft", "SAP"]} to show how money moves in the update.
    """
    plt = _style()
    out = reports_dir() / safe_name(filename, ".png")
    fig = None
    try:
        if chart_type == "pie":
            if not labels or not values or len(labels) != len(values):
                return "error: pie needs labels and values of the same length."
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.pie(
                values,
                labels=labels,
                autopct="%1.1f%%",
                startangle=90,
                colors=[PALETTE[i % len(PALETTE)] for i in range(len(values))],
                wedgeprops={"edgecolor": "white"},
                textprops={"fontsize": 8},
            )
            ax.axis("equal")
        elif chart_type == "bar":
            series = json.loads(series_json) if series_json else {"Value": values or []}
            if not labels or any(len(v) != len(labels) for v in series.values()):
                return "error: bar needs labels and series with the same length."
            fig, ax = plt.subplots(figsize=(9, 5.5))
            width = 0.8 / len(series)
            for index, (name, data) in enumerate(series.items()):
                positions = [p + index * width for p in range(len(labels))]
                ax.bar(positions, data, width, label=name, color=PALETTE[index % len(PALETTE)])
            ax.set_xticks([p + 0.4 - width / 2 for p in range(len(labels))])
            ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
            ax.axhline(0, color="#444444", linewidth=0.8)
            ax.grid(axis="y", alpha=0.3)
            if len(series) > 1:
                ax.legend()
        elif chart_type == "diagram":
            spec = json.loads(series_json or "{}")
            moves = spec.get("moves", [])
            hold = spec.get("hold", [])
            sources = list(dict.fromkeys(m["from"] for m in moves))
            targets = list(dict.fromkeys(m["to"] for m in moves))
            rows = max(len(sources), len(targets), 1)
            fig, ax = plt.subplots(figsize=(10, 1.2 * rows + (1.4 if hold else 0.6)))
            ax.set_xlim(0, 10)
            ax.set_ylim(-(1.4 if hold else 0.2), rows)
            ax.axis("off")

            def y_of(index: int, count: int) -> float:
                return rows - (index + 0.5) * rows / max(count, 1)

            positions = {}
            for i, name in enumerate(sources):
                y = y_of(i, len(sources))
                positions[("s", name)] = (3.0, y)
                ax.text(1.6, y, name, ha="center", va="center", fontsize=8, color="white",
                        bbox={"boxstyle": "round,pad=0.4", "fc": PALETTE[3], "ec": "none"})
            for i, name in enumerate(targets):
                y = y_of(i, len(targets))
                positions[("t", name)] = (7.0, y)
                ax.text(8.4, y, name, ha="center", va="center", fontsize=8, color="white",
                        bbox={"boxstyle": "round,pad=0.4", "fc": PALETTE[1], "ec": "none"})
            for move in moves:
                x0, y0 = positions[("s", move["from"])]
                x1, y1 = positions[("t", move["to"])]
                ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                            arrowprops={"arrowstyle": "->", "color": "#444444", "lw": 1.2})
                if move.get("label"):
                    ax.text((x0 + x1) / 2, (y0 + y1) / 2 + 0.12, move["label"], ha="center", fontsize=7)
            if hold:
                ax.text(5, -0.9, "Hold: " + ", ".join(hold), ha="center", va="center", fontsize=8,
                        bbox={"boxstyle": "round,pad=0.4", "fc": PALETTE[0], "ec": "none"}, color="white",
                        wrap=True)
        else:
            return f"error: unsupported chart_type '{chart_type}'."

        ax.set_title(title, fontsize=12, fontweight="bold")
        fig.tight_layout()
        fig.savefig(out, dpi=160)
    except (ValueError, KeyError, TypeError) as error:
        return f"error: could not render chart: {error}"
    finally:
        if fig is not None:
            plt.close(fig)
    return out.name


@tool(name="generate_pdf_report", approval_mode="never_require")
def generate_pdf_report(markdown: str, filename: str, title: str) -> str:
    """Create a professional PDF from Markdown (pdf-generator skill) and return its path and page count.

    markdown: report body. Use headings, Markdown tables (include the original portfolio elements),
    and charts created with render_chart referenced as ![alt](chart-file.png "caption").
    The branded 'Vadkerti Financial Services' footer is always retained by the generator.
    filename: output file name, for example Portfolio_Rebalancing_Review.pdf
    """
    directory = reports_dir()
    pdf_path = directory / safe_name(filename, ".pdf")
    source = directory / safe_name(filename, ".md")
    source.write_text(markdown, encoding="utf-8")
    result = _run(
        [
            sys.executable, str(PDF_SCRIPT),
            "--input", str(source),
            "--output", str(pdf_path),
            "--title", title,
            "--author", "PortfolioManager",
            "--header", "Portfolio Rebalancing Review",
            "--asset-root", str(directory),
            "--overwrite",
        ]
    )
    if result.returncode != 0 or not pdf_path.exists():
        return f"error: PDF was not created: {(result.stderr or result.stdout).strip()}"
    return f"PDF created: {pdf_path}\n{result.stdout.strip()}"


@tool(name="get_pdf_attachment", approval_mode="never_require")
def get_pdf_attachment(filename: str) -> str:
    """Prepare a generated PDF for e-mailing and return the two values to put into the mail attachment.

    Use the returned file name as the attachment's name field and the returned placeholder as the attachment's
    content (base64 bytes) field, using the exact field names of the e-mail tool's schema. The real bytes are
    inserted automatically when the mail is sent, so never write, shorten or alter the placeholder.
    """
    path = reports_dir() / safe_name(filename, ".pdf")
    if not path.exists():
        return f"error: {path} does not exist; create it with generate_pdf_report first."
    return json.dumps({"file_name": path.name, "content_placeholder": ATTACHMENT_PLACEHOLDER, "content_type": "application/pdf"})


def _find_key(mapping: dict, *needles: str, exclude: str = "") -> str | None:
    for key in mapping:
        lowered = str(key).lower()
        if all(n in lowered for n in needles) and not (exclude and exclude in lowered):
            return key
    return None


def inject_attachment_bytes(arguments) -> list[str]:
    """Replace the placeholder content in mail-tool attachments with the real base64 of the PDF.

    The model must not copy base64 itself: long base64 strings get truncated or altered, which corrupts the PDF.
    Field names are matched case-insensitively because connector schemas differ (name/Name, contentBytes/ContentBytes).
    Returns a list of diagnostic messages for logging.
    """
    notes: list[str] = []
    getter = arguments if isinstance(arguments, dict) else getattr(arguments, "__dict__", None)
    if not hasattr(arguments, "keys") and getter is None:
        return ["arguments have an unsupported type " + type(arguments).__name__]
    source = arguments if hasattr(arguments, "keys") else getter
    key = _find_key(source, "attach")
    notes.append(f"argument keys: {list(source.keys())}")
    if key is None:
        return notes + ["no attachments argument present"]
    attachments = source[key]
    was_text = isinstance(attachments, str)
    if was_text:
        try:
            attachments = json.loads(attachments)
        except ValueError:
            return notes + ["attachments is not valid JSON"]
    if isinstance(attachments, dict):
        attachments = [attachments]
    if not isinstance(attachments, list):
        return notes + ["attachments has an unsupported shape"]
    for item in attachments:
        if not isinstance(item, dict):
            continue
        name_key = _find_key(item, "name")
        content_key = _find_key(item, "content", exclude="type") or _find_key(item, "bytes")
        if name_key is None or not item.get(name_key):
            notes.append(f"attachment without name, keys: {list(item.keys())}")
            continue
        path = reports_dir() / safe_name(str(item[name_key]), ".pdf")
        if not path.exists():
            notes.append(f"{path} not found")
            continue
        content_key = content_key or "contentBytes"
        item[content_key] = base64.b64encode(path.read_bytes()).decode("ascii")
        notes.append(f"injected {path.stat().st_size} bytes into '{content_key}' of '{item[name_key]}'")
    source[key] = json.dumps(attachments) if was_text else attachments
    return notes
