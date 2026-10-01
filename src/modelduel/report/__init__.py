"""Generación del informe HTML: duelo de dos o liga de tres a seis contendientes."""

from __future__ import annotations

from pathlib import Path

from modelduel.report.html import render_versus
from modelduel.report.league import render_league
from modelduel.report.markdown import render_markdown
from modelduel.results import sides_of, summarize

__all__ = ["render_markdown", "render_report", "write_markdown", "write_report"]


def render_report(results: dict) -> str:
    summary = results.get("summary") or summarize(results)
    if len(sides_of(results)) > 2:
        return render_league(results, summary)
    return render_versus(results, summary)


def write_report(results: dict, out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "index.html"
    path.write_text(render_report(results), encoding="utf-8")
    return path


def write_markdown(results: dict, out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "informe.md"
    with path.open("w", encoding="utf-8", newline="") as handle:  # LF también en Windows
        handle.write(render_markdown(results))
    return path
