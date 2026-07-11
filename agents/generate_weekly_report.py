import base64
import json
import os
from datetime import datetime, timezone, timedelta
from collections import defaultdict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE     = os.path.join(_ROOT, "cache", "weekly_report_cache.json")
OUTPUT_FILE    = os.path.join(_ROOT, "cache", "weekly_report.html")

# ── Vendored assets (agents/assets/) — inlined so the report is fully
# self-contained: no CDN/Google Fonts fetch needed for offline viewing,
# archived copies, or PDF export. Latin subsets only (same coverage as the
# old Google Fonts links; non-latin glyphs fall back to system fonts).
_ASSETS_DIR = os.path.join(_ROOT, "agents", "assets")

def _b64_asset(*parts):
    with open(os.path.join(_ASSETS_DIR, *parts), "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")

vendored_font_css = "\n".join(
    "@font-face { font-family: '%s'; font-style: normal; font-weight: %s; "
    "src: url(data:font/woff2;base64,%s) format('woff2'); }" % (fam, wght, _b64_asset("fonts", fname))
    for fam, wght, fname in [
        ("DM Sans", "100 1000", "dm-sans-var.woff2"),   # variable font covers all weights used
        ("DM Mono", "400",      "dm-mono-400.woff2"),
        ("DM Mono", "500",      "dm-mono-500.woff2"),
    ]
)

with open(os.path.join(_ASSETS_DIR, "chart.umd.min.js")) as f:
    vendored_chartjs = f.read()

with open(CACHE_FILE) as f:
    cache = json.load(f)

TB_CACHE_FILE = os.path.join(_ROOT, "cache", "alert_timeblock_cache.json")
try:
    with open(TB_CACHE_FILE) as f:
        tb_cache = json.load(f)
except FileNotFoundError:
    tb_cache = {}

PIR_CACHE_FILE = os.path.join(_ROOT, "cache", "pir_action_cache.json")
try:
    with open(PIR_CACHE_FILE) as f:
        pir_cache = json.load(f)
except FileNotFoundError:
    pir_cache = {}

PIR_HISTORY_FILE = os.path.join(_ROOT, "cache", "pir_history_cache.json")
try:
    with open(PIR_HISTORY_FILE) as f:
        pir_history = json.load(f)
except FileNotFoundError:
    pir_history = {}

# Notes & Context panel removed from the exec slide 2026-07-05 (user request);
# cache/exec_notes.json is no longer read.

WEEK_KEYS = [k for k in sorted(cache.keys()) if not k.startswith("_")][-13:]  # 12 prior + current
today = datetime.now(tz=timezone.utc)
today_str = today.strftime("%-d %B %Y")

def fmt_week_label(iso_date, is_current=False):
    dt = datetime.strptime(iso_date, "%Y-%m-%d")
    label = f"{dt.day} {dt.strftime('%b')}"
    return label + "*" if is_current else label

def fmt_ts(ts):
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return f"{dt.day} {dt.strftime('%b')} {dt.strftime('%H:%M')}"

def fmt_date_dmy(iso_date):
    dt = datetime.strptime(iso_date, "%Y-%m-%d")
    return f"{dt.day} {dt.strftime('%b')}"

current_week = WEEK_KEYS[-1]
prev_week = WEEK_KEYS[-2]
CW = cache[current_week]
PW = cache[prev_week]

