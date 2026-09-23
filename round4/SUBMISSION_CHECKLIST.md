# Round 4 — Submission Checklist (Team Alphacoders)

## Integrity (must all be true)
- [x] Demo engine = submitted Round 3 artifact → **tag `v2.7.0`** (commit `553f3c3`).
- [x] Post-submission work (`regions.py`, `reliability.py`, commit `047803c`) is **excluded** from the demo path (frozen tag is checked out).
- [x] No hardcoded/pre-generated findings; the live run crawls the site in real time.
- [x] Read-only, robots-respecting, SSRF-safe, no live-site modification.
- [x] External corroboration OFF by default; only opt-in `--verify-external`, never fabricated.

## Reproducibility (30 pts)
- [x] `REPLAY_Alphacoders.txt` present at repo root, pinned to `v2.7.0`, copy-paste from clean checkout.
- [ ] `AGENT_HARNESS` version filled in (`claude --version`) before recording. **← ACTION**
- [x] Windows UTF-8 requirement documented (`PYTHONUTF8=1`, use `--out`).
- [x] Offline tests + eval documented and passing.
- [x] Zip ≤ 50 MB (repo ≈ 0.6 MB).

## Reasoning / methodology (35 pts)
- [x] `round4/ROUND4_METHODOLOGY.md` maps 6 signals → code → evidence → severity → fix → priority → test.
- [x] Severity/prioritization traceable to `auditlib/scoring.py`.
- [x] Coverage honesty (`PASS/FAIL/NOT_VERIFIED/PARTIAL`) explainable from `auditlib/coverage.py`.

## Live behaviour (35 pts)
- [x] Single real entrypoint runs live on an unseen URL (verified: sqlite.org, iiitmanipur.ac.in).
- [x] Finding drill-down: evidence → why → severity → fix → priority (`round4/view_report.py` + HTML).
- [x] Runtime well under 5 min (~22–45 s on demo sites).
- [x] Model + harness disclosure lines scripted (`round4/DEMO_SCRIPT.md`).

## Pre-record actions
- [ ] `git worktree add ../bar-v270 v2.7.0` (or clean clone + `git checkout v2.7.0`).
- [ ] `set PYTHONUTF8=1` in the recording shell.
- [ ] Dry-run the exact Part-2 commands once; confirm F-001 = "No structured data anywhere".
- [ ] Fill the harness version into `REPLAY_Alphacoders.txt`.

## Verification commands
```bash
python -m unittest discover -t . -s tests          # engine tests (v2.7.0: 168 / main: 192)
python skills/audit-orchestrator/scripts/eval.py    # 8/8, recall 1.00, 0 FP
python skills/audit-orchestrator/scripts/run_audit.py https://www.sqlite.org --out report.json
python skills/audit-orchestrator/scripts/validate_report.py report.json
python round4/view_report.py report.json --finding F-001
```
