"""Render an audit report as a single self-contained HTML analytics dashboard.

JSON stays the canonical output (per the spec); this is the human-facing view for a demo:
one file, inline CSS + inline SVG charts, no external assets or fonts, everything HTML-escaped.
It reads the ``analytics`` block (see ``analytics.py``) to present an analyst-grade report —
KPI row, executive summary, score projection, pillar radar, severity + effort charts, a
Now/Next/Later roadmap, page hotspots, and filterable findings — degrading gracefully to a
findings list if analytics is absent.
"""
from __future__ import annotations

import html
import json
import math
from typing import Any, Dict, List

_SEV_COLOR = {
    "critical": "#c0182f", "high": "#e05a1e", "medium": "#e0a500",
    "low": "#3f9d63", "info": "#6b7a8d",
}
_GRADE_COLOR = {"A": "#2e7d32", "B": "#66a838", "C": "#e0a500", "D": "#ef6c00", "F": "#c0182f"}
_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
_STATUS_COLOR = {"healthy": "#2e7d32", "warning": "#e0a500", "critical": "#c0182f",
                 "partial": "#2f6fb0", "not_assessed": "#8a8f98", "issues": "#e05a1e",
                 "opportunities": "#7a4fd0"}
_QUADRANT_COLOR = {
    "quick_win": "#2e7d32", "major_project": "#2f6fb0",
    "fill_in": "#8a8f98", "low_priority": "#b9bec6",
}
_QUADRANT_LABEL = {
    "quick_win": "Quick win", "major_project": "Major project",
    "fill_in": "Fill-in", "low_priority": "Low priority",
}


def render_html(report: Dict[str, Any]) -> str:
    """Return a complete HTML document string for *report*."""
    site = html.escape(str(report.get("site", "")))
    score = report.get("score", {})
    an = report.get("analytics", {})
    value = score.get("value", 0)
    grade = score.get("grade", "F")
    summary = report.get("summary", {})
    findings = report.get("findings", [])

    sections = [
        _hero(report, site, score, value, grade),
        _toolbar(),
        _kpi_row(an, summary),
        _exec_summary(an),
        _coverage_section(report),
        _projection_section(an),
        _score_explanation(report, an),
        _pillars_section(an),
        _charts_section(an),
        _roadmap_section(an),
        _hotspots_section(an),
        _sections_section(report),
        _findings_section(findings),
        _page_explorer_section(report),
        _opportunities_section(report),
        _limitations_section(report),
        _methodology(report),
    ]
    body = "\n".join(s for s in sections if s)
    # Embed the CANONICAL report so the UI (page explorer, exports, filters) reads one source of
    # truth — the rendered report and the exported JSON can never silently disagree.
    data = json.dumps(report, ensure_ascii=False).replace("</", "<\\/")

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Readiness Audit — {site}</title>
<style>{_CSS}</style></head>
<body>
{body}
<script id="audit-data" type="application/json">{data}</script>
<script>{_JS}</script>
</body></html>"""


def _toolbar() -> str:
    """Export/print controls (progressive-enhancement; hidden without JS)."""
    return """<div class="toolbar" hidden>
  <button id="dl-json" class="tbtn">⬇ Download JSON</button>
  <button id="copy-json" class="tbtn">⧉ Copy JSON</button>
  <button id="print" class="tbtn">🖶 Print</button>
  <span id="copy-note" class="tbtn-note" hidden>copied</span>
</div>"""


# --- hero -------------------------------------------------------------------------

def _hero(report, site, score, value, grade) -> str:
    disc = score.get("discoverability", 0)
    eng = score.get("engagement", 0)
    return f"""<header class="hero">
  <div class="gauge">{_gauge_svg(value, grade)}</div>
  <div class="hero-meta">
    <div class="eyebrow">AI Visibility Score</div>
    <h1>{site}</h1>
    <div class="subscores">
      {_subscore("Discoverability", disc)}
      {_subscore("Engagement", eng)}
    </div>
    <div class="meta-line">Audited {html.escape(str(report.get('audited_at','')))} ·
      profile: {html.escape(str(report.get('profile','balanced')))} ·
      {report.get('pages_crawled',0)} page(s) crawled</div>
    {_comparison_badge(report.get('comparison'))}
  </div>
</header>"""


def _comparison_badge(cmp: Any) -> str:
    """Render the score-vs-previous delta badge, if history comparison is present."""
    if not cmp or cmp.get("delta") is None:
        return ""
    delta = cmp["delta"]
    arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "=")
    color = "#7bd88f" if delta > 0 else ("#ff9a9a" if delta < 0 else "#ccc")
    return (f'<div class="delta" style="color:{color}">{arrow} {delta:+d} vs previous '
            f'({html.escape(str(cmp.get("previous_score")))} on '
            f'{html.escape(str(cmp.get("previous_at","")))[:10]})</div>')


def _gauge_svg(value: int, grade: str) -> str:
    """An SVG donut gauge showing the overall score and grade."""
    color = _GRADE_COLOR.get(grade, "#c0182f")
    r = 52
    circ = 2 * math.pi * r
    frac = max(0, min(100, value)) / 100.0
    dash = circ * frac
    return f"""<svg viewBox="0 0 130 130" width="132" height="132" role="img" aria-label="Score {value} of 100">
  <circle cx="65" cy="65" r="{r}" fill="none" stroke="rgba(255,255,255,.18)" stroke-width="12"/>
  <circle cx="65" cy="65" r="{r}" fill="none" stroke="{color}" stroke-width="12"
    stroke-linecap="round" stroke-dasharray="{dash:.1f} {circ:.1f}"
    transform="rotate(-90 65 65)"/>
  <text x="65" y="60" text-anchor="middle" font-size="32" font-weight="700" fill="#fff">{value}</text>
  <text x="65" y="84" text-anchor="middle" font-size="14" fill="rgba(255,255,255,.7)">grade {html.escape(grade)}</text>
</svg>"""


def _subscore(label: str, value: float) -> str:
    """A labelled horizontal bar for a per-dimension sub-score."""
    pct = max(0, min(100, value))
    return f"""<div class="subscore"><span>{html.escape(label)}</span>
      <div class="bar"><i style="width:{pct}%"></i></div><b>{value}</b></div>"""


# --- KPI row ----------------------------------------------------------------------

def _kpi_row(an, summary) -> str:
    kpis = an.get("kpis")
    if not kpis:
        return _legacy_tiles(summary)
    cards = [
        _kpi(f"{kpis['ai_visibility_score']}", f"Score · grade {kpis['grade']}", "big"),
        _kpi(str(kpis["total_findings"]), "Findings"),
        _kpi(str(kpis["critical_high"]), "Critical + high", "warn" if kpis["critical_high"] else ""),
        _kpi(str(kpis["quick_wins"]), "Quick wins", "good" if kpis["quick_wins"] else ""),
        _kpi(f"{kpis['projected_score']}", f"After quick wins (+{kpis['projected_gain']})", "good"),
        _kpi(str(kpis.get("opportunities", 0)), "Opportunities"),
        _kpi(str(kpis["pages_analyzed"]), "Pages analyzed"),
    ]
    if kpis.get("areas_total"):
        cards.append(_kpi(f"{kpis.get('areas_assessed')}/{kpis['areas_total']}", "Areas assessed"))
    else:
        cards.append(_kpi(kpis["effort_band"], "Est. effort"))
    return f'<section class="kpis">{"".join(cards)}</section>'


def _kpi(value: str, label: str, cls: str = "") -> str:
    return (f'<div class="kpi {cls}"><div class="kpi-n">{html.escape(str(value))}</div>'
            f'<div class="kpi-l">{html.escape(label)}</div></div>')


def _legacy_tiles(summary) -> str:
    """Fallback tiles if the analytics block is missing."""
    def tile(label, count, sev=""):
        color = _SEV_COLOR.get(sev, "#334")
        return (f'<div class="kpi"><div class="kpi-n" style="color:{color}">{count}</div>'
                f'<div class="kpi-l">{label}</div></div>')
    return f"""<section class="kpis">
  {tile("Findings", summary.get("total_findings", 0))}
  {tile("Critical", summary.get("critical", 0), "critical")}
  {tile("High", summary.get("high", 0), "high")}
  {tile("Medium", summary.get("medium", 0), "medium")}
  {tile("Low", summary.get("low", 0), "low")}
