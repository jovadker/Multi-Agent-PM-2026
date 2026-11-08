import importlib.util
from pathlib import Path

import pytest

MANAGER = Path(__file__).resolve().parents[1] / "portfolio-manager-agent"


@pytest.fixture
def report_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path))
    if not (MANAGER / "skills").exists():
        pytest.skip("run sync-skills.ps1 first")
    spec = importlib.util.spec_from_file_location("report_tools", MANAGER / "report_tools.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_classify_portfolio(report_tools):
    out = report_tools.classify_portfolio.func(
        '{"absolute_return":0,"real_estate":10,"commodities":10,"investment_grade_bonds":28,'
        '"high_yield_bonds":0,"cash":18,"equities":34}'
    )
    assert "Balanced" in out
    assert report_tools.classify_portfolio.func("not json").startswith("error")


def test_charts_and_pdf(report_tools, tmp_path):
    pie = report_tools.render_chart.func("pie", "Allocation", "alloc", ["A", "B"], [60, 40])
    bar = report_tools.render_chart.func(
        "bar", "Outcome", "bar", ["A", "B"], None, '{"Current":[1,2],"Proposed":[2,3]}'
    )
    diagram = report_tools.render_chart.func(
        "diagram", "Moves", "moves", None, None,
        '{"moves":[{"from":"Sell: X","to":"Buy: Y","label":"USD 100"}],"hold":["Z"]}',
    )
    assert (pie, bar, diagram) == ("alloc.png", "bar.png", "moves.png")

    markdown = "# Report\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n![Alloc](alloc.png)\n\n![Moves](moves.png)\n"
    result = report_tools.generate_pdf_report.func(markdown, "Report.pdf", "Report")
    assert result.startswith("PDF created")
    assert (tmp_path / "Report.pdf").stat().st_size > 1000
