"""Extra analyst-friendly renderings of a scored + analyzed report.

JSON stays canonical and HTML is the visual dashboard; these two are for the places analysts
actually live:

  * ``render_markdown`` — a portable report that pastes cleanly into a README, PR, or ticket.
  * ``findings_csv``    — one row per finding for a spreadsheet / pivot table.

Both are pure string builders over the report dict and add no dependencies.
"""
from __future__ import annotations

import csv
import io
from typing import Any, Dict, List

_SEV_EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "info": "⚪"}


def render_markdown(report: Dict[str, Any]) -> str:
    """Render the report as a self-contained Markdown analytics brief."""
    site = report.get("site", "")
    score = report.get("score", {})
    an = report.get("analytics", {})
    kpis = an.get("kpis", {})
    out: List[str] = []

    out.append(f"# AI Readiness Audit — {site}")
    out.append("")
    out.append(f"**AI Visibility Score: {score.get('value', 0)}/100 "
               f"(Grade {score.get('grade', 'F')})** · "
               f"discoverability {score.get('discoverability', 0)} · "
               f"engagement {score.get('engagement', 0)}")
    out.append("")
    out.append(f"_Audited {report.get('audited_at', '')} · profile "
               f"{report.get('profile', 'balanced')} · {report.get('pages_crawled', 0)} page(s) crawled_")
    out.append("")

    # Executive summary
    for line in an.get("narrative", []):
        out.append(f"> {line}")
    out.append("")

    # KPI table
    if kpis:
        out.append("## Key metrics")
        out.append("")
        out.append("| Metric | Value |")
        out.append("|---|---|")
        rows = [
            ("AI Visibility Score", f"{kpis.get('ai_visibility_score')}/100 ({kpis.get('grade')})"),
            ("Total findings", kpis.get("total_findings")),
            ("Critical + high", kpis.get("critical_high")),
            ("Quick wins", kpis.get("quick_wins")),
            ("Projected after quick wins", f"{kpis.get('projected_score')}/100 (+{kpis.get('projected_gain')})"),
            ("Full potential", f"{kpis.get('potential_score')}/100"),
            ("Weakest pillar", f"{kpis.get('weakest_pillar')} ({kpis.get('weakest_pillar_score')}/100)"),
            ("Estimated effort", kpis.get("effort_band")),
            ("Pages analyzed", kpis.get("pages_analyzed")),
        ]
        for label, val in rows:
            out.append(f"| {label} | {val} |")
        out.append("")

    # AI-readiness headline scores (can it be found, cited, engaged with?)
    scores = report.get("scores") or {}
    if scores:
        out.append("## AI readiness at a glance")
        out.append("")
        out.append("| Dimension | Score |")
        out.append("|---|---|")
        out.append(f"| Overall AI readiness | {scores.get('overall_ai_readiness')}/100 |")
        out.append(f"| Discoverability (can an AI find it?) | {scores.get('discoverability')}/100 |")
        out.append(f"| Citation readiness (will an AI quote it?) | {scores.get('citation_readiness')}/100 |")
        out.append(f"| Engagement readiness (will visitors stay?) | {scores.get('engagement_readiness')}/100 |")
        out.append("")

    # Citation readiness breakdown
    cr = report.get("citation_readiness") or {}
    if cr.get("components"):
        out.append(f"### Citation readiness — {cr.get('score')}/100 ({cr.get('grade')})")
        out.append("")
        out.append("| Signal | Score | Detail |")
        out.append("|---|---|---|")
        for c in cr["components"]:
            out.append(f"| {c['label']} | {c['value']}/100 | {c['detail']} |")
        if cr.get("limits"):
            out.append("")
            out.append(f"> _{cr['limits']}_")
        out.append("")

    # AI answer simulation — what an answer engine would do with these facts
    sim = report.get("ai_answer_simulation") or []
    if sim:
        out.append("### What an AI would answer about this brand")
        out.append("")
        out.append("| Question | Answerable | Would cite this site? | Basis |")
        out.append("|---|---|---|---|")
        for r in sim:
            out.append(f"| {r['question']} | {r['answerable']} | "
                       f"{'yes' if r['would_cite'] else 'no'} | {r['basis']} |")
        out.append("")

    # Claim inventory summary
    csum = (report.get("claims") or {}).get("summary") or {}
    if csum.get("total"):
        out.append("### Claim inventory")
        out.append("")
        out.append(f"- {csum['total']} brand facts extracted; "
                   f"{csum.get('machine_readable_pct')}% machine-readable, "
                   f"{csum.get('quotable_pct')}% quotable verbatim, "
                   f"{csum.get('contradicted')} contradicted.")
        out.append("")

    # Pillar breakdown
    pillars = an.get("pillars", [])
    if pillars:
        out.append("## Pillar breakdown")
        out.append("")
        out.append("| Pillar | Score | Status | Findings |")
        out.append("|---|---|---|---|")
        for p in pillars:
            out.append(f"| {p['label']} | {p['score']:.0f}/100 | {p['status']} | {p['findings']} |")
        out.append("")

    # Quick wins
    quick = an.get("quick_wins", [])
    if quick:
        out.append("## Quick wins (do these first)")
        out.append("")
        for q in quick:
            out.append(f"- **{q['title']}** — impact {q['impact']}/5, "
                       f"{q['effort_label'].lower()} effort, +{q['points_at_stake']} pts "
                       f"({q['id']})")
        out.append("")

    # Roadmap
    roadmap = an.get("roadmap", {})
    if roadmap:
        out.append("## Roadmap")
        out.append("")
        for bucket, heading in (("now", "Now"), ("next", "Next"), ("later", "Later")):
            items = roadmap.get(bucket, [])
            if not items:
                continue
            out.append(f"**{heading}**")
            out.append("")
            for it in items:
                out.append(f"- {_SEV_EMOJI.get(it['severity'], '')} {it['title']} "
                           f"({it['severity']}, {it['effort_label'].lower()} effort)")
            out.append("")

    # Full findings
    findings = report.get("findings", [])
    out.append("## Findings")
    out.append("")
    if not findings:
        out.append("_No findings — the site is in good shape on the checks run._")
    for f in findings:
        act = f.get("suggested_action", {})
        out.append(f"### {_SEV_EMOJI.get(f.get('severity', ''), '')} {f.get('id')} · "
                   f"{f.get('title')}  ")
        out.append(f"`{f.get('severity')}` · {f.get('dimension')} / {f.get('category')} · "
                   f"confidence {f.get('confidence')} · impact {f.get('impact')}/5")
        out.append("")
        if f.get("why"):
            out.append(f"- **Why it hurts:** {f.get('why')}")
        out.append(f"- **Evidence:** {f.get('evidence')}")
        out.append(f"- **Fix ({act.get('priority', '')}):** {act.get('summary', '')}")
        pages = f.get("affected_pages") or []
        if pages:
            out.append(f"- **Affected pages:** {', '.join(pages[:5])}"
                       + (" …" if len(pages) > 5 else ""))
        out.append("")

    out.append("---")
    out.append(f"_Generated by brand-ai-readiness-audit · {report.get('auditor', '')} · "
               "read-only, recommend-only. JSON is the canonical output._")
    return "\n".join(out)