</section>"""


# --- executive summary ------------------------------------------------------------

def _exec_summary(an) -> str:
    lines = an.get("narrative")
    if not lines:
        return ""
    items = "".join(f"<p>{html.escape(str(l))}</p>" for l in lines)
    return f"""<section class="card summary">
  <h2>Executive summary</h2>
  <div class="summary-body">{items}</div>
</section>"""


# --- coverage matrix --------------------------------------------------------------

_CHECK_STATE = {"pass": ("✓", "#2e7d32"), "fail": ("✕", "#c0182f"),
                "not_verified": ("?", "#8a8f98"), "partial": ("~", "#2f6fb0")}


def _coverage_section(report) -> str:
    cov = report.get("coverage") or {}
    areas = cov.get("areas")
    if not areas:
        return ""
    rows = "".join(_coverage_row(a) for a in areas)
    s = cov.get("summary", {})
    parts = []
    if s.get("areas_fully_assessed") is not None:
        parts.append(f'{s["areas_fully_assessed"]} fully assessed')
    if s.get("areas_partial"):
        parts.append(f'{s["areas_partial"]} partially assessed')
    if s.get("areas_not_assessed"):
        parts.append(f'{s["areas_not_assessed"]} not assessed')
    note = " · ".join(parts) + " — 0 findings ≠ healthy"
    return f"""<section class="card">
  <h2>Coverage <span class="hint">{html.escape(note)}</span></h2>
  <div class="cov-list">{rows}</div>
</section>"""


def _coverage_row(a: Dict[str, Any]) -> str:
    color = _STATUS_COLOR.get(a["status"], "#889")
    checks = a.get("checks", [])
    summary_counts = []
    if a.get("passed"):
        summary_counts.append(f'{a["passed"]}✓')
    if a.get("failed"):
        summary_counts.append(f'<span style="color:#c0182f">{a["failed"]}✕</span>')
    if a.get("not_verified"):
        summary_counts.append(f'{a["not_verified"]}?')
    if a.get("partial_checks"):
        summary_counts.append(f'{a["partial_checks"]}~')
    counts = " · ".join(summary_counts) or "—"
    check_items = "".join(
        f'<li><span class="cstate" style="color:{_CHECK_STATE.get(c["state"], ("•","#889"))[1]}">'
        f'{_CHECK_STATE.get(c["state"], ("•","#889"))[0]}</span> {html.escape(c["label"])} '
        f'<em>{html.escape(c["state"].replace("_"," "))}</em></li>' for c in checks)
    body = (f'<ul class="clist">{check_items}</ul>' if check_items else
            f'<p class="hint">{html.escape(a.get("note",""))}</p>')
    return f"""<details class="cov-row">
  <summary>
    <span class="chip mini" style="background:{color}">{html.escape(a.get("status_label", a["status"]))}</span>
    <span class="cov-area">{html.escape(a["label"])}</span>
    <span class="cov-counts">{counts}</span>
    <span class="cov-meta">{a.get("pages_assessed",0)} pg · {html.escape(a.get("confidence",""))} conf</span>
  </summary>
  <div class="cov-body"><p class="cov-note">{html.escape(a.get("note",""))}</p>{body}</div>
</details>"""


# --- score explanation ------------------------------------------------------------

def _score_explanation(report, an) -> str:
    score = report.get("score", {})
    if not score:
        return ""
    matrix = an.get("matrix", []) if an else []
    contrib = sorted([m for m in matrix if m.get("points_at_stake", 0) > 0],
                     key=lambda m: -m["points_at_stake"])[:6]
    rows = "".join(
        f'<li><span class="pe-id">{html.escape(m["id"])}</span>'
        f'<span class="pe-t">{html.escape(m["title"])}</span>'
        f'<b class="pe-p">−{m["points_at_stake"]}</b></li>' for m in contrib)
    contrib_html = f'<ul class="pe-list">{rows}</ul>' if rows else \
        '<p class="hint">No findings are currently reducing the score.</p>'
    return f"""<section class="card">
  <h2>How this score is calculated <span class="hint">deterministic &amp; traceable</span></h2>
  <p class="method">Overall = round(discoverability×0.6 + engagement×0.4). Each dimension starts
    at 100 and loses <code>severity&nbsp;×&nbsp;confidence</code> points per finding
    (critical 35 · high 18 · medium 8 · low 3 · info 1; ×1.0/0.75/0.5 for high/medium/low
    confidence). Current: discoverability <b>{score.get('discoverability',0)}</b>,
    engagement <b>{score.get('engagement',0)}</b> → <b>{score.get('value',0)}</b>.</p>
  <p class="method">Biggest point recoveries if fixed (each re-scored against the same model):</p>
  {contrib_html}
</section>"""


# --- proactive opportunities ------------------------------------------------------

def _opportunities_section(report) -> str:
    opps = report.get("opportunities") or []
    if not opps:
        return ""
    cards = ""
    for o in opps:
        cards += f"""<div class="opp">
      <div class="opp-head"><span class="chip mini" style="background:#7a4fd0">{html.escape(o.get('category',''))}</span>
        <span class="opp-title">{html.escape(o.get('title',''))}</span>
        <span class="opp-meta">{html.escape(str(o.get('effort','')))} effort · {html.escape(str(o.get('confidence','')))} confidence</span></div>
      <p class="opp-why">{html.escape(o.get('rationale',''))}</p>
      <p class="opp-do"><b>Do:</b> {html.escape(o.get('suggested_action',''))}</p>
      <p class="opp-impact"><b>Expected impact:</b> {html.escape(o.get('expected_impact',''))}</p>
    </div>"""
    return f"""<section class="card">
  <h2>Proactive opportunities <span class="hint">context-justified — not defects, no score impact</span></h2>
  {cards}
</section>"""


# --- limitations ------------------------------------------------------------------

def _limitations_section(report) -> str:
    cov = report.get("coverage") or {}
    not_assessed = [a["label"] for a in cov.get("areas", []) if a.get("status") == "not_assessed"]
    partial = [a["label"] for a in cov.get("areas", []) if a.get("status") == "partial"]
    items = [
        "Static, read-only analysis: JavaScript is not executed, so client-rendered content is "
        "inferred (medium confidence), not confirmed against a rendered DOM.",
        f"A bounded sample of {report.get('pages_crawled', 0)} page(s) was analyzed — findings describe "
        "patterns across the sample, not every URL on the site.",
        "Corroboration checks on-page signals only; it does not independently verify claims against "
        "external sources.",
    ]
    if not_assessed:
        items.append("Not assessed (insufficient signal or skill not run): " + ", ".join(not_assessed) + ".")
    if partial:
        items.append("Partially assessed: " + ", ".join(partial) + ".")
    lis = "".join(f"<li>{html.escape(x)}</li>" for x in items)
    return f"""<section class="card">
  <h2>Limitations <span class="hint">what this audit does and doesn't claim</span></h2>
  <ul class="limits">{lis}</ul>
</section>"""


# --- projection -------------------------------------------------------------------

def _projection_section(an) -> str:
    p = an.get("projection")
    if not p:
        return ""
    bars = [
        ("Current", p["current"], p["current_grade"], "#6b7a8d"),
        ("After quick wins", p["after_quick_wins"], p["after_quick_wins_grade"], "#3f9d63"),
        ("If all fixed", p["after_all_fixed"], p["after_all_grade"], "#2e7d32"),
    ]
    rows = "".join(
        f"""<div class="pbar">
          <span class="pbar-l">{html.escape(label)}</span>
          <div class="pbar-track"><i style="width:{max(2,min(100,val))}%;background:{color}"></i></div>
          <b class="pbar-v">{val} <em>({html.escape(g)})</em></b>
        </div>""" for label, val, g, color in bars)
    note = ""
    tng = p.get("to_next_grade")
    if tng:
        reach = "reachable with quick wins" if p.get("quick_wins_reach_next_grade") else \
                f"needs {tng['points']} more point(s)"
        note = f'<p class="proj-note">Next grade <b>{html.escape(tng["grade"])}</b> — {reach}.</p>'
    return f"""<section class="card">
  <h2>Score projection <span class="hint">what fixing issues would do</span></h2>
  <div class="pbars">{rows}</div>
  {note}
