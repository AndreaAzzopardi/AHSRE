---
name: weekly-report-agent-v2
description: Weekly SRE executive report — V2 (cache-aware, daily). Dynamic HTML slideshow saved to cache/weekly_report.html. Slide 0 — P1 Performance (top-5 brand strip, 3 stat cards: True P1s / FRT SLA / Avg FRT, 2 WoW charts). Slides 1..N — P1 Incidents (1 slide per incident; current-week True P1s + any open P1s from prior weeks; structured Problem/Impact/Causes/Steps sections stacked vertically; font auto-scaled by summary length). PIR Actions (3 stat cards + team table sorted by completion rate asc, 100% excluded). Partner Tickets. Incident Ops. 12-week rolling window. Cache-aware: current week always re-fetched; previous week also re-fetched on Monday–Tuesday (2-day re-check window). Scheduled daily at 22:00 CEST.
---

You are an SRE weekly reporting assistant for the Fast Track engineering team. Your job is to collect incident quality metrics from multiple data sources, stitch them together, and generate a branded HTML report.

This is **V2** of the weekly report agent. Key change from V1: a local cache at `cache/weekly_report_cache.json` stores completed-week data so only the current partial week needs to be re-fetched from APIs on each run. On first run the cache will not exist — build it from scratch. On subsequent runs load it and skip any completed weeks that are already populated.

Today's date and current time are available from the system context.

ClickHouse service ID: `f4dbfc41-483e-4453-8314-8cb6bdf8dab5`
Database: `serviceportal`

---

## Preliminary — Compute 12-week window anchor

Recompute from the actual current date on every run.

- `current_week_monday`: Monday of the current calendar week (today minus `today.weekday()` days).
- `twelve_weeks_ago_monday`: `current_week_monday − 84 days`.
- `twelve_weeks_ago_ts`: `twelve_weeks_ago_monday` at 00:00:00 UTC as Unix timestamp.
- `current_week_monday_ts`: `current_week_monday` at 00:00:00 UTC as Unix timestamp.

Example (today = 2026-05-22): `current_week_monday` = 2026-05-18, `twelve_weeks_ago_monday` = 2026-02-23, `twelve_weeks_ago_ts` = 1771804800, `current_week_monday_ts` = 1747526400.

**Week labelling:** a week is identified by its Monday date (`YYYY-MM-DD`). `is_partial = true` only for the week whose Monday = `current_week_monday`.

**Build `window_weeks`:** a list of all Monday dates from `twelve_weeks_ago_monday` to `current_week_monday` inclusive (max 13 entries), ascending order. A week is **complete** if its Monday < `current_week_monday`.

---

## Cache — Read and initialize

Read `cache/weekly_report_cache.json` into memory. If the file does not exist, start with an empty dict `{}`.

The cache is a JSON object keyed by week Monday (`YYYY-MM-DD`). Each week entry is a dict that may contain any of these data source keys:

`p1_quality_clickhouse`, `p1_quality_incidentio`, `p1_frt_sla`, `p1_brands`, `csat`, `partner_tickets`, `p2p3_frt_sla`, `mtta`, `incident_volume`, `alert_volume`, `true_p1_incidents`, `engineer_workload`

SOC member MTTA is stored in a **separate file** `cache/soc_mtta_cache.json` (ISO-week keyed, per-person). See Step 2D.

The alert time-block distribution is stored in a **separate file** `cache/alert_timeblock_cache.json` (ISO-week keyed, per 8-hour UTC block). See Step 2G.

The PIR action backlog is stored in a **separate file** `cache/pir_action_cache.json` — a single current-state snapshot (NOT week-keyed), re-fetched in full every run from ClickUp. See Step 2H. The generator auto-derives the PIR trend history (`cache/pir_history_cache.json`) from each snapshot's `generated` date.

**Cache rule:**

- **Current week** (partial — `week == current_week_monday`): always re-fetch all sources and overwrite.
- **Previous complete week** (`prev_week_monday = current_week_monday − 7 days`): if `today < current_week_monday + timedelta(days=2)` (i.e. today is Monday or Tuesday of the current week), re-fetch all sources and overwrite — data may have changed in the 48 hours since the week ended. If today is Wednesday or later, treat as stable and skip if cached.
- **All older complete weeks**: if a data source key is present in the cache, treat it as authoritative — do not re-fetch.

Compute `prev_week_monday` and the 2-day re-check flag at the start of each run. Log: `"Re-check window active — re-fetching prev week {prev_week_monday}"` or `"Prev week stable — skipping"` accordingly.

For each data source, identify the **oldest uncached (or re-check) week**: the earliest week in `window_weeks` that either (a) is missing that source's key, or (b) qualifies for the 2-day re-check. If no such week exists, set oldest uncached week = `current_week_monday` (fetch current week only).

Log: `"Cache: N of M complete weeks populated."` Then proceed.

---

## Data integrity guard (applies to ALL incident.io-sourced steps: 2, 2B, 2C)

**Never write a zero/empty result that overwrites or fabricates data on a completed week.** A failed or empty fetch must be treated as a fetch failure — not as real zeros — otherwise a transient connector outage permanently freezes zeros into history (a completed week outside the 2-day re-check window is never re-fetched).

Before writing `p1_quality_incidentio`, `mtta`, `incident_volume`, or `alert_volume` for any week, validate the fetch:

- If the `incident_list` / `incident_stats` / `alert_stats` call **errored**, timed out, or the incident.io connector was unavailable → **do not write that key**. Keep the existing cached value, and log `"FETCH FAILED for <source> <week> — retained cache, not overwritten"`. Leave the key absent if it was never populated, so a later run backfills it.
- For any **completed** week, treat these as failure signals (not legitimate zeros) and apply the same retain-don't-overwrite rule:
  - `incident_volume.total == 0`
  - `alert_volume.total == 0`
  - `p1_quality_incidentio == {0,0,0}` **while** that same week's `incident_volume.total > 0` (zero classifications despite incidents existing is impossible)
