"""PDF scan reporting helpers."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from html import escape
from shutil import which
from typing import Any

from app.core.config import settings
from app.models import Finding, Scan

_SEVERITY_PRIORITY = {
    "Critical": 5,
    "High": 4,
    "Medium": 3,
    "Low": 2,
    "Info": 1,
}

_GOOGLE_FONTS_STYLESHEET = (
    "https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:"
    "wght@300;400;500;600;700&display=swap"
)

_BRAND_MARK = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="19" fill="none" '
    'viewBox="0 0 48 46">'
    '<path fill="#863bff" d="M25.946 44.938c-.664.845-2.021.375-2.021-.698V33.937a2.26 '
    "2.26 0 0 0-2.262-2.262H10.287c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.497 "
    '0-3.578-1.842-3.578H1.237c-.92 0-1.456-1.04-.92-1.788L10.013.474c.214-.297.556-.474 '
    ".92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.579 1.842 "
    '3.579h11.377c.943 0 1.473 1.088.89 1.83L25.947 44.94z"/></svg>'
)


def is_chromium_available() -> bool:
    """Check if Chromium browser is available for PDF generation.

    Returns:
        True if Chromium executable can be found, False otherwise.
    """
    return _chromium_executable() is not None


def generate_scan_report_pdf(*, scan: Scan, findings: list[Finding]) -> bytes:
    """Render one scan report as a PDF document."""

    html = _render_scan_report_html(scan=scan, findings=findings)
    return _render_pdf_from_html(html)


def _render_pdf_from_html(html: str) -> bytes:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - exercised indirectly in endpoint tests
        raise RuntimeError(
            "PDF reporting requires the Python Playwright package to be installed."
        ) from exc

    launch_kwargs: dict[str, Any] = {"headless": True}
    executable_path = _chromium_executable()
    if executable_path:
        launch_kwargs["executable_path"] = executable_path

    browser = None
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(**launch_kwargs)
            try:
                page = browser.new_page()
                page.set_content(html, wait_until="networkidle")
                pdf = page.pdf(
                    format="A4",
                    print_background=True,
                    margin={
                        "top": "18mm",
                        "right": "14mm",
                        "bottom": "18mm",
                        "left": "14mm",
                    },
                )
                return pdf
            finally:
                if browser:
                    browser.close()
    except Exception as exc:  # pragma: no cover - depends on browser runtime
        raise RuntimeError(
            "PDF reporting is unavailable because Chromium could not be started."
        ) from exc


def _chromium_executable() -> str | None:
    candidates = [
        settings.playwright_chromium_executable_path,
        which("chromium"),
        which("chromium-browser"),
        which("google-chrome"),
    ]
    for candidate in candidates:
        if candidate:
            return candidate
    return None


def _render_scan_report_html(*, scan: Scan, findings: list[Finding]) -> str:
    severity_counts = Counter(finding.severity.value for finding in findings)
    category_counts = Counter(finding.category for finding in findings)
    tool_counts = Counter(finding.tool for finding in findings)
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    top_findings = sorted(
        findings,
        key=lambda finding: (
            -_SEVERITY_PRIORITY.get(finding.severity.value, 0),
            finding.id or 0,
        ),
    )[:10]
    policy = scan.scan_metadata.get("policy") if isinstance(scan.scan_metadata, dict) else None
    quality_rows = [
        ("Quality score", _metric_text(scan.quality_score, digits=1)),
        ("Quality grade", scan.quality_grade or "N/A"),
        ("Maintainability", _metric_text(scan.maintainability_score, digits=1)),
        ("Complexity", _metric_text(scan.complexity_score, digits=1)),
        ("Style", _metric_text(scan.style_score, digits=1)),
        ("Duplication", _metric_text(scan.duplication_percentage, suffix="%", digits=1)),
        (
            "Maintainability index",
            _metric_text(scan.maintainability_index, digits=1),
        ),
        (
            "Technical debt",
            (
                f"{scan.technical_debt_minutes} min"
                if scan.technical_debt_minutes is not None
                else "N/A"
            ),
        ),
    ]
    summary_cards = [
        ("Gate verdict", _gate_label(scan.quality_gate_passed)),
        ("Total findings", str(scan.total_findings)),
        ("Critical", str(scan.critical_findings)),
        ("High", str(scan.high_findings)),
        ("Suppressed", str(scan.suppressed_findings)),
        ("Included in report", str(len(findings))),
    ]

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <link href="{_GOOGLE_FONTS_STYLESHEET}" rel="stylesheet" />
    <title>VigilWeave Scan Report #{scan.id}</title>
    <style>
      @page {{
        size: A4;
        margin: 18mm 14mm;
      }}
      :root {{
        --bg: #f7f9fb;
        --surface: #ffffff;
        --ink: #191c1e;
        --muted: #444653;
        --line: #c4c5d5;
        --accent: #1e40af;
        --accent-soft: #dbeafe;
        --danger: #ba1a1a;
        --warning: #d97706;
      }}
      * {{
        box-sizing: border-box;
      }}
      body {{
        margin: 0;
        background: var(--bg);
        color: var(--ink);
        font-family: "Plus Jakarta Sans", "Helvetica Neue", Arial, sans-serif;
        font-size: 12px;
        line-height: 1.5;
      }}
      h1, h2, h3, p {{
        margin: 0;
      }}
      .page {{
        display: flex;
        flex-direction: column;
        gap: 16px;
      }}
      .hero {{
        border: 1px solid var(--line);
        background:
          linear-gradient(135deg, rgba(30, 64, 175, 0.08), rgba(247, 249, 251, 0.92)),
          var(--surface);
        border-radius: 20px;
        padding: 20px;
      }}
      .eyebrow {{
        color: var(--muted);
        font-size: 10px;
        letter-spacing: 0.18em;
        text-transform: uppercase;
      }}
      .hero-grid, .summary-grid, .breakdown-grid {{
        display: grid;
        gap: 12px;
      }}
      .hero-grid {{
        grid-template-columns: 2fr 1fr;
        margin-top: 12px;
      }}
      .summary-grid {{
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }}
      .breakdown-grid {{
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }}
      .panel, .card {{
        border: 1px solid var(--line);
        background: var(--surface);
        border-radius: 16px;
      }}
      .panel {{
        padding: 16px;
      }}
      .card {{
        padding: 14px;
      }}
      .card strong {{
        display: block;
        font-size: 24px;
        line-height: 1.1;
        margin-top: 6px;
      }}
      .muted {{
        color: var(--muted);
      }}
      .meta-list, .quality-table, .finding-meta {{
        width: 100%;
        border-collapse: collapse;
      }}
      .meta-list td, .quality-table td {{
        padding: 6px 0;
        border-bottom: 1px solid rgba(196, 197, 213, 0.6);
      }}
      .meta-list tr:last-child td, .quality-table tr:last-child td {{
        border-bottom: none;
      }}
      .metric-label {{
        color: var(--muted);
        width: 42%;
      }}
      .pill {{
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: 4px 10px;
        background: var(--accent-soft);
        color: var(--accent);
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }}
      .section-title {{
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        margin-bottom: 10px;
      }}
      .breakdown-list {{
        display: flex;
        flex-direction: column;
        gap: 8px;
      }}
      .breakdown-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid rgba(196, 197, 213, 0.5);
      }}
      .breakdown-row:last-child {{
        border-bottom: none;
        padding-bottom: 0;
      }}
      .finding {{
        break-inside: avoid;
        border: 1px solid var(--line);
        background: var(--surface);
        border-radius: 16px;
        padding: 14px;
      }}
      .finding + .finding {{
        margin-top: 12px;
      }}
      .finding-header {{
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
      }}
      .severity {{
        border-radius: 999px;
        padding: 3px 10px;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: white;
        background: var(--danger);
      }}
      .severity.High {{
        background: var(--warning);
      }}
      .severity.Medium {{
        background: #6b7280;
      }}
      .severity.Low, .severity.Info {{
        background: #9ca3af;
      }}
      .finding-meta {{
        margin-top: 10px;
      }}
      .finding-meta td {{
        padding: 2px 0;
        vertical-align: top;
      }}
      .code-block {{
        margin-top: 12px;
        border: 1px solid var(--line);
        border-radius: 12px;
        overflow: hidden;
        background: #0d1117;
        color: #c9d1d9;
        font-family: "SFMono-Regular", "SF Mono", Menlo, Monaco, Consolas, monospace;
        font-size: 11px;
      }}
      .code-line {{
        display: grid;
        grid-template-columns: 54px 1fr;
      }}
      .code-line span {{
        padding: 4px 10px;
        white-space: pre-wrap;
        word-break: break-word;
      }}
      .code-line .line-no {{
        color: rgba(201, 209, 217, 0.45);
        border-right: 1px solid rgba(201, 209, 217, 0.1);
        text-align: right;
      }}
      .code-line.issue {{
        background: rgba(180, 64, 50, 0.25);
      }}
      .policy-reasons {{
        margin-top: 10px;
        padding-left: 18px;
      }}
      .empty {{
        padding: 18px;
        border: 1px dashed var(--line);
        border-radius: 16px;
        color: var(--muted);
      }}
    </style>
  </head>
  <body>
    <main class="page">
      <section class="hero">
        <div style="display: flex; align-items: center; gap: 8px;">
          {_BRAND_MARK}
          <p class="eyebrow">VigilWeave report</p>
        </div>
        <div class="hero-grid">
          <div>
            <h1>Scan #{scan.id} report</h1>
            <p class="muted" style="margin-top: 8px;">{escape(scan.repo)}</p>
            <p class="muted">Generated {generated_at}</p>
            <div style="margin-top: 12px;">
              <span class="pill">{escape(_gate_label(scan.quality_gate_passed))}</span>
            </div>
          </div>
          <table class="meta-list">
            <tr><td class="metric-label">Branch</td><td>{escape(scan.branch or "N/A")}</td></tr>
            <tr><td class="metric-label">Commit</td><td>{escape(scan.commit or "N/A")}</td></tr>
            <tr><td class="metric-label">Source</td><td>{escape(scan.source)}</td></tr>
            <tr><td class="metric-label">Scan type</td><td>{escape(scan.scan_type.value)}</td></tr>
            <tr><td class="metric-label">Completed</td><td>{
        escape(_datetime_text(scan.completed_at))
    }</td></tr>
          </table>
        </div>
      </section>

      <section class="summary-grid">
        {_summary_cards_html(summary_cards)}
      </section>

      <section class="panel">
        <div class="section-title">
          <div>
            <p class="eyebrow">Policy</p>
            <h2>Quality gate evaluation</h2>
          </div>
        </div>
        {_policy_html(policy)}
      </section>

      <section class="breakdown-grid">
        <div class="panel">
          <div class="section-title">
            <div>
              <p class="eyebrow">Breakdown</p>
              <h2>Severity</h2>
            </div>
          </div>
          {_breakdown_html(severity_counts)}
        </div>
        <div class="panel">
          <div class="section-title">
            <div>
              <p class="eyebrow">Breakdown</p>
              <h2>Category</h2>
            </div>
          </div>
          {_breakdown_html(category_counts)}
        </div>
        <div class="panel">
          <div class="section-title">
            <div>
              <p class="eyebrow">Breakdown</p>
              <h2>Tool</h2>
            </div>
          </div>
          {_breakdown_html(tool_counts)}
        </div>
      </section>

      <section class="panel">
        <div class="section-title">
          <div>
            <p class="eyebrow">Quality</p>
            <h2>Metrics summary</h2>
          </div>
        </div>
        <table class="quality-table">
          {
        "".join(
            f"<tr><td class='metric-label'>{escape(label)}</td><td>{escape(value)}</td></tr>"
            for label, value in quality_rows
        )
    }
        </table>
      </section>

      <section class="panel">
        <div class="section-title">
          <div>
            <p class="eyebrow">Top findings</p>
            <h2>Prioritized issues</h2>
          </div>
          <p class="muted">Showing {len(top_findings)} of {len(findings)} filtered findings</p>
        </div>
        {_top_findings_html(top_findings)}
      </section>
    </main>
  </body>
</html>
"""


