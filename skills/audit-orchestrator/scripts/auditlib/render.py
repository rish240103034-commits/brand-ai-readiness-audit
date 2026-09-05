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
import math
from typing import Any, Dict, List

_SEV_COLOR = {
    "critical": "#c0182f", "high": "#e05a1e", "medium": "#e0a500",
    "low": "#3f9d63", "info": "#6b7a8d",
}
_GRADE_COLOR = {"A": "#2e7d32", "B": "#66a838", "C": "#e0a500", "D": "#ef6c00", "F": "#c0182f"}
_STATUS_COLOR = {"healthy": "#2e7d32", "warning": "#e0a500", "critical": "#c0182f"}
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
        _kpi_row(an, summary),
        _exec_summary(an),
        _projection_section(an),
        _pillars_section(an),
        _charts_section(an),
        _roadmap_section(an),
        _hotspots_section(an),
        _findings_section(findings),
        _methodology(report),
    ]
    body = "\n".join(s for s in sections if s)

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Readiness Audit — {site}</title>
<style>{_CSS}</style></head>
<body>
{body}
<script>{_JS}</script>
</body></html>"""


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
        _kpi(f"{kpis['potential_score']}", "Full potential"),
        _kpi(str(kpis["pages_analyzed"]), "Pages analyzed"),
        _kpi(kpis["effort_band"], "Est. effort"),
    ]
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
    rows = "".join(
        f"""<li>
          <span class="dot" style="background:{_STATUS_COLOR.get(p['status'], '#889')}"></span>
          <span class="pill-l">{html.escape(p['label'])}</span>
          <span class="pill-track"><i style="width:{max(2,min(100,p['score']))}%;
            background:{_STATUS_COLOR.get(p['status'], '#889')}"></i></span>
          <b>{p['score']:.0f}</b>
          <span class="pill-n">{p['findings']} issue(s)</span>
        </li>""" for p in pillars)
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
    return f"""<svg viewBox="0 0 380 300" width="100%" height="auto" role="img" aria-label="Pillar radar chart">
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
    return f"""<svg class="matrix-svg" viewBox="0 0 {W} {H}" width="100%" height="auto" role="img" aria-label="Impact by effort matrix">
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
    for bucket, title, sub in (("now", "Now", "critical, high & quick wins"),
                               ("next", "Next", "medium-severity fixes"),
                               ("later", "Later", "low-severity refinements")):
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


# --- findings ---------------------------------------------------------------------

def _findings_section(findings: List[Dict[str, Any]]) -> str:
    inner = _findings_html(findings)
    controls = ""
    if findings:
        controls = """<div class="filters" role="group" aria-label="Filter findings">
      <button class="fbtn active" data-filter="all">All</button>
      <button class="fbtn" data-filter="discoverability">Discoverability</button>
      <button class="fbtn" data-filter="engagement">Engagement</button>
      <button class="fbtn" data-filter="critical">Critical</button>
      <button class="fbtn" data-filter="high">High</button>
    </div>"""
    return f"""<main class="card">
  <h2>Findings <span class="hint">(most actionable first)</span></h2>
  {controls}
  <div id="findings">{inner}</div>
</main>"""


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
            items = "".join(f"<li>{html.escape(str(u))}</li>" for u in pages[:10])
            pages_html = f'<div class="pages"><span>Affected pages</span><ul>{items}</ul></div>'
        out.append(f"""<details class="finding" data-severity="{html.escape(sev)}"
    data-dimension="{html.escape(str(f.get('dimension','')))}">
  <summary>
    <span class="chip" style="background:{color}">{html.escape(sev.upper())}</span>
    <span class="dim">{html.escape(str(f.get('dimension','')))}</span>
    <span class="ftitle">{html.escape(str(f.get('title','')))}</span>
    <span class="impact" title="impact 1–5">impact {f.get('impact','')}</span>
  </summary>
  <div class="body">
    <p class="why"><b>Why it hurts:</b> {html.escape(str(f.get('why','')))}</p>
    <p class="evidence"><b>Evidence:</b> {html.escape(str(f.get('evidence','')))}</p>
    <p class="fix"><b>Fix ({html.escape(str(action.get('priority','')))}):</b>
       {html.escape(str(action.get('summary','')))}</p>
    {pages_html}
    <p class="cat">category: {html.escape(str(f.get('category','')))} ·
       confidence: {html.escape(str(f.get('confidence','')))} · id: {html.escape(str(f.get('id','')))}</p>
  </div>
</details>""")
    return "\n".join(out)


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
@media (max-width:760px) {
  .charts, .pillars-grid, .roadmap { grid-template-columns:1fr; }
  .card, main, footer, .kpis, .charts { margin-left:12px; margin-right:12px; }
}
"""

_JS = """
document.addEventListener('click', function(e){
  var b = e.target.closest('.fbtn'); if(!b) return;
  document.querySelectorAll('.fbtn').forEach(function(x){x.classList.remove('active');});
  b.classList.add('active');
  var f = b.getAttribute('data-filter');
  document.querySelectorAll('#findings .finding').forEach(function(el){
    var show = f==='all'
      || el.getAttribute('data-dimension')===f
      || el.getAttribute('data-severity')===f;
    el.style.display = show ? '' : 'none';
  });
});
"""