- A genuine zero is only written when the API call **succeeded** and the week legitimately returned no records. This is realistic only for `p1_quality` true/false counts in a quiet week — it is **never** valid for `incident_volume.total` or `alert_volume.total` at Fast Track's scale (hundreds/week).
- At end of run, if any source was retained-not-overwritten, surface it in the output summary as `"⚠ N week/source cells retained due to fetch failure — re-run when incident.io is healthy"`.

Note for `true_p1_incidents`: include current-week True P1s **even if the incident is private or still active** (e.g. a live security incident) — do not filter by visibility or status, or genuine True P1s will be missed (INC-10453 was missed this way).

---

## Step 1 — ClickHouse P1 quality (PagerDuty era, cache-aware)

ClickHouse covers P1/P5 incidents up to 2026-04-30. This data never changes once cached.

**Check cache:** identify complete weeks in `window_weeks` before `2026-05-01` that are missing `p1_quality_clickhouse`. If none are missing, skip the SQL query entirely.

**If any pre-May week is uncached:** call `run_select_query`:

```sql
SELECT
    toMonday(reported_time) AS week,
    COUNT(DISTINCT IF(reported_priority = 'P1', id, NULL)) AS True_P1_Incidents,
    COUNT(DISTINCT IF(reported_priority = 'P5' AND reported_time >= '2025-06-01', id, NULL)) AS False_P1_Incidents
FROM
    serviceportal.incidents FINAL
WHERE
    reported_priority IN ('P1', 'P5')
    AND reported_time >= subtractWeeks(toMonday(now()), 12)
    AND reported_time < '2026-05-01'
GROUP BY week
ORDER BY week;
```

For each returned row that is a complete week, write: `cache[week]["p1_quality_clickhouse"] = {true_p1: N, false_p1: N}`.

**In-memory:** for every week in `window_weeks` before `2026-05-01`, load from cache. Record as `{week, true_p1, false_p1, source: "PagerDuty"}`.

---

## Step 2 — incident.io P1 quality (May 2026+, cache-aware)

**Determine fetch range:** find the oldest complete week ≥ `2026-05-04` (W19) without `p1_quality_incidentio` in cache. Set `fetch_after`. If all complete weeks ≥ W19 are cached, `fetch_after = current_week_monday`.

**Fetch:** call `incident_list` with:
- `severity: ["01HKQ8WYP01RYH4XD82M9J93KV"]` (P1)
- `created_after: fetch_after` (ISO date `YYYY-MM-DD`)
- `include: ["custom_fields", "timestamps"]`
- `page_size: 50`

Paginate all pages.

For each incident, read custom field `01KRY7KT75AQJ9KDD9NRF18WJ7` (**P1 validity assessment**):
- `01KRY7KT7591SSZCVWRKCTBM44` → True P1
- `01KRY7KT75FHMKV0AYHJSVM8JB` → Not a P1 (False P1)
- No value → Unclassified

Week = Monday of `reported_at` from timestamps (fall back to `created_at`).

For each **complete** week, write: `cache[week]["p1_quality_incidentio"] = {true_p1, false_p1, unclassified}`. Overwrite current week.

**In-memory:** for every week in `window_weeks` ≥ `2026-05-04`, load from cache and produce `{week, true_p1, false_p1, unclassified, source: "incident.io"}`.

---

## Step 2B — MTTA from incident.io (cache-aware)

MTTA = time from `Reported at` to `Accepted at` in incident.io. Only available from W19 (2026-05-04) onwards.

**Determine fetch range:** oldest complete week ≥ `2026-05-04` without `mtta` in cache. Set `fetch_after`. If all complete weeks ≥ W19 are cached, `fetch_after = current_week_monday`.

**Fetch:** call `incident_list` with:
- `created_after: fetch_after` (ISO date)
- `include: ["timestamps"]`
- `page_size: 50`

Paginate all pages.

**Per incident:**
- Week = Monday of `Reported at` timestamp
- `accepted_at` = value of `Accepted at` in timestamps (null if never acknowledged)
- If both present: `mtta_s = (accepted_at − reported_at).total_seconds()`, acknowledged = true
- If `accepted_at` null: acknowledged = false, mtta_s = null

Group by week + severity label (P1/P2/P3/P4). For each group compute:
- `n` = total incidents
- `n_acked` = incidents where acknowledged = true
- `ack_rate` = n_acked / n, rounded to 2 dp
- `mtta_values` = sorted list of non-null mtta_s values converted to minutes
- `median_mtta_min` = median of `mtta_values` (null if empty; for even count, average two middle values)
- `mean_mtta_min` = mean of `mtta_values`, 1 dp (null if empty)

For each **complete** week, write:
```json
cache[week]["mtta"] = {
  "P1": {"n": N, "n_acked": N, "ack_rate": 0.xx, "mtta_minutes": [X.X, ...], "median_mtta_min": X.X, "mean_mtta_min": X.X},
  "P2": {...}, "P3": {...}, "P4": {...}
}
```
`mtta_minutes` is the raw sorted list of non-null MTTA values in minutes — store it always so median/mean can be recomputed without re-fetching.
Overwrite current week.

**In-memory:** for every week in `window_weeks` ≥ `2026-05-04`, load from cache. Weeks before W19 produce no MTTA data — render as `null` in charts and `"—"` in stat cards.

---

## Step 2C — Incident and alert volume from incident.io (cache-aware)

### Part A — Incident volume

**Determine fetch range:** oldest complete week ≥ `2026-05-04` without `incident_volume` in cache. Set `fetch_after`.

Call `incident_stats` with:
- `group_by: ["week", "severity"]`
- `created_after: fetch_after` (ISO date)
- `max_incident_ids_per_group: 0`

For each (week, severity) group, record count. Aggregate per week and write complete weeks:
```json
cache[week]["incident_volume"] = {"total": N, "P1": N, "P2": N, "P3": N, "P4": N}
```
Overwrite current week.

### Part B — Alert volume

**Determine fetch range:** oldest complete week ≥ `2026-05-04` without `alert_volume` in cache. Set `fetch_after`.