def findings_csv(report: Dict[str, Any]) -> str:
    """Render findings as CSV (one row per finding), enriched with analytics fields."""
    analytics_by_id = {m["id"]: m for m in report.get("analytics", {}).get("matrix", [])}
    buf = io.StringIO()
    cols = ["id", "priority", "severity", "dimension", "category", "confidence",
            "impact", "effort", "effort_label", "quadrant", "points_at_stake",
            "title", "evidence", "why", "suggested_action", "action_priority",
            "affected_pages"]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for f in report.get("findings", []):
        m = analytics_by_id.get(f.get("id"), {})
        act = f.get("suggested_action", {})
        w.writerow({
            "id": f.get("id", ""),
            "priority": f.get("priority", ""),
            "severity": f.get("severity", ""),
            "dimension": f.get("dimension", ""),
            "category": f.get("category", ""),
            "confidence": f.get("confidence", ""),
            "impact": f.get("impact", ""),
            "effort": m.get("effort", ""),
            "effort_label": m.get("effort_label", ""),
            "quadrant": m.get("quadrant", ""),
            "points_at_stake": m.get("points_at_stake", ""),
            "title": f.get("title", ""),
            "evidence": f.get("evidence", ""),
            "why": f.get("why", ""),
            "suggested_action": act.get("summary", ""),
            "action_priority": act.get("priority", ""),
            "affected_pages": " | ".join(f.get("affected_pages", []) or []),
        })
    return buf.getvalue()