def _summary_cards_html(cards: list[tuple[str, str]]) -> str:
    return "".join(
        (
            f"<article class='card'><p class='eyebrow'>{escape(label)}</p>"
            f"<strong>{escape(value)}</strong></article>"
        )
        for label, value in cards
    )


def _policy_html(policy: dict[str, Any] | None) -> str:
    policy_data = policy if isinstance(policy, dict) else None
    if policy_data is None:
        return "<div class='empty'>No policy evaluation metadata is stored for this scan.</div>"

    thresholds = (
        policy_data.get("thresholds") if isinstance(policy_data.get("thresholds"), dict) else {}
    )
    reasons = policy_data.get("reasons") if isinstance(policy_data.get("reasons"), list) else []
    profile_name = str(policy_data.get("profile_name") or "No matched profile")
    matched = bool(policy_data.get("matched"))
    passed = bool(policy_data.get("passed"))

    threshold_rows = [
        ("Profile", profile_name),
        ("Matched", "Yes" if matched else "No"),
        ("Passed", "Yes" if passed else "No"),
        (
            "Critical threshold",
            str(thresholds.get("max_critical_findings", "N/A")),
        ),
        (
            "High threshold",
            str(thresholds.get("max_high_findings", "N/A")),
        ),
        (
            "Minimum quality",
            str(thresholds.get("min_quality_score", "N/A")),
        ),
    ]
    reasons_html = (
        "<ul class='policy-reasons'>"
        + "".join(f"<li>{escape(str(reason))}</li>" for reason in reasons)
        + "</ul>"
        if reasons
        else "<p class='muted' style='margin-top: 10px;'>No policy violations were recorded.</p>"
    )
    return (
        "<table class='quality-table'>"
        + "".join(
            f"<tr><td class='metric-label'>{escape(label)}</td><td>{escape(value)}</td></tr>"
            for label, value in threshold_rows
        )
        + "</table>"
        + reasons_html
    )