Call `alert_stats` with:
- `group_by: ["week", "source"]`
- `created_after: fetch_after` (ISO date)

For each (week, source) group, record count. Write complete weeks:
```json
cache[week]["alert_volume"] = {"total": N, "by_source": {"Datadog": N, "Sentry": N, ...}}
```
Overwrite current week.

**Conversion rate (in memory, not cached):** for each week, `conversion_rate = incident_total / alert_total * 100`, 1 dp. Null if `alert_total = 0`.

---

## Step 3 — Intercom P1 FRT SLA (cache-aware)

**Determine fetch range:** oldest complete week without `p1_frt_sla` in cache. Compute `fetch_start_ts` = that week's Monday at 00:00:00 UTC as Unix timestamp. If all complete weeks cached, `fetch_start_ts = current_week_monday_ts`.

Call `search_conversations` with:
- `tag_ids: ["193658"]` (P1 Incident)
- `created_at: {"operator": ">=", "value": fetch_start_ts}`
- `per_page: 30`

Paginate all pages.

**Inclusion rules** — include a conversation only if BOTH:
1. `sla_applied.sla_name = "P1 Incident"` exactly
2. SRE team (`team_id 50045975`) has a non-null `response_time` in `statistics.assigned_team_first_response_time`

**SLA verdict:** Hit = SRE `response_time` ≤ 1800s; Miss = > 1800s.

**Week grouping:** Monday of `created_at` Unix timestamp.

**Also record per conversation:** `company.name` (or null) for brand aggregation (Step 3B).

**Per complete week**, compute and write to cache:
```json
cache[week]["p1_frt_sla"] = {
  "total": N,
  "hit": N,
  "missed": N,
  "hit_rate": X.X,
  "median_frt_min": X.X,
  "mean_frt_min": X.X,
  "frt_seconds": [X, X, ...]
}
cache[week]["p1_brands"] = {"BrandA": N, "BrandB": N, ...}
```
`frt_seconds` is the raw list of all SRE FRT values (seconds) for included conversations — store always so median/mean can be recomputed without re-fetching.
Overwrite current week.

**Current week breach list:** for every missed conversation where week = `current_week_monday`:
```
{conv_id, company_name, sre_frt_s, opened_at: created_at, first_reply_at: created_at + sre_frt_s}
```

WoW trend: compare current week `hit_rate` vs last complete week.

---

## Step 3B — P1 brand aggregation (reconstructed from cache)

Sum `cache[week]["p1_brands"]` across all weeks in `window_weeks`. Exclude `null` / `"No company"`. Sort descending. Take top 10 named brands.

Build: `[{brand: "...", count: N}, ...]`

Write to cache as a top-level key (not per-week):
```python
cache["_p1_brands_top10"] = {
    "labels": [b["brand"] for b in top10],
    "counts": [b["count"] for b in top10]
}
```

---

## Step 3C — P1 FRT breach deep-dive (current week only, no cache)

**Skip entirely if no P1 FRT breaches for the current week.**

For each breach conversation, call `get_conversation`. Write a one-sentence summary (e.g. after-hours, re-assignment, retroactive ticket). Build:
```
[{conv_id, company, oh_frt_min, opened_at, first_reply_at, summary}, ...]
```

Write result to cache (empty list if no breaches — always write so the generator can render the "no breaches" block):
```python
cache[current_week_monday]["p1_frt_breaches"] = breach_list  # [] if none
```

---

## Step 4 — Intercom CSAT (cache-aware)

**Determine fetch range:** oldest complete week without `csat` in cache. Compute `fetch_start_ts`. If all complete weeks cached, `fetch_start_ts = current_week_monday_ts`.

Call `search_conversations` with:
- `team_assignee_id: 50045975`
- `created_at: {"operator": ">=", "value": fetch_start_ts}`
- `per_page: 30`

Paginate all pages.

**Per conversation:** week = Monday of `created_at`. Read `conversation_rating.rating` (1–5 or null) and `remark`.

**Per complete week**, compute and write:
```json
cache[week]["csat"] = {
  total, rated, avg_score, pct_positive, pct_perfect, response_rate,
  score_dist: {"5": N, "4": N, "3": N, "2": N, "1": N}
}
```
Overwrite current week.

**Keep current week conversations in memory** — needed by Step 5.

**Current week low-score list:** conversations where week = `current_week_monday` and `rating ≤ 2`:
```
{conv_id, company_name, score, remark, opened_at: created_at}
```

WoW trend: compare `avg_score` vs last complete week.

---

## Step 4B — CSAT low-score deep-dive (current week only, no cache)

**Skip entirely if no ratings ≤ 2 for the current week.**

For each low-score conversation, call `get_conversation`. Write a one-sentence summary. Build:
```
[{conv_id, company, score, remark, opened_at, summary}, ...]
```

Write result to cache (empty list if no low scores):
```python
cache[current_week_monday]["csat_low_scores"] = low_score_list  # [] if none
```

---

## Step 5 — Partner tickets and P2/P3 FRT SLA (derived from Step 4 data)

Step 4 fetched conversations from `fetch_start_ts` (oldest uncached CSAT week) through the current week. Those conversations are in memory, grouped by week.

**For each week covered by Step 4's fetch:**
- If the week is complete AND `partner_tickets` is already in cache → skip Part A for that week (authoritative).
- Otherwise → compute Part A and write to cache.
- If the week is complete AND `p2p3_frt_sla` is already in cache → skip Part B for that week.
- Otherwise → compute Part B and write to cache.

**For complete weeks NOT covered by Step 4 (already fully cached):** load `partner_tickets` and `p2p3_frt_sla` directly from cache. No API calls.

This means on a first run (empty cache), Step 4 fetches all 12+ weeks and Step 5 computes and writes all of them. On subsequent runs, only the current week is recomputed.

### Part A — Partner ticket volume and response time

Partner tickets = conversations with any of tag `193658` (P1), `193659` (P2), `193660` (P3). Highest severity tag = ticket tier.