</section>"""


# --- pillars (radar + list) -------------------------------------------------------

def _pillars_section(an) -> str:
    pillars = an.get("pillars")
    if not pillars:
        return ""
    rows = "".join(_pillar_row(p) for p in pillars)
    return f"""<section class="card">
  <h2>Pillar health <span class="hint">six areas of AI readiness</span></h2>
  <div class="pillars-grid">
    <div class="radar">{_radar_svg(pillars)}</div>
    <ul class="pillar-list">{rows}</ul>
  </div>
</section>"""


# Short axis labels so nothing clips at the edge of the radar.
_PILLAR_SHORT = {
    "crawl_render": "Crawl", "structured_data": "Structured", "extractability": "Extract",
    "freshness": "Fresh", "corroboration": "Corrob", "engagement": "Engage",
}


_PILLAR_STATUS_LABEL = {"healthy": "healthy", "warning": "needs work", "critical": "critical",
                        "partial": "partial", "not_assessed": "not assessed"}


def _pillar_row(p: Dict[str, Any]) -> str:
    color = _STATUS_COLOR.get(p["status"], "#889")
    na = p["status"] == "not_assessed"
    score_cell = "—" if na else f"{p['score']:.0f}"
    if na or p["status"] == "partial":
        right = _PILLAR_STATUS_LABEL.get(p["status"], p["status"])
    else:
        right = f"{p['findings']} issue(s)"
    width = 0 if na else max(2, min(100, p["score"]))
    return (f'<li><span class="dot" style="background:{color}"></span>'
            f'<span class="pill-l">{html.escape(p["label"])}</span>'
            f'<span class="pill-track"><i style="width:{width}%;background:{color}"></i></span>'
            f'<b>{score_cell}</b>'
            f'<span class="pill-n">{html.escape(str(right))}</span></li>')


def _radar_svg(pillars: List[Dict[str, Any]]) -> str:
    """A radar/spider chart of the pillar scores (0–100 on each axis)."""
    # Wide viewBox with the chart centered leaves horizontal room for the axis labels.
    cx, cy, R = 190, 150, 104
    n = len(pillars)
    if n < 3:
        return ""
    rings = "".join(
        f'<circle cx="{cx}" cy="{cy}" r="{R*frac:.1f}" fill="none" stroke="#e6e8ec" stroke-width="1"/>'
        for frac in (0.25, 0.5, 0.75, 1.0))
    axes, labels, pts = [], [], []
    for i, p in enumerate(pillars):
        ang = -math.pi / 2 + i * 2 * math.pi / n
        ax, ay = cx + R * math.cos(ang), cy + R * math.sin(ang)
        axes.append(f'<line x1="{cx}" y1="{cy}" x2="{ax:.1f}" y2="{ay:.1f}" stroke="#e6e8ec" stroke-width="1"/>')
        frac = max(0, min(100, p["score"])) / 100.0
        px, py = cx + R * frac * math.cos(ang), cy + R * frac * math.sin(ang)
        pts.append(f"{px:.1f},{py:.1f}")
        lx, ly = cx + (R + 14) * math.cos(ang), cy + (R + 14) * math.sin(ang)
        anchor = "middle" if abs(math.cos(ang)) < 0.3 else ("start" if math.cos(ang) > 0 else "end")
        short = html.escape(_PILLAR_SHORT.get(p["key"], p["label"].split(" ")[0]))
        labels.append(f'<text x="{lx:.1f}" y="{ly+4:.1f}" text-anchor="{anchor}" '
                      f'font-size="11" fill="#5a6472">{short}</text>')
    poly = " ".join(pts)
    return f"""<svg viewBox="0 0 380 300" width="100%" role="img" aria-label="Pillar radar chart">
  {rings}
  {''.join(axes)}
  <polygon points="{poly}" fill="rgba(47,111,176,.20)" stroke="#2f6fb0" stroke-width="2"/>
  {''.join(f'<circle cx="{pt.split(",")[0]}" cy="{pt.split(",")[1]}" r="3" fill="#2f6fb0"/>' for pt in pts)}
  {''.join(labels)}
</svg>"""


# --- charts (severity donut + impact/effort matrix) -------------------------------

def _charts_section(an) -> str:
    dist = an.get("distribution")
    matrix = an.get("matrix")
    if not dist and not matrix:
        return ""
    left = f"""<div class="chart-card">
      <h3>Findings by severity</h3>
      {_severity_donut_svg(dist.get("by_severity", []) if dist else [])}
      {_confidence_bar(dist.get("by_confidence", []) if dist else [])}
    </div>"""
    right = f"""<div class="chart-card">
      <h3>Impact × effort <span class="hint">top-left = do first</span></h3>
      {_matrix_svg(matrix or [])}
    </div>"""
    return f'<section class="charts">{left}{right}</section>'


def _severity_donut_svg(by_sev: List[Dict[str, Any]]) -> str:
    total = sum(s["count"] for s in by_sev) or 0
    if not total:
        return '<p class="empty">No findings.</p>'
    cx, cy, r, sw = 90, 90, 62, 26
    circ = 2 * math.pi * r
    segs, legend, offset = [], [], 0.0
    for s in by_sev:
        frac = s["count"] / total
        color = _SEV_COLOR.get(s["key"], "#889")
        dash = circ * frac
        segs.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="{sw}" '
            f'stroke-dasharray="{dash:.1f} {circ - dash:.1f}" stroke-dashoffset="{-offset:.1f}" '
            f'transform="rotate(-90 {cx} {cy})"/>')
        offset += dash
        legend.append(
            f'<li><span class="dot" style="background:{color}"></span>'
            f'{html.escape(s["key"].title())} <b>{s["count"]}</b> '
            f'<em>{s["pct"]}%</em></li>')
    return f"""<div class="donut-wrap">
      <svg viewBox="0 0 180 180" width="160" height="160" role="img" aria-label="Severity distribution">
        {''.join(segs)}
        <text x="{cx}" y="{cy-4}" text-anchor="middle" font-size="30" font-weight="700" fill="#1c2430">{total}</text>
        <text x="{cx}" y="{cy+16}" text-anchor="middle" font-size="12" fill="#7a8595">findings</text>
      </svg>
      <ul class="legend">{''.join(legend)}</ul>
    </div>"""


def _confidence_bar(by_conf: List[Dict[str, Any]]) -> str:
    if not by_conf:
        return ""
    conf_color = {"high": "#3f9d63", "medium": "#e0a500", "low": "#c0182f"}
    segs = "".join(
        f'<span style="width:{c["pct"]}%;background:{conf_color.get(c["key"], "#889")}" '
        f'title="{html.escape(c["key"])} {c["count"]} ({c["pct"]}%)"></span>'
        for c in by_conf)
    keys = " · ".join(f'{html.escape(c["key"])} {c["pct"]}%' for c in by_conf)
    return f"""<div class="conf">
      <div class="conf-l">Confidence</div>
      <div class="conf-bar">{segs}</div>
      <div class="conf-legend">{keys}</div>
    </div>"""


def _matrix_svg(items: List[Dict[str, Any]]) -> str:
    """Scatter findings on an impact (y) × effort (x) grid with quadrant shading."""
    if not items:
        return '<p class="empty">No findings to plot.</p>'
    W, H = 320, 260
    pad_l, pad_b, pad_t, pad_r = 40, 34, 14, 14
    plot_w, plot_h = W - pad_l - pad_r, H - pad_b - pad_t
    # data range 0.5..5.5 so points 1..5 sit inside
    def sx(effort):
        return pad_l + (effort - 0.5) / 5.0 * plot_w
    def sy(impact):
        return pad_t + (1 - (impact - 0.5) / 5.0) * plot_h
    # quadrant boundaries: effort 2.5, impact 2.5
    bx, by = sx(2.5), sy(2.5)
    # jitter points sharing a cell so they don't fully overlap
    seen: Dict[tuple, int] = {}
    dots = []
    for it in items:
        key = (it["impact"], it["effort"])
        k = seen.get(key, 0)
        seen[key] = k + 1
        jx = ((k % 3) - 1) * 7
        jy = ((k // 3) - 1) * 7
        cx, cy = sx(it["effort"]) + jx, sy(it["impact"]) + jy
        color = _SEV_COLOR.get(it["severity"], "#889")
        rad = 5 + min(4, it.get("points_at_stake", 0))
        dots.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{rad}" fill="{color}" fill-opacity="0.85" '
            f'stroke="#fff" stroke-width="1"><title>{html.escape(it["title"])} — '
            f'impact {it["impact"]}, effort {it["effort"]}, +{it.get("points_at_stake",0)} pts</title></circle>')
    return f"""<svg class="matrix-svg" viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Impact by effort matrix">
  <rect x="{pad_l}" y="{pad_t}" width="{bx-pad_l:.1f}" height="{by-pad_t:.1f}" fill="rgba(46,125,50,.08)"/>
  <text x="{(pad_l+bx)/2:.0f}" y="{pad_t+14}" text-anchor="middle" font-size="10" fill="#2e7d32" font-weight="700">QUICK WINS</text>
  <text x="{(bx+W-pad_r)/2:.0f}" y="{pad_t+14}" text-anchor="middle" font-size="10" fill="#2f6fb0" font-weight="700">MAJOR PROJECTS</text>
  <line x1="{bx:.1f}" y1="{pad_t}" x2="{bx:.1f}" y2="{H-pad_b}" stroke="#cfd4db" stroke-dasharray="4 3"/>
  <line x1="{pad_l}" y1="{by:.1f}" x2="{W-pad_r}" y2="{by:.1f}" stroke="#cfd4db" stroke-dasharray="4 3"/>
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{H-pad_b}" stroke="#9aa4b0" stroke-width="1"/>
  <line x1="{pad_l}" y1="{H-pad_b}" x2="{W-pad_r}" y2="{H-pad_b}" stroke="#9aa4b0" stroke-width="1"/>
  <text x="{pad_l-8}" y="{pad_t+6}" text-anchor="end" font-size="9" fill="#7a8595">5</text>
  <text x="{pad_l-8}" y="{H-pad_b}" text-anchor="end" font-size="9" fill="#7a8595">1</text>
  <text x="12" y="{(pad_t+H-pad_b)/2:.0f}" text-anchor="middle" font-size="10" fill="#5a6472"
    transform="rotate(-90 12 {(pad_t+H-pad_b)/2:.0f})">Impact →</text>
  <text x="{(pad_l+W-pad_r)/2:.0f}" y="{H-8}" text-anchor="middle" font-size="10" fill="#5a6472">Effort →</text>
  {''.join(dots)}
