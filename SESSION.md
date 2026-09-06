# SESSION.md — handoff notes

A continuity doc for the next working session on **brand-ai-readiness-audit**. Read this
first; it captures state, decisions, and where to look — so you don't re-derive context.

_Last updated: 2026-09-05 · version 2.5.0_

---

## 1. What this project is
An **Agent Skill Marketplace** for **Adobe University Hackathon 2026 — Round 3**
("Build the Agent Skill Marketplace"). Point it at any website; it audits the site for
problems hurting its **AI discoverability** (getting found/cited by AI assistants) and
**on-site engagement** (keeping visitors), and emits **one prioritized audit report**
(JSON canonical; optional HTML). Read-only, recommend-only, robots-respecting, stdlib-only.

The brief PDF is at:
`C:\Users\Asus\.claude\uploads\9204bbf0-dc90-418e-a84b-aa47693a138b\30a083c2-6a8ffdf33590a_round3handoutupdated_2.pdf`
(extracted text: scratchpad `round3_text.txt`).

## 2. Current status — DONE and working
- Full marketplace built: entrypoint `audit-orchestrator` + 5 focused skills.
- **v1.2 adds an analyst layer**: every report now carries an `analytics` block (pillars,
  impact×effort matrix, score projection, hotspots, roadmap, KPIs, auto-written summary),
  a rewritten **HTML dashboard**, and two new outputs: `--format md` and `--csv`.
- **v1.3 is a fairness pass**: removed site-type bias — language-neutral CTA + CJK-aware word
  counts, host-scoped crawl by default (`--crawl-scope host|domain`), dropped brand-name-length penalty.
- **v2.0 is a Round-3 depth pass** (in-place, same architecture): a **coverage matrix**
  (`coverage.py`; 0 findings ≠ healthy — not_assessed/partial statuses), a **richer evidence model**
  (per-finding specific why/how_to_fix/scope/measurements/expected_impact), **proactive
  opportunities** (`proactive.py`; never affect score), a **traceable score explanation**, many new
  detections (canonical, broken links, nofollow, render-blocking, login walls, link-text, empty/
  conflicting schema, heading hierarchy, title/meta quality, retrieval-vs-training robots), and a
  report UI with coverage/opportunities/limitations + **dynamic filters**.