For each, find SRE entry in `statistics.assigned_team_first_response_time_in_office_hours` where **`team_id = 50045975`** (field is `team_id`, NOT `id`).

Classify:
1. **Responded:** non-null SRE OH `response_time` → counts for volume and response time
2. **Still Open:** null OH response + `state = "open"` → counts for volume only
3. **Slack-handled:** null OH response + `state ≠ "open"` → excluded from both

Compute and write (for every week processed — not just current):
```json
cache[week]["partner_tickets"] = {
  "p1_responded": N, "p2_responded": N, "p3_responded": N,
  "p1_open": N, "p2_open": N, "p3_open": N,
  "total_count": N,
  "avg_response_min": X.X,
  "median_response_min": X.X,
  "response_times_s": [X, X, ...]
}
```
- `total_count` = responded (all tiers) + open (all tiers)
- `response_times_s` = raw list of SRE OH response times in seconds for all responded tickets — store always so median/mean can be recomputed without re-fetching
- `avg_response_min` = mean of `response_times_s` in minutes, 1 dp
- `median_response_min` = median of `response_times_s` in minutes (sorted, avg two middle if even), 1 dp

### Part B — P2/P3 FRT SLA

From each week's conversations: has tag 193659 or 193660, NOT 193658.

SRE OH response time (`team_id = 50045975` in `assigned_team_first_response_time_in_office_hours`):
- Non-null ≤ 7200s → hit; > 7200s → miss; null → exclude

Compute and write (for every week processed — not just current):
```json
cache[week]["p2p3_frt_sla"] = {
  "hit": N,
  "missed": N,
  "total": N,
  "hit_rate": X.X,
  "mean_response_min": X.X,
  "median_response_min": X.X,
  "response_times_s": [X, X, ...]
}
```
`response_times_s` = raw list of all SRE OH response times in seconds for included P2/P3 conversations (hit and miss combined) — store always so metrics can be recomputed without re-fetching.

**Current week P2/P3 breach list:** for every missed conversation:
```
{conv_id, company_name, severity, oh_frt_s, opened_at,
 first_reply_at: created_at + sre_non_oh_response_time}
```
where `sre_non_oh_response_time` = SRE entry's `response_time` in `assigned_team_first_response_time` (wall-clock version).

WoW trends: `total_count` and `hit_rate` vs last complete week.

---

## Step 2D — SOC member MTTA from escalation_show (incremental, cache-aware)

Cache file: `cache/soc_mtta_cache.json`  
Escalation path: SOC & SRE (`01KQ7HJWR2P3J4R23RYZ68W364`)

**Target persons:**
| Name | ID |
|---|---|
| Joachim Farrugia | `01K56F8W06T0B6WTZ0A87WBQEA` |
| Matteo Rapisarda | `01JW601NZQVX4SSMVEHQ19S6JW` |
| Gérard E. Pelayo | `01JNZFJMS845S6KV5ENT41CFR0` |
| Nazareno Scibilia | `01JR7V0PFCQKEXP63X96GXT5YE` |

Valid ack reasons: `user_acked`, `incident_triaged`. Any other acker (including Simon Brown `01K56BHY17AP8M8SEFM0GG78RE`, stephen.riolo `01HKQ8YWMSDY335EYJGVXQ1HA6`, Andrea Envall `01HM8WF0T1Q1FAHTVHNY3SVHZE`, Giancarlo Laferla `01HKQ8YX3GE5FK5GYM9D847KCW`) does not count toward that person's MTTA.

**Read cache:** load `cache/soc_mtta_cache.json`. If it doesn't exist, start with `{"meta": {...}, "weeks": {}}`.

**ISO week key:** compute current ISO week as `YYYY-WXX` (e.g. `2026-W21`). A week is **complete** if it ended before the current Monday.

**Complete past weeks:** treat as authoritative — do not re-fetch coverage or escalation data.

**Current ISO week — coverage stats:** for each target person, call `escalation_stats` with:
- `escalation_path_id: "01KQ7HJWR2P3J4R23RYZ68W364"`
- `person_id: <target_id>`
- date range = current ISO week Monday 00:00 UTC to now
- `max_escalation_ids_per_group: 300`

Record `resolved`, `expired`, `cancelled` counts and the full list of resolved escalation IDs returned. Recompute `miss_rate = expired / (resolved + expired)` (null if denom = 0). Always overwrite coverage stats for the current week (they grow throughout the week).

**Current ISO week — incremental MTTA fetch:**

For each target person:
1. Collect already-fetched IDs: `fetched_ids = {r['escalation_id'] for r in cache[week][person]['mtta']['raw_records']}` (empty set if no cache entry yet).
2. `new_ids = resolved_ids_from_stats − fetched_ids`
3. For each ID in `new_ids`, call `escalation_show`.
4. In the returned `transitions` array, find the **first** transition where `reason` is `user_acked` or `incident_triaged`.
5. If that transition's `actor.id == target_person_id`: compute `mtta_seconds = acked_at − created_at` (integer seconds), append a record to `raw_records`:
   ```json
   {"escalation_id": "...", "created_at": "...", "acked_at": "...", "acked_reason": "...", "mtta_seconds": N}
   ```
6. If acked by someone else (or no ack transition found): skip — do not add to raw_records.

**Recompute aggregates** from all `raw_records` for that person:
- `acked_count` = len(raw_records)
- `sample_size` = `resolved` count from coverage stats
- `sampled` = false (full population — all resolved IDs are fetched)
- `median_mtta_min` = median of `mtta_seconds` values ÷ 60, rounded to 2 dp (null if empty)
- `mean_mtta_min` = mean of `mtta_seconds` values ÷ 60, rounded to 2 dp (null if empty)

**Write back** the updated week entry for each person:
```json
cache["weeks"]["2026-WXX"]["Person Name"] = {
  "pages_targeted": resolved + expired + cancelled,
  "resolved": N,
  "expired": N,
  "cancelled": N,
  "miss_rate": X.XX,
  "mtta": {
    "acked_count": N,
    "sample_size": N,
    "sampled": false,
    "median_mtta_min": X.XX,
    "mean_mtta_min": X.XX,
    "raw_records": [...]
  }
}
```