</svg>"""


# --- roadmap ----------------------------------------------------------------------

def _roadmap_section(an) -> str:
    rm = an.get("roadmap")
    if not rm or not (rm.get("now") or rm.get("next") or rm.get("later")):
        return ""
    cols = []
    for bucket, title, sub in (("now", "Now", "critical & high severity, plus quick wins (any severity)"),
                               ("next", "Next", "remaining medium-severity fixes"),
                               ("later", "Later", "remaining low-severity refinements")):
        items = rm.get(bucket, [])
        lis = "".join(
            f'<li><span class="chip mini" style="background:{_SEV_COLOR.get(it["severity"], "#889")}">'
            f'{html.escape(it["severity"][:4].upper())}</span> {html.escape(it["title"])} '
            f'<em>({html.escape(it["effort_label"].lower())} effort)</em></li>'
            for it in items) or '<li class="none">—</li>'
        cols.append(f'<div class="road-col"><h3>{title} <span>{len(items)}</span></h3>'
                    f'<p class="road-sub">{sub}</p><ul>{lis}</ul></div>')
    return f'<section class="card"><h2>Action roadmap</h2><div class="roadmap">{"".join(cols)}</div></section>'


# --- hotspots ---------------------------------------------------------------------

def _hotspots_section(an) -> str:
    hs = an.get("hotspots")
    if not hs:
        return ""
    rows = "".join(
        f'<tr><td class="url">{html.escape(h["url"])}</td>'
        f'<td>{h["findings"]}</td><td>{h["impact"]}</td>'
        f'<td><span class="chip mini" style="background:{_SEV_COLOR.get(h["top_severity"], "#889")}">'
        f'{html.escape(h["top_severity"].upper())}</span></td></tr>'
        for h in hs)
    return f"""<section class="card">
  <h2>Page hotspots <span class="hint">pages carrying the most weighted issues</span></h2>
  <table class="hotspots">
    <thead><tr><th>Page</th><th>Findings</th><th>Impact</th><th>Top severity</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</section>"""


# --- site-section analysis --------------------------------------------------------

def _section_color(score: float) -> str:
    return "#2e7d32" if score >= 90 else "#e0a500" if score >= 70 else "#c0182f"


def _sections_section(report) -> str:
    sections = report.get("sections") or []
    if not sections:
        return ""
    rows = ""
    for s in sections:
        color = _section_color(s["score"])
        sev = s.get("top_severity")
        sev_chip = (f'<span class="chip mini" style="background:{_SEV_COLOR.get(sev, "#889")}">{html.escape(sev.upper())}</span>'
                    if sev else '<span class="sec-ok">clean</span>')
        rows += f"""<div class="sec-row">
          <span class="sec-l">{html.escape(s["label"])}</span>
          <span class="sec-track"><i style="width:{max(2,min(100,s['score']))}%;background:{color}"></i></span>
          <b class="sec-score" style="color:{color}">{s['score']}</b>
          <span class="sec-meta">{s['pages']} pg · {s['findings']} finding(s)</span>
          {sev_chip}
        </div>"""
    return f"""<section class="card">
  <h2>Section analysis <span class="hint">which part of the site drags the score — weakest first</span></h2>
  <div class="sec-list">{rows}</div>
</section>"""


# --- findings ---------------------------------------------------------------------

def _findings_section(findings: List[Dict[str, Any]]) -> str:
    inner = _findings_html(findings)
    controls = _filter_controls(findings)
    whatif = _whatif_panel(findings)
    return f"""<main class="card">
  <h2>Findings <span class="hint">(most actionable first)</span></h2>
  {whatif}
  {controls}
  <div id="findings">{inner}</div>
</main>"""


def _whatif_panel(findings: List[Dict[str, Any]]) -> str:
    """Live 'what-if' planner: tick findings to fix and watch the score recompute in the page."""
    if not findings:
        return ""
    return """<div class="whatif" hidden>
  <div class="wi-head">
    <span class="wi-title">What-if planner</span>
    <span class="wi-hint">tick findings below to simulate fixing them</span>
  </div>
  <div class="wi-scores">
    <div class="wi-box"><span>Current</span><b id="wi-current">–</b></div>
    <div class="wi-arrow">→</div>
    <div class="wi-box wi-proj"><span>Projected</span><b id="wi-proj">–</b> <em id="wi-grade"></em></div>
    <div class="wi-box"><span>Change</span><b id="wi-delta">+0</b></div>
    <div class="wi-box"><span>Fixed</span><b id="wi-count">0</b></div>
  </div>
  <div class="wi-actions">
    <button id="wi-quick" class="fbtn">Tick all quick wins</button>
    <button id="wi-all" class="fbtn">Tick all</button>
    <button id="wi-reset" class="fbtn">Reset</button>
  </div>