# The exec summary / stat cards only ever show fully-completed weeks — never the
# in-progress current week. A week key is its Monday; the week is complete once
# today (UTC) has passed the following Monday. Trends (WEEK_KEYS) still include the
# partial current week, marked with a '*'.
def week_is_complete(iso_monday):
    start = datetime.strptime(iso_monday, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return today >= start + timedelta(days=7)

complete_weeks = [k for k in WEEK_KEYS if week_is_complete(k)]
# Stat cards track the CURRENT (in-progress) week — the nightly run refreshes it
# daily, so cards show live numbers with a "· in progress" marker until the week
# completes. Deltas compare against the previous week. (Changed 2026-07-10; was
# complete_weeks[-1].)
stat_week      = WEEK_KEYS[-1]
stat_prev_week = WEEK_KEYS[-2]

# Week labels
WK = [fmt_week_label(k, k == current_week) for k in WEEK_KEYS]
# WK19 = incident.io era, fixed from 2026-05-04 regardless of cache completeness
WK19_KEYS = [k for k in WEEK_KEYS if k >= "2026-05-04"]
WK19 = [fmt_week_label(k, k == current_week) for k in WK19_KEYS]


def js_arr(vals):
    parts = []
    for v in vals:
        if v is None:
            parts.append("null")
        elif isinstance(v, float):
            parts.append(f"{v:.1f}" if v != int(v) else str(int(v)))
        else:
            parts.append(str(v))
    return "[" + ",".join(parts) + "]"

def js_str_arr(vals):
    return "[" + ",".join(f"'{v}'" for v in vals) + "]"

def get(week, *keys, default=None):
    obj = cache.get(week, {})
    for k in keys:
        if obj is None: return default
        obj = obj.get(k)
    return obj if obj is not None else default

def delta_str(current, prev, unit="", higher_is_better=True, decimals=1):
    if current is None or prev is None:
        return ("d-muted", "—")
    diff = current - prev
    if abs(diff) < 0.05:
        fmt = f"0{unit} vs wk {fmt_date_dmy(stat_prev_week)}"
        return ("d-muted", fmt)
    sign = "+" if diff > 0 else "−"
    abs_diff = abs(diff)
    if decimals == 0:
        fmt_diff = str(int(round(abs_diff)))
    else:
        fmt_diff = f"{abs_diff:.{decimals}f}"
    fmt = f"{sign}{fmt_diff}{unit} vs wk {fmt_date_dmy(stat_prev_week)}"
    good = diff > 0 if higher_is_better else diff < 0
    cls = "d-green" if good else "d-red"
    return (cls, fmt)

def color_pct(pct, green_thresh=90, amber_thresh=75):
    if pct is None: return "c-muted"
    if pct >= green_thresh: return "c-green"
    if pct >= amber_thresh: return "c-amber"
    return "c-red"

def color_csat(score):
    if score is None: return "c-muted"
    if score >= 4.5: return "c-green"
    if score >= 4.0: return "c-amber"
    return "c-red"

# ── SECTION 1 — P1 PERFORMANCE ──────────────────────────────────────────────
# P1 quality arrays
def p1_quality_row(week):
    if "p1_quality_clickhouse" in cache[week]:
        d = cache[week]["p1_quality_clickhouse"]
        true_p1 = d.get("true_p1", 0)
        false_p1 = d.get("false_p1", 0)
        unclassified = 0
        total = true_p1 + false_p1
        fp_rate = round(false_p1 / total * 100, 1) if total > 0 else None
    else:
        d = cache[week].get("p1_quality_incidentio", {})
        true_p1 = d.get("true_p1", 0)
        false_p1 = d.get("false_p1", 0)
        unclassified = d.get("unclassified", 0)
        total = true_p1 + false_p1 + unclassified
        fp_rate = round((false_p1 + unclassified) / total * 100, 1) if total > 0 else None
    return true_p1, false_p1, unclassified, fp_rate

trueP1_arr, falseP1_arr, unclassP_arr, fpRate_arr = [], [], [], []
for wk in WEEK_KEYS:
    t, f, u, fp = p1_quality_row(wk)
    trueP1_arr.append(t); falseP1_arr.append(f); unclassP_arr.append(u); fpRate_arr.append(fp)
unclass_ds = "{label:'Unclassified',data:unclassP,backgroundColor:'#64748b',stack:'q'}," if sum(v or 0 for v in unclassP_arr) > 0 else ""

# P1 FRT SLA arrays
p1Hit_arr  = [get(wk, "p1_frt_sla", "hit", default=0) for wk in WEEK_KEYS]
p1Miss_arr = [get(wk, "p1_frt_sla", "missed", default=0) for wk in WEEK_KEYS]
p1Rate_arr = [get(wk, "p1_frt_sla", "hit_rate") for wk in WEEK_KEYS]

# MTTA — arrays kept although the "MTTA by Severity" chart was dropped
# 2026-07-10 (P1 line null since ~5 Jun, incident.io Accepted-at regression).
# Reinstate the chart from git history once upstream stamping is fixed.
mP1_arr = [get(wk, "mtta", "P1", "median_mtta_min") for wk in WEEK_KEYS]
mP2_arr = [get(wk, "mtta", "P2", "median_mtta_min") for wk in WEEK_KEYS]
mP3_arr = [get(wk, "mtta", "P3", "median_mtta_min") for wk in WEEK_KEYS]

# Brands — always recomputed from per-week p1_brands (cache key _p1_brands_top10 ignored)
_brand_totals = defaultdict(int)
for _wk in WEEK_KEYS:
    for _brand, _cnt in (cache[_wk].get("p1_brands") or {}).items():
        _brand_totals[_brand] += _cnt
_ranked = sorted(_brand_totals.items(), key=lambda x: (-x[1], x[0]))
bL = [b for b, _ in _ranked[:10]]
bC = [c for _, c in _ranked[:10]]

# ── SECTION 2 — PARTNER TICKETS ─────────────────────────────────────────────
p23Hit_arr  = [get(wk, "p2p3_frt_sla", "hit", default=0) for wk in WEEK_KEYS]
p23Miss_arr = [get(wk, "p2p3_frt_sla", "missed", default=0) for wk in WEEK_KEYS]
p23Rate_arr = [get(wk, "p2p3_frt_sla", "hit_rate") for wk in WEEK_KEYS]

cs5_arr  = [get(wk, "csat", "score_dist", "5", default=0) for wk in WEEK_KEYS]
cs4_arr  = [get(wk, "csat", "score_dist", "4", default=0) for wk in WEEK_KEYS]
cs3_arr  = [get(wk, "csat", "score_dist", "3", default=0) for wk in WEEK_KEYS]
cs2_arr  = [get(wk, "csat", "score_dist", "2", default=0) for wk in WEEK_KEYS]
cs1_arr  = [get(wk, "csat", "score_dist", "1", default=0) for wk in WEEK_KEYS]
csA_arr  = [get(wk, "csat", "avg_score") for wk in WEEK_KEYS]

def pt_responded(week):
    pt = cache[week].get("partner_tickets", {})
    return pt.get("p1_responded", 0) + pt.get("p2_responded", 0) + pt.get("p3_responded", 0)

ptP1_arr   = [get(wk, "partner_tickets", "p1_responded", default=0) + get(wk, "partner_tickets", "p1_open", default=0) for wk in WEEK_KEYS]
ptP2_arr   = [get(wk, "partner_tickets", "p2_responded", default=0) + get(wk, "partner_tickets", "p2_open", default=0) for wk in WEEK_KEYS]
ptP3_arr   = [get(wk, "partner_tickets", "p3_responded", default=0) + get(wk, "partner_tickets", "p3_open", default=0) for wk in WEEK_KEYS]
ptMed_arr  = [get(wk, "partner_tickets", "median_response_min") for wk in WEEK_KEYS]
ptAvg_arr  = [get(wk, "partner_tickets", "avg_response_min") for wk in WEEK_KEYS]

# ── SECTION 3 — INCIDENT OPERATIONS ─────────────────────────────────────────
iP1_arr = [get(wk, "incident_volume", "P1", default=0) for wk in WEEK_KEYS]
iP2_arr = [get(wk, "incident_volume", "P2", default=0) for wk in WEEK_KEYS]
iP3_arr = [get(wk, "incident_volume", "P3", default=0) for wk in WEEK_KEYS]
iP4_arr = [get(wk, "incident_volume", "P4", default=0) for wk in WEEK_KEYS]
# Unknown/unsevered = computed remainder (total − P1..P4) so the stack always
# reconciles to the card total — in-flight incidents on the current partial week
# often have no severity assigned yet and appear in total only.
iUnk_arr = [max(0, (get(wk, "incident_volume", "total", default=0) or 0)
                   - (iP1_arr[i] or 0) - (iP2_arr[i] or 0)
                   - (iP3_arr[i] or 0) - (iP4_arr[i] or 0))
            for i, wk in enumerate(WEEK_KEYS)]

def _src(wk, *keys):
    return sum(get(wk, "alert_volume", "by_source", k, default=0) for k in keys)

aDMS_arr  = [_src(wk, "DMS", "Dead Mans Snitch", "Dead Man's Snitch") for wk in WEEK_KEYS]
aSOC_arr  = [_src(wk, "Grafana SOC", "Grafana SOC alerts") for wk in WEEK_KEYS]
aHTTP_arr = [_src(wk, "HTTP", "HTTP alerts") for wk in WEEK_KEYS]
aGraf_arr = [_src(wk, "Grafana", "Grafana alerts") for wk in WEEK_KEYS]
aIcom_arr = [_src(wk, "Intercom") for wk in WEEK_KEYS]
aFTML_arr = [_src(wk, "HTTP DMS FTML", "HTTP DMS FTML Alerts") for wk in WEEK_KEYS]
# "Other" = every incident.io source not broken out above (e.g. Cloudflare Security
# Scanner, Database Security AI Loop) so the stacked bar always reconciles to
# alert_volume.total. Computed as total minus the six named series; only rendered for
# W19+ weeks (the chart slices to WK19), where total is entirely incident.io sources.
aOther_arr = [max(0, get(wk, "alert_volume", "total", default=0)
                  - (aDMS_arr[i] + aSOC_arr[i] + aHTTP_arr[i] + aGraf_arr[i]
                     + aIcom_arr[i] + aFTML_arr[i]))
              for i, wk in enumerate(WEEK_KEYS)]
# PD-era sources (pre-W19)
aPD_SP_arr  = [get(wk, "alert_volume", "by_source", "Service Portal", default=0) for wk in WEEK_KEYS]
aPD_BO_arr  = [get(wk, "alert_volume", "by_source", "Backoffice", default=0) for wk in WEEK_KEYS]

# ── ALERT TIMEBLOCK (W19 onwards) ────────────────────────────────────────────
def tb_get(week, block, key, default=0):
    return (tb_cache.get(week, {}).get("blocks", {}).get(block, {}).get(key) or default)

def tb_week_val(week, key, default=None):
    return tb_cache.get(week, {}).get(key, default)

# INCIDENT counts per 8-hr block (incident_blocks, fetched from incident.io by
# Step 2G since 2026-07-10) — a true workload view that reconciles with
# incident_volume, unlike alert counts where one incident can absorb many
# alerts. The declined/noise angle was dropped the same day: waste%% has been
# flat 5-7%% since early June (reinstate from git history if it regresses).
def tb_inc(week, block):
    return (tb_cache.get(week, {}).get("incident_blocks") or {}).get(block, 0)

tbDay_arr    = [tb_inc(wk, "day")     for wk in WK19_KEYS]
tbEve_arr    = [tb_inc(wk, "evening") for wk in WK19_KEYS]
tbNight_arr  = [tb_inc(wk, "night")   for wk in WK19_KEYS]

# ── STAT CARD CALCULATIONS ───────────────────────────────────────────────────
_stat_week_partial = not week_is_complete(stat_week)
cw_date = fmt_date_dmy(stat_week) + (" · in progress" if _stat_week_partial else "")

# S1 cards
cw_true_p1, cw_false_p1, cw_unclass, cw_fp_rate = p1_quality_row(stat_week)
pw_true_p1, pw_false_p1, pw_unclass, pw_fp_rate   = p1_quality_row(stat_prev_week)

true_p1_delta_cls, true_p1_delta = delta_str(cw_true_p1, pw_true_p1, "", higher_is_better=False, decimals=0)
fp_rate_delta_cls, fp_rate_delta = delta_str(cw_fp_rate, pw_fp_rate, "%", higher_is_better=False)

cw_p1_frt_rate = get(stat_week, "p1_frt_sla", "hit_rate")
pw_p1_frt_rate = get(stat_prev_week, "p1_frt_sla", "hit_rate")
cw_p1_med_frt  = get(stat_week, "p1_frt_sla", "mean_frt_min")
pw_p1_med_frt  = get(stat_prev_week, "p1_frt_sla", "mean_frt_min")

p1_frt_delta_cls, p1_frt_delta = delta_str(cw_p1_frt_rate, pw_p1_frt_rate, "%")
p1_med_delta_cls, p1_med_delta = delta_str(cw_p1_med_frt, pw_p1_med_frt, " min", higher_is_better=False)

cw_p1_mtta     = get(stat_week, "mtta", "P1", "median_mtta_min")
pw_p1_mtta     = get(stat_prev_week, "mtta", "P1", "median_mtta_min")
p1_mtta_delta_cls, p1_mtta_delta = delta_str(cw_p1_mtta, pw_p1_mtta, " min", higher_is_better=False)

# S2 cards
cw_p23_rate = get(stat_week, "p2p3_frt_sla", "hit_rate")
pw_p23_rate = get(stat_prev_week, "p2p3_frt_sla", "hit_rate")
p23_delta_cls, p23_delta = delta_str(cw_p23_rate, pw_p23_rate, "%")

cw_csat_avg = get(stat_week, "csat", "avg_score")
pw_csat_avg = get(stat_prev_week, "csat", "avg_score")
csat_delta_cls, csat_delta = delta_str(cw_csat_avg, pw_csat_avg, "")

cw_pt_resp = pt_responded(stat_week)
pw_pt_resp = pt_responded(stat_prev_week)
cw_pt_p1 = get(stat_week, "partner_tickets", "p1_responded", default=0)
cw_pt_p2 = get(stat_week, "partner_tickets", "p2_responded", default=0)
cw_pt_p3 = get(stat_week, "partner_tickets", "p3_responded", default=0)
pt_delta_cls, pt_delta = delta_str(cw_pt_resp, pw_pt_resp, "", higher_is_better=False, decimals=0)

cw_pt_med = get(stat_week, "partner_tickets", "median_response_min")
pw_pt_med = get(stat_prev_week, "partner_tickets", "median_response_min")
pt_med_delta_cls, pt_med_delta = delta_str(cw_pt_med, pw_pt_med, " min", higher_is_better=False)
if cw_pt_med is None:
    pt_med_cls = "c-muted"
elif cw_pt_med <= 60:
    pt_med_cls = "c-green"
elif cw_pt_med <= 120:
    pt_med_cls = "c-amber"
else:
    pt_med_cls = "c-red"

# S3 cards
cw_inc_total = get(stat_week, "incident_volume", "total", default=0)
pw_inc_total = get(stat_prev_week, "incident_volume", "total", default=0)
cw_inc_p1 = get(stat_week, "incident_volume", "P1", default=0)
cw_inc_p2 = get(stat_week, "incident_volume", "P2", default=0)
cw_inc_p3 = get(stat_week, "incident_volume", "P3", default=0)
cw_inc_p4 = get(stat_week, "incident_volume", "P4", default=0)
cw_inc_unk = max(0, (cw_inc_total or 0) - (cw_inc_p1 or 0) - (cw_inc_p2 or 0)
                    - (cw_inc_p3 or 0) - (cw_inc_p4 or 0))
cw_inc_unk_note = f" &middot; Unclassified: {cw_inc_unk}" if cw_inc_unk else ""
inc_delta_cls, inc_delta = delta_str(cw_inc_total, pw_inc_total, "", higher_is_better=False, decimals=0)

cw_alerts = get(stat_week, "alert_volume", "total", default=0)
pw_alerts = get(stat_prev_week, "alert_volume", "total", default=0)
alerts_delta_cls, alerts_delta = delta_str(cw_alerts, pw_alerts, "", higher_is_better=False, decimals=0)
# Alert colour thresholds keyed to the composite per-source target:
# HTTP <400 + SOC <200 + DMS <150 = 750/wk (untargeted sources ride on top).
if cw_alerts == 0:
    alerts_cls = "c-muted"
elif cw_alerts <= 750:
    alerts_cls = "c-green"
elif cw_alerts <= 1125:
    alerts_cls = "c-amber"
else:
    alerts_cls = "c-red"

# P1 Ack Rate card dropped 2026-07-05: incident.io stopped stamping "Accepted at"
# on IC-Ticket incidents (~3–5 Jun regression), so the rate cannot be computed.
# Reinstate from git history once upstream stamping is fixed.

cw_conv_rate = round(cw_inc_total / cw_alerts * 100, 1) if cw_alerts else None

# Alerts by time block — share of the week's alerts per 8-hr UTC block
# (replaced the Alert→Incident Rate card 2026-07-10). Uses the timeblock
# cache totals (accepted + declined = everything that fired).
def _tb_shares(week):
    blocks = tb_cache.get(week, {}).get("blocks", {})
    counts = {b: (blocks.get(b) or {}).get("total", 0) or 0 for b in ("day", "evening", "night")}
    total = sum(counts.values())
    if not total:
        return None
    return {b: (c, round(c / total * 100)) for b, c in counts.items()}, total

_tb_cw = _tb_shares(stat_week)
_tb_pw = _tb_shares(stat_prev_week)
if _tb_cw:
    _shares, _tb_cw_total = _tb_cw
    _dom_block, (_dom_n, _dom_pct) = max(_shares.items(), key=lambda kv: kv[1][0])
    tb_card_value   = f"{_dom_pct}% {_dom_block.capitalize()}"
    tb_card_subnote = " &middot; ".join(
        f"{b.capitalize()}: {n} ({p}%)" for b, (n, p) in _shares.items()
    ) + f" &middot; {_tb_cw_total} alerts"
else:
    tb_card_value, tb_card_subnote = "—", "no time-block data for this week"
if _tb_pw:
    tb_card_delta = "prev wk: " + " &middot; ".join(
        f"{b.capitalize()} {p}%" for b, (n, p) in _tb_pw[0].items()
    )
else:
    tb_card_delta = ""

# ── BREACH BLOCKS ────────────────────────────────────────────────────────────
week_label_long = (f"Week of {fmt_date_dmy(stat_week)} {datetime.strptime(stat_week, '%Y-%m-%d').year}"
                   + (" (in progress)" if _stat_week_partial else ""))

def render_p1_breach_block(week):
    breaches = cache.get(week, {}).get("p1_frt_breaches", None)
    if breaches is None:
        return f'''    <div class="breach-block">
      <div class="breach-list-title" style="color:#22c55e">SLA Breaches — {week_label_long}</div>
      <div class="breach-clean c-green">No SLA breach data available.</div>
    </div>'''
    if not breaches:
        return f'''    <div class="breach-block">
      <div class="breach-list-title" style="color:#22c55e">SLA Breaches — {week_label_long}</div>
      <div class="breach-clean c-green">No SLA breaches this week.</div>
    </div>'''
    items = []
    for b in breaches:
        ts_html = ""
        opened_ts = b.get("opened_ts")
        real_rt = b.get("sre_real_rt_s")
        if opened_ts:
            opened = fmt_ts(opened_ts)
            first_reply = fmt_ts(opened_ts + real_rt) if real_rt else "—"
            ts_html = f'<span class="breach-ts">Opened {opened} &middot; First reply {first_reply}</span>'
        oh_min = b.get("sre_oh_min", "—")
        items.append(f'''      <div class="breach-item">
        <div class="breach-header">
          <span class="breach-conv-id">#{b["conv_id"]}</span>
          <span class="breach-meta">{b.get("brand","—")} &middot; {b.get("priority","—")}</span>
          <span class="breach-frt">{oh_min} min</span>
          {ts_html}
        </div>
        <div class="breach-summary">{b.get("summary","")}</div>
      </div>''')
    items_html = "\n".join(items)
    return f'''    <div class="breach-block">
      <div class="breach-list-title">SLA Breaches — {week_label_long}</div>
{items_html}
    </div>'''

def render_p23_breach_block(week):
    breaches = cache.get(week, {}).get("p2p3_frt_breaches", None)
    if breaches is None:
        return f'''    <div class="breach-block">
      <div class="breach-list-title" style="color:#22c55e">SLA Breaches — {week_label_long}</div>
      <div class="breach-clean c-green">No SLA breach data available.</div>
    </div>'''
    if not breaches:
        return f'''    <div class="breach-block">
      <div class="breach-list-title" style="color:#22c55e">SLA Breaches — {week_label_long}</div>
      <div class="breach-clean c-green">No SLA breaches this week.</div>
    </div>'''
    items = []
    for b in breaches:
        ts_html = ""
        opened_ts = b.get("opened_ts")
        real_rt = b.get("sre_real_rt_s")
        if opened_ts:
            opened = fmt_ts(opened_ts)
            first_reply = fmt_ts(opened_ts + real_rt) if real_rt else "—"
            ts_html = f'<span class="breach-ts">Opened {opened} &middot; First reply {first_reply}</span>'
        oh_min = b.get("sre_oh_min", round(b.get("oh_frt_s", 0)/60, 1) if b.get("oh_frt_s") else "—")
        brand = b.get("brand") or b.get("company_name") or "—"
        priority = b.get("priority") or b.get("severity") or "—"
        items.append(f'''      <div class="breach-item">
        <div class="breach-header">
          <span class="breach-conv-id">#{b["conv_id"]}</span>
          <span class="breach-meta">{brand} &middot; {priority}</span>
          <span class="breach-frt">{oh_min} min</span>
          {ts_html}
        </div>
        <div class="breach-summary">{b.get("summary","")}</div>
      </div>''')
    items_html = "\n".join(items)
    return f'''    <div class="breach-block">
      <div class="breach-list-title">SLA Breaches — {week_label_long}</div>
{items_html}
    </div>'''

def render_csat_breach_block(week):
    low = cache.get(week, {}).get("csat_low_scores", None)
    if low is None:
        return f'''    <div class="breach-block">
      <div class="breach-list-title" style="color:#22c55e">Low CSAT Scores — {week_label_long}</div>
      <div class="breach-clean c-green">No low CSAT data available.</div>
    </div>'''
    if not low:
        return f'''    <div class="breach-block">
      <div class="breach-list-title" style="color:#22c55e">Low CSAT Scores — {week_label_long}</div>
      <div class="breach-clean c-green">No low CSAT scores this week.</div>
    </div>'''
    items = []
    for b in low:
        brand = b.get("brand") or b.get("company_name") or "—"
        rating = b.get("rating") or b.get("score") or "—"
        priority = b.get("priority", "")
        meta = f"{brand} &middot; {priority}" if priority else brand
        items.append(f'''      <div class="breach-item">
        <div class="breach-header">
          <span class="breach-conv-id">#{b["conv_id"]}</span>
          <span class="breach-meta">{meta}</span>
          <span class="breach-frt">&#9733; {rating}</span>
        </div>
        <div class="breach-summary">{b.get("summary","")}</div>
      </div>''')
    items_html = "\n".join(items)
    return f'''    <div class="breach-block">
      <div class="breach-list-title">Low CSAT Scores — {week_label_long}</div>
{items_html}
    </div>'''

def render_true_p1_detail_block(week):
    incidents = cache.get(week, {}).get("true_p1_incidents", None)
    if not incidents:
        return ""
    items = []
    for inc in incidents:
        status = inc.get("status", "")
        # "Documenting" (post-incident phase) = resolved; impact over, PIR pending
        status_cls = "c-green" if (status or "").lower() in ("closed", "resolved", "postmortem", "documenting") else "c-amber"
        cause = inc.get("cause", "")
        cause_html = f'<span class="breach-meta">{cause}</span>' if cause else ""
        paras = [p.strip() for p in inc.get("summary","").split("\n\n") if p.strip()]
        def fmt_para(p):
            if ":" in p:
                label, _, rest = p.partition(":")
                return f'<p class="p1-detail-para"><strong>{label}:</strong>{rest}</p>'
            return f'<p class="p1-detail-para">{p}</p>'
        summary_html = "".join(fmt_para(p) for p in paras)
        items.append(f'''      <div class="breach-item">
        <div class="breach-header">
          <span class="breach-conv-id">{inc["reference"]}</span>
          <span class="{status_cls}" style="font-size:11px;font-weight:600">{status}</span>
          {cause_html}
        </div>
        <div style="font-size:13px;font-weight:700;color:#e2e8f0;margin:6px 0 4px">{inc["name"]}</div>
        <div class="breach-summary">{summary_html}</div>
      </div>''')
    items_html = "\n".join(items)
    return f'''    <div class="breach-block">
      <div class="breach-list-title">True P1 Incident Details — {week_label_long}</div>
{items_html}
    </div>'''

p1_breach_html  = render_p1_breach_block(stat_week)
p23_breach_html = render_p23_breach_block(stat_week)
csat_breach_html = render_csat_breach_block(stat_week)
true_p1_detail_html = render_true_p1_detail_block(stat_week)

# ── Partner RT callout (weeks where median or avg > 120 min) ─────────────────
def render_pir_team_table(teams):
    if not teams:
        return ""
    def _rate(t):
        total = t["open"] + t["completed"]
        return t["completed"] / total if total > 0 else 0
    rows = []
    for t in sorted(teams, key=_rate):
        name = t["name"]
        op   = t["open"]
        comp = t["completed"]
        total_team = op + comp
        if total_team == 0:
            continue
        rate = round(comp / total_team * 100)
        if rate == 100:
            rows.append(f'''      <tr style="border-bottom:1px solid rgba(255,255,255,0.05);opacity:0.55">
        <td style="padding:5px 12px;color:#e2e8f0;font-size:12px">{name}</td>
        <td style="padding:5px 12px;text-align:right;font-family:'DM Mono',monospace;font-size:12px;color:#64748b">{op}</td>
        <td style="padding:5px 12px;text-align:right;font-family:'DM Mono',monospace;font-size:12px;color:#22c55e">{comp}</td>
        <td style="padding:5px 12px;text-align:right;font-family:'DM Mono',monospace;font-size:12px;color:#22c55e">100% ✓</td>
      </tr>''')
            continue
        rate_cls = "c-green" if rate >= 75 else "c-amber" if rate >= 40 else "c-red"
        open_cls = "c-red" if op >= 20 else "c-amber" if op >= 8 else "c-muted"
        rows.append(f'''      <tr style="border-bottom:1px solid rgba(255,255,255,0.05)">
        <td style="padding:5px 12px;color:#e2e8f0;font-size:12px">{name}</td>
        <td style="padding:5px 12px;text-align:right;font-family:'DM Mono',monospace;font-size:12px" class="{open_cls}">{op}</td>
        <td style="padding:5px 12px;text-align:right;font-family:'DM Mono',monospace;font-size:12px;color:#22c55e">{comp}</td>
        <td style="padding:5px 12px;text-align:right;font-family:'DM Mono',monospace;font-size:12px" class="{rate_cls}">{rate}%</td>
      </tr>''')
    rows_html = "\n".join(rows)
    return f'''    <div style="flex:1;min-height:0;overflow:hidden;background:#0d1629;border:1px solid rgba(255,255,255,0.07);border-radius:8px;margin-top:12px">
      <table style="width:100%;border-collapse:collapse">
        <thead>
          <tr style="border-bottom:1px solid rgba(255,255,255,0.1)">
            <th style="padding:6px 12px;text-align:left;font-size:10px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.06em">Team</th>
            <th style="padding:6px 12px;text-align:right;font-size:10px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.06em">Open</th>
            <th style="padding:6px 12px;text-align:right;font-size:10px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.06em">Done</th>
            <th style="padding:6px 12px;text-align:right;font-size:10px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.06em">Rate</th>
          </tr>
        </thead>
        <tbody>
{rows_html}
        </tbody>
      </table>
    </div>'''

def render_prt_callout():
    flags = []
    for wk in WEEK_KEYS:
        pt = cache[wk].get('partner_tickets', {})
        med = pt.get('median_response_min')
        avg = pt.get('avg_response_min')
        wk_label = fmt_week_label(wk, wk == current_week)
        if med is not None and med > 120:
            flags.append(f"<li><strong>{wk_label}</strong> — median {med:.0f} min</li>")
        elif avg is not None and avg > 120:
            flags.append(f"<li><strong>{wk_label}</strong> — avg {avg:.0f} min (median {med:.0f} min)</li>")
    if not flags:
        return '''    <div class="breach-block">
      <div class="breach-list-title" style="color:#22c55e">Response Time Callouts</div>
      <div class="breach-clean c-green">No weeks above 2-hour threshold.</div>
    </div>'''
    items = "\n".join(flags)
    return f'''    <div class="breach-block">
      <div class="breach-list-title">Response Time Callouts — weeks above 2-hr threshold</div>
      <ul style="font-size:12px;color:#94a3b8;margin:4px 0 0 16px;line-height:1.8">{items}</ul>
    </div>'''

prt_callout_html = render_prt_callout()

# ── P1 quality note ──────────────────────────────────────────────────────────
ch_last = next((k for k in reversed(WEEK_KEYS) if "p1_quality_clickhouse" in cache[k]), None)
io_first = next((k for k in WEEK_KEYS if "p1_quality_incidentio" in cache[k]), None)
if ch_last and io_first:
    ch_last_dt = datetime.strptime(ch_last, "%Y-%m-%d")
    p1q_note = f"PagerDuty data up to {ch_last_dt.strftime('%b %Y')} &middot; incident.io from May 2026"
else:
    p1q_note = "PagerDuty data up to Apr 2026 &middot; incident.io from May 2026"

# Brand chart date range
first_dt = datetime.strptime(WEEK_KEYS[0], "%Y-%m-%d")
last_dt  = datetime.strptime(current_week, "%Y-%m-%d") + timedelta(days=6)
brand_note = f"Source: Intercom &middot; P1 Incident tag &middot; {first_dt.day} {first_dt.strftime('%b')} – {last_dt.day} {last_dt.strftime('%b %Y')} &middot; Top 10 brands"
brand_range_note = f"{first_dt.day} {first_dt.strftime('%b')} – {last_dt.day} {last_dt.strftime('%b %Y')}"

# ── P1 INCIDENT SUMMARIES ─────────────────────────────────────────────────────
_p1_inc_raw = cache.get(stat_week, {}).get("true_p1_incidents") or []

def _fmt_dt_short(iso_str):
    if not iso_str:
        return ""
    try:
        dt = datetime.strptime(iso_str[:19], "%Y-%m-%dT%H:%M:%S")
        return f"{dt.day} {dt.strftime('%b')} · {dt.strftime('%H:%M')} UTC"
    except Exception:
        return iso_str[:10]

def _p1_status_cls(status):
    s = (status or "").lower()
    # "documenting" = post-incident phase: impact resolved, only the PIR is pending → treat as resolved
    return "c-green" if s in ("closed", "resolved", "postmortem", "documenting") else "c-amber"

import re as _re_name
def _clean_inc_name(name):
    return _re_name.sub(r'^\[P\d\] (?:Intercom Incident : )?', '', name or '')

def _exec_status(status):
    s = (status or "").lower()
    if s in ("closed", "resolved", "postmortem", "documenting"):
        return ("Resolved", "#22c55e")
    elif s == "monitoring":
        return ("Monitoring · awaiting fix", "#f59e0b")
    else:
        return ("Active · ongoing", "#ef4444")

def _build_p1_cards(incidents):
    if not incidents:
        return '    <div class="p1-no-data c-muted">No True P1 incidents this week.</div>'
    cards = []
    for inc in incidents:
        status  = inc.get("status", "—")
        sc      = _p1_status_cls(status)
        status_label, _ = _exec_status(status)
        dt_str  = _fmt_dt_short(inc.get("reported_at", ""))
        cause   = inc.get("cause", "")
        ref     = inc.get("reference", "")
        name    = inc.get("name", "")
        name = _clean_inc_name(name)
        summary = inc.get("summary", "")
        href    = inc.get("permalink", "")
        ref_html   = f'<a href="{href}" target="_blank" class="p1-ref">{ref}</a>' if href else f'<span class="p1-ref">{ref}</span>'
        cause_html = f'<span class="p1-cause">{cause}</span>' if cause else ""
        cards.append(f'''    <div class="p1-inc-card">
      <div class="p1-inc-header">
        {ref_html}
        <span class="p1-status-badge {sc}">{status_label}</span>
        <span class="p1-inc-date">{dt_str}</span>
        {cause_html}
      </div>
      <div class="p1-inc-title">{name}</div>
      <div class="p1-inc-overview">{summary}</div>
    </div>''')
    return "\n".join(cards)

p1_cards_html = _build_p1_cards(_p1_inc_raw)
cw_p1_open = sum(1 for inc in _p1_inc_raw if _p1_status_cls(inc.get("status", "")) != "c-green")

def _build_brand_strip(brands, range_note):
    if not brands:
        return ''
    items = []
    for i, (brand, count) in enumerate(brands, 1):
        items.append(f'<span class="brand-pill"><span class="brand-pill-rank">#{i}</span><span class="brand-pill-name">{brand}</span><span class="brand-pill-count">{count}</span></span>')
    return f'  <div class="brand-strip"><span class="brand-strip-label">Top Brands &middot; 12-wk</span>{"".join(items)}<span class="brand-strip-note">{range_note}</span></div>'

brand_strip_html = _build_brand_strip(_ranked[:5], brand_range_note)

# Recurring-cause themes: weeks may carry a "p1_theme" key (written by Step 2E
# when >=2 True P1s share a root cause). Map ref -> theme label so incident
# cards can be tagged, including carry-overs from earlier themed weeks.
_theme_by_ref = {}
for _wk in WEEK_KEYS:
    _th = cache.get(_wk, {}).get("p1_theme") or {}
    # multi-theme weeks carry sub-themes under "themes"; single-theme weeks
    # keep label/incident_refs at the top level
    for _sub in (_th.get("themes") or [_th]):
        for _ref in _sub.get("incident_refs", []):
            _theme_by_ref[_ref] = _sub.get("label", _th.get("label", ""))

def _parse_summary_sections(summary):
    sections = []
    for para in (summary or "").split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if ":" in para:
            label, _, body = para.partition(":")
            sections.append((label.strip(), body.strip()))
        else:
            sections.append(("", para))
    return sections

# ── WK19 first date label ─────────────────────────────────────────────────────
wk19_first_dt = datetime.strptime(WK19_KEYS[0], "%Y-%m-%d") if WK19_KEYS else None
wk19_note = f"incident.io &middot; from W19 ({wk19_first_dt.day} {wk19_first_dt.strftime('%b %Y')})" if wk19_first_dt else "incident.io &middot; from W19"

# ── CSAT avg formatting ──────────────────────────────────────────────────────
def fmt_csat(v):
    return f"{v:.2f}" if v is not None else "—"

def fmt_rate(v, decimals=1):
    if v is None: return "—"
    return f"{v:.{decimals}f}%"

def fmt_min(v):
    if v is None: return "—"
    return f"{v:.1f}"

def fmt_conv_rate(v):
    if v is None: return "—"
    return f"{v:.1f}%"

# ── PIR ACTION ITEMS DATA ────────────────────────────────────────────────────
_pir_gen_raw = pir_cache.get("generated", "—")
try:
    _pir_gen_dt = datetime.strptime(_pir_gen_raw, "%Y-%m-%d")
    pir_generated = f"{_pir_gen_dt.day} {_pir_gen_dt.strftime('%b %Y')}"
except (ValueError, TypeError):
    pir_generated = _pir_gen_raw
pir_open         = pir_cache.get("open", 0)
pir_completed    = pir_cache.get("completed", 0)
pir_total        = pir_cache.get("total", 0)
pir_comp_rate    = pir_cache.get("completion_rate", 0.0)
pir_stale        = pir_cache.get("stale_count", 0)
pir_stale_pct    = pir_cache.get("stale_pct", 0.0)
pir_teams        = pir_cache.get("teams", [])
pir_categories   = pir_cache.get("categories", {})
# Class split (added 2026-07-10): "critical" = items born from Critical Incident /
# P1 postmortems (no "sre incident" tag); "sre_incident" = day-to-day improvement
# suggestions SRE raises to teams. Serve different purposes — visualised apart.
pir_classes      = pir_cache.get("classes") or {}
pir_crit         = pir_classes.get("critical", {})
pir_sre          = pir_classes.get("sre_incident", {})

def _pir_rate_cls(rate):
    return "c-green" if rate >= 85 else "c-amber" if rate >= 65 else "c-red"

pir_comp_cls   = _pir_rate_cls(pir_comp_rate)
pir_stale_cls  = "c-red" if pir_stale_pct >= 50 else "c-amber" if pir_stale_pct >= 25 else "c-green"

pir_cat_labels  = list(pir_categories.keys())
pir_cat_open    = [v.get("open", 0)   if isinstance(v, dict) else v for v in pir_categories.values()]
pir_cat_closed  = [v.get("closed", 0) if isinstance(v, dict) else 0 for v in pir_categories.values()]

# Top 5 pain points — sorted by open count descending
# "SRE Incident" is excluded — it's a class of its own (see the split cards),
# not a Critical-PIR pain-point category. Top 5 selected by open count, then
# displayed by total bar length (open+done) so the stacked bars read ordered.
_pir_cat_sorted = sorted(
    [(k, v.get("open", 0), v.get("closed", 0)) for k, v in pir_categories.items()
     if k != "SRE Incident"],
    key=lambda x: x[1], reverse=True
)[:5]
_pir_cat_sorted.sort(key=lambda x: (x[1] + x[2], x[1]), reverse=True)
pir_top5_labels = [x[0] for x in _pir_cat_sorted]
pir_top5_open   = [x[1] for x in _pir_cat_sorted]
pir_top5_done   = [x[2] for x in _pir_cat_sorted]

pir_teams_chart = sorted([t for t in pir_teams if t.get("open", 0) > 0], key=lambda t: t["open"], reverse=True)
pir_team_labels = [t["name"]      for t in pir_teams_chart]
pir_team_open   = [t["open"]      for t in pir_teams_chart]
pir_team_closed = [t["completed"] for t in pir_teams_chart]
pir_team_table_html = render_pir_team_table(pir_teams)

# PIR stat cards — split by class when the snapshot carries it: Critical
# Incident PIRs (red accent) vs SRE Improvements (cyan accent). Falls back to
# the old global two-card row for snapshots without "classes".
if pir_classes:
    _crit_rate = pir_crit.get("completion_rate", 0.0)
    _sre_rate  = pir_sre.get("completion_rate", 0.0)
    pir_cards_html = f'''  <div class="stat-grid-4">
    <div class="stat-card" style="border-left:3px solid #ef4444">
      <div class="card-label">Open &middot; Critical Incident PIRs</div>
      <div class="card-value c-amber">{pir_crit.get("open", 0)}</div>
      <div class="card-subnote">From Critical Incident &amp; P1 postmortems &middot; {pir_crit.get("total", 0)} tracked</div>
    </div>
    <div class="stat-card" style="border-left:3px solid #ef4444">
      <div class="card-label">Completion &middot; Critical PIRs</div>
      <div class="card-value {_pir_rate_cls(_crit_rate)}">{int(round(_crit_rate))}%</div>
      <div class="card-subnote">{pir_crit.get("completed", 0)} of {pir_crit.get("total", 0)} done &middot; Target: 85%</div>
    </div>
    <div class="stat-card" style="border-left:3px solid #38bdf8">
      <div class="card-label">Open &middot; SRE Improvements</div>
      <div class="card-value c-amber">{pir_sre.get("open", 0)}</div>
      <div class="card-subnote">Day-to-day SRE suggestions to teams &middot; {pir_sre.get("total", 0)} tracked</div>
    </div>
    <div class="stat-card" style="border-left:3px solid #38bdf8">
      <div class="card-label">Completion &middot; SRE Improvements</div>
      <div class="card-value {_pir_rate_cls(_sre_rate)}">{int(round(_sre_rate))}%</div>
      <div class="card-subnote">{pir_sre.get("completed", 0)} of {pir_sre.get("total", 0)} done &middot; Target: 85%</div>
    </div>
  </div>'''
else:
    pir_cards_html = f'''  <div class="stat-grid-2">
    <div class="stat-card">
      <div class="card-label">Open PIR Items</div>
      <div class="card-value c-amber">{pir_open}</div>
      <div class="card-subnote">{pir_total} total tracked</div>
    </div>
    <div class="stat-card">
      <div class="card-label">Completion Rate</div>
      <div class="card-value {pir_comp_cls}">{int(round(pir_comp_rate))}%</div>
      <div class="card-subnote">{pir_completed} of {pir_total} done</div>
      <div class="card-subnote">Target: 85%</div>
    </div>
  </div>'''

# ── PIR HISTORY — write current week snapshot & build chart arrays ────────────
_pir_snap_key = pir_cache.get("generated", current_week)
pir_history[_pir_snap_key] = {
    "open":      pir_open,
    "completed": pir_completed,
    "total":     pir_total,
    "rate":      round(pir_comp_rate, 1),
    **({"crit_rate": pir_crit.get("completion_rate"),
        "sre_rate":  pir_sre.get("completion_rate")} if pir_classes else {}),
}
with open(PIR_HISTORY_FILE, "w") as _f:
    json.dump(dict(sorted(pir_history.items())), _f, indent=2)

# Snapshots are daily now (GitHub Action) — the trend chart is WEEKLY: one
# point per week (the latest snapshot inside that week wins), capped to the
# last 13 weeks to mirror WEEK_KEYS. The current week's point moves daily
# until the week closes, so it carries the usual '*' marker.
_pir_by_week = {}
for _d in sorted(pir_history.keys()):
    _dt  = datetime.strptime(_d, "%Y-%m-%d")
    _mon = (_dt - timedelta(days=_dt.weekday())).strftime("%Y-%m-%d")
    _pir_by_week[_mon] = pir_history[_d]
_pir_hist_keys  = sorted(_pir_by_week.keys())[-13:]
pir_hist_labels = [fmt_week_label(k, k == current_week) for k in _pir_hist_keys]
pir_hist_rate   = [_pir_by_week[k]["rate"] for k in _pir_hist_keys]
# Per-class rates (tracked from 9 Jul 2026) — null before that, so the class
# lines simply start where the data does.
pir_hist_crit   = [_pir_by_week[k].get("crit_rate") for k in _pir_hist_keys]
pir_hist_sre    = [_pir_by_week[k].get("sre_rate")  for k in _pir_hist_keys]

# ── P1 INCIDENT SLIDE GENERATION ─────────────────────────────────────────────
# Two fixed slides: "Current Week" (in-page ‹ › pager, 2 cards per view) and
# "Past Weeks" (scrollable archive of every cached prior-week True P1).
_idx_p1perf   = 1
_idx_p1cur    = 2
_idx_p1past   = 3
_idx_pir      = 4
_idx_partner  = 5
_idx_ops      = 6
_idx_svc      = 7
_idx_eng      = 8
_total_slides = 9

# ── ENGINEER WORKLOAD SLIDE (pre-built string; IC-ticket leads, all teams) ────
def _eng_parse_iso(ts):
    if not ts:
        return None
    try:
        return datetime.strptime(str(ts)[:19], "%Y-%m-%dT%H:%M:%S")
    except Exception:
        return None

def compute_engineer_workload(tickets):
    """Compute per-engineer aggregates from the raw IC-ticket records in cache.
    Raw record: {reference, lead, severity, reported_at, resolved_at|null, closed:bool}."""
    agg = {}
    for t in (tickets or []):
        lead = t.get("lead") or "Unassigned"
        a = agg.setdefault(lead, {"led": 0, "closed": 0, "open": 0, "_mins": []})
        a["led"] += 1
        if t.get("closed"):
            a["closed"] += 1
        else:
            a["open"] += 1
        r = _eng_parse_iso(t.get("reported_at"))
        rs = _eng_parse_iso(t.get("resolved_at"))
        if r and rs and rs >= r:
            a["_mins"].append((rs - r).total_seconds() / 60.0)
    engineers = {}
    for lead, a in agg.items():
        mins = a["_mins"]
        engineers[lead] = {"led": a["led"], "closed": a["closed"], "open": a["open"],
                           "avg_resolve_min": round(sum(mins) / len(mins), 1) if mins else None}
    totals = {"led": sum(e["led"] for e in engineers.values()),
              "closed": sum(e["closed"] for e in engineers.values()),
              "open": sum(e["open"] for e in engineers.values())}
    return engineers, totals

# ── ENGINEER WORKLOAD — multi-week focus view (Giancarlo / Matteo / Simon) ───
ENG_FOCUS  = ["Giancarlo Laferla", "Matteo Rapisarda", "Simon Brown"]
ENG_SHORT  = {"Giancarlo Laferla": "Giancarlo", "Matteo Rapisarda": "Matteo", "Simon Brown": "Simon"}
ENG_COLORS = {"Giancarlo Laferla": "#38bdf8", "Matteo Rapisarda": "#a78bfa", "Simon Brown": "#22c55e"}

# weeks (in WEEK_KEYS order) that actually carry raw engineer_workload tickets
eng_week_keys = [k for k in WEEK_KEYS
                 if (((cache.get(k, {}) or {}).get("engineer_workload") or {}).get("tickets"))]

def eng_assigned_series(week_keys, names):
    """Per-engineer per-week ASSIGNED count (tickets REPORTED that week) + avg resolve.
    Bucketed by reported_at week — the raw tickets already live in their reported week."""
    series = {n: {"assigned": [], "avg_h": []} for n in names}
    for wk in week_keys:
        tickets = ((cache.get(wk, {}) or {}).get("engineer_workload") or {}).get("tickets") or []
        eng, _ = compute_engineer_workload(tickets)
        for n in names:
            e = eng.get(n) or {}
            series[n]["assigned"].append(e.get("led", 0))
            avg = e.get("avg_resolve_min")
            series[n]["avg_h"].append(round(avg / 60.0, 1) if avg is not None else None)
    return series

def eng_closed_by_resolved_week(week_keys, names):
    """Per-engineer count of tickets RESOLVED within each week (bucketed by resolved_at),
    no matter when they were reported. Scans every stored week's tickets (dedup by ref)."""
    wk_index = {wk: i for i, wk in enumerate(week_keys)}
    out = {n: [0] * len(week_keys) for n in names}
    seen = set()
    for wk in WEEK_KEYS:
        tickets = ((cache.get(wk, {}) or {}).get("engineer_workload") or {}).get("tickets") or []
        for t in tickets:
            ref = t.get("reference")
            if ref and ref in seen:
                continue
            if ref:
                seen.add(ref)
            lead = t.get("lead")
            if lead not in out:
                continue
            rs = _eng_parse_iso(t.get("resolved_at"))
            if not rs:
                continue
            mon = (rs - timedelta(days=rs.weekday())).strftime("%Y-%m-%d")
            i = wk_index.get(mon)
            if i is not None:
                out[lead][i] += 1
    return out

def _median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return None
    m = n // 2
    return s[m] if n % 2 else (s[m - 1] + s[m]) / 2.0

# Office-hours window for resolve-time stats: Mon–Fri, 08:00–17:00 (9h/day),
# in MALTA local time (Europe/Malta — CET/CEST, DST handled automatically).
# Cache timestamps are UTC and get converted to Malta local before clipping.
OFFICE_START_H = 8
OFFICE_END_H   = 17
try:
    from zoneinfo import ZoneInfo
    OFFICE_TZ = ZoneInfo("Europe/Malta")
except Exception:                       # no tzdata → fall back to fixed CEST (+2)
    OFFICE_TZ = timezone(timedelta(hours=2))

def business_hours_between(start, end):
    """Hours of overlap between [start, end] and Mon–Fri 08:00–17:00 Malta time.
    Nights & weekends excluded; DST handled via Europe/Malta. start/end naive UTC."""
    if not start or not end or end <= start:
        return 0.0
    start = start.replace(tzinfo=timezone.utc).astimezone(OFFICE_TZ)
    end   = end.replace(tzinfo=timezone.utc).astimezone(OFFICE_TZ)
    total = 0.0
    day = start.date()
    last = end.date()
    while day <= last:
        if day.weekday() < 5:  # Mon–Fri
            day_open  = datetime(day.year, day.month, day.day, OFFICE_START_H, tzinfo=OFFICE_TZ)
            day_close = datetime(day.year, day.month, day.day, OFFICE_END_H, tzinfo=OFFICE_TZ)
            s = max(start, day_open)
            e = min(end, day_close)
            if e > s:
                total += (e - s).total_seconds() / 3600.0
        day += timedelta(days=1)
    return total

def eng_overview_stats(week_keys, names):
    """Two per-engineer stats the weekly bars don't show:
    - median_h: MEDIAN reported→resolved time over resolved tickets in week_keys,
      counted in OFFICE HOURS only (Mon–Fri 08:00–17:00 Malta time — nights/weekends
      excluded). Robust 'typical' working-time close cost; outliers can't skew it.
    - open_n / oldest_d / over7_n: LIVE open-ticket backlog across ALL stored weeks,
      aged from reported_at to now (dedup by reference)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    durs = {n: [] for n in names}
    for wk in week_keys:
        for t in ((cache.get(wk, {}) or {}).get("engineer_workload") or {}).get("tickets") or []:
            lead = t.get("lead")
            if lead not in durs:
                continue
            r = _eng_parse_iso(t.get("reported_at")); rs = _eng_parse_iso(t.get("resolved_at"))
            if r and rs and rs >= r:
                durs[lead].append(business_hours_between(r, rs))
    open_n = {n: 0 for n in names}; oldest_d = {n: None for n in names}; over7_n = {n: 0 for n in names}
    seen = set()
    for wk in WEEK_KEYS:
        for t in ((cache.get(wk, {}) or {}).get("engineer_workload") or {}).get("tickets") or []:
            ref = t.get("reference")
            if ref and ref in seen:
                continue
            if ref:
                seen.add(ref)
            lead = t.get("lead")
            if lead not in open_n or t.get("closed"):
                continue
            r = _eng_parse_iso(t.get("reported_at"))
            if not r:
                continue
            age = (now - r).days
            open_n[lead] += 1
            if oldest_d[lead] is None or age > oldest_d[lead]:
                oldest_d[lead] = age
            if age >= 7:
                over7_n[lead] += 1
    med = {n: (round(_median(durs[n]), 1) if durs[n] else None) for n in names}
    return med, open_n, oldest_d, over7_n

def eng_median_by_week(week_keys, names):
    """Per-engineer per-week MEDIAN office-hours resolve time (hrs) over tickets
    reported that week — the week-by-week version of the card's overall median."""
    out = {n: [] for n in names}
    for wk in week_keys:
        per = {n: [] for n in names}
        for t in ((cache.get(wk, {}) or {}).get("engineer_workload") or {}).get("tickets") or []:
            lead = t.get("lead")
            if lead not in per:
                continue
            r = _eng_parse_iso(t.get("reported_at")); rs = _eng_parse_iso(t.get("resolved_at"))
            if r and rs and rs >= r:
                per[lead].append(business_hours_between(r, rs))
        for n in names:
            m = _median(per[n])
            out[n].append(round(m, 1) if m is not None else None)
    return out

eng_series        = eng_assigned_series(eng_week_keys, ENG_FOCUS)
eng_closed_resolv = eng_closed_by_resolved_week(eng_week_keys, ENG_FOCUS)
eng_median_week   = eng_median_by_week(eng_week_keys, ENG_FOCUS)
eng_median_h, eng_open_n, eng_oldest_d, eng_over7_n = eng_overview_stats(eng_week_keys, ENG_FOCUS)
eng_wk_labels     = [datetime.strptime(k, "%Y-%m-%d").strftime("%-d %b") for k in eng_week_keys]

def render_engineer_workload_slide():
    if not eng_week_keys:
        body = '    <div class="p1-no-data c-muted">No engineer workload data yet.</div>'
        return f'''<!-- ═══ SLIDE — ENGINEER WORKLOAD ═══ -->
<div class="slide" id="sEng"><div class="page">
  <div class="group-label">Engineer Workload</div>
{body}
</div></div>'''

    last = len(eng_week_keys) - 1
    _latest_lbl = eng_wk_labels[last]
    _nwk        = len(eng_week_keys)
    _range_lbl  = f"{eng_wk_labels[0]}&ndash;{eng_wk_labels[last]}" if _nwk > 1 else eng_wk_labels[last]

    cards = []
    for n in ENG_FOCUS:
        assigned = eng_series[n]["assigned"][last]
        closed   = eng_closed_resolv[n][last]
        med      = eng_median_h[n]
        open_n   = eng_open_n[n]; oldest = eng_oldest_d[n]; over7 = eng_over7_n[n]
        net = assigned - closed   # >0 = took in more than closed this week (backlog up)
        if net > 0:
            net_cls = "c-red" if net >= 3 else "c-amber"
            net_txt = f"+{net} backlog"
        elif net < 0:
            net_cls = "c-green"; net_txt = f"{net} cleared"
        else:
            net_cls = "c-muted"; net_txt = "even"
        if med is None:
            med_html = '<span class="c-muted">&mdash;</span>'
        else:
            # office-hours scale: ≤9h ≈ within 1 working day, ≤27h ≈ 3 working days
            mcls = "c-red" if med > 27 else "c-amber" if med > 9 else "c-green"
            med_html = f'<span class="{mcls}">{med:.1f}h</span>'
        if open_n == 0:
            open_html = '<span class="c-muted">0 open</span>'
        else:
            ocls = "c-red" if (oldest or 0) >= 7 else "c-amber" if (oldest or 0) >= 3 else "c-muted"
            extra = f", {over7} &gt;7d" if over7 else ""
            open_html = f'<span class="{ocls}">{open_n} open</span> <span style="color:#64748b">(oldest {oldest}d{extra})</span>'
        cards.append(f'''      <div class="stat-card" style="border-left:3px solid {ENG_COLORS[n]}">
        <div style="display:flex;align-items:center;gap:7px;margin-bottom:6px">
          <span style="width:9px;height:9px;border-radius:50%;background:{ENG_COLORS[n]};display:inline-block"></span>
          <span style="font-size:13px;font-weight:700;color:#e2e8f0">{ENG_SHORT[n]}</span>
        </div>
        <div style="display:flex;align-items:baseline;gap:14px">
          <span><span style="font-family:'DM Mono',monospace;font-size:26px;font-weight:700;color:#e2e8f0">{assigned}</span> <span style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:0.05em">assigned</span></span>
          <span><span style="font-family:'DM Mono',monospace;font-size:26px;font-weight:700;color:#22c55e">{closed}</span> <span style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:0.05em">closed</span></span>
          <span class="{net_cls}" style="font-size:12px">{net_txt}</span>
        </div>
        <div style="font-size:9.5px;color:#475569;text-transform:uppercase;letter-spacing:0.04em;margin-top:2px">Week of {_latest_lbl} &middot; assigned vs closed that week</div>
        <div style="margin-top:8px;font-size:12px">{med_html} <span style="color:#64748b">median resolve (office hours)</span></div>
        <div style="font-size:9.5px;color:#475569;text-transform:uppercase;letter-spacing:0.04em;margin-top:1px">Typical close time &middot; {_nwk}-wk median &middot; {_range_lbl}</div>
        <div style="margin-top:8px;font-size:12px">{open_html}</div>
      </div>''')
    cards_html = "\n".join(cards)

    panels = []
    for i, n in enumerate(ENG_FOCUS):
        panels.append(f'''    <div style="flex:1;min-width:0;display:flex;flex-direction:column;background:#0d1629;border:1px solid rgba(255,255,255,0.07);border-radius:8px;padding:10px 12px">
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;flex-shrink:0">
        <span style="width:8px;height:8px;border-radius:50%;background:{ENG_COLORS[n]};display:inline-block"></span>
        <span style="font-size:12px;font-weight:700;color:#cbd5e1">{ENG_SHORT[n]}</span>
        <span style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:0.05em">&middot; assigned vs closed &middot; <span style="color:#f59e0b">median resolve</span></span>
      </div>
      <div class="chart-container"><canvas id="cEngAC{i}" style="width:100%;height:100%"></canvas></div>
    </div>''')
    panels_html = "\n".join(panels)

    return f'''<!-- ═══ SLIDE — ENGINEER WORKLOAD ═══ -->
<div class="slide" id="sEng"><div class="page">
  <div class="group-label">
    Engineer Workload
    <span style="font-weight:400;text-transform:none;letter-spacing:normal;font-size:11px">&middot; IC Tickets &middot; Giancarlo &middot; Matteo &middot; Simon &middot; widgets = {_latest_lbl}</span>
  </div>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;flex-shrink:0">
{cards_html}
  </div>
  <div style="flex:1;min-height:0;display:flex;gap:12px;margin-top:12px">
{panels_html}
  </div>
  <div style="font-size:11px;color:#475569;margin-top:8px">Source: incident.io IC-Ticket incidents (Intercom partner tickets), by Incident Lead. Bars (left axis): <b>Assigned</b> = reported that week, <b>Closed</b> = resolved that week (any report date) &mdash; when Closed trails Assigned, backlog is growing. <span style="color:#f59e0b"><b>Median resolve</b></span> line (right axis, hrs) = median reported&rarr;resolved per report week, counting only Mon&ndash;Fri 08:00&ndash;17:00 Malta time (nights &amp; weekends excluded); cards show the {len(eng_week_keys)}-wk overall median. <b>Open</b> = tickets still open now, aged from report date. Full all-team roster retained in cache.</div>
</div></div>'''

engineer_workload_slide_html = render_engineer_workload_slide()

# ── ENGINEER WORKLOAD CHART JS (pre-built to avoid f-string brace-escaping) ──
_eng_lbl_js = js_str_arr(eng_wk_labels)
eng_ac_chart_js = ""
if eng_week_keys:
    _parts = []
    for i, n in enumerate(ENG_FOCUS):
        _parts.append(
            "new Chart(document.getElementById('cEngAC" + str(i) + "'),{data:{labels:" + _eng_lbl_js + ",datasets:["
            "{type:'bar',label:'Assigned',data:" + js_arr(eng_series[n]["assigned"]) + ",backgroundColor:'#64748b',barPercentage:0.9,categoryPercentage:0.62,yAxisID:'y'},"
            "{type:'bar',label:'Closed',data:" + js_arr(eng_closed_resolv[n]) + ",backgroundColor:'#22c55e',barPercentage:0.9,categoryPercentage:0.62,yAxisID:'y'},"
            "{type:'line',label:'Median resolve (h)',data:" + js_arr(eng_median_week[n]) + ",borderColor:'#f59e0b',backgroundColor:'transparent',tension:0.3,fill:false,spanGaps:true,pointRadius:3,pointBackgroundColor:'#f59e0b',yAxisID:'medh'}"
            "]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:LG,tooltip:TT},"
            "scales:{x:XA,y:YL(false),"
            "medh:{type:'linear',position:'right',min:0,ticks:{color:'#f59e0b',callback:function(v){return v+'h'}},grid:{display:false}}}}});"
        )
    eng_ac_chart_js = "\n".join(_parts)

def _build_p1_pair_cards(chunk):
    if not chunk:
        return '    <div class="p1-no-data c-muted">No True P1 incidents this week.</div>'
    cards = []
    for inc in chunk:
        status = inc.get("status", "—")
        sc = _p1_status_cls(status)
        status_label, _ = _exec_status(status)
        dt_str = _fmt_dt_short(inc.get("reported_at", ""))
        ref = inc.get("reference", "")
        name = inc.get("name", "")
        name = _clean_inc_name(name)
        href = inc.get("permalink", "")
        ref_html = f'<a href="{href}" target="_blank" class="p1-ref">{ref}</a>' if href else f'<span class="p1-ref">{ref}</span>'
        carry_html = ('<span class="p1-carry-badge">Carry-over</span>'
                      if inc.get("_carryover") else "")
        theme_lbl = _theme_by_ref.get(ref)
        theme_html = (f'<span class="p1-theme-badge">Recurring cause: {theme_lbl}</span>'
                      if theme_lbl else "")
        sections = _parse_summary_sections(inc.get("summary", ""))
        sections_html = ""
        for lbl, body in sections:
            if lbl:
                sections_html += f'      <div class="p1-section"><div class="p1-section-label">{lbl}</div><div class="p1-section-body">{body}</div></div>\n'
            else:
                sections_html += f'      <div class="p1-section"><div class="p1-section-body">{body}</div></div>\n'
        cards.append(f'''    <div class="p1-full-card">
      <div class="p1-inc-header">
        {ref_html}
        <span class="p1-status-badge {sc}">{status_label}</span>
        {carry_html}{theme_html}
        <span class="p1-inc-date">{dt_str}</span>
      </div>
      <div class="p1-inc-title">{name}</div>
      <div class="p1-sections">
{sections_html}      </div>
    </div>''')
    return "\n".join(cards)

p1_tab_btns_html = (
    f'    <button class="slide-tab" onclick="showSlide({_idx_p1cur})">P1 Incidents · Current Week</button>\n'
    f'    <button class="slide-tab" onclick="showSlide({_idx_p1past})">P1 Incidents · Past Weeks</button>\n'
)

_nav_btn_style = ("width:24px;height:22px;display:flex;align-items:center;justify-content:center;"
                  "background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.14);"
                  "border-radius:4px;color:#e2e8f0;font-size:14px;cursor:pointer;padding:0")

# ── Slide: P1 Incidents · Current Week (in-page pager, 2 cards per view) ─────
_cw_p1_incs  = cache.get(stat_week, {}).get("true_p1_incidents") or []
_cw_p1_pages = [_cw_p1_incs[i:i+2] for i in range(0, len(_cw_p1_incs), 2)] or [[]]
_p1cw_pages_html = ""
for _pi, _pg in enumerate(_cw_p1_pages):
    _chars = sum(len(inc.get("summary", "")) for inc in _pg)
    _fs    = 13 if _chars > 2000 else (14 if _chars > 1400 else 15)
    _disp  = "flex" if _pi == 0 else "none"
    _p1cw_pages_html += (
        f'  <div class="p1-two-up p1cw-page" style="font-size:{_fs}px;display:{_disp}">\n'
        + _build_p1_pair_cards(_pg) + '\n  </div>\n'
    )
_p1cw_nav_html = ""
if len(_cw_p1_pages) > 1:
    _p1cw_nav_html = (
        f'    <div style="margin-left:auto;display:flex;align-items:center;gap:6px">\n'
        f'      <button type="button" id="p1cwPrev" onclick="p1cwNav(-1)" title="Previous incidents" style="{_nav_btn_style}">&#8249;</button>\n'
        f'      <span id="p1cwPos" style="font-size:11px;color:#64748b;font-family:\'DM Mono\',monospace;white-space:nowrap"></span>\n'
        f'      <button type="button" id="p1cwNext" onclick="p1cwNav(1)" title="Next incidents" style="{_nav_btn_style}">&#8250;</button>\n'
        f'    </div>\n'
    )
_p1cw_n = len(_cw_p1_incs)
p1_all_slides_html = f'''
<!-- ═══ P1 INCIDENTS · CURRENT WEEK ════════════════════════════ -->
<div class="slide" id="sP1cur"><div class="page">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;flex-shrink:0">
    <div class="group-label" style="margin-bottom:0">P1 Incidents · Current Week · {cw_date} · {_p1cw_n} incident{"s" if _p1cw_n != 1 else ""}</div>
{_p1cw_nav_html}  </div>
{_p1cw_pages_html}</div></div>
'''

# ── Slide: P1 Incidents · Past Weeks (per-week slider, like the exec nav) ────
# One view per cached prior week, deduped by reference (newest occurrence wins;
# refs already shown on the Current Week slide are skipped). ‹ › header buttons
# flip between weeks, most recent past week shown by default.
_seen_p1_refs = {inc.get("reference", "") for inc in _cw_p1_incs}
_p1pw_views = []  # (range_str, count, open_n, cards_html) — collected newest first for dedupe
for _wk in reversed([w for w in WEEK_KEYS if w != stat_week]):
    _wk_incs = [inc for inc in (cache.get(_wk, {}).get("true_p1_incidents") or [])
                if inc.get("reference", "") not in _seen_p1_refs]
    if not _wk_incs:
        continue
    _seen_p1_refs.update(inc.get("reference", "") for inc in _wk_incs)
    _wk_end = fmt_date_dmy((datetime.strptime(_wk, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d"))
    _open_n = sum(1 for inc in _wk_incs if _p1_status_cls(inc.get("status", "")) != "c-green")
    _p1pw_views.append((f"{fmt_date_dmy(_wk)} – {_wk_end}", len(_wk_incs), _open_n,
                        _build_p1_pair_cards(_wk_incs)))
_p1pw_views.reverse()  # oldest → newest, so the default index (last) is the most recent

_p1pw_divs = ""
for _vi, (_rng, _n, _open_n, _cards) in enumerate(_p1pw_views):
    _disp = "flex" if _vi == len(_p1pw_views) - 1 else "none"
    _p1pw_divs += (
        f'  <div class="p1pw-week" data-range="{_rng}" data-count="{_n}" data-open="{_open_n}" '
        f'style="display:{_disp};flex-direction:column;flex:1;min-height:0">\n'
        f'    <div style="flex:1;min-height:0;overflow-y:auto;font-size:13px;padding-right:6px">\n'
        f'      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">\n'
        + _cards + '\n      </div>\n    </div>\n  </div>\n'
    )
if not _p1pw_divs:
    _p1pw_divs = '  <div class="p1-no-data c-muted">No prior-week True P1 incidents in the cache window.</div>\n'

_p1pw_nav_html = ""
if len(_p1pw_views) > 1:
    _p1pw_nav_html = (
        f'    <div style="margin-left:auto;display:flex;align-items:center;gap:6px">\n'
        f'      <button type="button" id="p1pwPrev" onclick="p1pwNav(-1)" title="Older week" style="{_nav_btn_style}">&#8249;</button>\n'
        f'      <span id="p1pwPos" style="font-size:11px;color:#64748b;font-family:\'DM Mono\',monospace;white-space:nowrap"></span>\n'
        f'      <button type="button" id="p1pwNext" onclick="p1pwNav(1)" title="Newer week" style="{_nav_btn_style}">&#8250;</button>\n'
        f'    </div>\n'
    )

p1_all_slides_html += f'''
<!-- ═══ P1 INCIDENTS · PAST WEEKS ══════════════════════════════ -->
<div class="slide" id="sP1past"><div class="page">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;flex-shrink:0">
    <div class="group-label" style="margin-bottom:0">P1 Incidents · Past Weeks · <span id="p1pwRange"></span></div>
    <span id="p1pwMeta" style="font-size:11px;color:#64748b;white-space:nowrap"></span>
{_p1pw_nav_html}  </div>
{_p1pw_divs}  <div style="font-size:11px;color:#475569;padding-top:6px;flex-shrink:0">Incident-level detail is cached from 25 May 2026; earlier weeks appear in the P1 Quality trend only.</div>
</div></div>
<script>
(function(){{
  var pages = document.querySelectorAll('#sP1cur .p1cw-page');
  if (!pages.length) return;
  var idx = 0;
  function render(){{
    for (var i = 0; i < pages.length; i++) pages[i].style.display = (i === idx ? 'flex' : 'none');
    var pos = document.getElementById('p1cwPos');
    if (pos) pos.textContent = (idx + 1) + ' / ' + pages.length;
    var p = document.getElementById('p1cwPrev'), n = document.getElementById('p1cwNext');
    if (p) {{ p.disabled = (idx === 0);                p.style.opacity = (idx === 0 ? 0.35 : 1); }}
    if (n) {{ n.disabled = (idx === pages.length - 1); n.style.opacity = (idx === pages.length - 1 ? 0.35 : 1); }}
  }}
  window.p1cwNav = function(d){{ idx = Math.max(0, Math.min(pages.length - 1, idx + d)); render(); }};
  render();
}})();
(function(){{
  var weeks = document.querySelectorAll('#sP1past .p1pw-week');
  if (!weeks.length) return;
  var idx = weeks.length - 1;
  function render(){{
    for (var i = 0; i < weeks.length; i++) weeks[i].style.display = (i === idx ? 'flex' : 'none');
    var w = weeks[idx];
    document.getElementById('p1pwRange').textContent = w.getAttribute('data-range');
    var open = parseInt(w.getAttribute('data-open') || '0', 10);
    var meta = w.getAttribute('data-count') + ' True P1' + (w.getAttribute('data-count') === '1' ? '' : 's');
    document.getElementById('p1pwMeta').innerHTML = meta +
      (open ? ' &middot; <span style="color:#f59e0b">' + open + ' still open</span>' : '');
    var pos = document.getElementById('p1pwPos');
    if (pos) pos.textContent = (idx + 1) + ' / ' + weeks.length;
    var p = document.getElementById('p1pwPrev'), n = document.getElementById('p1pwNext');
    if (p) {{ p.disabled = (idx === 0);                p.style.opacity = (idx === 0 ? 0.35 : 1); }}
    if (n) {{ n.disabled = (idx === weeks.length - 1); n.style.opacity = (idx === weeks.length - 1 ? 0.35 : 1); }}
  }}
  window.p1pwNav = function(d){{ idx = Math.max(0, Math.min(weeks.length - 1, idx + d)); render(); }};
  render();
}})();
</script>
'''

# ── EXECUTIVE SUMMARY SLIDE (pre-built to avoid f-string brace-escaping) ─────
# Exec slide always reports on the last complete week (prev_week), not the partial current week
# ═══ EXECUTIVE SUMMARY — one pre-rendered view per complete week ═════════════
# The exec slide is navigable: ‹ › header buttons flip between per-week views,
# newest shown by default. Averages / trend arrows are computed as-of each week
# (trailing window up to and including it). The PIR chip and the PIR narrative
# line read the CURRENT ClickUp snapshot (not week-keyed), so they render only
# on the latest view. Incident statuses shown are as cached today, not as they
# stood during that week.
import math as _math
import re as _re

def _first_sentence(txt):
    m = _re.search(r'[.!?]', txt)
    return txt[:m.end()].strip() if m else txt.strip()

def _exec_chip(label, value, context, val_color="#e2e8f0", bg="rgba(255,255,255,0.04)",
               bdr="rgba(255,255,255,0.09)", ctx_color="#64748b"):
    return (
        f'<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;'
        f'background:{bg};border:1px solid {bdr};border-radius:6px;padding:7px 12px">'
        f'<span style="font-size:12px;color:#64748b;font-weight:600;text-transform:uppercase;'
        f'letter-spacing:0.06em;white-space:nowrap">{label}</span>'
        f'<span style="font-family:\'DM Mono\',monospace;font-size:18px;font-weight:600;'
        f'color:{val_color};white-space:nowrap">{value}</span>'
        f'<span style="font-size:12px;color:{ctx_color};white-space:nowrap">{context}</span>'
        f'</div>'
    )

def _build_exec_week_view(_ew, _wk_i, _is_latest):
    """Return (range_str, inner_html) for the exec-summary view of week _ew
    (index _wk_i in WEEK_KEYS)."""
    _ew_true_p1 = p1_quality_row(_ew)[0]
    _ew_p1_frt  = get(_ew, "p1_frt_sla", "hit_rate")
    _ew_csat    = get(_ew, "csat", "avg_score")
    _ew_p23     = get(_ew, "p2p3_frt_sla", "hit_rate")
    _ew_p1_incs = cache.get(_ew, {}).get("true_p1_incidents") or []
    _ew_theme   = cache.get(_ew, {}).get("p1_theme") or None
    _ew_date    = fmt_date_dmy(_ew)
    _ew_end     = fmt_date_dmy((datetime.strptime(_ew, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d"))
    _ew_range   = f"{_ew_date} – {_ew_end}"

    # As-of averages: complete weeks up to and including this one
    _p1_hist_vals = [v for v in (p1_quality_row(w)[0] for w in WEEK_KEYS[:_wk_i + 1]) if v is not None]
    _p1_4wk_avg   = round(sum(_p1_hist_vals) / len(_p1_hist_vals), 1) if _p1_hist_vals else None
    _p1_12wk_n    = len(_p1_hist_vals)
    _frt_prior   = [v for v in p1Rate_arr[:_wk_i + 1]  if v is not None]
    _csat_prior  = [v for v in csA_arr[:_wk_i + 1]     if v is not None]
    _p23_prior   = [v for v in p23Rate_arr[:_wk_i + 1] if v is not None]
    _exec_frt_avg  = round(sum(_frt_prior)  / len(_frt_prior))     if _frt_prior  else None
    _exec_csat_avg = round(sum(_csat_prior) / len(_csat_prior), 2) if _csat_prior else None
    _exec_p23_avg  = round(sum(_p23_prior)  / len(_p23_prior))     if _p23_prior  else None
    _exec_p1_avg   = round(sum(_p1_hist_vals) / len(_p1_hist_vals)) if _p1_hist_vals else None

    # Story narrative — incident quality headline + PIR concern (latest view only)
    _avg = _math.ceil(_p1_4wk_avg) if _p1_4wk_avg is not None else None
    _active_n = sum(1 for inc in _ew_p1_incs
                    if inc.get("status", "").lower() not in ("closed", "resolved", "postmortem"))
    if _ew_true_p1 == 0:
        _exec_line1 = "No True P1 incidents this week — all response and quality metrics are on target."
    elif _avg is not None and _ew_true_p1 <= _avg:
        _mon = (f" {_active_n} incident{'s' if _active_n != 1 else ''} still in Monitoring, awaiting resolution."
                if _active_n else "")
        _exec_line1 = (f"Incident handling is in good shape — response times, SLAs, and CSAT are all on target "
                       f"and trending in the right direction. P1 count is consistent with the {_p1_12wk_n}-week average.{_mon}")
    else:
        _parts = []
        if _avg is not None and _ew_true_p1 > _avg:
            _parts.append(f"{_ew_true_p1} True P1s vs {_avg}/wk {_p1_12wk_n}-week average")
        if _ew_p1_frt is not None and _ew_p1_frt < 0.90:
            _parts.append(f"P1 FRT SLA {fmt_rate(_ew_p1_frt, 0)}")
        if _ew_csat is not None and _ew_csat < 4.5:
            _parts.append(f"CSAT {fmt_csat(_ew_csat)}")
        _mon = (f" {_active_n} incident{'s' if _active_n != 1 else ''} still open." if _active_n else "")
        _exec_line1 = (f"Elevated week — {'; '.join(_parts)}.{_mon}" if _parts
                       else f"Elevated week — {_ew_true_p1} True P1s this week.{_mon}")
    _exec_line2 = ""
    if _is_latest and pir_comp_rate < 85:
        _pct = int(round(pir_comp_rate))
        _worst = sorted([t for t in pir_teams if t.get("open", 0) > 0],
                        key=lambda t: t.get("open", 0), reverse=True)
        if len(_worst) >= 2:
            _exec_line2 = (f"The key concern remains PIR action completion — at {_pct}% against a target of 85%, "
                           f"this is a persistent gap. {_worst[0]['name']} ({_worst[0]['open']} open) and "
                           f"{_worst[1]['name']} ({_worst[1]['open']} open) are the largest contributors and need attention.")
        elif len(_worst) == 1:
            _exec_line2 = (f"The key concern remains PIR action completion — at {_pct}% against a target of 85%. "
                           f"{_worst[0]['name']} ({_worst[0]['open']} open) is the largest contributor.")
        else:
            _exec_line2 = f"PIR action completion is at {_pct}% vs 85% target — needs attention."

    # P1 incidents compact list — one header row + one detail line per incident
    _inc_detail_sz = "11px" if len(_ew_p1_incs) >= 3 else "12px"
    _exec_inc_rows = ""
    if _ew_p1_incs:
        for _inc in _ew_p1_incs:
            _ref  = _inc.get("reference", "")
            _nm   = _inc.get("name", "")
            _nm = _clean_inc_name(_nm)
            _st_raw = _inc.get("status", "—")
            _st_label, _st_col = _exec_status(_st_raw)
            _dt   = _fmt_dt_short(_inc.get("reported_at", ""))
            _href = _inc.get("permalink", "")
            _rh   = (f'<a href="{_href}" target="_blank" style="font-family:DM Mono,monospace;font-size:12px;color:#38bdf8;text-decoration:none;font-weight:500;white-space:nowrap;flex-shrink:0">{_ref}</a>'
                     if _href else f'<span style="font-family:DM Mono,monospace;font-size:12px;color:#38bdf8;font-weight:500;white-space:nowrap;flex-shrink:0">{_ref}</span>')
            _secs     = {lbl: body for lbl, body in _parse_summary_sections(_inc.get("summary", ""))}
            _s_prob   = _first_sentence(_secs.get("Problem", ""))
            _s_impact = _first_sentence(_secs.get("Impact", ""))
            _s_action = _first_sentence(_secs.get("Actions Taken", _secs.get("Steps to resolve", _secs.get("Action / Next steps", _secs.get("Next steps", "")))))
            # 2-3 sentences: Problem + Impact + Actions Taken
            _sentences = [s for s in [_s_prob, _s_impact, _s_action] if s][:3]
            _detail = " ".join(_sentences)
            _exec_inc_rows += (
                f'<div style="padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.05)">'
                # Row 1: ref · title · status · date
                f'<div style="display:flex;align-items:center;gap:8px;min-width:0">'
                f'{_rh}'
                f'<span style="flex:1;font-size:13px;color:#e2e8f0;font-weight:600;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;min-width:0">{_nm}</span>'
                f'<span style="font-size:11px;font-weight:700;padding:2px 7px;border-radius:3px;background:rgba(255,255,255,0.05);color:{_st_col};white-space:nowrap;flex-shrink:0">{_st_label}</span>'
                f'<span style="font-size:11px;color:#475569;white-space:nowrap;flex-shrink:0">{_dt}</span>'
                f'</div>'
                # Row 2: 2-sentence summary — Impact + Actions Taken
                + (f'<div style="font-size:{_inc_detail_sz};color:#94a3b8;line-height:1.4;margin-top:3px">{_detail}</div>' if _detail else '')
                + f'</div>'
            )
    elif _ew_true_p1:
        _exec_inc_rows = (f'<div style="font-size:12px;color:#64748b;padding:10px 0">'
                          f'{_ew_true_p1} True P1{"s" if _ew_true_p1 != 1 else ""} recorded, but incident-level '
                          f'detail is not cached for this week (kept from 25 May 2026 onward).</div>')
    else:
        _exec_inc_rows = '<div style="font-size:13px;color:#22c55e;padding:10px 0">No True P1 incidents this week.</div>'

    # Overall RAG status
    # CRITICAL   = P1s still actively impacting users (not in Monitoring/Resolved)
    # MONITORING = P1 count significantly above the rolling average
    # STABLE     = P1s on trend, all in Monitoring or Resolved
    # ON TRACK   = no P1s at all this week
    _has_truly_active_p1 = any(
        inc.get("status", "").lower() not in ("closed", "resolved", "postmortem", "monitoring", "documenting")
        for inc in _ew_p1_incs
    )
    _p1_above_avg = (
        (_exec_p1_avg is not None and _ew_true_p1 > _exec_p1_avg + 2)
        or _ew_true_p1 >= 5
    )
    if _has_truly_active_p1:
        _rag_label = "CRITICAL"
        _rag_hex   = "#ef4444"
        _rag_bg    = "rgba(239,68,68,0.08)"
        _rag_bdr   = "rgba(239,68,68,0.25)"
    elif _p1_above_avg:
        _rag_label = "MONITORING"
        _rag_hex   = "#f59e0b"
        _rag_bg    = "rgba(245,158,11,0.08)"
        _rag_bdr   = "rgba(245,158,11,0.25)"
    elif _ew_true_p1 == 0:
        _rag_label = "ON TRACK"
        _rag_hex   = "#22c55e"
        _rag_bg    = "rgba(34,197,94,0.06)"
        _rag_bdr   = "rgba(34,197,94,0.20)"
    else:
        _rag_label = "STABLE"
        _rag_hex   = "#22c55e"
        _rag_bg    = "rgba(34,197,94,0.06)"
        _rag_bdr   = "rgba(34,197,94,0.20)"

    # Exec metric chips — 3-col grid in status banner
    _exec_chips = []
    # True P1s
    if _exec_p1_avg is not None:
        _p1_arrow = "↓" if _ew_true_p1 < _exec_p1_avg else ("↑" if _ew_true_p1 > _exec_p1_avg else "↔")
        _p1_ctx   = f'{_p1_12wk_n}w avg {_exec_p1_avg} {_p1_arrow}'
    else:
        _p1_ctx = '—'
    _exec_chips.append(_exec_chip("True P1s", str(_ew_true_p1), _p1_ctx))
    # P1 FRT SLA
    if _ew_p1_frt is not None:
        _frt_val   = fmt_rate(_ew_p1_frt, 0)
        _frt_color = "#22c55e" if _ew_p1_frt >= 0.90 else ("#f59e0b" if _ew_p1_frt >= 0.75 else "#ef4444")
        _frt_bg    = ("rgba(34,197,94,0.07)"  if _ew_p1_frt >= 0.90 else
                      "rgba(245,158,11,0.07)" if _ew_p1_frt >= 0.75 else "rgba(239,68,68,0.07)")
        _frt_bdr   = ("rgba(34,197,94,0.20)"  if _ew_p1_frt >= 0.90 else
                      "rgba(245,158,11,0.25)" if _ew_p1_frt >= 0.75 else "rgba(239,68,68,0.25)")
        _frt_arrow = ("↑" if _ew_p1_frt * 100 > (_exec_frt_avg or 0)
                      else "↓" if _ew_p1_frt * 100 < (_exec_frt_avg or 100) else "→")
        _frt_ctx   = f'{_p1_12wk_n}w avg {_exec_frt_avg}% {_frt_arrow}' if _exec_frt_avg is not None else '—'
        _exec_chips.append(_exec_chip("P1 FRT SLA", _frt_val, _frt_ctx, _frt_color, _frt_bg, _frt_bdr))
    # CSAT
    if _ew_csat is not None:
        _cs_val   = fmt_csat(_ew_csat)
        _cs_color = "#22c55e" if _ew_csat >= 4.5 else ("#f59e0b" if _ew_csat >= 4.0 else "#ef4444")
        _cs_bg    = ("rgba(34,197,94,0.07)"  if _ew_csat >= 4.5 else
                     "rgba(245,158,11,0.07)" if _ew_csat >= 4.0 else "rgba(239,68,68,0.07)")
        _cs_bdr   = ("rgba(34,197,94,0.20)"  if _ew_csat >= 4.5 else
                     "rgba(245,158,11,0.25)" if _ew_csat >= 4.0 else "rgba(239,68,68,0.25)")
        _cs_arrow = ("↑" if _ew_csat > (_exec_csat_avg or 0)
                     else "↓" if _ew_csat < (_exec_csat_avg or 5) else "→")
        _cs_ctx   = f'{_p1_12wk_n}w avg {_exec_csat_avg} {_cs_arrow}' if _exec_csat_avg is not None else '—'
        _exec_chips.append(_exec_chip("CSAT", _cs_val, _cs_ctx, _cs_color, _cs_bg, _cs_bdr))
    # Partner FRT SLA (P2/P3)
    if _ew_p23 is not None:
        _p23_val   = fmt_rate(_ew_p23, 0)
        _p23_color = "#22c55e" if _ew_p23 >= 0.90 else ("#f59e0b" if _ew_p23 >= 0.75 else "#ef4444")
        _p23_bg    = ("rgba(34,197,94,0.07)"  if _ew_p23 >= 0.90 else
                      "rgba(245,158,11,0.07)" if _ew_p23 >= 0.75 else "rgba(239,68,68,0.07)")
        _p23_bdr   = ("rgba(34,197,94,0.20)"  if _ew_p23 >= 0.90 else
                      "rgba(245,158,11,0.25)" if _ew_p23 >= 0.75 else "rgba(239,68,68,0.25)")
        _p23_arrow = ("↑" if _ew_p23 * 100 > (_exec_p23_avg or 0)
                      else "↓" if _ew_p23 * 100 < (_exec_p23_avg or 100) else "→")
        _p23_ctx   = f'{_p1_12wk_n}w avg {_exec_p23_avg}% {_p23_arrow}' if _exec_p23_avg is not None else '—'
        _exec_chips.append(_exec_chip("Partner FRT SLA", _p23_val, _p23_ctx, _p23_color, _p23_bg, _p23_bdr))
    # PIR Completion — the latest view reads the live snapshot; historical views
    # read the closest pir_history snapshot dated on/before that week's Sunday
    # (snapshots exist from 25 May 2026; older weeks simply omit the chip).
    _pir_rate = None
    if _is_latest:
        _pir_rate    = pir_comp_rate
        _pir_ctx_txt = "target 85% ⚠" if pir_comp_rate < 85 else "target 85% ✓"
        _pir_ctx_col = "#f59e0b"       if pir_comp_rate < 85 else "#22c55e"
    else:
        _week_end_iso = (datetime.strptime(_ew, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d")
        _snaps = [d for d in pir_history if d <= _week_end_iso]
        if _snaps:
            _snap_d      = max(_snaps)
            _pir_rate    = pir_history[_snap_d]["rate"]
            _pir_ctx_txt = f"as of {fmt_date_dmy(_snap_d)}"
            _pir_ctx_col = "#64748b"
    if _pir_rate is not None:
        _pir_chip_color = "#22c55e" if _pir_rate >= 85 else ("#f59e0b" if _pir_rate >= 65 else "#ef4444")
        _pir_chip_bg    = ("rgba(34,197,94,0.07)"  if _pir_rate >= 85 else
                           "rgba(245,158,11,0.07)" if _pir_rate >= 65 else "rgba(239,68,68,0.07)")
        _pir_chip_bdr   = ("rgba(34,197,94,0.20)"  if _pir_rate >= 85 else
                           "rgba(245,158,11,0.25)" if _pir_rate >= 65 else "rgba(239,68,68,0.25)")
        _exec_chips.append(_exec_chip("PIR Completion", fmt_rate(_pir_rate, 0), _pir_ctx_txt,
                                       _pir_chip_color, _pir_chip_bg, _pir_chip_bdr, _pir_ctx_col))

    _exec_chip_grid_html = (
        '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;'
        'padding-top:6px;border-top:1px solid rgba(255,255,255,0.05)">'
        + ''.join(_exec_chips)
        + '</div>'
    )

    # ── Theme of the week — standalone widget below the status banner ────────
    # Rendered only when the week carries a p1_theme (>=2 True P1s sharing a
    # root cause). Incident refs link to incident.io where a permalink is known.
    _theme_widget_html = ""
    if _ew_theme and _ew_theme.get("summary"):
        _theme_permalinks = {inc.get("reference", ""): inc.get("permalink", "") for inc in _ew_p1_incs}
        _chip_style = ("font-family:'DM Mono',monospace;font-size:10px;font-weight:500;color:#c4b5fd;"
                       "background:rgba(167,139,250,0.12);border:1px solid rgba(167,139,250,0.28);"
                       "border-radius:4px;padding:1px 6px;text-decoration:none;white-space:nowrap")

        def _theme_chips(refs):
            chips = ""
            for _ref in refs:
                _href = _theme_permalinks.get(_ref, "")
                chips += (f'<a href="{_href}" target="_blank" style="{_chip_style}">{_ref}</a>'
                          if _href else f'<span style="{_chip_style}">{_ref}</span>')
            return chips

        _sub_themes = _ew_theme.get("themes") or []
        if _sub_themes:
            # Multi-theme week: header + one single-line row per failure mode.
            # Summaries are ellipsis-clipped to guarantee one line; the full
            # detail is exposed as a hover tooltip.
            _STATUS_COLS = {"FIXED": "#22c55e", "MITIGATED": "#f59e0b"}
            _theme_rows = ""
            for _sub in _sub_themes:
                _st      = _sub.get("status", "")
                _st_col  = _STATUS_COLS.get(_st, "#94a3b8")
                _st_note = _sub.get("status_note", "")
                _st_tip  = f' title="{_st_note}"' if _st_note else ''
                _st_html = (f'<span style="width:76px;flex-shrink:0;text-align:right;font-size:10px;'
                            f'font-weight:700;color:{_st_col};white-space:nowrap"{_st_tip}>{_st}'
                            + ('<span style="color:#f59e0b">*</span>' if _st_note and _st == "FIXED" else '')
                            + '</span>')
                _tip = (_sub.get("detail") or _sub.get("summary", "")).replace('"', '&quot;')
                _theme_rows += (
                    f'    <div style="display:flex;align-items:center;gap:12px;padding:5px 0;'
                    f'border-top:1px solid rgba(167,139,250,0.12)">\n'
                    f'      <span style="font-family:\'DM Mono\',monospace;font-size:12px;font-weight:600;'
                    f'color:#c4b5fd;white-space:nowrap;flex-shrink:0;width:158px;overflow:hidden;'
                    f'text-overflow:ellipsis">{_sub.get("label", "")}</span>\n'
                    f'      <span style="flex:1;min-width:0;font-size:12px;color:#cbd5e1;white-space:nowrap;'
                    f'overflow:hidden;text-overflow:ellipsis" title="{_tip}">{_sub.get("summary", "")}</span>\n'
                    f'      {_st_html}\n'
                    f'      <span style="flex-shrink:0;display:flex;gap:4px;align-items:center;'
                    f'width:236px;justify-content:flex-end">{_theme_chips(_sub.get("incident_refs", []))}</span>\n'
                    f'    </div>\n'
                )
            _theme_widget_html = (
                f'  <div style="margin-bottom:10px;padding:8px 16px 4px;background:rgba(167,139,250,0.07);'
                f'border:1px solid rgba(167,139,250,0.30);border-left:4px solid #a78bfa;border-radius:6px;'
                f'flex-shrink:0">\n'
                f'    <div style="display:flex;align-items:center;gap:12px;padding-bottom:6px">\n'
                f'      <span style="font-size:10px;font-weight:800;letter-spacing:0.12em;color:#a78bfa;'
                f'text-transform:uppercase;white-space:nowrap">Themes of the week</span>\n'
                f'      <span style="flex:1;min-width:0;font-size:12px;color:#94a3b8;white-space:nowrap;'
                f'overflow:hidden;text-overflow:ellipsis">{_ew_theme.get("summary", "")}</span>\n'
                f'    </div>\n'
                + _theme_rows
                + f'  </div>\n'
            )
        else:
            # Single-theme week: original one-line banner
            _theme_widget_html = (
                f'  <div style="margin-bottom:10px;padding:10px 16px;background:rgba(167,139,250,0.07);'
                f'border:1px solid rgba(167,139,250,0.30);border-left:4px solid #a78bfa;border-radius:6px;'
                f'display:flex;align-items:center;gap:16px;flex-shrink:0">\n'
                f'    <div style="flex-shrink:0;display:flex;flex-direction:column;gap:2px;min-width:0">\n'
                f'      <span style="font-size:10px;font-weight:800;letter-spacing:0.12em;color:#a78bfa;'
                f'text-transform:uppercase;white-space:nowrap">Theme of the week</span>\n'
                f'      <span style="font-family:\'DM Mono\',monospace;font-size:15px;font-weight:600;'
                f'color:#e2e8f0">{_ew_theme.get("label", "")}</span>\n'
                f'    </div>\n'
                f'    <div style="flex:1;min-width:0;font-size:13px;color:#cbd5e1;line-height:1.5">'
                f'{_ew_theme.get("summary", "")}</div>\n'
                f'    <div style="flex-shrink:0;display:flex;gap:6px;align-items:center">{_theme_chips(_ew_theme.get("incident_refs", []))}</div>\n'
                f'  </div>\n'
            )

    _inner = (
        # ── STATUS BANNER ─────────────────────────────────────────────────────
        f'  <div style="margin-bottom:10px;padding:12px 16px;background:{_rag_bg};border:1px solid {_rag_bdr};border-radius:6px;display:flex;flex-direction:column;gap:8px;flex-shrink:0">\n'
        # Row 1: RAG dot + 2-line story narrative
        f'    <div style="display:flex;align-items:flex-start;gap:12px">\n'
        f'      <div style="display:flex;align-items:center;gap:7px;flex-shrink:0;padding-top:2px">'
        f'<div style="width:13px;height:13px;border-radius:50%;background:{_rag_hex};box-shadow:0 0 7px {_rag_hex}"></div>'
        f'<span style="font-size:13px;font-weight:800;color:{_rag_hex};letter-spacing:0.12em;white-space:nowrap">{_rag_label}</span>'
        f'</div>\n'
        f'      <div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:3px">\n'
        f'        <span style="font-size:14px;color:#e2e8f0;font-weight:600;line-height:1.5">{_exec_line1}</span>\n'
        + (f'        <span style="font-size:13px;color:#94a3b8;line-height:1.5">'
           f'<span style="color:#f59e0b;font-weight:600">{_exec_line2}</span></span>\n'
           if _exec_line2 else '')
        + f'      </div>\n'
        f'    </div>\n'
        # Row 2: metric chip grid (3 columns)
        f'    {_exec_chip_grid_html}\n'
        f'  </div>\n'

        # ── THEME OF THE WEEK widget (own card, below the banner) ────────────
        + _theme_widget_html

        # ── BODY: P1 Incidents This Week (full width, scrolls internally) ────
        + '  <div style="flex:1;min-height:0;display:flex;flex-direction:row;gap:10px">\n'
        + f'    <div style="flex:1;min-width:0;min-height:0;overflow:hidden;display:flex;flex-direction:column;background:#0d1629;border:1px solid rgba(255,255,255,0.07);border-radius:8px;padding:12px 16px">\n'
        + f'      <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid rgba(255,255,255,0.05);flex-shrink:0">\n'
        + f'        <span style="font-size:13px;font-weight:700;color:#e2e8f0;letter-spacing:0.07em;text-transform:uppercase">P1 Incidents This Week</span>\n'
        + f'        <span style="font-size:12px;color:#475569">{_ew_range} · {_ew_true_p1} incident{"s" if _ew_true_p1 != 1 else ""}</span>\n'
        + f'      </div>\n'
        + '      <div style="flex:1;min-height:0;overflow-y:auto">\n'
        + _exec_inc_rows
        + '\n      </div>\n'
        + '    </div>\n'
        + '  </div>\n'
    )
    return _ew_range, _inner

# Build one view per complete week in the window (oldest → newest)
_exec_week_keys = [wk for wk in WEEK_KEYS[:-1] if p1_quality_row(wk)[0] is not None]
if not _exec_week_keys:
    _exec_week_keys = [prev_week]
_exec_views = [
    _build_exec_week_view(_wk, WEEK_KEYS.index(_wk), _wk == _exec_week_keys[-1])
    for _wk in _exec_week_keys
]

_exec_week_divs = ""
for _vi, (_rng, _view_inner) in enumerate(_exec_views):
    _disp = "flex" if _vi == len(_exec_views) - 1 else "none"
    _exec_week_divs += (
        f'<div class="exec-week" data-range="{_rng}" style="display:{_disp};'
        f'flex-direction:column;flex:1;min-height:0">\n' + _view_inner + '</div>\n'
    )

_exec_nav_btn_style = ("width:24px;height:22px;display:flex;align-items:center;justify-content:center;"
                       "background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.14);"
                       "border-radius:4px;color:#e2e8f0;font-size:14px;cursor:pointer;padding:0")

exec_slide_html = (
    '<!-- ═══ SLIDE 0 — EXECUTIVE SUMMARY (per-week views + nav) ══════════ -->\n'
    '<div class="slide active" id="sExec"><div class="page">\n'
    '  <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;flex-shrink:0">\n'
    + f'    <div class="group-label" style="margin-bottom:0">Executive Summary · <span id="execWkRange">{_exec_views[-1][0]}</span></div>\n'
    + '    <span id="execHistTag" style="display:none;font-size:10px;font-weight:800;letter-spacing:0.1em;'
      'color:#f59e0b;border:1px solid rgba(245,158,11,0.4);border-radius:4px;padding:1px 7px;'
      'white-space:nowrap">PAST WEEK</span>\n'
    + '    <div style="margin-left:auto;display:flex;align-items:center;gap:6px">\n'
    + f'      <button type="button" id="execPrevBtn" onclick="execNav(-1)" title="Previous week" style="{_exec_nav_btn_style}">‹</button>\n'
    + '      <span id="execWkPos" style="font-size:11px;color:#64748b;font-family:\'DM Mono\',monospace;white-space:nowrap"></span>\n'
    + f'      <button type="button" id="execNextBtn" onclick="execNav(1)" title="Next week" style="{_exec_nav_btn_style}">›</button>\n'
    + '    </div>\n'
    + '  </div>\n'
    + _exec_week_divs
    + '<script>\n'
    '(function(){\n'
    '  var weeks = document.querySelectorAll("#sExec .exec-week");\n'
    '  var idx = weeks.length - 1;\n'
    '  function render(){\n'
    '    for (var i = 0; i < weeks.length; i++) weeks[i].style.display = (i === idx ? "flex" : "none");\n'
    '    document.getElementById("execWkRange").textContent = weeks[idx].getAttribute("data-range");\n'
    '    document.getElementById("execWkPos").textContent = (idx + 1) + " / " + weeks.length;\n'
    '    document.getElementById("execHistTag").style.display = (idx === weeks.length - 1 ? "none" : "inline-block");\n'
    '    var p = document.getElementById("execPrevBtn"), n = document.getElementById("execNextBtn");\n'
    '    p.disabled = (idx === 0);                 p.style.opacity = (idx === 0 ? 0.35 : 1);\n'
    '    n.disabled = (idx === weeks.length - 1);  n.style.opacity = (idx === weeks.length - 1 ? 0.35 : 1);\n'
    '  }\n'
    '  window.execNav = function(d){ idx = Math.max(0, Math.min(weeks.length - 1, idx + d)); render(); };\n'
    '  render();\n'
    '})();\n'
    '</script>\n'
    '</div></div>\n'
)

# ── PIR CATEGORY CHART JS (pre-built to avoid f-string brace-escaping) ───────
_pir_cat_lbl_js = js_str_arr(pir_top5_labels)
_pir_cat_open_js = js_arr(pir_top5_open)
_pir_cat_done_js = js_arr(pir_top5_done)
pir_cat_chart_js = (
    "new Chart(document.getElementById('cPIRCat'),{"
    "type:'bar',data:{labels:" + _pir_cat_lbl_js + ",datasets:["
    "{label:'Open',data:" + _pir_cat_open_js + ",backgroundColor:'#f59e0b',stack:'c',barPercentage:0.7},"
    "{label:'Done',data:" + _pir_cat_done_js + ",backgroundColor:'#22c55e',stack:'c',barPercentage:0.7}"
    "]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,"
    "plugins:{legend:LG,tooltip:TT},"
    "scales:{x:{type:'linear',min:0,stacked:true,ticks:{color:'#64748b',precision:0},grid:{color:'rgba(255,255,255,0.05)'}},"
    "y:{ticks:{color:'#e2e8f0',font:{size:13}},grid:{color:'rgba(255,255,255,0.05)'}}}"
    "}})"
    ";"
)

# ── PIR TREND CHART JS ───────────────────────────────────────────────────────
_pir_hist_lbl_js  = js_str_arr(pir_hist_labels)
_pir_hist_rate_js = js_arr(pir_hist_rate)
_pir_hist_crit_js = js_arr(pir_hist_crit)
_pir_hist_sre_js  = js_arr(pir_hist_sre)
pir_trend_chart_js = (
    "new Chart(document.getElementById('cPIRTrend'),{"
    "type:'line',data:{labels:" + _pir_hist_lbl_js + ",datasets:["
    "{label:'All items',data:" + _pir_hist_rate_js + ","
    "borderColor:'#a78bfa',backgroundColor:'rgba(167,139,250,0.08)',tension:0.3,fill:true,"
    "pointRadius:4,pointBackgroundColor:'#a78bfa',pointBorderColor:'#0d1629',pointBorderWidth:2},"
    "{label:'Critical PIRs',data:" + _pir_hist_crit_js + ",spanGaps:true,"
    "borderColor:'#ef4444',tension:0.3,fill:false,"
    "pointRadius:4,pointBackgroundColor:'#ef4444',pointBorderColor:'#0d1629',pointBorderWidth:2},"
    "{label:'SRE Improvements',data:" + _pir_hist_sre_js + ",spanGaps:true,"
    "borderColor:'#38bdf8',tension:0.3,fill:false,"
    "pointRadius:4,pointBackgroundColor:'#38bdf8',pointBorderColor:'#0d1629',pointBorderWidth:2},"
    "{label:'Target 85%',data:Array(" + str(len(pir_hist_rate)) + ").fill(85),"
    "borderColor:'#22c55e',borderDash:[5,4],borderWidth:2,pointRadius:0,fill:false,tension:0}"
    "]},options:{responsive:true,maintainAspectRatio:false,"
    "plugins:{legend:LG,tooltip:TT},"
    "scales:{x:{ticks:{color:'#64748b',font:{size:11}},grid:{color:'rgba(255,255,255,0.05)'}},"
    "y:{type:'linear',min:0,max:100,ticks:{color:'#64748b',stepSize:20,callback:function(v){return v+'%'}},grid:{color:'rgba(255,255,255,0.05)'}}}}"
    "});"
)

# ── SERVICING & ESCALATION SLIDE (cache/service_split_cache.json) ────────────
# Who serviced each incident (Incident Lead → roster bucket) and how often SOC
# escalated to SRE — explicit hand-offs (SRE path pages) vs ladder climbs
# (15-min ack timeout roll-ups on the SOC+SRE path). Added 2026-07-11.
SVC_CACHE_FILE = os.path.join(_ROOT, "cache", "service_split_cache.json")
try:
    with open(SVC_CACHE_FILE) as f:
        svc_cache = json.load(f)
except FileNotFoundError:
    svc_cache = {}

# Charts plot the full cached history (capped 13 weeks, same as WEEK_KEYS);
# stat cards show the newest cached week vs the week before it. Current
# in-progress week included (Step 2I maintains it nightly — leads wholesale,
# climb/cover classification incremental).
svc_weeks_all = sorted(svc_cache.get("weeks", {}).keys())[-13:]
_svc_roster = svc_cache.get("roster", {})
_svc_soc, _svc_sre = set(_svc_roster.get("soc", [])), set(_svc_roster.get("sre", []))
_svc_mgmt = set(_svc_roster.get("mgmt", []))

def _svc_buckets(week):
    b = {"soc": 0, "sre": 0, "mgmt": 0, "other": 0, "nolead": 0}
    for name, n in svc_cache["weeks"][week].get("leads", {}).items():
        if name == "NO LEAD":       b["nolead"] += n
        elif name in _svc_soc:      b["soc"]    += n
        elif name in _svc_sre:      b["sre"]    += n
        elif name in _svc_mgmt:     b["mgmt"]   += n
        else:                       b["other"]  += n
    return b

# The slide always renders (positional nav requires a fixed slide count) —
# without cache data it shows a placeholder.
svc_charts_js  = ""
svc_tab_html   = f'    <button class="slide-tab" onclick="showSlide({_idx_svc})">Servicing</button>\n'
svc_slide_html = ('\n<div class="slide" id="sSvc"><div class="page">\n'
                  '  <div class="group-label">Incident Servicing &amp; Escalation</div>\n'
                  '  <div class="p1-no-data c-muted">No servicing data — cache/service_split_cache.json is missing or empty.</div>\n'
                  '</div></div>\n')
if svc_weeks_all:
    _svc_rows   = {wk: _svc_buckets(wk) for wk in svc_weeks_all}
    _svc_esc    = {wk: svc_cache["weeks"][wk].get("escalations", {}) for wk in svc_weeks_all}
    _svc_totals = {wk: svc_cache["weeks"][wk].get("total", 0) for wk in svc_weeks_all}
    _svc_lbls   = [fmt_week_label(wk, not week_is_complete(wk)) for wk in svc_weeks_all]
    _svc_range  = (f"{fmt_date_dmy(svc_weeks_all[0])} – " + fmt_date_dmy(
        (datetime.strptime(svc_weeks_all[-1], "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d"))
        + (" · current week in progress" if not week_is_complete(svc_weeks_all[-1]) else ""))

    # Stat cards: current (newest cached) week vs the week before it
    _svc_cw = svc_weeks_all[-1]
    _svc_pw = svc_weeks_all[-2] if len(svc_weeks_all) >= 2 else None
    _svc_ho = {wk: svc_cache["weeks"][wk].get("handoffs") or
                   {"sre": {}, "other": {}} for wk in svc_weeks_all}

    def _svc_wk_stats(wk):
        if wk is None:
            return None
        r, tot = _svc_rows[wk], _svc_totals[wk]
        ho_sre, ho_oth = sum(_svc_ho[wk]["sre"].values()), sum(_svc_ho[wk]["other"].values())
        pc = lambda n: round(n / tot * 100, 1) if tot else None
        return {"total": tot, "soc": r["soc"], "sre": r["sre"], "mgmt": r["mgmt"],
                "other": r["other"], "nolead": r["nolead"],
                "soc_pct": pc(r["soc"]), "sre_pct": pc(r["sre"]), "other_pct": pc(r["other"]),
                "ho_sre": ho_sre, "ho_other": ho_oth, "ho": ho_sre + ho_oth,
                "climbs": _svc_esc[wk].get("ladder_climbs", 0)}

    _scw, _spw = _svc_wk_stats(_svc_cw), _svc_wk_stats(_svc_pw)
    _svc_cw_date = fmt_date_dmy(_svc_cw) + (" · in progress" if not week_is_complete(_svc_cw) else "")

    def _svc_delta(cur, prev, unit="", higher_is_better=True, decimals=1):
        # delta_str clone with the servicing prev-week label (cache weeks can
        # lag the report's stat_prev_week if a nightly run is missed)
        if cur is None or prev is None or _svc_pw is None:
            return ("d-muted", "—")
        diff = cur - prev
        if abs(diff) < 0.05:
            return ("d-muted", f"0{unit} vs wk {fmt_date_dmy(_svc_pw)}")
        sign = "+" if diff > 0 else "−"
        fmt_diff = str(int(round(abs(diff)))) if decimals == 0 else f"{abs(diff):.{decimals}f}"
        good = diff > 0 if higher_is_better else diff < 0
        return ("d-green" if good else "d-red",
                f"{sign}{fmt_diff}{unit} vs wk {fmt_date_dmy(_svc_pw)}")

    # SOC share up = good (work absorbed at L1); SRE share / hand-offs up = bad
    # (interrupts on SRE); other-teams share is neutral.
    _soc_d_cls, _soc_d = _svc_delta(_scw["soc_pct"], _spw and _spw["soc_pct"], "%", True)
    _sre_d_cls, _sre_d = _svc_delta(_scw["sre_pct"], _spw and _spw["sre_pct"], "%", False)
    _oth_d_cls, _oth_d = _svc_delta(_scw["other_pct"], _spw and _spw["other_pct"], "%", True)
    _oth_d_cls = "d-muted"
    _ho_d_cls, _ho_d = _svc_delta(_scw["ho"], _spw and _spw["ho"], "", False, decimals=0)
    _fmt_pct = lambda v: f"{round(v)}%" if v is not None else "—"

    svc_tab_html = f'    <button class="slide-tab" onclick="showSlide({_idx_svc})">Servicing</button>\n'

    svc_slide_html = f'''
<!-- ═══ SLIDE — SERVICING & ESCALATION ═════════════════════════ -->
<div class="slide" id="sSvc"><div class="page">
  <div class="group-label">Incident Servicing &amp; Escalation <span style="font-weight:400;text-transform:none;letter-spacing:normal;font-size:11px">&middot; charts: {len(svc_weeks_all)} weeks &middot; {_svc_range} &middot; cards: week of {_svc_cw_date}</span></div>
  <div class="stat-grid-4">
    <div class="stat-card" style="border-left:3px solid #38bdf8">
      <div class="card-label">Serviced by SOC ({_svc_cw_date})</div>
      <div class="card-value c-muted">{_fmt_pct(_scw["soc_pct"])}</div>
      <div class="card-delta {_soc_d_cls}">{_soc_d}</div>
      <div class="card-subnote">{_scw["soc"]} of {_scw["total"]} incidents &middot; Incident Lead on SOC roster</div>
    </div>
    <div class="stat-card" style="border-left:3px solid #a78bfa">
      <div class="card-label">Serviced by SRE ({_svc_cw_date})</div>
      <div class="card-value c-muted">{_fmt_pct(_scw["sre_pct"])}</div>
      <div class="card-delta {_sre_d_cls}">{_sre_d}</div>
      <div class="card-subnote">{_scw["sre"]} incidents &middot; + management {_scw["mgmt"]}</div>
    </div>
    <div class="stat-card" style="border-left:3px solid #64748b">
      <div class="card-label">Other Teams ({_svc_cw_date})</div>
      <div class="card-value c-muted">{_fmt_pct(_scw["other_pct"])}</div>
      <div class="card-delta {_oth_d_cls}">{_oth_d}</div>
      <div class="card-subnote">{_scw["other"]} incidents &middot; no lead: {_scw["nolead"]}</div>
    </div>
    <div class="stat-card" style="border-left:3px solid #f59e0b">
      <div class="card-label">SOC Hand-offs ({_svc_cw_date})</div>
      <div class="card-value c-amber">{_scw["ho"]}</div>
      <div class="card-delta {_ho_d_cls}">{_ho_d}</div>
      <div class="card-subnote">SRE {_scw["ho_sre"]} &middot; other teams {_scw["ho_other"]} &middot; + {_scw["climbs"]} ladder climbs</div>
    </div>
  </div>
  <div class="charts-area">
    <div class="chart-row">
      <div class="chart-section">
        <div class="chart-title">Incidents Serviced &middot; by Team</div>
        <div class="chart-note">Incident Lead per incident &middot; person &#8594; team via roster</div>
        <div class="chart-container"><canvas id="cSvcSplit" style="width:100%;height:100%"></canvas></div>
      </div>
      <div class="chart-section">
        <div class="chart-title">SOC Hand-offs to SRE &middot; by Time of Day</div>
        <div class="chart-note">Human-created escalations only (auto alert pages excluded) &middot; 8-hr UTC blocks &middot; hand-offs to other teams tracked in the card, not plotted</div>
        <div class="chart-container"><canvas id="cSvcEsc" style="width:100%;height:100%"></canvas></div>
      </div>
    </div>
  </div>
  <div style="margin-top:8px;padding:7px 12px;background:rgba(56,189,248,0.08);border-left:3px solid #38bdf8;border-radius:4px;font-size:11px;color:#93c5fd;line-height:1.5;">&#9432;&nbsp; Servicing is attributed by the person holding Incident Lead, mapped to their team — an SRE covering a SOC rotation shift counts under SRE. Escalation counts are pages, not incidents. Private incidents excluded.{" For the in-progress week, recently opened incidents often have no Incident Lead assigned yet — they sit under No lead until triaged, so team shares firm up as the week completes." if not week_is_complete(_svc_cw) else ""}</div>
</div></div>
'''

    _js = lambda key: js_arr([_svc_rows[wk][key] for wk in svc_weeks_all])
    svc_charts_js = (
        "new Chart(document.getElementById('cSvcSplit'),{type:'bar',data:{labels:" + js_str_arr(_svc_lbls) + ",datasets:["
        "{label:'SOC',data:" + _js("soc") + ",backgroundColor:'#38bdf8',stack:'s'},"
        "{label:'SRE',data:" + _js("sre") + ",backgroundColor:'#a78bfa',stack:'s'},"
        "{label:'Management',data:" + _js("mgmt") + ",backgroundColor:'#f59e0b',stack:'s'},"
        "{label:'Other teams',data:" + _js("other") + ",backgroundColor:'#64748b',stack:'s'},"
        "{label:'No lead',data:" + _js("nolead") + ",backgroundColor:'#475569',stack:'s'}"
        "]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:LG,tooltip:TT},scales:{x:XA,y:YL(true)}}});\n"
        "new Chart(document.getElementById('cSvcEsc'),{type:'bar',data:{labels:" + js_str_arr(_svc_lbls) + ",datasets:["
        "{label:'Day',data:" + js_arr([_svc_ho[wk]["sre"].get("day", 0) for wk in svc_weeks_all]) + ",backgroundColor:'#38bdf8',stack:'sre'},"
        "{label:'Evening',data:" + js_arr([_svc_ho[wk]["sre"].get("evening", 0) for wk in svc_weeks_all]) + ",backgroundColor:'#f59e0b',stack:'sre'},"
        "{label:'Night',data:" + js_arr([_svc_ho[wk]["sre"].get("night", 0) for wk in svc_weeks_all]) + ",backgroundColor:'#64748b',stack:'sre'}"
        "]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:LG,tooltip:TT},scales:{x:XA,y:YL(true)}}});"
    )

# ── HTML GENERATION ──────────────────────────────────────────────────────────
wk_label_cur = fmt_week_label(current_week, True).rstrip("*")
title_date   = datetime.strptime(current_week, "%Y-%m-%d").strftime("%-d %B %Y")

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Weekly Incident Report — {title_date}</title>
  <style>{vendored_font_css}</style>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #080f1e; color: #e2e8f0; font-family: 'DM Sans', sans-serif; height: 100vh; overflow: hidden; display: flex; flex-direction: column; }}
    .topbar {{ display: flex; align-items: center; justify-content: space-between; padding: 0 24px; height: 50px; border-bottom: 1px solid rgba(255,255,255,0.08); flex-shrink: 0; gap: 24px; }}
    .topbar-title {{ font-size: 15px; font-weight: 700; color: #e2e8f0; white-space: nowrap; }}
    .topbar-meta {{ font-size: 12px; color: #64748b; white-space: nowrap; }}
    .slide-tabs {{ display: flex; gap: 4px; }}
    .slide-tab {{ background: none; border: 1px solid transparent; border-radius: 6px; color: #64748b; font-family: 'DM Sans', sans-serif; font-size: 12px; font-weight: 500; padding: 5px 12px; cursor: pointer; transition: all 0.15s; }}
    .slide-tab:hover {{ color: #e2e8f0; border-color: rgba(255,255,255,0.12); }}
    .slide-tab.active {{ color: #e2e8f0; background: #1e293b; border-color: rgba(255,255,255,0.12); }}
    .slides-wrap {{ flex: 1; overflow: hidden; position: relative; min-height: 0; }}
    .slide {{ position: absolute; inset: 0; display: none; flex-direction: column; overflow: hidden; }}
    .slide.active {{ display: flex; }}
    .page {{ flex: 1; display: flex; flex-direction: column; padding: 14px 24px 10px; min-height: 0; }}
    .slide-controls {{ display: flex; align-items: center; justify-content: space-between; padding: 0 24px; height: 40px; border-top: 1px solid rgba(255,255,255,0.08); flex-shrink: 0; }}
    .slide-btn {{ background: none; border: 1px solid rgba(255,255,255,0.1); border-radius: 5px; color: #94a3b8; font-family: 'DM Sans', sans-serif; font-size: 12px; padding: 4px 14px; cursor: pointer; transition: all 0.15s; }}
    .slide-btn:hover {{ color: #e2e8f0; border-color: rgba(255,255,255,0.25); }}
    .slide-counter {{ font-family: 'DM Mono', monospace; font-size: 11px; color: #475569; }}
    .group-label {{ font-size: 13px; color: #64748b; letter-spacing: 0.1em; text-transform: uppercase; font-weight: 600; margin-bottom: 8px; flex-shrink: 0; }}
    .stat-grid-4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 10px; flex-shrink: 0; }}
    .stat-card {{ background: #0d1629; border: 1px solid rgba(255,255,255,0.07); border-radius: 8px; padding: 10px 14px; }}
    .card-label {{ font-size: 12px; color: #64748b; margin-bottom: 5px; font-weight: 500; line-height: 1.3; }}
    .card-value {{ font-family: 'DM Mono', monospace; font-size: 26px; font-weight: 500; line-height: 1; margin-bottom: 3px; }}
    .card-value .unit {{ font-size: 14px; font-weight: 400; }}
    .card-subnote {{ font-size: 12px; color: #64748b; margin-bottom: 2px; }}
    .card-delta {{ font-family: 'DM Mono', monospace; font-size: 12px; margin-top: 3px; }}
    .c-red   {{ color: #ef4444; }}
    .c-amber {{ color: #f59e0b; }}
    .c-green {{ color: #22c55e; }}
    .c-muted {{ color: #94a3b8; }}
    .d-red   {{ color: #ef4444; }}
    .d-green {{ color: #22c55e; }}
    .d-muted {{ color: #475569; }}
    .charts-area {{ flex: 1; display: flex; flex-direction: column; gap: 8px; min-height: 0; }}
    .chart-row {{ display: flex; gap: 8px; flex: 1; min-height: 0; }}
    .chart-section {{ background: #0d1629; border: 1px solid rgba(255,255,255,0.07); border-radius: 8px; padding: 10px 14px; display: flex; flex-direction: column; flex: 1; min-height: 0; }}
    .chart-title {{ font-size: 14px; font-weight: 600; color: #e2e8f0; margin-bottom: 2px; flex-shrink: 0; }}
    .chart-note  {{ font-size: 12px; color: #64748b; margin-bottom: 8px; flex-shrink: 0; }}
    .chart-container {{ flex: 1; min-height: 0; position: relative; }}
    .stat-grid-2 {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 10px; flex-shrink: 0; }}
    .stat-grid-3 {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 10px; flex-shrink: 0; }}
    .p1-inc-area {{ flex: 1.4; display: flex; flex-direction: column; gap: 8px; min-height: 0; margin-bottom: 8px; }}
    .p1-inc-card {{ background: #0d1629; border: 1px solid rgba(255,255,255,0.07); border-radius: 8px; padding: 12px 16px; flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }}
    .p1-inc-header {{ display: flex; align-items: center; gap: 10px; flex-shrink: 0; margin-bottom: 4px; flex-wrap: wrap; }}
    .p1-ref {{ font-family: 'DM Mono', monospace; font-size: 13px; color: #38bdf8; font-weight: 500; text-decoration: none; }}
    .p1-ref:hover {{ text-decoration: underline; }}
    .p1-status-badge {{ font-size: 12px; font-weight: 600; padding: 3px 9px; border-radius: 4px; background: rgba(255,255,255,0.06); }}
    .p1-carry-badge {{ font-size: 11px; font-weight: 600; padding: 3px 9px; border-radius: 4px; color: #94a3b8; background: rgba(148,163,184,0.10); border: 1px solid rgba(148,163,184,0.25); }}
    .p1-theme-badge {{ font-size: 11px; font-weight: 600; padding: 3px 9px; border-radius: 4px; color: #c4b5fd; background: rgba(167,139,250,0.10); border: 1px solid rgba(167,139,250,0.30); }}
    .p1-inc-date {{ font-size: 13px; color: #64748b; margin-left: auto; }}
    .p1-cause {{ font-size: 13px; color: #94a3b8; }}
    .p1-inc-title {{ font-size: 1.15em; font-weight: 700; color: #e2e8f0; margin-bottom: 4px; flex-shrink: 0; line-height: 1.3; }}
    .p1-inc-overview {{ font-size: 14px; color: #94a3b8; line-height: 1.7; overflow: hidden; }}
    .p1-no-data {{ font-size: 14px; padding: 16px 0; }}
    .brand-strip {{ display: flex; align-items: center; gap: 10px; padding: 6px 0 8px; flex-shrink: 0; border-bottom: 1px solid rgba(255,255,255,0.06); margin-bottom: 10px; flex-wrap: wrap; }}
    .brand-strip-label {{ font-size: 10px; color: #475569; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; white-space: nowrap; margin-right: 4px; }}
    .brand-pill {{ display: inline-flex; align-items: center; gap: 6px; background: #0d1629; border: 1px solid rgba(255,255,255,0.07); border-radius: 6px; padding: 4px 10px; }}
    .brand-pill-rank {{ font-family: 'DM Mono', monospace; font-size: 10px; color: #475569; }}
    .brand-pill-name {{ font-size: 12px; color: #e2e8f0; }}
    .brand-pill-count {{ font-family: 'DM Mono', monospace; font-size: 13px; font-weight: 600; color: #38bdf8; }}
    .brand-strip-note {{ font-size: 10px; color: #475569; margin-left: auto; white-space: nowrap; }}
    .p1-two-up {{ flex: 1; display: flex; flex-direction: row; gap: 10px; min-height: 0; }}
    .p1-full-card {{ flex: 1; min-width: 0; min-height: 0; display: flex; flex-direction: column; background: #0d1629; border: 1px solid rgba(255,255,255,0.07); border-radius: 8px; padding: 14px 18px; overflow: hidden; }}
    .p1-sections {{ display: flex; flex-direction: column; gap: 10px; margin-top: 10px; flex: 1; min-height: 0; overflow: hidden; }}
    .p1-section {{ min-height: 0; overflow: hidden; border-left: 1px solid rgba(255,255,255,0.06); padding-left: 14px; }}
    .p1-section:first-child {{ border-left: none; padding-left: 0; }}
    .p1-section-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: #38bdf8; font-weight: 700; border-bottom: 1px solid rgba(56,189,248,0.15); padding-bottom: 3px; margin-bottom: 6px; }}
    .p1-section-body {{ font-size: 1em; color: #94a3b8; line-height: 1.65; overflow: hidden; }}
  </style>
</head>
<body>

<div class="topbar">
  <div class="topbar-title">Weekly Incident Report</div>
  <div class="slide-tabs">
    <button class="slide-tab active" onclick="showSlide(0)">Executive Summary</button>
    <button class="slide-tab" onclick="showSlide({_idx_p1perf})">P1 Performance</button>
{p1_tab_btns_html}    <button class="slide-tab" onclick="showSlide({_idx_pir})">PIR Actions</button>
    <button class="slide-tab" onclick="showSlide({_idx_partner})">Partner Tickets</button>
    <button class="slide-tab" onclick="showSlide({_idx_ops})">Incident Ops</button>
{svc_tab_html}    <button class="slide-tab" onclick="showSlide({_idx_eng})">Engineer Workload</button>
  </div>
  <div class="topbar-meta">{today_str}</div>
</div>

<div class="slides-wrap">

{exec_slide_html}
<!-- ═══ SLIDE 1 — P1 PERFORMANCE ════════════════════════════════════ -->
<div class="slide" id="s0"><div class="page">
  <div class="group-label">P1 Performance · {cw_date}</div>
{brand_strip_html}
  <div class="stat-grid-3">
    <div class="stat-card">
      <div class="card-label">True P1s This Week ({cw_date})</div>
      <div class="card-value {'c-green' if cw_true_p1 == 0 else 'c-red'}">{cw_true_p1}</div>
      <div class="card-delta {true_p1_delta_cls}">{true_p1_delta}</div>
    </div>
    <div class="stat-card">
      <div class="card-label">SOC & SRE P1 FRT SLA ({cw_date})</div>
      <div class="card-value {color_pct(cw_p1_frt_rate)}">{fmt_rate(cw_p1_frt_rate, 0) if cw_p1_frt_rate is not None else '—'}</div>
      <div class="card-subnote">Target: 30 min</div>
      <div class="card-delta {p1_frt_delta_cls}">{p1_frt_delta}</div>
    </div>
    <div class="stat-card">
      <div class="card-label">SOC & SRE P1 Avg FRT ({cw_date})</div>
      <div class="card-value {'c-green' if cw_p1_med_frt is not None and cw_p1_med_frt <= 30 else 'c-red' if cw_p1_med_frt is not None else 'c-muted'}">{fmt_min(cw_p1_med_frt)} <span class="unit">min</span></div>
      <div class="card-subnote">Target: 30 min</div>
      <div class="card-delta {p1_med_delta_cls}">{p1_med_delta}</div>
    </div>
  </div>
  <div class="charts-area">
    <div class="chart-row">
      <div class="chart-section">
        <div class="chart-title">P1 Incident Quality — Week on Week</div>
        <div class="chart-note">{p1q_note}</div>
        <div class="chart-container"><canvas id="cP1Q" style="width:100%;height:100%"></canvas></div>
      </div>
      <div class="chart-section">
        <div class="chart-title">SOC & SRE P1 First Response SLA — Week on Week</div>
        <div class="chart-note">Source: Intercom &middot; P1 Incident SLA only &middot; 30-min target &middot; excludes downgraded and unanswered tickets</div>
        <div class="chart-container"><canvas id="cP1F" style="width:100%;height:100%"></canvas></div>
      </div>
    </div>
  </div>
</div></div>

{p1_all_slides_html}

<div class="slide" id="s2"><div class="page">
  <div class="group-label">PIR Action Items
    <span style="font-weight:400;text-transform:none;letter-spacing:normal;font-size:11px">&middot; ClickUp post-incident reviews &middot; excl. SRE internal &middot; as of {pir_generated}</span>
  </div>
{pir_cards_html}
  <div style="flex:1;min-height:0;display:flex;gap:12px;margin-top:0">
    <div style="flex:1;min-height:0;display:flex;flex-direction:column">
{pir_team_table_html}
    </div>
    <div style="flex:1.5;min-height:0;display:flex;flex-direction:column;background:#0d1629;border:1px solid rgba(255,255,255,0.07);border-radius:8px;padding:14px 16px;margin-top:12px">
      <div class="chart-title" style="margin-bottom:8px">Completion Rate · Week on Week</div>
      <div style="flex:1;min-height:0;position:relative"><canvas id="cPIRTrend" style="width:100%;height:100%"></canvas></div>
    </div>
    <div style="flex:1.2;min-height:0;display:flex;flex-direction:column;background:#0d1629;border:1px solid rgba(255,255,255,0.07);border-radius:8px;padding:14px 16px;margin-top:12px">
      <div class="chart-title" style="margin-bottom:8px">Top 5 Pain Points · Open Items by Category</div>
      <div style="flex:1;min-height:0;position:relative"><canvas id="cPIRCat" style="width:100%;height:100%"></canvas></div>
    </div>
  </div>
  <div style="margin-top:8px;padding:7px 12px;background:rgba(56,189,248,0.08);border-left:3px solid #38bdf8;border-radius:4px;font-size:11px;color:#93c5fd;line-height:1.5;">&#9432;&nbsp; From w/c 8 Jun 2026, Producers will hold weekly meetings with the Head of SRE to track progress and plan PIR action items.</div>
</div></div>

<!-- ═══ SLIDE 3 — PARTNER TICKETS ══════════════════════════════════ -->
<div class="slide" id="s3"><div class="page">
  <div class="group-label">Partner Tickets</div>
  <div class="stat-grid-4">
    <div class="stat-card">
      <div class="card-label">SOC & SRE P2/P3 FRT SLA ({cw_date})</div>
      <div class="card-value {color_pct(cw_p23_rate)}">{fmt_rate(cw_p23_rate, 1) if cw_p23_rate is not None else '—'}</div>
      <div class="card-subnote">Target: 2 hr · office hours</div>
      <div class="card-delta {p23_delta_cls}">{p23_delta}</div>
    </div>
    <div class="stat-card">
      <div class="card-label">Avg. SOC & SRE CSAT Score ({cw_date})</div>
      <div class="card-value {color_csat(cw_csat_avg)}">{fmt_csat(cw_csat_avg)}<span class="unit">/5</span></div>
      <div class="card-delta {csat_delta_cls}">{csat_delta}</div>
    </div>
    <div class="stat-card">
      <div class="card-label">Partner Tickets This Week ({cw_date})</div>
      <div class="card-value c-muted">{cw_pt_resp}</div>
      <div class="card-subnote">P1: {cw_pt_p1} &middot; P2: {cw_pt_p2} &middot; P3: {cw_pt_p3}</div>
      <div class="card-subnote">As tagged at intake &mdash; P1 tag &ne; confirmed True P1 (see P1 Performance)</div>
      <div class="card-delta {pt_delta_cls}">{pt_delta}</div>
    </div>
    <div class="stat-card">
      <div class="card-label">Avg. Partner Tickets Response Time ({cw_date})</div>
      <div class="card-value {pt_med_cls}">{fmt_min(cw_pt_med)} <span class="unit">min</span></div>
      <div class="card-subnote">Target: &lt;2 hr</div>
      <div class="card-delta {pt_med_delta_cls}">{pt_med_delta}</div>
    </div>
  </div>
  <div class="charts-area">
    <div class="chart-row">
      <div class="chart-section">
        <div class="chart-title">SOC & SRE P2/P3 First Response SLA — Week on Week</div>
        <div class="chart-note">Source: Intercom &middot; P2/P3 Incident tagged &middot; 2-hour target, office hours &middot; Slack-handled excluded</div>
        <div class="chart-container"><canvas id="cP23F" style="width:100%;height:100%"></canvas></div>
      </div>
      <div class="chart-section">
        <div class="chart-title">SOC & SRE CSAT — Week on Week</div>
        <div class="chart-note">Source: Intercom &middot; All SRE conversations &middot; 1–5 scale</div>
        <div class="chart-container"><canvas id="cCSAT" style="width:100%;height:100%"></canvas></div>
      </div>
      <div class="chart-section">
        <div class="chart-title">Partner Ticket Volume — Week on Week</div>
        <div class="chart-note">Source: Intercom &middot; All P1/P2/P3 Incident tagged tickets assigned to SRE</div>
        <div class="chart-container"><canvas id="cPVol" style="width:100%;height:100%"></canvas></div>
      </div>
    </div>
    <div style="margin-top:6px;padding:7px 12px;background:rgba(56,189,248,0.08);border-left:3px solid #38bdf8;border-radius:4px;font-size:11px;color:#93c5fd;line-height:1.5;flex-shrink:0;">&#9432;&nbsp; From w/c 25 May 2026, Partner Support agreed to route all partner incidents directly to SRE.</div>
  </div>
</div></div>

<!-- ═══ SLIDE 4 — INCIDENT OPERATIONS ══════════════════════════════ -->
<div class="slide" id="s4"><div class="page">
  <div class="group-label">
    Incident Operations
    <span style="font-weight:400;text-transform:none;letter-spacing:normal;font-size:11px">&middot; {wk19_note}</span>
  </div>
  <div class="stat-grid-3">
    <div class="stat-card">
      <div class="card-label">Incidents This Week ({cw_date})</div>
      <div class="card-value c-muted">{cw_inc_total}</div>
      <div class="card-subnote">P1: {cw_inc_p1} &middot; P2: {cw_inc_p2} &middot; P3: {cw_inc_p3} &middot; P4: {cw_inc_p4}{cw_inc_unk_note}</div>
      <div class="card-delta {inc_delta_cls}">{inc_delta}</div>
    </div>
    <div class="stat-card">
      <div class="card-label">Alerts This Week ({cw_date})</div>
      <div class="card-value {alerts_cls}">{cw_alerts}</div>
      <div class="card-subnote">Composite target: &lt;750/wk (HTTP 400 &middot; SOC 200 &middot; DMS 150)</div>
      <div class="card-delta {alerts_delta_cls}">{alerts_delta}</div>
    </div>
    <div class="stat-card">
      <div class="card-label">Alerts by Time Block ({cw_date})</div>
      <div class="card-value c-muted">{tb_card_value}</div>
      <div class="card-subnote">{tb_card_subnote}</div>
      <div class="card-delta c-muted">{tb_card_delta}</div>
    </div>
  </div>
  <div class="charts-area">
    <div class="chart-row">
      <div class="chart-section">
        <div class="chart-title">Accepted Incidents by Severity</div>
        <div class="chart-note">incident.io &middot; W19 onwards</div>
        <div class="chart-container"><canvas id="cIVol" style="width:100%;height:100%"></canvas></div>
      </div>
      <div class="chart-section">
        <div class="chart-title">Alert Volume by Source</div>
        <div class="chart-note">incident.io &middot; W19 onwards &middot; incident.io sources only</div>
        <div class="chart-container"><canvas id="cAVol" style="width:100%;height:100%"></canvas></div>
      </div>
      <div class="chart-section">
        <div class="chart-title">Incidents by Time Block</div>
        <div class="chart-note">incident.io &middot; W19 onwards &middot; Accepted incidents per 8-hr UTC block &middot; workload view</div>
        <div class="chart-container"><canvas id="cTBVol" style="width:100%;height:100%"></canvas></div>
      </div>
    </div>
  </div>
</div></div>

{svc_slide_html}
{engineer_workload_slide_html}

</div><!-- /slides-wrap -->

<div class="slide-controls">
  <button class="slide-btn" onclick="showSlide(currentSlide-1)">&#8592; Prev</button>
  <span class="slide-counter" id="slide-counter">1 / {_total_slides}</span>
  <button class="slide-btn" onclick="showSlide(currentSlide+1)">Next &#8594;</button>
</div>

<script>{vendored_chartjs}</script>
<script>
const WK   = {js_str_arr(WK)};
const WK19 = {js_str_arr(WK19)};

const trueP1  = {js_arr(trueP1_arr)};
const falseP1 = {js_arr(falseP1_arr)};
const unclassP= {js_arr(unclassP_arr)};
const fpRate  = {js_arr(fpRate_arr)};

const p1Hit  = {js_arr(p1Hit_arr)};
const p1Miss = {js_arr(p1Miss_arr)};
const p1Rate = {js_arr(p1Rate_arr)};


const p23Hit  = {js_arr(p23Hit_arr)};
const p23Miss = {js_arr(p23Miss_arr)};
const p23Rate = {js_arr(p23Rate_arr)};

const cs5  = {js_arr(cs5_arr)};
const cs4  = {js_arr(cs4_arr)};
const cs3  = {js_arr(cs3_arr)};
const cs2  = {js_arr(cs2_arr)};
const cs1  = {js_arr(cs1_arr)};
const csA  = {js_arr(csA_arr)};

const ptP1   = {js_arr(ptP1_arr)};
const ptP2   = {js_arr(ptP2_arr)};
const ptP3   = {js_arr(ptP3_arr)};
const ptMed  = {js_arr(ptMed_arr)};
const ptAvg  = {js_arr(ptAvg_arr)};
const T120 = Array(WK.length).fill(120);

const iP1 = {js_arr(iP1_arr)};
const iP2 = {js_arr(iP2_arr)};
const iP3 = {js_arr(iP3_arr)};
const iP4 = {js_arr(iP4_arr)};
const iUnk = {js_arr(iUnk_arr)};

const aDMS  = {js_arr(aDMS_arr)};
const aSOC  = {js_arr(aSOC_arr)};
const aHTTP = {js_arr(aHTTP_arr)};
const aGraf = {js_arr(aGraf_arr)};
const aIcom = {js_arr(aIcom_arr)};
const aFTML = {js_arr(aFTML_arr)};
const aOther = {js_arr(aOther_arr)};
const aPD_SP  = {js_arr(aPD_SP_arr)};
const aPD_BO  = {js_arr(aPD_BO_arr)};

const tbDay    = {js_arr(tbDay_arr)};
const tbEve    = {js_arr(tbEve_arr)};
const tbNight  = {js_arr(tbNight_arr)};

const pirCatLabels = {js_str_arr(pir_top5_labels)};
const pirCatOpen   = {js_arr(pir_top5_open)};
const pirCatDone   = {js_arr(pir_top5_done)};

const TT = {{ backgroundColor:'#0d1629', borderColor:'rgba(255,255,255,0.1)', borderWidth:1, titleColor:'#e2e8f0', bodyColor:'#e2e8f0', padding:8 }};
const LG = {{ position:'top', labels:{{ color:'#e2e8f0', boxWidth:12, padding:10, font:{{size:11}} }} }};
const XA = {{ ticks:{{ color:'#64748b', font:{{size:11}} }}, grid:{{ color:'rgba(255,255,255,0.05)' }} }};
const YL = (s=false) => ({{ type:'linear', position:'left', min:0, stacked:s, ticks:{{ color:'#64748b', precision:0 }}, grid:{{ color:'rgba(255,255,255,0.05)' }} }});
const RA   = {{ type:'linear', position:'right', min:0, max:100, ticks:{{ color:'#a78bfa', callback:v=>v+'%' }}, grid:{{ display:false }} }};
const YPct = {{ type:'linear', min:0, max:100, ticks:{{ color:'#64748b', callback:v=>v+'%' }}, grid:{{ color:'rgba(255,255,255,0.05)' }} }};
const T90 = Array(WK.length).fill(90);
const noT = item => item.text !== '90% target';
const no45= item => item.text !== '4.5 target';

new Chart(document.getElementById('cP1Q'),{{type:'bar',data:{{labels:WK,datasets:[
  {{label:'True P1',     data:trueP1,  backgroundColor:'#ef4444',stack:'q'}},
  {{label:'False P1',    data:falseP1, backgroundColor:'#f59e0b',stack:'q'}},
  {unclass_ds}
]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:LG,tooltip:TT}},scales:{{x:XA,y:YL(true)}}}}}});

new Chart(document.getElementById('cP1F'),{{type:'bar',data:{{labels:WK,datasets:[
  {{label:'Hit',   data:p1Hit, backgroundColor:'#22c55e',stack:'f'}},
  {{label:'Missed',data:p1Miss,backgroundColor:'#ef4444',stack:'f'}},
  {{label:'SLA Hit Rate %',type:'line',data:p1Rate,borderColor:'#a78bfa',backgroundColor:'transparent',tension:0.3,fill:false,yAxisID:'rate',pointRadius:3,pointBackgroundColor:'#a78bfa'}},
  {{label:'90% target',type:'line',data:T90,borderColor:'rgba(167,139,250,0.3)',borderDash:[5,5],pointRadius:0,fill:false,yAxisID:'rate'}}
]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{...LG,labels:{{...LG.labels,filter:noT}}}},tooltip:TT}},scales:{{x:XA,y:YL(true),rate:RA}}}}}});

new Chart(document.getElementById('cP23F'),{{type:'bar',data:{{labels:WK,datasets:[
  {{label:'Hit',   data:p23Hit, backgroundColor:'#22c55e',stack:'f2'}},
  {{label:'Missed',data:p23Miss,backgroundColor:'#ef4444',stack:'f2'}},
  {{label:'SLA Hit Rate %',type:'line',data:p23Rate,borderColor:'#a78bfa',backgroundColor:'transparent',tension:0.3,fill:false,yAxisID:'rate',pointRadius:3,pointBackgroundColor:'#a78bfa'}},
  {{label:'90% target',type:'line',data:T90,borderColor:'rgba(167,139,250,0.3)',borderDash:[5,5],pointRadius:0,fill:false,yAxisID:'rate'}}
]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{...LG,labels:{{...LG.labels,filter:noT}}}},tooltip:TT}},scales:{{x:XA,y:YL(true),rate:RA}}}}}});

new Chart(document.getElementById('cCSAT'),{{type:'bar',data:{{labels:WK,datasets:[
  {{label:'5★',data:cs5,backgroundColor:'#22c55e',stack:'c'}},
  {{label:'4★',data:cs4,backgroundColor:'#86efac',stack:'c'}},
  {{label:'3★',data:cs3,backgroundColor:'#64748b',stack:'c'}},
  {{label:'2★',data:cs2,backgroundColor:'#f97316',stack:'c'}},
  {{label:'1★',data:cs1,backgroundColor:'#ef4444',stack:'c'}},
  {{label:'Avg Score',type:'line',data:csA,borderColor:'#a78bfa',backgroundColor:'transparent',tension:0.3,fill:false,yAxisID:'rate',pointRadius:3,pointBackgroundColor:'#a78bfa'}},
  {{label:'4.5 target',type:'line',data:Array(WK.length).fill(4.5),borderColor:'rgba(167,139,250,0.3)',borderDash:[5,5],pointRadius:0,fill:false,yAxisID:'rate'}}
]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{...LG,labels:{{...LG.labels,filter:no45}}}},tooltip:TT}},scales:{{x:XA,y:YL(true),rate:{{type:'linear',position:'right',min:0,max:5,ticks:{{color:'#a78bfa',callback:v=>v.toFixed(1)}},grid:{{display:false}}}}}}}}}});

new Chart(document.getElementById('cPVol'),{{type:'bar',data:{{labels:WK,datasets:[
  {{label:'P1',data:ptP1,backgroundColor:'#ef4444',stack:'t'}},
  {{label:'P2',data:ptP2,backgroundColor:'#f59e0b',stack:'t'}},
  {{label:'P3',data:ptP3,backgroundColor:'#3b82f6',stack:'t'}}
]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:LG,tooltip:TT}},scales:{{x:XA,y:YL(true)}}}}}});

new Chart(document.getElementById('cIVol'),{{type:'bar',data:{{labels:WK19,datasets:[
  {{label:'P1',data:iP1.slice(-WK19.length),backgroundColor:'#ef4444',stack:'i'}},
  {{label:'P2',data:iP2.slice(-WK19.length),backgroundColor:'#f59e0b',stack:'i'}},
  {{label:'P3',data:iP3.slice(-WK19.length),backgroundColor:'#3b82f6',stack:'i'}},
  {{label:'P4',data:iP4.slice(-WK19.length),backgroundColor:'#64748b',stack:'i'}},
  {{label:'Unknown',data:iUnk.slice(-WK19.length),backgroundColor:'#475569',stack:'i'}}
]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:LG,tooltip:TT}},scales:{{x:XA,y:YL(true)}}}}}});

new Chart(document.getElementById('cAVol'),{{type:'bar',data:{{labels:WK19,datasets:[
  {{label:'DMS',        data:aDMS.slice(-WK19.length), backgroundColor:'#38bdf8',stack:'a'}},
  {{label:'Grafana SOC',data:aSOC.slice(-WK19.length), backgroundColor:'#a78bfa',stack:'a'}},
  {{label:'HTTP',       data:aHTTP.slice(-WK19.length),backgroundColor:'#22c55e',stack:'a'}},
  {{label:'Grafana',    data:aGraf.slice(-WK19.length),backgroundColor:'#f59e0b',stack:'a'}},
  {{label:'FTML',       data:aFTML.slice(-WK19.length),backgroundColor:'#ec4899',stack:'a'}},
  {{label:'Intercom',   data:aIcom.slice(-WK19.length),backgroundColor:'#64748b',stack:'a'}},
  {{label:'Other',      data:aOther.slice(-WK19.length),backgroundColor:'#475569',stack:'a'}}
]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:LG,tooltip:TT}},scales:{{x:XA,y:YL(true)}}}}}});

new Chart(document.getElementById('cTBVol'),{{type:'bar',data:{{labels:WK19,datasets:[
  {{label:'Day (08–16 UTC)',    data:tbDay,   backgroundColor:'#38bdf8',stack:'tb'}},
  {{label:'Evening (16–00 UTC)',data:tbEve,   backgroundColor:'#f59e0b',stack:'tb'}},
  {{label:'Night (00–08 UTC)', data:tbNight, backgroundColor:'#64748b',stack:'tb'}}
]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:LG,tooltip:TT}},scales:{{x:XA,y:YL(true)}}}}}});

{pir_cat_chart_js}
{pir_trend_chart_js}
{eng_ac_chart_js}
{svc_charts_js}



let currentSlide = 0;
const slides = document.querySelectorAll('.slide');
const tabs   = document.querySelectorAll('.slide-tab');
function showSlide(n) {{
  const total = slides.length;
  n = ((n % total) + total) % total;
  slides[currentSlide].classList.remove('active');
  tabs[currentSlide].classList.remove('active');
  currentSlide = n;
  slides[currentSlide].classList.add('active');
  tabs[currentSlide].classList.add('active');
  document.getElementById('slide-counter').textContent = (currentSlide + 1) + ' / ' + total;
  if (typeof Chart !== 'undefined') Object.values(Chart.instances).forEach(c => c.resize());
}}
document.addEventListener('keydown', e => {{
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') showSlide(currentSlide + 1);
  if (e.key === 'ArrowLeft'  || e.key === 'ArrowUp')   showSlide(currentSlide - 1);
}});
</script>
</body>
</html>'''

with open(OUTPUT_FILE, "w") as f:
    f.write(html)

print(f"Report written to {OUTPUT_FILE}")
print(f"Current week: {current_week} ({cw_date})")
print(f"WK19 weeks: {WK19_KEYS}")
print(f"Brands top-10: {list(zip(bL, bC))}")
print(f"W21 incidents: {cw_inc_total} (P1:{cw_inc_p1} P2:{cw_inc_p2} P3:{cw_inc_p3})")
print(f"W21 alerts: {cw_alerts}")
print(f"W21 conv rate: {cw_conv_rate}%")
print(f"W21 partner tickets: {cw_pt_resp} (P1:{cw_pt_p1} P2:{cw_pt_p2} P3:{cw_pt_p3})")
print(f"W21 P2/P3 FRT SLA: {cw_p23_rate}%")
print(f"W21 CSAT: {cw_csat_avg}")
