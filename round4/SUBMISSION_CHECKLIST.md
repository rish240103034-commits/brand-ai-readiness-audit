# Round 4 — Submission Checklist (Team Alphacoders)

**Video recorded** on **www.samsung.com** with the **v2.7.0** engine · **Claude Opus 4.8** ·
**Claude Code v2.1.281**. Submit **the video + `REPLAY_Alphacoders.txt`** (Round 3 marketplace is NOT resubmitted).

## Integrity (must all be true) — the gates
- [x] Demo engine = submitted Round 3 artifact → **tag `v2.7.0`** (commit `553f3c3`); video ran from a v2.7.0 checkout.
- [x] Post-submission work (`regions.py`, `reliability.py`, commit `047803c`) is **excluded** from the demo path.
- [x] No hardcoded/pre-generated findings; the live run crawls the site in real time.
- [x] Read-only, robots-respecting, SSRF-safe, no live-site modification.
- [x] External corroboration OFF by default; only opt-in `--verify-external`, never fabricated.
- [x] `REPLAY_Alphacoders.txt` (URL, model, harness) **matches the video**.

## Reproducibility (30 pts)
- [x] `REPLAY_Alphacoders.txt` present at repo root, pinned to `v2.7.0`, copy-paste from clean checkout.
- [x] `AGENT_HARNESS` = **Claude Code v2.1.281**; `LLM_MODEL` = **Claude Opus 4.8**.
- [x] `TEST_SITE_URLS` = **https://www.samsung.com/** (the video's URL).
- [x] `EXPECTED_OUTPUT` records the real samsung.com result (~9 findings, 77/100 C, F-001 = Product/Offer schema).
- [x] Windows UTF-8 requirement documented (`PYTHONUTF8=1`, use `--out`).
- [x] Offline tests + eval documented and passing.
- [x] `requirements.txt` present (declares zero deps — stdlib only).
- [x] Zip ≤ 50 MB (repo ≈ 0.6 MB) — n/a for submission (Round 3 package reused).

## Reasoning / methodology (35 pts)
- [x] `round4/ROUND4_METHODOLOGY.md` maps 6 signals → code → evidence → severity → fix → priority → test.
- [x] `round4/PART1_SCRIPT.md` — camera-ready A/B/C narration with `[SHOW file:line]` cues.
- [x] Severity/prioritization traceable to `auditlib/scoring.py`.
- [x] Coverage honesty (`PASS/FAIL/NOT_VERIFIED/PARTIAL`) explainable from `auditlib/coverage.py`.

## Live behaviour (35 pts)
- [x] Single real entrypoint runs live on an unseen URL — verified on **samsung.com** (v2.7.0: 20s, 9 findings, 77/C), plus sqlite.org / iiitmanipur.ac.in.
- [x] Finding drill-down: evidence → why → severity → fix → priority (`round4/view_report.py` + HTML).
- [x] Runtime well under 5 min (~20–40 s).
- [x] Model + harness disclosure lines scripted (`round4/DEMO_SCRIPT.md`, `PART1_SCRIPT.md`).

## Final submission steps (for the team)
- [ ] Upload **the recorded video** to the submission portal.
- [ ] Upload **`REPLAY_Alphacoders.txt`** alongside it (download from repo root, or the pushed GitHub copy).
- [ ] Double-check the video's spoken model/harness/URL == REPLAY (Opus 4.8 · Claude Code v2.1.281 · samsung.com).

## Verification commands (reproduce the video)
```bash
git checkout v2.7.0            # the submitted engine
set PYTHONUTF8=1               # Windows only
python -m unittest discover -t . -s tests           # 168 tests, OK
python skills/audit-orchestrator/scripts/eval.py     # 8/8, recall 1.00, 0 FP
python skills/audit-orchestrator/scripts/run_audit.py https://www.samsung.com --out report.json
python skills/audit-orchestrator/scripts/validate_report.py report.json
python round4/view_report.py report.json --finding F-001   # (viewer is on main; run from a main checkout)
```