</div>"""


def _filter_controls(findings: List[Dict[str, Any]]) -> str:
    """Combined, dynamic filters — only dimensions/severities/confidences that actually occur.

    Dimension + severity + confidence + text search are AND-combined; results are sortable.
    """
    if len(findings) < 2:
        return ""
    dims = [d for d in ("discoverability", "engagement")
            if any(f.get("dimension") == d for f in findings)]
    sevs = [s for s in ("critical", "high", "medium", "low", "info")
            if any(f.get("severity") == s for f in findings)]
    confs = [c for c in ("high", "medium", "low")
             if any(f.get("confidence") == c for f in findings)]

    def sel(sid, label, opts):
        options = '<option value="all">All</option>' + "".join(
            f'<option value="{o}">{o.title()}</option>' for o in opts)
        return f'<label class="fsel">{label}<select id="{sid}">{options}</select></label>'

    controls = []
    if len(dims) > 1:
        controls.append(sel("f-dimension", "Dimension", dims))
    if len(sevs) > 1:
        controls.append(sel("f-severity", "Severity", sevs))
    if len(confs) > 1:
        controls.append(sel("f-confidence", "Confidence", confs))
    controls.append('<label class="fsel">Sort<select id="f-sort">'
                    '<option value="priority">Priority</option>'
                    '<option value="severity">Severity</option>'
                    '<option value="impact">Impact</option>'
                    '<option value="page">Affected pages</option></select></label>')
    controls.append('<input id="f-search" type="search" placeholder="Search findings…" aria-label="Search findings">')
    controls.append('<button id="f-reset" class="fbtn">Reset</button>')
    controls.append('<span id="f-count" class="fcount"></span>')
    return f'<div class="filters" role="group" aria-label="Filter findings">{"".join(controls)}</div>'


def _findings_html(findings: List[Dict[str, Any]]) -> str:
    """Render each finding as a collapsible <details> block."""
    if not findings:
        return '<p class="empty">No findings — the site is in good shape on the checks run.</p>'
    out = []
    for f in findings:
        sev = f.get("severity", "medium")
        color = _SEV_COLOR.get(sev, "#789")
        action = f.get("suggested_action", {})
        pages = f.get("affected_pages", []) or []
        pages_html = ""
        if pages:
            items = "".join(
                f'<li><a href="{html.escape(str(u))}" target="_blank" rel="noopener noreferrer">'
                f'{html.escape(str(u))} ↗</a> '
                f'<button class="fjump-pg" data-url="{html.escape(str(u))}">in explorer</button></li>'
                for u in pages[:10])
            more = f'<li class="more">+{len(pages)-10} more</li>' if len(pages) > 10 else ""
            pages_html = (f'<div class="pages"><span>Affected pages ({len(pages)})</span>'
                          f'<ul>{items}{more}</ul></div>')
        sortkey = _SEV_ORDER.get(sev, 9)
        out.append(f"""<details class="finding" id="{html.escape(str(f.get('id','')))}"
    data-severity="{html.escape(sev)}"
    data-dimension="{html.escape(str(f.get('dimension','')))}"
    data-confidence="{html.escape(str(f.get('confidence','')))}"
    data-category="{html.escape(str(f.get('category','')))}"
    data-impact="{f.get('impact', 0)}" data-priority="{f.get('priority', 999)}"
    data-pages="{len(pages)}" data-sev-order="{sortkey}"
    data-text="{html.escape((str(f.get('title',''))+' '+str(f.get('evidence',''))).lower())}">
  <summary>
    <label class="wi-check" title="Mark as fixed (what-if)"><input type="checkbox" class="wi-cb"></label>
    <span class="chip" style="background:{color}">{html.escape(sev.upper())}</span>
    <span class="dim">{html.escape(str(f.get('dimension','')))}</span>
    <span class="ftitle">{html.escape(str(f.get('title','')))}</span>
    <span class="impact" title="impact 1–5">impact {f.get('impact','')}</span>
  </summary>
  <div class="body">
    <p class="why"><b>Why it hurts:</b> {html.escape(str(f.get('why','')))}</p>
    <p class="evidence"><b>Evidence:</b> {html.escape(str(f.get('evidence','')))}</p>
    {_scope_line(f)}
    <p class="fix"><b>How to fix ({html.escape(str(action.get('priority','')))}):</b>
       {html.escape(str(f.get('how_to_fix') or action.get('summary','')))}</p>
    {_impact_line(f)}
    {_measurements_html(f)}
    {pages_html}
    <p class="cat">category: {html.escape(str(f.get('category','')))} ·
       confidence: {html.escape(str(f.get('confidence','')))} ·
       impact: {html.escape(str(f.get('impact','')))}/5 · id: {html.escape(str(f.get('id','')))}</p>
  </div>
</details>""")
    return "\n".join(out)


def _scope_line(f: Dict[str, Any]) -> str:
    return f'<p class="scope"><b>Scope:</b> {html.escape(str(f["scope"]))}</p>' if f.get("scope") else ""


def _impact_line(f: Dict[str, Any]) -> str:
    return (f'<p class="xi"><b>Expected impact:</b> {html.escape(str(f["expected_impact"]))}</p>'
            if f.get("expected_impact") else "")


def _measurements_html(f: Dict[str, Any]) -> str:
    m = f.get("measurements") or {}
    if not m:
        return ""
    chips = "".join(f'<span class="mchip">{html.escape(str(k))}: {html.escape(str(v))}</span>'
                    for k, v in list(m.items())[:8])
    return f'<div class="measures">{chips}</div>'


# --- page explorer ----------------------------------------------------------------

def _page_explorer_section(report) -> str:
    pages = report.get("pages") or []
    if not pages:
        return ""
    controls = """<div class="pe-controls">
      <input id="pe-search" type="search" placeholder="Search pages by URL / title…" aria-label="Search pages">
      <select id="pe-sort" aria-label="Sort pages">
        <option value="score">Lowest score first</option>
        <option value="findings">Most findings first</option>
        <option value="url">URL A–Z</option>
      </select>
      <span id="pe-count" class="pe-cnt"></span>
    </div>"""
    cards = "".join(_page_card(i, p) for i, p in enumerate(pages))
    return f"""<section class="card">
  <h2>Page explorer <span class="hint">{len(pages)} page(s) audited — click to expand</span></h2>
  {controls}
  <div id="page-list">{cards}</div>
</section>"""


def _page_card(i: int, p: Dict[str, Any]) -> str:
    sev = p.get("top_severity") or "none"
    sev_color = _SEV_COLOR.get(sev, "#8a8f98")
    url = html.escape(str(p.get("url", "")))
    title = html.escape(str(p.get("title", "")) or "(no title)")
    dims = ", ".join(p.get("dimensions", [])) or "—"
    sd = ", ".join(p.get("structured_data_types", [])) or "none"

    def row(label, val):
        return f'<div class="pf"><span>{html.escape(label)}</span><b>{html.escape(str(val))}</b></div>'

    idx = "yes" if p.get("indexable") else "NO (noindex)"
    facts = "".join([
        row("Title", (p.get("title") or "—")[:90] + (f"  ({p.get('title_len')} chars)" if p.get("title_len") else "")),
        row("Meta description", (p.get("meta_description") or "— none —")[:120]),
        row("H1", (p.get("h1") or "— none —")[:90] + (f"  (×{p.get('h1_count')})" if p.get("h1_count", 0) != 1 else "")),
        row("H2 sections", p.get("h2_count", 0)),
        row("Structured data", sd),
        row("Language", p.get("lang") or "— not set —"),
        row("Canonical", (p.get("canonical") or "— none —")[:90]),
        row("Indexable", idx),
        row("Links", f"{p.get('internal_links',0)} internal · {p.get('external_links',0)} external · {p.get('pdf_links',0)} PDF"),
        row("Primary CTA", "present" if p.get("cta_signal") else "not detected"),
        row("Images", f"{p.get('images',0)} ({p.get('images_missing_alt',0)} missing alt)"),
        row("Weight", f"{p.get('html_kb',0)} KB HTML · {p.get('scripts',0)} scripts" +
            (f" · {p.get('response_ms')} ms" if p.get("response_ms") is not None else "")),
        row("Rendering", "static HTML only (rendered DOM not verified)"),
        row("HTTP", f"{p.get('status','?')}" + (" · redirected" if p.get("redirected") else "")),
        row("Confidence", p.get("confidence", "—")),
    ])
    fids = p.get("finding_ids") or []
    fids_html = ""
    if fids:
        chips = "".join(f'<button class="fjump" data-fid="{html.escape(str(x))}">{html.escape(str(x))}</button>' for x in fids)
        fids_html = f'<div class="pf-findings"><span>Findings on this page</span>{chips}</div>'
    return f"""<details class="pcard" id="pg-{i}" data-url="{url}" data-score="{p.get('score',100)}"
    data-findings="{p.get('finding_count',0)}" data-title="{html.escape(str(p.get('title','')).lower())}">
  <summary>
    <span class="pscore" style="color:{sev_color}">{p.get('score',100)}</span>
    <span class="ptitle">{title}</span>
    <span class="purl">{url}</span>
    <span class="pmeta">{p.get('finding_count',0)} finding(s) · {html.escape(dims)}</span>
    <a class="popen" href="{url}" target="_blank" rel="noopener noreferrer">Open ↗</a>
  </summary>
  <div class="pbody">{facts}{fids_html}</div>
