#!/usr/bin/env python3
"""
Deterministic current-week freshness/completeness gate for the weekly report cache.

WHY THIS EXISTS
---------------
The nightly agent fetches ~10 data sources via MCP across many sequential steps.
On 2026-06-25 it did a PARTIAL run: it refreshed alert_volume / incident_volume /
p1_quality / true_p1, but silently SKIPPED engineer_workload (Step 2F), mtta
(Step 2B) and the Intercom steps (3/4/5) — then committed and reported success.
Result: the Engineer Workload slide was frozen 24h stale (22 IC tickets vs the
real 31) and nobody noticed until the numbers were eyeballed against incident.io.

This script is a HARD GATE meant to run AFTER all fetch steps and BEFORE the
commit. It needs no network/MCP — it only cross-checks the cache against itself.
Exit code 0 = safe to commit; non-zero = a partial/stale run was detected, DO NOT
commit; re-run the implicated step.

It cannot catch *symmetric* staleness (every source skipped together) — that's the
agent's job via the live re-count reconciliation in Step 8. This catches the much
more common case where some sources refresh and others don't (they then disagree).

Usage:
    python3 agents/verify_current_week.py            # checks cache/weekly_report_cache.json
    python3 agents/verify_current_week.py --cache /path/to/cache.json
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(_ROOT, "cache", "weekly_report_cache.json")
if "--cache" in sys.argv:
    CACHE = sys.argv[sys.argv.index("--cache") + 1]

# Every key the nightly run is expected to (re)populate for the current week.
EXPECTED_KEYS = [
    "p1_quality_incidentio", "mtta", "incident_volume", "alert_volume",
    "true_p1_incidents", "engineer_workload", "partner_tickets",
    "p1_frt_sla", "p2p3_frt_sla", "csat",
]

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

hard_fails = []   # block the commit
warnings = []     # surface but don't block


def fail(msg):
    hard_fails.append(msg)


def warn(msg):
    warnings.append(msg)


def is_empty(v):
    if v is None:
        return True
    if isinstance(v, (list, dict, str)) and len(v) == 0:
        return True
    return False


def main():
    with open(CACHE) as f:
        cache = json.load(f)

    week_keys = sorted(k for k in cache if _DATE_RE.match(k))
    if not week_keys:
        fail("no ISO-week keys found in cache")
        return report()
    cw = week_keys[-1]
    week = cache[cw] or {}
    print(f"Current week under test: {cw}\n")

    # ── 1. Completeness ──────────────────────────────────────────────────────
    # true_p1_incidents is LEGITIMATELY empty on quiet weeks (zero confirmed P1s).
    # It is only suspicious if p1_quality says there WERE true P1s — then an empty
    # list means the fetch (Step 2D) didn't run. So exempt it from the blanket
    # "empty = fetch produced nothing" rule and check it conditionally below.
    p1q = week.get("p1_quality_incidentio") or {}
    true_p1_count = p1q.get("true_p1") if isinstance(p1q, dict) else None
    for k in EXPECTED_KEYS:
        if k not in week:
            fail(f"[{cw}] missing key '{k}' — a fetch step did not run")
        elif k == "true_p1_incidents":
            # Only fail on empty if p1_quality claims there were true P1s this week.
            if is_empty(week[k]) and true_p1_count:
                fail(f"[{cw}] key 'true_p1_incidents' is empty but p1_quality.true_p1="
                     f"{true_p1_count} — Step 2D did not run")
        elif is_empty(week[k]):
            fail(f"[{cw}] key '{k}' is empty — fetch step produced nothing")

    ew = (week.get("engineer_workload") or {}).get("tickets") or []
    av_intercom = ((week.get("alert_volume") or {}).get("by_source") or {}).get("Intercom")
    iv_total = (week.get("incident_volume") or {}).get("total")
    ic_count = (week.get("incident_volume") or {}).get("ic_ticket_count")
    pt_total = (week.get("partner_tickets") or {}).get("total_count")

    # ── 2. Keystone cross-check (the one that catches a divergent partial run) ─
    # PRIMARY: engineer_workload (Step 2F) is the per-ticket list of IC-Ticket
    # incidents (excl. declined/merged); incident_volume.ic_ticket_count (Step 2C,
    # an INDEPENDENT incident_stats fetch) is the same population counted directly.
    # They must match EXACTLY — a partial run that skips Step 2F leaves a stale
    # engineer_workload while Step 2C refreshes ic_ticket_count, so any mismatch
    # means one step didn't refresh this run. (Original 2026-06-25 catch: stale
    # engineer_workload=22 vs fresh count=31.) This replaces the old Intercom-alert
    # proxy below, which wrongly assumed alerts↔incidents are 1:1.
    if ic_count is not None:
        line = (f"engineer_workload tickets = {len(ew)}  vs  "
                f"incident_volume.ic_ticket_count = {ic_count}")
        if len(ew) != ic_count:
            fail(f"[{cw}] STALE/PARTIAL: {line} — engineer_workload (Step 2F) or "
                 f"incident_volume (Step 2C) did not refresh this run")
        else:
            print("  OK  " + line)
    elif av_intercom is None:
        # No authoritative count AND no Intercom alert count — can't cross-check.
        fail(f"[{cw}] incident_volume.ic_ticket_count absent and alert_volume.Intercom "
             f"absent — cannot cross-check engineer_workload freshness")
    else:
        # Fallback for caches predating ic_ticket_count: use the old Intercom-alert
        # proxy as a hard gate so freshness is still enforced until Step 2C is updated.
        gap = abs(len(ew) - av_intercom)
        tol = max(3, round(0.12 * av_intercom))
        line = (f"engineer_workload tickets = {len(ew)}  vs  "
                f"alert_volume.Intercom = {av_intercom}  (gap {gap}, tolerance {tol})")
        if gap > tol:
            fail(f"[{cw}] STALE/PARTIAL: {line} — one of these incident.io steps "
                 f"did not refresh this run (ic_ticket_count missing; using alert proxy)")
        else:
            print("  OK  " + line)

    # SECONDARY (warning only): Intercom alerts vs IC incidents are NOT 1:1 — a
    # single incident can carry several Intercom alerts (e.g. multi-brand auth
    # outages), so divergence here is informational, not a failure.
    if av_intercom is not None and ew:
        gap = abs(len(ew) - av_intercom)
        if gap > max(3, round(0.12 * av_intercom)):
            warn(f"[{cw}] engineer_workload tickets ({len(ew)}) diverges from "
                 f"alert_volume.Intercom ({av_intercom}) by {gap} — expected when "
                 f"multiple Intercom alerts attach to one incident; verify if unexpected")

    # ── 3. Sanity bounds ─────────────────────────────────────────────────────
    if iv_total is not None and len(ew) > iv_total:
        fail(f"[{cw}] engineer_workload ({len(ew)}) > incident_volume.total ({iv_total}) "
             f"— impossible, IC tickets are a subset of all incidents")

    # ── 4. Soft cross-checks (warn only — legit scope differences possible) ──
    if pt_total is not None and av_intercom:
        if pt_total < 0.6 * av_intercom:
            warn(f"[{cw}] partner_tickets.total_count ({pt_total}) is well below "
                 f"Intercom IC count ({av_intercom}) — Intercom steps may be stale")

    # ── 5. Freshness-by-age (warn) ───────────────────────────────────────────
    newest = max((t.get("reported_at", "") for t in ew), default="")
    if newest:
        try:
            dt = datetime.fromisoformat(newest.replace("Z", "+00:00"))
            age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
            if age_h > 30:
                warn(f"[{cw}] newest engineer_workload ticket is {age_h:.0f}h old "
                     f"({newest}) — verify the current week was re-fetched")
        except ValueError:
            pass

    return report()


def report():
    if warnings:
        print("\nWARNINGS:")
        for w in warnings:
            print("  ⚠ " + w)
    if hard_fails:
        print("\nFAILED — do NOT commit:")
        for fl in hard_fails:
            print("  ✗ " + fl)
        print(f"\n{len(hard_fails)} hard failure(s).")
        return 1
    print("\nPASS — current week is internally consistent. Safe to commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