def _breakdown_html(counts: Counter[str]) -> str:
    if not counts:
        return "<div class='empty'>No findings matched the current filters.</div>"
    return (
        "<div class='breakdown-list'>"
        + "".join(
            f"<div class='breakdown-row'><span>{escape(label)}</span><strong>{count}</strong></div>"
            for label, count in counts.most_common()
        )
        + "</div>"
    )


def _top_findings_html(findings: list[Finding]) -> str:
    if not findings:
        return "<div class='empty'>No findings matched the current filters.</div>"
    return "".join(_finding_html(finding) for finding in findings)


def _finding_html(finding: Finding) -> str:
    location = "N/A"
    if finding.file_path:
        location = finding.file_path
        if finding.line:
            location = f"{location}:{finding.line}"
    code_context = _code_context_html(finding.tool_metadata)
    return f"""
<article class="finding">
  <div class="finding-header">
    <div>
      <h3>{escape(finding.title)}</h3>
      <p class="muted" style="margin-top: 4px;">{escape(finding.message)}</p>
    </div>
    <span class="severity {escape(finding.severity.value)}">{escape(finding.severity.value)}</span>
  </div>
  <table class="finding-meta">
    <tr><td class="metric-label">Category</td><td>{escape(finding.category)}</td></tr>
    <tr><td class="metric-label">Tool</td><td>{escape(finding.tool)}</td></tr>
    <tr><td class="metric-label">Location</td><td>{escape(location)}</td></tr>
    <tr><td class="metric-label">Rule</td><td>{
        escape(finding.rule_id or finding.identifier or "N/A")
    }</td></tr>
    <tr><td class="metric-label">Review status</td><td>{escape(finding.review_status)}</td></tr>
  </table>
  {
        (
            f"<p class='muted' style='margin-top: 10px;'>{escape(finding.description)}</p>"
            if finding.description
            else ""
        )
    }
  {code_context}
</article>
"""