</details>"""


# --- methodology / footer ---------------------------------------------------------

def _methodology(report) -> str:
    notes = report.get("notes", []) or []
    skills = report.get("skills_run", []) or []
    notes_html = "".join(f"<li>{html.escape(str(n))}</li>" for n in notes)
    skills_html = ", ".join(html.escape(str(s)) for s in skills)
    return f"""<footer>
  <h2>Methodology &amp; coverage</h2>
  <p class="method">Static, read-only, robots-respecting analysis. Profile
    <b>{html.escape(str(report.get('profile','balanced')))}</b> ·
    {report.get('pages_crawled',0)} page(s) sampled · checks run: {skills_html or '—'}.
    The AI Visibility Score and every projection use one transparent, deterministic model
    (see <code>auditlib/scoring.py</code>); effort estimates are category-based heuristics.</p>
  <ul class="notes">{notes_html}</ul>
  <p class="fine">Generated by brand-ai-readiness-audit · recommend-only. JSON remains the
    canonical machine-readable output.</p>
</footer>"""


_CSS = """
:root {
  --bg:#eef1f5; --card:#fff; --ink:#1c2430; --muted:#7a8595; --line:#e6e8ec;
  --hero1:#1f2a44; --hero2:#2f6fb0; --accent:#2f6fb0;
}
* { box-sizing: border-box; }
body { margin:0; font:15px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
  color:var(--ink); background:var(--bg); }
