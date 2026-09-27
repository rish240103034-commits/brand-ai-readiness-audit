# PART 1 — METHODOLOGY (camera-ready, filled)

**Target time: 2:30–2:50.** Engine = frozen Round 3 submission, tag `v2.7.0`. Every claim
points at real code. `[SCREEN]` = what to show; **Say:** = read aloud.

---

## 0:00–0:20 — What our marketplace does
**[SCREEN]** `marketplace.json` (one `entrypoint`) → the six `SKILL.md` files under `skills/`.

**Say:**
> "Our Round 3 marketplace audits any website for **AI discoverability** — can an AI assistant
> find, read, and cite this brand — and **on-site engagement**. One entrypoint, `audit-orchestrator`,
> composes six focused skills into a single scored report.
> The important part: **every finding is produced by an implemented check, not by the model.**
> So I'll show exactly how a signal becomes a finding."

---

# A. HOW WE DISCOVER SIGNALS

## 0:20–1:20 — Signal → Code → Logic → Finding

### Signal 1: Structured data
**[SCREEN]** `skills/audit-orchestrator/scripts/auditlib/checks/structured_data.py` → function `_absence` (line 57).

**Say:**
> "Take structured data. Assistants quote a fact reliably only when it's restated in
> machine-readable JSON-LD. So the **signal** is: does the page carry any JSON-LD, microdata, or
> RDFa? The **code** is `structured_data.py`. The **logic** — `_absence` — scans every crawled
> page for those markup blocks. If none exist, it emits the **finding** *'No structured data
> anywhere in the sampled pages'* with the page count as evidence.
>
> So the chain is: **Signal: missing JSON-LD → Code: structured_data.py → Logic: `_absence` →
> Finding: structured data is absent**, with evidence like *'0 of 8 pages contain JSON-LD'*."

**[Important visual moment — point at the code]**
> "Notice: we're **not asking the model** whether structured data is missing. The code parses the
> HTML and counts. The number `0 of 8` is measured, not judged."

### Signal 2: Crawlability — AI answer-engine access
**[SCREEN]** `auditlib/checks/crawl_render.py` → `_robots_findings` (line 57) and the `AI_BOTS` list (line 24).

**Say:**
> "Same approach for every signal. This one checks **crawlability** — but specifically for the
> crawlers AI assistants use: GPTBot, ClaudeBot, PerplexityBot, Google-Extended. The
> implementation parses `robots.txt` into user-agent groups; if a group blocks one of those AI
> bots at the site root, the check produces a crawlability finding with the exact rule as evidence.
> Before a machine can read a page, it has to be let in — so we detect that explicitly."

---

# B. HOW WE DETERMINE SEVERITY

## 1:20–2:00 — Evidence → Severity → Priority
**[SCREEN]** `auditlib/scoring.py` — the constants at the top (lines 15–21) and `score_report` (line 108).

**Say:**
> "Once a finding exists, we don't treat every issue equally. Severity is assigned **in the check
> itself**, on a fixed four-level ladder — **Critical, High, Medium, Low**.
>
> The clearest proof it's principled is the crawlability check I just showed: blocking AI
> **retrieval** crawlers is **Critical** — the brand disappears from answers — but blocking AI
> **training** crawlers is only **Low**, because that's a legitimate publisher choice, not an
> invisibility bug. Missing structured data is **High**; a missing meta description is **Medium**.
>
> Then scoring is **deterministic**. Each dimension starts at 100 and subtracts
> `SEVERITY_PENALTY` — Critical 35, High 18, Medium 8, Low 3 — multiplied by a
> `CONFIDENCE_FACTOR`, so a heuristic check at 0.75 or 0.5 never gets punished like a directly
> observed one. The overall score is discoverability × 0.6 plus engagement × 0.4, mapped to an
> A–F grade."

**[Point at the constants]**
> "These penalties and confidence factors are applied consistently by `score_report` — **severity
> isn't chosen during the demo; it's computed by this code.**"

---

# C. HOW WE GENERATE SUGGESTED FIXES

## 2:00–2:35 — Problem → Evidence → Severity → Recommended action
**[SCREEN]** run `python round4/view_report.py report.json --finding F-001` (or the `how_to_fix` field in `structured_data.py`, line ~66).

**Say:**
> "Finally, we don't stop at the problem. Every finding carries a fix matched to the **exact
> mechanism** it detected. For 'no structured data', the `how_to_fix` is *add schema.org JSON-LD —
> Organization plus WebSite on the homepage, and page-appropriate types elsewhere* — because that
> is precisely the missing machine-readable restatement that made the fact unquotable. Problem →
> evidence → severity → **a fix that closes that specific gap**, not a generic tip.
>
> And prioritization falls straight out of the scoring model: findings are ordered by severity ×
> confidence, so the highest-leverage problem is always **F-001**. Our analyst layer then crosses
> **impact against effort** to flag *quick wins*, and computes `points_at_stake` — the actual
> score points you'd recover — so a projection like *'fix these two → +9 → a C'* is a real
> recomputation with the same model."

**[Point at the `how_to_fix` / `suggested_action` field]**
> "The recommendation is stored **with** the finding, so the report explains not just what's wrong,
> but what to change — and in what order."

---

## 2:35–2:50 — Methodology summary → transition
**[SCREEN]** `round4/ROUND4_METHODOLOGY.md` (or keep `scoring.py` up).

**Say:**
> "So every finding follows one traceable pipeline: **Signal → detection code → evidence →
> severity → recommended fix → priority.** Because all of it is implemented in our Round 3 engine —
> tag `v2.7.0` — the methodology I just showed is the exact methodology the live run uses.
> Our offline eval harness backs this up: **recall 1.00** on failure-mode fixtures and **zero false
> positives** on a clean site.
>
> Now let's prove it on a real website."

**→ Switch to Part 2 (live run).**

---

### Cheat-sheet (verified data to drop in on camera)
| Anchor | Value (v2.7.0) |
|---|---|
| Structured-data check | `structured_data.py::_absence` (line 57); finding severity **high** (line 62) |
| Live F-001 (samsung.com, in video) | *"Product-like pages missing Product/Offer schema"* (structured-data, **high**) — product pages carry cart/price cues but no Product JSON-LD |
| AI-bot crawlability | `crawl_render.py::_robots_findings` (57); `AI_BOTS` (24); retrieval-block **critical** (74–75), training-block **low** (90–91) |
| Severity → score | `scoring.py`: `SEVERITY_PENALTY` {crit 35, high 18, med 8, low 3} (15); `CONFIDENCE_FACTOR` {1.0/0.75/0.5} (17); `score_report` (108) |
| Overall | discoverability×0.6 + engagement×0.4 → A/B/C/D/F |
| Demo headline (video) | samsung.com → **77/100 (C)**, 9 findings, ~20 s |
| Generalization | `eval.py`: recall 1.00, 0 false positives |
