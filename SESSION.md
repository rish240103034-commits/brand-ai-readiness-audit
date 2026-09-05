# SESSION.md — handoff notes

A continuity doc for the next working session on **brand-ai-readiness-audit**. Read this
first; it captures state, decisions, and where to look — so you don't re-derive context.

_Last updated: 2026-09-05 · version 1.3.0_

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
  counts, host-scoped crawl by default (`--crawl-scope host|domain`; no longer scores a brand on
  third-party help-desk subdomains), and dropped the brand-name-length penalty. By-design biases
  (fetch-only SPA assumption, type-scaled schema demands) are kept but documented in README's
  "Fairness, bias & limitations".
- **84 unit/integration tests pass**, fully offline (`python -m unittest discover -t . -s tests`).
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
        scoring.py         AI Visibility Score, grade, why/impact/priority (+ reusable compute_scores)
        analytics.py       ANALYST LAYER: pillars, impact×effort matrix, projection, hotspots, roadmap, KPIs, narrative
        render.py          self-contained HTML analytics DASHBOARD (inline SVG charts)
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
    dn[:]=[d for d in dn if d!="__pycache__"]
    for f in fn:
        if f.endswith(".pyc"): continue
        z.write(os.path.join(dp,f))
z.close(); print("zip rebuilt")
PY
```

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