h2 { font-size:18px; margin:0 0 14px; } h3 { font-size:14px; margin:0 0 10px; color:#33404f; }
.hint { font-weight:400; color:var(--muted); font-size:12px; }
.card, main, footer { background:var(--card); border:1px solid var(--line); border-radius:14px;
  margin:16px 24px; padding:20px 22px; }
/* hero */
.hero { display:flex; gap:26px; align-items:center; padding:30px 32px; margin:0;
  background:linear-gradient(120deg,var(--hero1),var(--hero2)); color:#fff; border:none; border-radius:0; }
.hero-meta h1 { margin:2px 0 12px; font-size:25px; word-break:break-all; }
.eyebrow { text-transform:uppercase; letter-spacing:.09em; font-size:12px; color:rgba(255,255,255,.7); }
.subscores { display:flex; gap:22px; flex-wrap:wrap; margin-bottom:10px; }
.subscore { display:flex; align-items:center; gap:8px; font-size:13px; color:rgba(255,255,255,.85); }
.subscore .bar { width:150px; height:8px; background:rgba(255,255,255,.2); border-radius:5px; overflow:hidden; }
.subscore .bar i { display:block; height:100%; background:#7bd88f; }
.subscore b { color:#fff; }
.meta-line { font-size:12px; color:rgba(255,255,255,.7); }
.delta { font-size:13px; font-weight:700; margin-top:6px; }
/* KPI row */
.kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:12px;
  padding:16px 24px 0; }
.kpi { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px; }
.kpi-n { font-size:26px; font-weight:700; color:var(--ink); }
.kpi.big .kpi-n { color:var(--accent); }
.kpi.good .kpi-n { color:#2e7d32; } .kpi.warn .kpi-n { color:#c0182f; }
.kpi-l { font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; margin-top:2px; }
/* exec summary */
.summary-body p { margin:0 0 8px; color:#33404f; }
.summary-body p:first-child { font-size:16px; font-weight:600; color:var(--ink); }
/* projection */
.pbars { display:flex; flex-direction:column; gap:10px; }
.pbar { display:flex; align-items:center; gap:12px; }
.pbar-l { width:130px; font-size:13px; color:#4a5563; }
.pbar-track { flex:1; height:16px; background:#eef1f5; border-radius:8px; overflow:hidden; }
.pbar-track i { display:block; height:100%; border-radius:8px; }
.pbar-v { width:78px; text-align:right; font-size:14px; } .pbar-v em { color:var(--muted); font-style:normal; font-size:12px; }
.proj-note { margin:12px 0 0; font-size:13px; color:#4a5563; }
/* pillars */
.pillars-grid { display:grid; grid-template-columns:320px 1fr; gap:20px; align-items:center; }
.radar { max-width:340px; margin:0 auto; width:100%; }
.radar svg { max-width:100%; height:auto; }
.pillar-list { list-style:none; margin:0; padding:0; }
.pillar-list li { display:flex; align-items:center; gap:10px; padding:7px 0; font-size:13px; border-bottom:1px solid #f2f4f7; }
.pillar-list .pill-l { width:130px; color:#33404f; }
.pill-track { flex:1; height:8px; background:#eef1f5; border-radius:5px; overflow:hidden; }
.pill-track i { display:block; height:100%; }
.pillar-list b { width:34px; text-align:right; }
.pill-n { width:74px; text-align:right; color:var(--muted); font-size:12px; }
.dot { width:10px; height:10px; border-radius:50%; display:inline-block; flex:none; }
/* charts */
.charts { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin:16px 24px; }
.chart-card { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:18px 20px; }
.matrix-svg { max-width:460px; display:block; margin:0 auto; height:auto; }
.donut-wrap { display:flex; gap:18px; align-items:center; flex-wrap:wrap; }
.legend { list-style:none; margin:0; padding:0; font-size:13px; }
.legend li { display:flex; align-items:center; gap:8px; padding:3px 0; }
.legend b { margin-left:auto; } .legend em { color:var(--muted); font-style:normal; width:38px; text-align:right; }
.conf { margin-top:16px; } .conf-l { font-size:12px; color:var(--muted); margin-bottom:5px; }
.conf-bar { display:flex; height:12px; border-radius:6px; overflow:hidden; background:#eef1f5; }
.conf-bar span { display:block; height:100%; }
.conf-legend { font-size:11px; color:var(--muted); margin-top:5px; }
/* roadmap */
.roadmap { display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }
.road-col h3 { display:flex; align-items:center; gap:8px; }
.road-col h3 span { background:var(--accent); color:#fff; font-size:11px; border-radius:20px; padding:1px 8px; }
.road-sub { font-size:11px; color:var(--muted); margin:0 0 8px; text-transform:uppercase; letter-spacing:.03em; }
.road-col ul { list-style:none; margin:0; padding:0; }
.road-col li { font-size:13px; padding:6px 0; border-bottom:1px solid #f2f4f7; color:#33404f; }
.road-col li em { color:var(--muted); font-style:normal; font-size:11px; }
.road-col li.none { color:var(--muted); }
/* hotspots */
.hotspots { width:100%; border-collapse:collapse; font-size:13px; }
.hotspots th, .hotspots td { text-align:left; padding:8px 10px; border-bottom:1px solid #f2f4f7; }
.hotspots th { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.04em; }
.hotspots td.url { word-break:break-all; color:#33404f; }
.hotspots th:nth-child(2), .hotspots th:nth-child(3),
.hotspots td:nth-child(2), .hotspots td:nth-child(3) { text-align:center; width:70px; }
/* findings */
.filters { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px; }
.fbtn { border:1px solid var(--line); background:#fff; color:#4a5563; border-radius:20px;
  padding:5px 14px; font-size:12px; cursor:pointer; }
.fbtn.active { background:var(--accent); color:#fff; border-color:var(--accent); }
.finding { background:#fff; border:1px solid var(--line); border-radius:10px; margin:10px 0; }
.finding summary { cursor:pointer; padding:14px 16px; display:flex; gap:10px; align-items:center; list-style:none; }
.finding summary::-webkit-details-marker { display:none; }
.chip { color:#fff; font-size:11px; font-weight:700; padding:3px 8px; border-radius:20px; }
.chip.mini { font-size:9px; padding:2px 6px; }
.dim { font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }
.ftitle { font-weight:600; flex:1; }
.impact { font-size:12px; color:var(--muted); }
.finding .body { padding:0 16px 16px; border-top:1px solid #f2f4f7; }
.finding .body p { margin:10px 0; }
.why { color:#33404f; } .evidence { color:#4a5563; }
.fix { background:#eef7f1; border-left:3px solid #3f9d63; padding:8px 12px; border-radius:4px; }
.pages span { font-size:12px; color:var(--muted); } .pages ul { margin:4px 0; padding-left:18px; font-size:13px; color:#556; }
.cat { font-size:11px; color:#aab2bd; }
.empty { color:#2e7d32; font-weight:600; }
/* footer */
footer h2 { font-size:16px; } .method { color:#4a5563; font-size:13px; }
.notes { color:var(--muted); font-size:12px; padding-left:18px; } .notes li { margin:3px 0; }
.fine { color:#aab2bd; font-size:12px; margin-top:12px; }
code { background:#f2f4f7; padding:1px 5px; border-radius:4px; font-size:12px; }
/* toolbar */
.toolbar { position:sticky; top:0; z-index:20; display:flex; gap:8px; align-items:center;
  padding:10px 24px; background:rgba(255,255,255,.92); backdrop-filter:blur(6px);
  border-bottom:1px solid var(--line); }
.tbtn { border:1px solid var(--line); background:#fff; color:#33404f; border-radius:8px;
  padding:6px 12px; font-size:13px; cursor:pointer; }
.tbtn:hover { border-color:var(--accent); color:var(--accent); }
.tbtn-note { font-size:12px; color:#2e7d32; }
@media print { .toolbar,.filters,.pe-controls { display:none !important; } .finding,.pcard,.cov-row { break-inside:avoid; } details{} details>*{display:revert;} }
/* coverage as expandable rows */
.cov-list { display:flex; flex-direction:column; }
.cov-row { border-bottom:1px solid #f2f4f7; }
.cov-row > summary { list-style:none; cursor:pointer; display:flex; align-items:center; gap:12px; padding:10px 4px; }
.cov-row > summary::-webkit-details-marker { display:none; }
.cov-area { font-weight:600; color:#33404f; min-width:150px; }
.cov-counts { font-size:13px; color:#4a5563; } .cov-meta { margin-left:auto; color:var(--muted); font-size:12px; }
.cov-body { padding:4px 4px 14px 12px; } .cov-note { color:var(--muted); font-size:12px; margin:0 0 8px; }
.clist { list-style:none; margin:0; padding:0; columns:2; }
.clist li { font-size:13px; padding:3px 0; color:#33404f; break-inside:avoid; }
.clist .cstate { font-weight:700; margin-right:6px; } .clist em { color:var(--muted); font-style:normal; font-size:11px; }
/* filters (selects) */
.filters { display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-bottom:12px; }
.fsel { font-size:12px; color:var(--muted); display:flex; flex-direction:column; gap:2px; }
.fsel select, #f-search, #pe-search, #pe-sort { border:1px solid var(--line); border-radius:8px;
  padding:5px 8px; font-size:13px; background:#fff; color:#1c2430; }
#f-search, #pe-search { min-width:180px; flex:1; max-width:280px; }
.fcount, .pe-cnt { font-size:12px; color:var(--muted); margin-left:auto; }
.finding[hidden] { display:none; }
.flash { outline:2px solid var(--accent); outline-offset:2px; border-radius:10px; }
/* page explorer */
.pe-controls { display:flex; gap:10px; align-items:center; margin-bottom:12px; flex-wrap:wrap; }
.pcard { border:1px solid var(--line); border-radius:10px; margin:8px 0; }
.pcard[hidden] { display:none; }
.pcard > summary { list-style:none; cursor:pointer; display:flex; align-items:center; gap:12px; padding:12px 14px; flex-wrap:wrap; }
.pcard > summary::-webkit-details-marker { display:none; }
.pscore { font-weight:700; font-size:18px; min-width:32px; }
.ptitle { font-weight:600; } .purl { color:var(--muted); font-size:12px; word-break:break-all; flex:1; min-width:120px; }
.pmeta { color:var(--muted); font-size:12px; } .popen { font-size:12px; color:var(--accent); text-decoration:none; }
.pbody { padding:0 14px 14px; border-top:1px solid #f2f4f7; display:grid; grid-template-columns:1fr 1fr; gap:2px 24px; }
.pf { display:flex; justify-content:space-between; gap:10px; font-size:13px; padding:5px 0; border-bottom:1px solid #f7f8fa; }
.pf span { color:var(--muted); } .pf b { color:#33404f; text-align:right; word-break:break-word; font-weight:500; }
.pf-findings { grid-column:1/-1; margin-top:8px; display:flex; gap:6px; flex-wrap:wrap; align-items:center; }
.pf-findings span { color:var(--muted); font-size:12px; }
.fjump, .fjump-pg { border:1px solid var(--line); background:#f6f8fb; color:var(--accent);
  border-radius:6px; padding:2px 8px; font-size:11px; cursor:pointer; font-family:ui-monospace,Consolas,monospace; }
.pages a { color:var(--accent); text-decoration:none; word-break:break-all; }
.pages li { margin:3px 0; }
/* section analysis */
.sec-list { display:flex; flex-direction:column; gap:4px; }
.sec-row { display:flex; align-items:center; gap:12px; padding:6px 0; border-bottom:1px solid #f2f4f7; }
.sec-l { width:150px; font-weight:600; color:#33404f; word-break:break-all; }
.sec-track { flex:1; height:10px; background:#eef1f5; border-radius:6px; overflow:hidden; }
.sec-track i { display:block; height:100%; border-radius:6px; }
.sec-score { width:34px; text-align:right; } .sec-meta { width:150px; text-align:right; color:var(--muted); font-size:12px; }
.sec-ok { color:#2e7d32; font-size:11px; font-weight:600; }
/* what-if planner */
.whatif { border:1px solid #d7cdf5; background:linear-gradient(180deg,#faf8ff,#fff); border-radius:12px;
  padding:14px 16px; margin-bottom:14px; }
.wi-head { display:flex; align-items:baseline; gap:10px; margin-bottom:10px; }
.wi-title { font-weight:700; color:#4a2fa0; } .wi-hint { color:var(--muted); font-size:12px; }
.wi-scores { display:flex; align-items:center; gap:16px; flex-wrap:wrap; margin-bottom:10px; }
.wi-box { display:flex; flex-direction:column; } .wi-box span { font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }
.wi-box b { font-size:24px; font-weight:700; color:#1c2430; }
.wi-proj b { color:#4a2fa0; } .wi-proj em { font-style:normal; color:#4a2fa0; font-size:14px; }
.wi-arrow { font-size:22px; color:var(--muted); }
.wi-actions { display:flex; gap:8px; flex-wrap:wrap; }
.wi-check { display:inline-flex; align-items:center; cursor:pointer; margin-right:2px; }
.wi-check input { width:15px; height:15px; cursor:pointer; }
/* legacy coverage table (unused, kept harmless) */
.coverage { width:100%; border-collapse:collapse; font-size:13px; }
.coverage th, .coverage td { text-align:left; padding:8px 10px; border-bottom:1px solid #f2f4f7; vertical-align:top; }
.coverage th { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.04em; }
.coverage .area { font-weight:600; color:#33404f; white-space:nowrap; }
.coverage .checks { color:var(--muted); font-size:12px; }
.coverage .num, .coverage .conf { text-align:center; }
.coverage td.num { width:64px; } .coverage .conf { color:var(--muted); }
/* score explanation */
.pe-list { list-style:none; margin:8px 0 0; padding:0; }
.pe-list li { display:flex; align-items:center; gap:10px; font-size:13px; padding:5px 0; border-bottom:1px solid #f2f4f7; }
.pe-id { font-family:ui-monospace,Consolas,monospace; font-size:11px; color:var(--muted); width:52px; }
.pe-t { flex:1; color:#33404f; } .pe-p { color:#c0182f; width:44px; text-align:right; }
/* opportunities */
.opp { border:1px solid var(--line); border-left:3px solid #7a4fd0; border-radius:8px; padding:12px 14px; margin:10px 0; background:#faf8fe; }
.opp-head { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.opp-title { font-weight:600; } .opp-meta { color:var(--muted); font-size:11px; margin-left:auto; }
.opp p { margin:8px 0 0; font-size:13px; color:#44506a; }
.opp-do { background:#fff; border-radius:4px; padding:6px 10px; }
/* limitations + evidence extras */
.limits { color:#4a5563; font-size:13px; padding-left:18px; } .limits li { margin:6px 0; }
.scope { color:#556; font-size:13px; } .xi { color:#2e7d32; font-size:13px; }
.measures { display:flex; gap:6px; flex-wrap:wrap; margin:8px 0; }
.mchip { background:#f2f4f7; color:#4a5563; font-size:11px; border-radius:5px; padding:2px 8px; font-family:ui-monospace,Consolas,monospace; }
@media (max-width:760px) {
  .charts, .pillars-grid, .roadmap { grid-template-columns:1fr; }
  .card, main, footer, .kpis, .charts { margin-left:12px; margin-right:12px; }
  .coverage .checks { display:none; }
}
"""

_JS = r"""
(function(){
  'use strict';
  function $(s,r){return (r||document).querySelector(s);}
  function $all(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s));}
  function val(id){var e=$('#'+id);return e?e.value:'all';}

  // --- canonical data + exports (single source of truth) --------------------------
  function data(){try{return JSON.parse($('#audit-data').textContent);}catch(e){return {};}}
  var tb=$('.toolbar'); if(tb) tb.hidden=false;
  function download(){
    var blob=new Blob([JSON.stringify(data(),null,2)],{type:'application/json'});
    var d=data(), name=((d.site||'audit')+'-audit.json').replace(/[^a-z0-9.-]/gi,'_');
    var a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=name;
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(function(){URL.revokeObjectURL(a.href);},1000);
  }
  function copy(){
    var text=JSON.stringify(data(),null,2);
    var done=function(){var n=$('#copy-note'); if(n){n.hidden=false; setTimeout(function(){n.hidden=true;},1500);}};
    if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(text).then(done,fallback);}
    else fallback();
    function fallback(){var t=document.createElement('textarea'); t.value=text; document.body.appendChild(t);
      t.select(); try{document.execCommand('copy');done();}catch(e){} t.remove();}
  }
  if($('#dl-json')) $('#dl-json').addEventListener('click',download);
  if($('#copy-json')) $('#copy-json').addEventListener('click',copy);
  if($('#print')) $('#print').addEventListener('click',function(){window.print();});

  // --- findings: combined filter + search + sort ----------------------------------
  var list=$('#findings');
  function applyFindings(){
    if(!list) return;
    var dim=val('f-dimension'), sev=val('f-severity'), conf=val('f-confidence');
    var q=(($('#f-search')||{}).value||'').trim().toLowerCase();
    var shown=0;
    $all('.finding',list).forEach(function(el){
      var ok=(dim==='all'||el.getAttribute('data-dimension')===dim)
        &&(sev==='all'||el.getAttribute('data-severity')===sev)
        &&(conf==='all'||el.getAttribute('data-confidence')===conf)
        &&(!q||(el.getAttribute('data-text')||'').indexOf(q)>=0);
      el.hidden=!ok; if(ok) shown++;
    });
    var sort=val('f-sort'); if(sort==='all') sort='priority';
    var nodes=$all('.finding',list).filter(function(e){return !e.hidden;});
    nodes.sort(function(a,b){
      if(sort==='severity') return num(a,'data-sev-order')-num(b,'data-sev-order');
      if(sort==='impact') return num(b,'data-impact')-num(a,'data-impact');
      if(sort==='page') return num(b,'data-pages')-num(a,'data-pages');
      return num(a,'data-priority')-num(b,'data-priority');
    });
    nodes.forEach(function(n){list.appendChild(n);});
    var c=$('#f-count'); if(c) c.textContent=shown+' of '+$all('.finding',list).length+' findings';
  }
  function num(el,a){return parseFloat(el.getAttribute(a))||0;}
  ['f-dimension','f-severity','f-confidence','f-sort'].forEach(function(id){
    var e=$('#'+id); if(e) e.addEventListener('change',applyFindings);});
  if($('#f-search')) $('#f-search').addEventListener('input',applyFindings);
  if($('#f-reset')) $('#f-reset').addEventListener('click',function(){
    ['f-dimension','f-severity','f-confidence','f-sort'].forEach(function(id){var e=$('#'+id); if(e) e.selectedIndex=0;});
    if($('#f-search')) $('#f-search').value=''; applyFindings();});
  applyFindings();

  // --- page explorer: search + sort -----------------------------------------------
  var plist=$('#page-list');
  function applyPages(){
    if(!plist) return;
    var q=(($('#pe-search')||{}).value||'').trim().toLowerCase(), shown=0;
    $all('.pcard',plist).forEach(function(el){
      var ok=!q||(el.getAttribute('data-url')||'').toLowerCase().indexOf(q)>=0
        ||(el.getAttribute('data-title')||'').indexOf(q)>=0;
      el.hidden=!ok; if(ok) shown++;
    });
    var sort=val('pe-sort'); var nodes=$all('.pcard',plist).filter(function(e){return !e.hidden;});
    nodes.sort(function(a,b){
      if(sort==='findings') return num(b,'data-findings')-num(a,'data-findings');
      if(sort==='url') return (a.getAttribute('data-url')||'').localeCompare(b.getAttribute('data-url')||'');
      return num(a,'data-score')-num(b,'data-score');
    });
    nodes.forEach(function(n){plist.appendChild(n);});
    var c=$('#pe-count'); if(c) c.textContent=shown+' of '+$all('.pcard',plist).length+' pages';
  }
  if($('#pe-search')) $('#pe-search').addEventListener('input',applyPages);
  if($('#pe-sort')) $('#pe-sort').addEventListener('change',applyPages);
  applyPages();

  // --- what-if planner: recompute the score as findings are ticked "fixed" --------
  var D=data(), model=D.scoring_model, wi=$('.whatif');
  if(wi && model && list){
    wi.hidden=false;
    var sp=model.severity_penalty||{}, cf=model.confidence_factor||{}, w=model.weights||{};
    var bands=model.grade_bands||[[90,'A'],[80,'B'],[70,'C'],[60,'D'],[0,'F']];
    var qw=(((D.analytics||{}).quick_wins)||[]).map(function(q){return q.id;});
    function pen(el){return (sp[el.getAttribute('data-severity')]||8)*(cf[el.getAttribute('data-confidence')]||1);}
    function grade(v){for(var i=0;i<bands.length;i++){if(v>=bands[i][0])return bands[i][1];}return 'F';}
    function dimScore(sum){return Math.max(0,Math.round((100-sum)*10)/10);}
    function recompute(){
      var sums={discoverability:0,engagement:0}, fixed=0;
      $all('.finding',list).forEach(function(el){
        var cb=$('.wi-cb',el); if(cb&&cb.checked){fixed++;return;}
        var d=el.getAttribute('data-dimension'); if(sums[d]!==undefined) sums[d]+=pen(el);
      });
      var disc=dimScore(sums.discoverability), eng=dimScore(sums.engagement);
      var wd=w.discoverability||0, we=w.engagement||0, tot=(wd+we)||1;
      var overall=Math.round((disc*wd+eng*we)/tot);
      var cur=(D.score||{}).value; if(cur===undefined) cur=overall;
      $('#wi-current').textContent=cur;
      $('#wi-proj').textContent=overall;
      $('#wi-grade').textContent='('+grade(overall)+')';
      var dl=overall-cur; var de=$('#wi-delta'); de.textContent=(dl>=0?'+':'')+dl;
      de.style.color=dl>0?'#2e7d32':(dl<0?'#c0182f':'#666');
      $('#wi-count').textContent=fixed;
    }
    // Toggle the checkbox without expanding/collapsing the finding.
    $all('.finding > summary',list).forEach(function(sm){
      sm.addEventListener('click',function(e){
        if(e.target.closest('.wi-check')){e.preventDefault();
          var box=sm.querySelector('.wi-cb'); box.checked=!box.checked; recompute();}
      });
    });
    if($('#wi-quick')) $('#wi-quick').addEventListener('click',function(){
      $all('.finding',list).forEach(function(el){var cb=$('.wi-cb',el); if(cb) cb.checked=qw.indexOf(el.id)>=0;}); recompute();});
    if($('#wi-all')) $('#wi-all').addEventListener('click',function(){
      $all('.wi-cb',list).forEach(function(cb){cb.checked=true;}); recompute();});
    if($('#wi-reset')) $('#wi-reset').addEventListener('click',function(){
      $all('.wi-cb',list).forEach(function(cb){cb.checked=false;}); recompute();});
    recompute();
  }

  // --- cross-navigation: finding <-> page -----------------------------------------
  function reveal(el){ if(!el) return; if(el.tagName==='DETAILS') el.open=true;
    el.scrollIntoView({behavior:'smooth',block:'center'}); el.classList.add('flash');
    setTimeout(function(){el.classList.remove('flash');},1200);}
  document.addEventListener('click',function(e){
    var pg=e.target.closest('.fjump-pg');
    if(pg){var u=pg.getAttribute('data-url');
      var card=$all('.pcard').filter(function(c){return c.getAttribute('data-url')===u;})[0];
      reveal(card); return;}
    var fj=e.target.closest('.fjump');
    if(fj){reveal(document.getElementById(fj.getAttribute('data-fid'))); return;}
  });
})();
"""