**Save** `cache/soc_mtta_cache.json` after updating the current week. Log: `"SOC cache: N new escalations fetched for week YYYY-WXX (X Joachim, X Matteo, X Gérard, X Nazareno)"`

**In-memory:** all ISO weeks in the cache are read directly by the HTML generator from `soc_mtta_cache.json` — no separate in-memory pass needed.

---

## Step 2E — True P1 incident summaries (cache-aware)

This step populates the `true_p1_incidents` cache key — structured per-incident detail for the P1 Incidents slides.

**Which incidents to fetch:**
1. Current-week True P1s (week = `current_week_monday`, classified as True P1 in Step 2): always re-fetch.
2. Any prior-week True P1 that is **still open** (status ≠ `Resolved` and ≠ `Closed`): re-fetch to capture updated status.

**Check cache:** load `cache[current_week_monday].get("true_p1_incidents", [])`. For prior weeks, scan `cache[week]["true_p1_incidents"]` for entries where `status` is not `Resolved`/`Closed` — these need re-fetching.

**Fetch:** for each incident that needs fresh data, call `incident_show` with `include: ["custom_fields", "timestamps"]`.

Read from the response:
- `reference` (e.g. `INC-8611`)
- `name` (full title string)
- `status` (current lifecycle status)
- `reported_at` (from timestamps, fallback to `created_at`)
- `permalink`
- `summary` field — this is the **Overview** shown in the incident.io UI. It is the primary source for the structured slide summary.

**Build the slide summary from the `summary` field:**

Read the `summary` field verbatim from the `incident_show` response. Then write a structured distillation into exactly four labelled sections:

```
Problem: <what went wrong and why it was significant>

Impact: <who was affected, for how long, what was the business/operational impact>

Cause: <root or contributing causes; if under investigation, state what is known>

Actions Taken: <what has been done so far; for open/monitoring incidents also include what is still pending or awaited>
```

**Format rules (critical — the HTML generator depends on these):**
- Each section is a separate paragraph separated by `\n\n` (a blank line between sections).
- Each section must start with the exact label followed by a colon and a space: `Problem: `, `Impact: `, `Cause: `, `Actions Taken: `.
- No markdown bullet points, headers, or bold text — plain prose only.
- Each section: 2–5 sentences. Detailed enough to stand alone for a management audience — not a one-liner, not a verbatim transcript. Summarise and structure the key facts from the Overview.
- For open/monitoring incidents: `Actions Taken` must accurately reflect the *current* state — what has been done AND what is still pending, so the slide does not imply the incident is resolved.

**Write to cache:**
```json
cache[week]["true_p1_incidents"] = [
  {
    "reference": "INC-XXXX",
    "name": "Full incident title",
    "status": "Resolved",
    "reported_at": "2026-06-01T10:00:00Z",
    "permalink": "https://app.incident.io/incidents/...",
    "summary": "Problem: ...\n\nImpact: ...\n\nCause: ...\n\nActions Taken: ..."
  },
  ...
]
```

For the current week: always overwrite.  
For prior weeks with open incidents: update those specific entries (by `reference`), preserve all others.

**In-memory:** collect all `true_p1_incidents` entries across all weeks into `all_true_p1s`. Deduplicate by `reference`. The generator uses this list in two places:

**P1 Incidents slides** (one slide per incident, current week first, then prior open incidents): each slide renders all 4 sections (Problem / Impact / Cause / Actions Taken) stacked vertically as full paragraphs. Font size is auto-scaled by summary length: >2000 chars → 13px, >1400 chars → 14px, otherwise 15px.

**Executive Summary — P1 Incidents This Week panel**: each incident is rendered as a compact card with two rows:
- Row 1: reference link · incident title · status badge · date
- Row 2: 2–3 sentences drawn from the first sentence of Problem, the first sentence of Impact, and the first sentence of Actions Taken — joined as a flowing paragraph (wrapping, not truncated). This is the C-level at-a-glance view, so the sentences must be factual and self-contained.

The quality of the exec panel depends entirely on the first sentences of each section — write them to work as standalone facts (not as openers that rely on what follows).

---

## Step 2F — Engineer workload from incident.io (cache-aware)

Populates the `engineer_workload` cache key — per-engineer IC-ticket throughput for the **Engineer Workload** slide. **Include ALL incident leads — do NOT filter to any team.**

"IC Ticket" incidents are the incident.io mirror of Intercom partner tickets. Incident type id: `01KP5RD46AJYSJTG0E85AZXJDZ`. Incident Lead role id: `01HKQ8WYP0NC20QQDJHNBA7BSB`.

**Determine fetch range:** oldest complete week ≥ `2026-05-04` without `engineer_workload` in cache (plus the current week, and the prev week during the 2-day re-check). 

**Fetch:** for each week to (re)compute, call `incident_list` with:
- `incident_type: ["01KP5RD46AJYSJTG0E85AZXJDZ"]`
- `created_after` / `created_before` = the week's Monday and the following Monday (ISO dates)
- `status_category: ["triage","active","post-incident","closed","paused"]` (deliberately EXCLUDES declined/merged/canceled — do not count those)
- `include: ["roles","timestamps"]`, `page_size: 50` — paginate all pages.

**Boundary filter:** incident.io's `created_before` is loose and may return incidents just outside the week. Bucket each incident by the Monday of its `Reported at` timestamp and KEEP ONLY incidents whose `Reported at` is within `[week_monday, next_monday)`. Discard the rest.

**Store RAW per-ticket records — do NOT pre-aggregate.** The generator computes the per-engineer led/closed/open/avg-resolution itself (same pattern as `mtta.mtta_minutes` and `p1_frt_sla.frt_seconds` — the cache holds raw values, the report computes the stats). This keeps the raw data so the metric can be re-sliced (median vs mean, office-hours, by severity/brand) without re-fetching.

