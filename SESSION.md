# SESSION.md — handoff notes

A continuity doc for the next working session on **brand-ai-readiness-audit**. Read this
first; it captures state, decisions, and where to look — so you don't re-derive context.

_Last updated: 2026-09-23 · released tag v2.7.0 · regional-variants work committed on top (unreleased)_

---

## 1. What this project is
An **Agent Skill Marketplace** for **Adobe University Hackathon 2026 — Round 3**
("Build the Agent Skill Marketplace"). Point it at any website; it audits for problems hurting
its **AI discoverability** (found/cited by AI assistants) and **on-site engagement** (keeping
visitors), and emits **one prioritized audit report** — canonical JSON, plus HTML dashboard /
Markdown / CSV. Read-only, recommend-only, robots-respecting, SSRF-safe, stdlib-only.

Brief PDF: `C:\Users\Asus\.claude\uploads\9204bbf0-dc90-418e-a84b-aa47693a138b\30a083c2-6a8ffdf33590a_round3handoutupdated_2.pdf`
(extracted text in scratchpad `round3_text.txt`).

## 2. Hard constraints (never violate)
stdlib-only Python (no pip deps, no model weights) · read-only · recommend-only · robots-
respecting · SSRF-safe · deterministic by default · self-contained manifest · exactly ONE
entrypoint skill (`audit-orchestrator`) · zip ≤ 50 MB · runtime < 5 min. External corroboration
stays an **opt-in, provider-neutral** abstraction (`--verify-external`) that degrades to
"unavailable/limited" — never fabricate corroboration.

## 3. Current status
- **Tests: 191 passing**, fully offline, ~5.6s (`python -m unittest discover -t . -s tests`).
- Released **v2.7.0** (tag pushed). On top of it, a new **Regional-variant + reliability**
  increment is now committed locally (see §5) — marketplace.json still reads 2.7.0; not tagged.
- The feature set spans v1.1 → v2.7: analyst layer (analytics/pillars/impact×effort/projection/
  roadmap), coverage matrix + check registry (PASS/FAIL/NOT_VERIFIED/PARTIAL), page explorer,
  what-if planner, section analysis, opt-in external corroboration, answer-readiness, llms.txt,
  hallucination-risk scan, knowledge-graph preview, prompt-pack readiness, eval harness,
  competitor benchmarking, visibility funnel, agent-native fix snippets, AI-readiness fact layer
  (claims/citation/answer-simulation), smart sampling, provider-neutral search abstraction.

## 4. Git / GitHub state — READ THIS
- Repo: **https://github.com/rish240103034-commits/brand-ai-readiness-audit** (PUBLIC).
- **Two admins**: `rish240103034-commits` (owner, the `gh`-authed account) AND
  **`louvkrishnaupadhyay <louv2k@gmail.com>`** — an SIH teammate who also pushes. Expect commits
  from both. On 2026-09-07 they pushed `eefd964` (a whitespace no-op in `tests/__init__.py`, under
  a mislabeled "Initial commit v1.1.0" message) on top of v2.7.0.
- **Credential gotcha:** the Windows credential manager may cache a *different* GitHub account
  (`pandeyrishabh027`) and cause a 403 on `git push`. Push via gh's creds:
  `git -c credential.helper= -c credential.helper='!gh auth git-credential' push origin main`.
  `gh auth setup-git` has been run, so a fresh shell usually works.
- Tags v1.1.0 … v2.7.0 exist on both local and remote.

## 5. This session's committed work (regional variants + reliability)
New/changed toward the CHANGELOG `[Unreleased]` "Regional 'branch' analysis":
- `auditlib/regions.py` — detects declared locale branches (India/Global/UK/US…). **hreflang
  alternates are authoritative**; URL/selector fallback only when no hreflang. Concurrent,
  no-retry, robots-respecting HEAD reachability probe (wall-clock bounded); a declared-but-dead
  branch → high `i18n` finding (401/403/405 count as reachable, not dead). Surfaced as
  `report.regions` + a "Regional variants" report section.
- `auditlib/reliability.py` — confidence guard: if the crawl was too thin (site blocked/timed
  out), mark the score **provisional** so a 1-page result isn't read as a full assessment
  (`report.reliability`).
- Touch-ups across `http.py`, `crawl_render.py`, `config.py`, `render.py`, `report.py`,
  `exports.py`, `run_audit.py`, `report-schema.md`, `SKILL.md`, `CHANGELOG.md`, + tests
  (`test_regions.py`, `test_reliability.py`, `test_hardening_ssrf_dedup.py`).
- Was rebased onto the teammate's `eefd964` so history stays linear.
- **Not pushed** (user drives releases — see §8). Not tagged.

