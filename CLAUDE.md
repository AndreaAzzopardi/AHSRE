# AHSRE

## Start of every session

**Run `git pull --rebase` before reading caches or making any changes.** This
repo receives two automated pushes to `main` every day:

- **19:15 UTC** — GitHub Action "Refresh PIR cache" commits
  `cache/pir_action_cache.json` + `cache/pir_history_cache.json`
- **20:03 UTC** — the nightly weekly-report cloud routine commits
  `cache/weekly_report_cache.json` and other cache refreshes

A local clone is therefore stale by default; working without pulling means
building reports on yesterday's data and getting the push rejected later.

## Committing

- Push soon after committing — unpushed local commits conflict with the next
  automated push.
- `cache/weekly_report.html` is generated output and gitignored; regenerate it
  with `python3 agents/generate_weekly_report.py` (PDF via
  `python3 agents/export_pdf.py`).
- Before committing cache changes, run the gate:
  `python3 agents/verify_current_week.py` (exit 0 = safe to commit).