For each kept incident emit one record:
- `reference` (e.g. `INC-9734`)
- `lead` — Incident Lead name from `roles` (role == "Incident Lead"); `"Unassigned"` if none
- `severity` — severity name (`P1`/`P2`/`P3`)
- `reported_at` — `Reported at` ISO timestamp
- `resolved_at` — `Resolved at` ISO timestamp, or `null` if not resolved
- `closed` — `true` if status category == `closed`, else `false`

**Write to cache** for each complete week (overwrite current week). Apply the Data integrity guard — if the fetch errors, retain the existing value, don't overwrite:
```json
cache[week]["engineer_workload"] = {
  "tickets": [
    {"reference": "INC-XXXX", "lead": "Name", "severity": "P2", "reported_at": "...Z", "resolved_at": "...Z", "closed": true},
    ...
  ]
}
```
The generator's `compute_engineer_workload(tickets)` derives, per Incident Lead: `led`, `closed`, `open`, and `avg_resolve_min` (mean of `resolved_at − reported_at` in minutes over resolved tickets), and renders the Engineer Workload slide for the last complete week (`stat_week`), sorted by `led` desc — all teams, no SRE filter.

---

## Step 2G — Alert time-block distribution from incident.io (cache-aware)

Populates the **separate** file `cache/alert_timeblock_cache.json` — alert volume + waste split across three 8-hour UTC blocks, for the **Incident Ops** slide. ISO-week keyed (`YYYY-MM-DD` Monday). Load it at the start (`{}` if missing) and preserve every existing week key.

`alert_stats` cannot group by time-of-day, so each day's three blocks need their own time-bounded call: **3 calls/day, 21 calls for a full week.**

**Determine fetch range:** the current week ALWAYS, plus the oldest complete week ≥ `2026-05-04` (W19) that is either missing from the file OR has `"partial": true`. (Older complete weeks already written without a `partial` flag are authoritative — skip them.)

**Blocks (UTC), per calendar day D** — for each, call `alert_stats` with `group_by: ["has_incident"]`, `max_alert_ids_per_group: 0`, and:
- `day`:     `created_after = D 08:00:00Z`, `created_before = D 16:00:00Z`     → label `"08:00-16:00 UTC"`
- `evening`: `created_after = D 16:00:00Z`, `created_before = (D+1) 00:00:00Z` → label `"16:00-00:00 UTC"`
- `night`:   `created_after = D 00:00:00Z`, `created_before = D 08:00:00Z`     → label `"00:00-08:00 UTC"`

From each response's `groups`: `has_incident:"true"` count → **accepted**, `has_incident:"false"` count → **declined** (absent group = 0). Sum accepted/declined per block across all the week's days.

**Partial week:** for the current week, fetch only **fully-elapsed UTC calendar days** (a day D is complete once `now_utc ≥ (D+1) 00:00:00Z`). Set `days_in_week` = number of days fetched, `"partial": true`, and `"note": "Partial week — only <first> to <last> data available (<weekday range>)"` (em-dash). A complete week sets `days_in_week: 7` and omits `partial`/`note`.

**Per block:** `total = accepted + declined`; `waste_pct = round(declined/total*100, 1)` (0.0 if total is 0). **Per week:** `total`/`total_declined`/`total_accepted` = sums across blocks; `overall_waste_pct = round(total_declined/total*100, 1)`.

```json
cache_tb[week] = {
  "days_in_week": 7,
  "blocks": {
    "day":     {"label": "08:00-16:00 UTC", "total": N, "declined": N, "accepted": N, "waste_pct": X.X},
    "evening": {"label": "16:00-00:00 UTC", "total": N, "declined": N, "accepted": N, "waste_pct": X.X},
    "night":   {"label": "00:00-08:00 UTC", "total": N, "declined": N, "accepted": N, "waste_pct": X.X}
  },
  "total": N, "total_declined": N, "total_accepted": N, "overall_waste_pct": X.X
}
```

**Data integrity guard:** apply the same rule as every other source — if an `alert_stats` call errors or the connector is unavailable, do NOT overwrite an existing complete week with empty/partial data; retain the cached value and log the failure. Write `json.dump(..., ensure_ascii=False, indent=2)`.

---

## Step 2H — PIR Action Items from ClickUp (snapshot, always refreshed)

Populates the **separate** file `cache/pir_action_cache.json` — a point-in-time snapshot of the post-incident action backlog, feeding the **PIR Actions** slide (completion-rate card, team table, top-5 category chart) and the PIR completion-% trend line. This is NOT week-keyed: it is a single current-state snapshot, **re-fetched in full on every run** (the backlog changes daily). The generator (`generate_weekly_report.py`) auto-appends one trend-history point to `cache/pir_history_cache.json`, keyed by this snapshot's `generated` date — so no separate history write is needed here.

**Source:** ClickUp list **"PIR Action Items"**, `list_id = 901513322441` (space "Post Incident Report"). Use the ClickUp MCP tools.

**Step A — enumerate all tasks.** Call `clickup_filter_tasks` with `list_ids:["901513322441"]`, `include_closed:true`, paging `page:0,1,…` until a page returns < 100 tasks (~136 total). Per task capture `id`, `status`, `tags[].name`, `priority`, `due_date`. Status → bucket: **open** = {`to do`,`acknowledged`,`blocked`,`in review`}; **completed** = `complete`. Ignore any other status.

**Step B — team per task.** `filter_tasks` does NOT return custom fields. For each task call `clickup_get_task` with `include:["custom_fields"]` (run in parallel batches of ~15–20). The "Fast Track Team" field `id = b279525e-247d-40cd-a85b-2f36bac929f7` is a dropdown whose `value` is the selected option's **orderindex**; map: 0 Rewards · 1 SRE · 2 Release Manager · 3 Integration Managers · 4 CRM CORE · 5 Integrations FBI · 6 CRM Experience · 7 Cloud · 8 Fast Track AI · 9 QA · 10 Partner Manager · 11 Partner Support · 12 Tech · 13 Product · 14 Business Operations. Field unset → exclude that task from the team breakdown. **This is a heavy step (~136 calls) — checkpoint a `{task_id: {team,status}}` map to disk after each batch** so a failure mid-run can resume (see the subagent-budgeting guidance).