## 6. Layout / where things live
```
marketplace.json          manifest: 6 skills, one entrypoint (version 2.7.0)
README.md  CHANGELOG.md  SESSION.md
examples/                 canonical sample-report.{json,html,md,csv} (real smashingmagazine.com audit)
tests/                    18 offline test files (unit + mock-server integration + eval)
skills/
  audit-orchestrator/     ENTRYPOINT (composes others; no detection logic of its own)
    SKILL.md
    scripts/
      run_audit.py        entrypoint CLI (validate → discover skills → crawl once → checks
                          concurrently → score → analytics → render)
      eval.py             generalization / false-positive harness (labeled offline corpus)
      validate_report.py  schema validator
      auditlib/           SHARED ENGINE — ~34 modules. Key ones:
        config.py         ALL tunables + thresholds + profiles (nothing magic-numbered inline)
        http.py           fetch, robots, SSRF validate_target (is_global rule), smart crawl sampling
        htmlparse.py      stdlib HTML → Page model
        registry.py       skill auto-discovery + SKILL.md validation + check binding
        report.py scoring.py analytics.py coverage.py pages.py render.py exports.py
        proactive.py external.py answer_readiness.py llmstxt.py consistency.py
        knowledge_graph.py prompts.py funnel.py benchmark.py snippets.py claims.py
        citation.py answersim.py regions.py reliability.py search_provider.py history.py
        runner.py logutil.py frontmatter.py context.py
        checks/           crawl_render, structured_data, extractability, freshness,
                          corroboration, engagement  (each: pure analyze(ctx) -> [Finding])
  crawl-render-audit/ structured-data-audit/ content-extractability-audit/
  freshness-corroboration/ engagement-audit/   each: SKILL.md, scripts/run.py, references/
```

## 7. Run / test cheatsheet
```bash
python skills/audit-orchestrator/scripts/run_audit.py example.com                       # JSON
python skills/audit-orchestrator/scripts/run_audit.py example.com --format html --out report.html
python skills/audit-orchestrator/scripts/run_audit.py example.com --format md --out report.md
python skills/audit-orchestrator/scripts/run_audit.py example.com --csv findings.csv
python skills/audit-orchestrator/scripts/run_audit.py example.com --skills crawl-render,structured-data
python skills/audit-orchestrator/scripts/run_audit.py example.com --profile strict --verify-external
python skills/audit-orchestrator/scripts/eval.py                                         # eval harness
python -m unittest discover -t . -s tests                                               # 191 tests, offline
```
Exit codes: 0 ok · 1 partial (a check errored/timed out) · 2 bad input/unauditable.

## 8. Release discipline (IMPORTANT)
The user drives releases. Do **NOT** `git commit`, `git push`, or tag unless they explicitly
say so *in that turn* ("commit and push", "tag it"). After an increment: run tests, report what
changed, **offer**, then wait. Commit trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`;
PR trailer `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

## 9. Key decisions & gotchas (don't re-litigate)
- **stdlib only.** Keep it. No pip deps.
- **False-positive discipline** drives the rubric. Guards exist (stale-copyright needs no other
  recent-date signal; brand-name check ignores localized `og:site_name`; product detection needs
  real commerce cues; regional count driven by authoritative hreflang, not deep links).
- **SSRF uses `is_global`** as the deciding signal — NAT64 IPv6 (`64:ff9b::/96`) is `is_reserved`
  yet globally routable, so a reserved-first check wrongly blocked real sites. Don't revert.
- Input is tolerant: bare domains, Markdown links `[t](url)`, `< >`/quote/backtick wrappers.
- Thresholds live ONLY in `config.py`; checks read `ctx.cfg.t("name")`.
- Tests must stay **offline** (FakeFetcher in `tests/helpers.py`; mock server in
  `test_integration.py`). Run with `-t .` so the `tests` package `__init__` sets sys.path.
- Never delete the user's stray `*.pdf` from the repo root — it's `.gitignore`d and zip-excluded,
  not removed.
- Windows/Git-Bash: `--out /tmp/x` path-translates oddly; use a real path.

## 10. Rebuild the submission zip (after any change)
```bash
cd D:/SIH && python - <<'PY'
import os, zipfile
root="brand-ai-readiness-audit"; z=zipfile.ZipFile("brand-ai-readiness-audit.zip","w",zipfile.ZIP_DEFLATED)
for dp,dn,fn in os.walk(root):
    dn[:]=[d for d in dn if d not in ("__pycache__",".git")]
    for f in fn:
        if f.endswith((".pyc",".pdf")): continue
        z.write(os.path.join(dp,f))
z.close(); print("zip rebuilt")
PY
```

## 11. Possible next steps
- [ ] Push the regional-variants commit when the user approves (remember §4 credential gotcha).
- [ ] Finalize the CHANGELOG `[Unreleased]` → a version + bump `marketplace.json` + tag (on request).
- [ ] Optional: true JS-render confirmation via an *optional* headless renderer that degrades
      gracefully (render gaps are heuristic / medium-confidence by design).
- [ ] Coordinate with teammate `louvkrishnaupadhyay` to avoid diverging histories.

## 12. Environment
Python 3.13 (`python`, Windows Store build); pip works. gh CLI authenticated as
`rish240103034-commits`. No secrets used by the tool; nothing is uploaded anywhere.
