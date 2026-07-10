#!/usr/bin/env python3
"""
Refresh cache/pir_action_cache.json (+ pir_history_cache.json) from ClickUp.

Replaces the manual Step 2H of the weekly-report agent. Uses the ClickUp REST
API directly — GET /list/{id}/task returns custom_fields inline, so the whole
list is ~2 paginated requests instead of the ~136 per-task MCP calls the
connector needed.

Runs from the "Refresh PIR cache" GitHub Actions workflow (daily 19:15 UTC,
before the 20:03 UTC report routine clones the repo), or manually:

    CLICKUP_API_TOKEN=pk_... python3 agents/refresh_pir_cache.py

Never overwrites the existing snapshot on failure or on a suspiciously small
result (same integrity rule as every other report source).
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

LIST_ID = "901513322441"  # "PIR Action Items" in space "Post Incident Report"
TEAM_FIELD_ID = "b279525e-247d-40cd-a85b-2f36bac929f7"  # "Fast Track Team" dropdown

# Dropdown value = option orderindex. Fallback map if type_config is absent.
TEAM_BY_ORDERINDEX = {
    0: "Rewards", 1: "SRE", 2: "Release Manager", 3: "Integration Managers",
    4: "CRM CORE", 5: "Integrations FBI", 6: "CRM Experience", 7: "Cloud",
    8: "Fast Track AI", 9: "QA", 10: "Partner Manager", 11: "Partner Support",
    12: "Tech", 13: "Product", 14: "Business Operations",
}

OPEN_STATUSES = {"to do", "acknowledged", "blocked", "in review"}
DONE_STATUSES = {"complete"}

CATEGORY_BY_TAG = {
    "sre incident": "SRE Incident",
    "engineering improvement": "Engineering Improvement",
    "system monitoring": "System Monitoring",
    "qa + testing improvement": "QA & Testing",
    "deployment governance": "Deployment Governance",
    "product improvement": "Product Improvement",
    "incident management": "Incident Management",
    "release management": "Release Management",
    "decomission goverance": "Decommission Governance",
    "development improvement": "Development Improvement",
    "product knowledge": "Product Knowledge",
}
IGNORED_TAGS = {"goalsandmilestones"}

PRIORITY_KEYS = ["Urgent", "High", "Normal", "Low", "No priority"]

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE = os.path.join(_ROOT, "cache", "pir_action_cache.json")
HISTORY_FILE = os.path.join(_ROOT, "cache", "pir_history_cache.json")


def fetch_all_tasks(token):
    tasks, page = [], 0
    while True:
        url = (f"https://api.clickup.com/api/v2/list/{LIST_ID}/task"
               f"?page={page}&include_closed=true")
        req = urllib.request.Request(url, headers={"Authorization": token})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
        batch = data.get("tasks", [])
        tasks.extend(batch)
        if data.get("last_page") or len(batch) < 100:
            return tasks
        page += 1


def team_of(task):
    for f in task.get("custom_fields", []):
        if f.get("id") != TEAM_FIELD_ID:
            continue
        val = f.get("value")
        if val is None:
            return None
        for opt in (f.get("type_config") or {}).get("options", []):
            if opt.get("orderindex") == val or opt.get("id") == val:
                return opt.get("name")
        try:
            return TEAM_BY_ORDERINDEX.get(int(val))
        except (TypeError, ValueError):
            return None
    return None


def main():
    token = os.environ.get("CLICKUP_API_TOKEN")
    if not token:
        print("FAIL: CLICKUP_API_TOKEN not set", file=sys.stderr)
        return 1

    try:
        raw = fetch_all_tasks(token)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"FAIL: ClickUp fetch error: {e} — keeping existing snapshot", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    n_open = n_done = 0
    stale = no_due = 0
    teams = {}
    categories = {}
    open_by_priority = {k: 0 for k in PRIORITY_KEYS}
    # Class split: items tagged "sre incident" are day-to-day SRE improvement
    # suggestions to teams; everything else comes from Critical Incident / P1
    # postmortems. Each task is classed exactly once.
    classes = {
        "critical":     {"open": 0, "completed": 0},
        "sre_incident": {"open": 0, "completed": 0},
    }

    for t in raw:
        status = ((t.get("status") or {}).get("status") or "").lower()
        if status in OPEN_STATUSES:
            bucket = "open"
            n_open += 1
        elif status in DONE_STATUSES:
            bucket = "completed"
            n_done += 1
        else:
            continue  # any other status is ignored, per Step 2H spec

        team = team_of(t)
        if team:
            teams.setdefault(team, {"open": 0, "completed": 0})[bucket] += 1

        tags = [tag.get("name", "").lower() for tag in t.get("tags", [])]
        cats = [CATEGORY_BY_TAG[tg] for tg in tags if tg in CATEGORY_BY_TAG]
        for cat in (cats or ["Other"]):
            c = categories.setdefault(cat, {"open": 0, "closed": 0})
            c["open" if bucket == "open" else "closed"] += 1

        cls = "sre_incident" if "sre incident" in tags else "critical"
        classes[cls][bucket] += 1

        if bucket == "open":
            pri = ((t.get("priority") or {}).get("priority") or "").capitalize()
            open_by_priority[pri if pri in PRIORITY_KEYS else "No priority"] += 1
            due = t.get("due_date")
            if due is None:
                no_due += 1
            elif datetime.fromtimestamp(int(due) / 1000, tz=timezone.utc) < now:
                stale += 1

    total = n_open + n_done
    if total == 0:
        print("FAIL: 0 relevant tasks returned — keeping existing snapshot", file=sys.stderr)
        return 1
    try:
        with open(CACHE_FILE) as f:
            prev_total = json.load(f).get("total", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        prev_total = 0
    if total < 0.5 * prev_total:
        print(f"FAIL: fetched total {total} < half of previous {prev_total} — "
              f"looks like a partial fetch, keeping existing snapshot", file=sys.stderr)
        return 1

    rate = round(n_done / total * 100, 2)
    for cls in classes.values():
        cls_total = cls["open"] + cls["completed"]
        cls["total"] = cls_total
        cls["completion_rate"] = round(cls["completed"] / cls_total * 100, 2) if cls_total else 0.0
    snapshot = {
        "generated": now.strftime("%Y-%m-%d"),
        "total": total,
        "open": n_open,
        "completed": n_done,
        "completion_rate": rate,
        "stale_count": stale,
        "stale_pct": round(stale / n_open * 100, 1) if n_open else 0.0,
        "no_due_date_count": no_due,
        "no_due_date_pct": round(no_due / n_open * 100, 1) if n_open else 0.0,
        "teams": sorted(
            [{"name": k, **v} for k, v in teams.items()],
            key=lambda x: (-(x["open"] + x["completed"]), x["name"]),
        ),
        "categories": dict(sorted(categories.items(), key=lambda kv: -kv[1]["open"])),
        "open_by_priority": open_by_priority,
        "classes": classes,
    }
    with open(CACHE_FILE, "w") as f:
        json.dump(snapshot, f, indent=2)

    # Same snapshot the HTML generator would append — kept here so the history
    # accrues even on runs where the generator never executes.
    try:
        with open(HISTORY_FILE) as f:
            history = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        history = {}
    history[snapshot["generated"]] = {
        "open": n_open, "completed": n_done, "total": total, "rate": round(rate, 1),
        "crit_rate": classes["critical"]["completion_rate"],
        "sre_rate":  classes["sre_incident"]["completion_rate"],
    }
    with open(HISTORY_FILE, "w") as f:
        json.dump(dict(sorted(history.items())), f, indent=2)

    print(f"OK: {total} tasks ({n_open} open / {n_done} done, {rate}%) — "
          f"{len(teams)} teams, {len(categories)} categories")
    return 0


if __name__ == "__main__":
    sys.exit(main())
