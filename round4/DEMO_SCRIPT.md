# Round 4 — 5-Minute Demo Script & Shot List (Team Alphacoders)

Two parts: **Part 1 methodology ≤ 3 min**, **Part 2 live run ≤ 2 min**. Idle waiting may be
trimmed; **findings must come from one real continuous run** — never spliced or hardcoded.

The demo runs the **submitted Round 3 engine (tag `v2.7.0`)**, driven live by the Claude Code
agent (Claude Opus 4.8). The read-only viewer only formats the engine's own JSON.

---

## Pre-flight (before recording — off camera)
```bash
# One-time staging: a clean v2.7.0 checkout for the engine, main for the round4/ tooling.
git worktree add ../bar-v270 v2.7.0        # frozen engine lives here
# (Windows) force UTF-8 in the recording shell:
set PYTHONUTF8=1
```
- Have two terminals ready: one in `../bar-v270` (engine), one in the repo root (viewer/docs).
- Confirm connectivity to the demo site. Pick a fresh URL on camera if you want to prove "unseen".
- Have `round4/ROUND4_METHODOLOGY.md` open for Part 1 pointers.

---

## PART 1 — Methodology (≤ 3:00) — screen: code + methodology map
Narrate from `round4/ROUND4_METHODOLOGY.md`; show the actual files.

1. **(0:00–0:30) What & why.** "We audit any website for why AI assistants can't find/cite it
   and why visitors bounce. One entrypoint composes six focused skills into one scored report."
   Show `marketplace.json` (one `entrypoint`) and `SKILL.md` files.
2. **(0:30–1:15) How findings are discovered.** Open `auditlib/checks/structured_data.py` →
   `_absence`. "Signal: no JSON-LD. Evidence is a counted fact — `0 of 8 pages`. No LLM guessing."
   Mention auto-discovery: `registry.py::discover_skills` binds checks from each SKILL.md.
3. **(1:15–2:00) Severity & prioritization.** Open `auditlib/scoring.py`. Point at
   `SEVERITY_PENALTY`, `CONFIDENCE_FACTOR`, `DIMENSION_WEIGHT`, `score_report`. "Deterministic:
   each dimension starts at 100, loses severity×confidence points; findings sort most-actionable
   first. The model is exported so the report's what-if planner matches exactly."
4. **(2:00–2:30) Suggested fixes & honesty.** Show a finding's `how_to_fix`; then
   `coverage.py` statuses `PASS/FAIL/NOT_VERIFIED/PARTIAL` — "0 findings ≠ healthy; rendering is
   NOT_VERIFIED because we run no browser."
5. **(2:30–3:00) Generalization.** Run the eval harness live (fast, offline):
   ```bash
   python skills/audit-orchestrator/scripts/eval.py
   ```
   "Recall 1.00 on failure-mode fixtures, 0 false positives on clean/non-English — it's built for
   unseen sites."

---

## PART 2 — Live trial run (≤ 2:00) — screen: terminal
Do this in the `../bar-v270` (v2.7.0) terminal so the engine is provably the submitted one.

1. **(0:00–0:20) Disclosure (say clearly, on camera):**
   - "Model: **Claude Opus 4.8**. Harness: **Claude Code**."
   - "The agent is invoking the **actual Round 3 marketplace entrypoint** `run_audit.py` directly —
     these findings are from this one live crawl, nothing pre-generated."
2. **(0:20–0:30) Enter a real URL on camera** and run the engine:
   ```bash
   python skills/audit-orchestrator/scripts/run_audit.py https://www.samsung.com --format html --out report.html
   python skills/audit-orchestrator/scripts/run_audit.py https://www.samsung.com --out report.json
   ```
   (Let it run continuously; trim only dead air in edit. ~20–40 s.)
3. **(0:30–1:00) Prioritized findings.** In the repo-root terminal:
   ```bash
   python round4/view_report.py report.json --top 6
   ```
   Point at the ordering: "Sorted by impact — F-001 is the highest-leverage problem."
4. **(1:00–1:40) Drill into the hero finding:**
   ```bash
   python round4/view_report.py report.json --finding F-001
   ```
   Read the chain aloud: **evidence** (samsung F-001 = *Product-like pages missing Product/Offer
   schema*) → **why** → **severity/impact** → **suggested fix** → **priority**. Optionally open
   `report.html` and show the same finding with the page explorer / filters.
5. **(1:40–2:00) Close.** "Read-only, robots-respecting, SSRF-safe, deterministic, stdlib-only —
   and fully reproducible from a clean checkout via `REPLAY_Alphacoders.txt`."

---

## The exact agent prompt (paste into Claude Code for the live run)
> Run our Round 3 marketplace audit on https://www.samsung.com using the frozen v2.7.0 engine:
> `python skills/audit-orchestrator/scripts/run_audit.py https://www.samsung.com --format html --out report.html`
> and also `--out report.json`. Then show the top 6 findings with
> `python round4/view_report.py report.json --top 6` and drill into F-001 with `--finding F-001`.
> State the model and harness, confirm this is the real Round-3 entrypoint, and read the
> evidence, severity, and suggested fix for F-001.

## Fallback sites (if the primary is slow/unreachable on the day)
- `https://www.sqlite.org` (verified: ~36 s, 12 findings, 62/D — hero finding *No structured data anywhere*)
- `https://www.iiitmanipur.ac.in` (verified: ~22 s, 12 findings, 60/D, clear structured-data story)
- Any public login-free site. The engine is not tuned to any site; pick one live to prove it.

## Guardrails during recording
- Keep the run **default/offline** — do NOT pass `--verify-external` (avoids third-party calls
  and keeps the run deterministic and clearly non-fabricated).
- Windows: `set PYTHONUTF8=1` and always use `--out` (never rely on bare-stdout JSON).
- Do not edit the engine to make a site produce findings. If a site is thin, say so — the report
  marks the score provisional and coverage as not_assessed, which is the honest behaviour.