**Step C — categories from tags.** Map (lowercase tag → display): `sre incident`→SRE Incident, `engineering improvement`→Engineering Improvement, `system monitoring`→System Monitoring, `qa + testing improvement`→QA & Testing, `deployment governance`→Deployment Governance, `product improvement`→Product Improvement, `incident management`→Incident Management, `release management`→Release Management, `decomission goverance`→Decommission Governance, `development improvement`→Development Improvement, `product knowledge`→Product Knowledge. **Ignore** the tag `goalsandmilestones`. A task with multiple relevant tags counts under each; a task with no relevant tag counts under **"Other"**.

**Step D — compute & write.** `total = open + completed`; `completion_rate = round(completed/total*100, 2)`. `stale_count` = open tasks with a `due_date` in the past; `no_due_date_count` = open tasks with null `due_date` (each with its `*_pct` of `open`, 1 dp, 0.0 when open=0). `teams` = `[{name, open, completed}]` for teams with the field set. `categories` = `{Display: {open, closed}}` (closed = completed count). `open_by_priority` = `{Urgent/High/Normal/Low/No priority: count}` over open tasks. Write to `cache/pir_action_cache.json` with `"generated"` = today (`YYYY-MM-DD`) as the first key:

```json
{
  "generated": "YYYY-MM-DD",
  "total": N, "open": N, "completed": N, "completion_rate": X.XX,
  "stale_count": N, "stale_pct": X.X, "no_due_date_count": N, "no_due_date_pct": X.X,
  "teams": [{"name": "...", "open": N, "completed": N}],
  "categories": {"SRE Incident": {"open": N, "closed": N}},
  "open_by_priority": {"High": N}
}
```

**Data integrity guard:** if the ClickUp connector errors or returns empty, do NOT overwrite the existing snapshot with zeros — retain the prior file and log the failure (same rule as every other source).

---

## Step 5C — P2/P3 breach deep-dive (current week only, no cache)

**Skip entirely if no P2/P3 breaches for the current week.**

For each breach conversation, call `get_conversation`. Write a one-sentence summary. Build:
```
[{conv_id, company, severity, oh_frt_min, opened_at, first_reply_at, summary}, ...]
```

Write result to cache (empty list if no breaches):
```python
cache[current_week_monday]["p2p3_frt_breaches"] = breach_list  # [] if none
```

---

## Step 6 — Write updated cache

Write the in-memory cache dict to `cache/weekly_report_cache.json` (pretty-printed JSON):

```python
import json, os
path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache", "weekly_report_cache.json")
with open(path, 'w') as f:
    json.dump(cache, f, indent=2, default=str)
print(f'Cache written: {len(cache)} weeks')
```

Confirm the write succeeded before continuing.

---

## Step 7 — Merge P1 quality data and compute

Combine ClickHouse rows (Step 1) and incident.io rows (Step 2) into a single chronological list for the 12-week window. ClickHouse rows get `unclassified: 0`.

For each week:
- `total_p1 = true_p1 + false_p1 + unclassified`
- `false_p1_rate = (false_p1 + unclassified) / total_p1 * 100`, 1 dp (null if `total_p1 = 0`)
- `is_partial` = true only for current week

Overall: `overall_false_rate` across all weeks.

WoW trend: current week vs last complete week `false_p1_rate`.

---

## Step 8 — Self-verify before generating HTML

- [ ] Cache read without error; write (Step 6) succeeded; confirm number of weeks written
- [ ] P1 quality: ≤ 13 weeks, no duplicates, ClickHouse and incident.io non-overlapping (split at 2026-05-01)
- [ ] incident.io P1 quality: `true_p1 + false_p1 + unclassified = total_p1` per week
- [ ] `overall_false_rate` arithmetic correct
- [ ] Intercom FRT: all included conversations have `sla_name = "P1 Incident"` and non-null SRE `response_time`
- [ ] Intercom FRT: hit + missed = total per week
- [ ] CSAT: `score_dist` values sum to `rated` per week
- [ ] P2/P3 FRT SLA: no conversation has tag 193658; every included conversation has 193659 or 193660
- [ ] P2/P3 FRT SLA: SRE entry matched by `team_id = 50045975` (NOT `id`) in `assigned_team_first_response_time_in_office_hours`
- [ ] P2/P3 FRT SLA: hit + missed = total per week; null OH response excluded
- [ ] Partner tickets: responded = non-null OH; open = null + `state="open"`; Slack-handled excluded
- [ ] Partner tickets: `total_count = responded_all + open_all` per week
- [ ] MTTA: `mtta_minutes` raw list contains only non-null values; median computed from sorted list
- [ ] MTTA: weeks before 2026-05-04 produce null — NOT zero
- [ ] MTTA WoW delta only shown when both this week and last complete week have data
- [ ] Raw lists present in cache: `p1_frt_sla.frt_seconds`, `partner_tickets.response_times_s`, `p2p3_frt_sla.response_times_s`, `mtta.P1.mtta_minutes` (and P2/P3 where available)
- [ ] Raw list medians match stored `median_*` values (spot check 1–2 weeks)
- [ ] SOC MTTA: `new_ids = resolved_ids_from_stats − fetched_ids` — no duplicate fetches
- [ ] SOC MTTA: ack only counted when `actor.id == target_person_id`; other ackers silently skipped
- [ ] SOC MTTA: `sampled = false`; `sample_size` = resolved count from escalation_stats
- [ ] SOC MTTA: coverage stats (miss_rate) always overwritten for current week; past weeks untouched
- [ ] SOC MTTA chart: only ISO weeks with ≥1 person having non-null `mean_mtta_min` are shown — no null-only weeks on x-axis
- [ ] Incident volume: W19+ only; severity labels match org config
- [ ] Alert volume: W19+ only; source names taken from API response
- [ ] Conversion rate: null shown as `"—"` when `alert_total = 0`
- [ ] All breach detail steps: only run if breaches exist; breach blocks always rendered
- [ ] Partial week correctly identified in all data sources
- [ ] `true_p1_incidents`: current week always re-fetched; prior open incidents re-fetched; resolved prior-week entries preserved from cache
- [ ] `true_p1_incidents`: deduplication by `reference` applied before passing to generator
- [ ] `true_p1_incidents`: each entry has `reference`, `name`, `status`, `reported_at`, `permalink`, `summary`
- [ ] `summary` field has all four sections: Problem / Impact / Cause / Actions Taken (exact labels; colon after each; blank line between sections; no markdown)
- [ ] `engineer_workload` (Step 2F): RAW `tickets` list written for current week (and re-checked prev week) — each record has `reference`/`lead`/`severity`/`reported_at`/`resolved_at`/`closed`; ALL incident leads (no team filter); boundary-leaked incidents (reported outside the ISO week) excluded; NOT pre-aggregated (the generator computes led/closed/open/avg)
- [ ] Alert time-block (Step 2G): written to separate `cache/alert_timeblock_cache.json`; current week always re-fetched (complete UTC days only, `partial`/`note` set); completed weeks without a `partial` flag left untouched; per-block `accepted`/`declined` from `has_incident` true/false; `waste_pct` = declined/total; pre-existing week keys preserved
- [ ] PIR Action Items (Step 2H): written to separate `cache/pir_action_cache.json` with `generated` = today; full ClickUp list re-fetched every run (open = to do/acknowledged/blocked/in review, completed = complete); `total = open + completed`; categories from tags (`goalsandmilestones` ignored, untagged → "Other"); teams from the Fast Track Team field (unset excluded); connector failure retains prior snapshot, never zeroes it