def _code_context_html(tool_metadata: dict[str, Any] | None) -> str:
    if not isinstance(tool_metadata, dict):
        return ""
    context = tool_metadata.get("code_context")
    if not isinstance(context, dict):
        return ""
    lines = context.get("lines")
    issue_line = context.get("issue_line")
    if not isinstance(lines, list):
        return ""
    rendered_lines: list[str] = []
    for entry in lines:
        if not isinstance(entry, dict):
            continue
        line_number = entry.get("line")
        text = entry.get("text")
        if not isinstance(line_number, int) or not isinstance(text, str):
            continue
        issue_class = " issue" if line_number == issue_line else ""
        rendered_lines.append(
            "<div class='code-line"
            + issue_class
            + (
                f"'><span class='line-no'>{line_number}</span>"
                f"<span>{escape(text) or '&nbsp;'}</span></div>"
            )
        )
    if not rendered_lines:
        return ""
    return "<div class='code-block'>" + "".join(rendered_lines) + "</div>"


def _gate_label(gate_passed: bool | None) -> str:
    if gate_passed is True:
        return "Quality Gate Passed"
    if gate_passed is False:
        return "Quality Gate Failed"
    return "Gate Not Evaluated"


def _datetime_text(value: datetime | None) -> str:
    if value is None:
        return "N/A"
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _metric_text(value: float | None, *, suffix: str = "", digits: int = 0) -> str:
    if value is None:
        return "N/A"
    return f"{value:.{digits}f}{suffix}"