- **v2.1 is an interactive-report + engine-depth pass**: `pages.py` (per-URL detail → **page
  explorer**), coverage rewritten as a **check registry** (named PASS/FAIL/NOT_VERIFIED/PARTIAL;
  Rendering honestly *partial*, never fake-healthy), report now renders from the **embedded
  canonical JSON** (report/export can't disagree) with combined filters + search + sort, two-way
  finding↔page nav, and Download/Copy/Print. Added accessibility checks (form labels, iframe titles).
- **v2.2 adds analysis tools**: an in-report **what-if planner** (tick findings → score recomputes
  live from the embedded `scoring_model`; planner's Current == engine score) and **site-section
  analysis** (`sections`, pages grouped by URL path, scored weakest-first).
- **v2.3 adds opt-in off-site corroboration** (`external.py`, `--verify-external`,
  `report.external_verification`): Wikidata entity + P856 link-back + Wikipedia, and resolving the
  brand's declared sameAs/social links; upgrades Corroboration from *partial* to verified/not-found.
  Default runs still touch no third-party sites. Keyless, bounded, SSRF-guarded, never fabricated.
- **v2.4 adds three analysis features**: AI **answer-readiness** scorecard (`answer_readiness.py`;
  who/what/where/contact/pricing/hours graded machine-readable/text-only/missing/n-a), **llms.txt**
  detect+generate (`llmstxt.py`), and **hreflang/i18n** checks (in `crawl_render.py`; x-default,
  invalid codes, non-reciprocal — only fire on international sites).
- **v2.5 adds four AI-era differentiators**: **hallucination-risk scan** (`consistency.py`; site
  audited against itself for contradictory founding year/phone/social), **"what a fetch-only AI
  sees"** (per-page extractable text + density risk in the explorer), **knowledge-graph preview**
  (`knowledge_graph.py`; entity graph from JSON-LD with missing edges), and **prompt-pack readiness**
  (`prompts.py`; real AI queries graded ready/partial/weak).
- **130 unit/integration tests pass**, fully offline (`python -m unittest discover -t . -s tests`).
  All UI verified in-browser (hallucination cards, KG SVG, prompt-pack, machine view, what-if,
  0 console errors). `--verify-external` verified live on python.org (Wikidata Q28865, links_back).
  Generalization spot-checked on example.com (1 page → Freshness not_assessed), python.org, cloudflare.
- Runs in ~8 s for 8 pages (budget is < 5 min). Verified on example.com, python.org,
  blog.cloudflare.com, smashingmagazine.com, www.iiitmanipur.ac.in.
- Canonical sample regenerated in all 4 formats from ONE real audit of smashingmagazine.com
  (63/D) → `examples/sample-report.{json,html,md,csv}` + root `report.html`.
- Submission zip produced (~141 KB) — **regenerate it after any change** (see §7).

## 3. Layout / where things live
```
marketplace.json          manifest: 6 skills, one entrypoint, semver 1.1.0
README.md  CHANGELOG.md    docs
examples/                  sample-report.json + sample-report.html (canonical samples)
tests/                     offline unittest suite (unit + mock-server integration)
skills/
  audit-orchestrator/      ENTRYPOINT
    SKILL.md
    scripts/
      run_audit.py         the entrypoint CLI (crawl→checks→score→report)
      validate_report.py   schema validator
      auditlib/            SHARED ENGINE (all real logic lives here)
        config.py          ALL tunables + thresholds + profiles (no inline magic numbers)
        http.py            fetch, robots, SSRF validate_target, crawl sampling
        htmlparse.py       stdlib HTML → Page model
        frontmatter.py     minimal SKILL.md YAML parser
        registry.py        skill auto-discovery + validation + check binding
        context.py         AuditContext (shared crawl passed to checks)
        report.py          Finding model, build_report, validate
        scoring.py         AI Visibility Score, grade, why(fallback)/impact/priority (+ reusable compute_scores)
        coverage.py        COVERAGE MATRIX + CHECK REGISTRY: per-area PASS/FAIL/NOT_VERIFIED/PARTIAL
        pages.py           PAGE EXPLORER data: per-URL facts, signals, findings, per-page score
        proactive.py       PROACTIVE OPPORTUNITIES: context-justified, non-defect recommendations
        external.py        OPT-IN off-site corroboration (--verify-external): Wikidata + declared profiles
        answer_readiness.py  AI ANSWER-READINESS scorecard (who/what/where machine-readability)
        llmstxt.py         llms.txt detect + generate a suggested one
        consistency.py     HALLUCINATION-RISK scan: site audited against itself for contradictory facts
        knowledge_graph.py KNOWLEDGE-GRAPH preview: entity graph from JSON-LD + missing edges
        prompts.py         PROMPT-PACK readiness: real AI queries graded ready/partial/weak
        analytics.py       ANALYST LAYER: pillars (coverage-aware status), matrix, projection, hotspots, roadmap, KPIs, narrative
        render.py          self-contained HTML DASHBOARD (coverage, opportunities, limitations, score explanation, dynamic filters)
        exports.py         Markdown brief + findings CSV
        history.py         SQLite score history (--compare-previous)
        runner.py          shared hardened CLI for standalone skills
        logutil.py         logging setup
        checks/            crawl_render, structured_data, extractability,
                           freshness, corroboration, engagement
  crawl-render-audit/ structured-data-audit/ content-extractability-audit/
  freshness-corroboration/ engagement-audit/   each: SKILL.md, scripts/run.py, references/
```

## 4. How it works (one paragraph)
`run_audit.py` validates the target (SSRF-safe), `registry.discover_skills()` scans `skills/`
and binds each skill's checks from its `SKILL.md` `metadata.checks`, `AuditContext.build()`
does ONE polite crawl, checks run **concurrently** under a global timeout, `report.build_report`
+ `scoring.score_report` produce the scored/prioritized report, output as JSON or HTML.
Each check is a pure `analyze(ctx) -> [Finding]`; the orchestrator owns only crawl+merge+score.

## 5. Run / test cheatsheet
```bash
# full audit (JSON)
python skills/audit-orchestrator/scripts/run_audit.py example.com
# analytics dashboard (HTML) · Markdown brief · CSV sidecar
python skills/audit-orchestrator/scripts/run_audit.py example.com --format html --out report.html
python skills/audit-orchestrator/scripts/run_audit.py example.com --format md --out report.md
python skills/audit-orchestrator/scripts/run_audit.py example.com --csv findings.csv
# subset / profile / history
python skills/audit-orchestrator/scripts/run_audit.py example.com --skills crawl-render,structured-data
python skills/audit-orchestrator/scripts/run_audit.py example.com --profile strict --compare-previous
# tests
python -m unittest discover -t . -s tests
```
Exit codes: 0 ok · 1 partial (a check errored/timed out) · 2 bad input/unauditable.

## 6. Key decisions & gotchas (don't re-litigate)
- **stdlib only** — no pip deps, by design (portable, self-contained per the brief). Keep it.
- **False-positive discipline** matters for the rubric. Guards already added:
  stale-copyright needs no other recent-date signal; brand-name check ignores localized
  `og:site_name`; product detection needs real commerce cues (not prose prices).
- **SSRF classifier uses `is_global`** as the deciding signal — a NAT64 IPv6 (`64:ff9b::/96`)
  is `is_reserved` yet globally routable, so checking reserved first wrongly blocked real
  sites (fixed). Don't revert to a reserved-first check.
- Input is tolerant: bare domains, Markdown links `[t](url)`, `< >`/quote/backtick wrappers.
- Thresholds live ONLY in `config.py`; checks read `ctx.cfg.t("name")`. Never hardcode.
- Tests must stay **offline** (FakeFetcher in `tests/helpers.py`; mock server in
  `test_integration.py`). Run with `-t .` so the `tests` package `__init__` sets sys.path.
- Windows/Git-Bash: `--out /tmp/x` gets path-translated oddly; use a real path.

## 7. Rebuild the submission zip (after any change)
```bash
cd D:/SIH && python - <<'PY'
import os, zipfile
root="brand-ai-readiness-audit"; z=zipfile.ZipFile("brand-ai-readiness-audit.zip","w",zipfile.ZIP_DEFLATED)
for dp,dn,fn in os.walk(root):
    dn[:]=[d for d in dn if d not in ("__pycache__",".git")]
    for f in fn:
        if f.endswith((".pyc",".pdf")): continue   # exclude stray handouts/PDFs and bytecode
        z.write(os.path.join(dp,f))
z.close(); print("zip rebuilt")
PY
```
> Note: a stray `iitm.pdf` (~1.6 MB) was found in the repo root once; it's now `.gitignore`d and
> excluded from the zip. Keep the `.pdf` exclusion so the submission stays small.

## 8. Not done / possible next steps
- [x] `git init` + first commit — done (branch `main`, commit bd8aa53).
- [x] Published to GitHub (PUBLIC): https://github.com/rish240103034-commits/brand-ai-readiness-audit
- [x] "60-second demo (for judges)" section in README — done (v1.2.0).
- [x] Analyst-grade output: analytics layer + HTML dashboard + Markdown/CSV exports — done (v1.2.0).
- [ ] NOT yet committed/pushed: the v1.2.0 changes are on disk only. `git add -A && git commit`
      then push when ready (working tree was clean before this session's edits).
- [ ] Optional new checks (drop-in, no core edits — see README "Add a new skill"):
      hreflang/i18n, canonical conflicts, FAQ/HowTo schema opportunities, sitemap freshness.
- [ ] Optional: true JS-render confirmation via an *optional* headless renderer that
      degrades gracefully (currently render gaps are heuristic, medium-confidence by design).
- [ ] Consider `--max-pages` default tuning per profile.

## 9. Environment notes
- Python 3.13 at `python` (Windows Store build); pip works. gh CLI installed + authenticated
  (account `rish240103034-commits`).
- No secrets or credentials are used by the tool. Nothing is uploaded anywhere.