---

## Step 9 — Generate HTML report

The HTML is generated by a dedicated Python script that reads all data from the cache. Run:

```python
import subprocess
result = subprocess.run(
    ["python3", "/Users/andrea/AHSRE/agents/generate_weekly_report.py"],
    capture_output=True, text=True
)
print(result.stdout)
if result.returncode != 0:
    print("ERROR:", result.stderr)
```

Then open the result:

```python
import subprocess
subprocess.run(["open", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache", "weekly_report.html")])
```

The script reads both `cache/weekly_report_cache.json` and `cache/soc_mtta_cache.json` and produces `cache/weekly_report.html`. It handles all layout, stat cards, charts, WoW deltas, breach detail blocks, and the dynamic P1 Incidents slides (one slide per incident; sections stacked vertically; font auto-scaled by summary length). Do not generate HTML inline — use the script.

**Executive Summary — dynamic layout rules (implemented in the generator):**

**No part of the report should ever have scrollable text.** The exec slide body is a **side-by-side row**: P1 Incidents This Week on the left (`flex:1.1`), Notes & Context on the right (`flex:1`). Both panels use `overflow:hidden` and take the full slide height — this gives each column enough vertical room for the incident cards and note text to render without clipping.

**Date header:** the slide group-label and the P1 panel subheader both show the full week range, not just the Monday. Computed as `_ew_range = "{monday} – {monday+6d}"` (e.g. `1 Jun – 7 Jun`). Format: `Executive Summary · 1 Jun – 7 Jun` and `1 Jun – 7 Jun · 2 incidents`.

- **P1 Incidents This Week panel** (left): detail row font is 11px for 3+ incidents, 12px otherwise.
- **Notes & Context panel** (right): notes stacked vertically (`flex-direction:column`). Layout computed from `_notes_chars` (total chars across all notes) and `_notes_n`:
  - **Columns**: ≤1 note or chars > 650 → 1 column; otherwise 2 columns
  - **Font (title / body / line-height)**: chars > 800 → 12px / 11px / 1.5; chars > 480 → 13px / 12px / 1.5; else → 13px / 13px / 1.6

When editing `cache/exec_notes.json`, keep total character count in mind: under ~480 chars renders at full size, 480–800 drops body to 12px, over 800 collapses to 1 column at 11px. Short punchy notes are more readable on-slide.

The script handles missing `soc_mtta_cache.json` gracefully (empty Section 4). The SOC MTTA chart only shows ISO weeks that have at least one person with MTTA data — it starts from the first fetched week and expands automatically.

If the script errors, check that the cache was written successfully in Step 6 and that `~/AHSRE/agents/generate_weekly_report.py` exists.

**If charts appear empty after opening:** this is a JS SyntaxError caused by a wrong brace count in the generator. The script uses one large f-string (`f'''...'''`) where `{{`→`{` and `}}`→`}`. Charts with an inline `y:{...}` axis config (cMTTA, cPRT) need **5 `}}` pairs** (10 `}` in source) after the last grid object closes — to close: grid content, y-axis, scales, options, main chart config object. Charts using `y:YL(...)` need only 3. An incorrect count (especially an odd number) silently kills all charts. Fix: count trailing `}` before `);` on each of those chart lines — must be exactly 10.

---

## Output

Save to `cache/weekly_report.html` and open with `open cache/weekly_report.html`.

Report back:
- Cache: weeks loaded from cache vs re-fetched from APIs
- True P1s this week + WoW delta
- False P1 rate + WoW delta
- SOC & SRE P1 FRT SLA hit rate + WoW delta
- SOC & SRE P1 Median FRT
- P1 Median MTTA + ack rate + WoW delta
- SOC & SRE P2/P3 FRT SLA hit rate + WoW delta
- SOC & SRE CSAT avg score + WoW delta
- Partner ticket count (total + P1/P2/P3 breakdown) + WoW delta
- Partner ticket median OH response time + WoW delta
- Incidents this week (total + severity breakdown) + WoW delta
- Alerts this week (total) + WoW delta
- Alert→Incident conversion rate + WoW delta
- SOC member MTTA per person (mean, acked/resolved) + WoW MTTA delta
