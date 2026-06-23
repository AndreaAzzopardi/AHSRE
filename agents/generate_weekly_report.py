import json
import os
from datetime import datetime, timezone, timedelta
from collections import defaultdict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE     = os.path.join(_ROOT, "cache", "weekly_report_cache.json")
OUTPUT_FILE    = os.path.join(_ROOT, "cache", "weekly_report.html")

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

EXEC_NOTES_FILE = os.path.join(_ROOT, "cache", "exec_notes.json")
try:
    with open(EXEC_NOTES_FILE) as f:
        exec_notes_data = json.load(f).get("notes", [])
except FileNotFoundError:
    exec_notes_data = []

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
stat_week      = complete_weeks[-1]
stat_prev_week = complete_weeks[-2]

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

# MTTA — WK19 only
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
iUnk_arr = [get(wk, "incident_volume", "Unknown", default=0) for wk in WEEK_KEYS]

def _src(wk, *keys):
    return sum(get(wk, "alert_volume", "by_source", k, default=0) for k in keys)

aDMS_arr  = [_src(wk, "DMS", "Dead Mans Snitch", "Dead Man's Snitch") for wk in WEEK_KEYS]
aSOC_arr  = [_src(wk, "Grafana SOC", "Grafana SOC alerts") for wk in WEEK_KEYS]
aHTTP_arr = [_src(wk, "HTTP", "HTTP alerts") for wk in WEEK_KEYS]
aGraf_arr = [_src(wk, "Grafana", "Grafana alerts") for wk in WEEK_KEYS]
aIcom_arr = [_src(wk, "Intercom") for wk in WEEK_KEYS]
aFTML_arr = [_src(wk, "HTTP DMS FTML", "HTTP DMS FTML Alerts") for wk in WEEK_KEYS]
# PD-era sources (pre-W19)
aPD_SP_arr  = [get(wk, "alert_volume", "by_source", "Service Portal", default=0) for wk in WEEK_KEYS]
aPD_BO_arr  = [get(wk, "alert_volume", "by_source", "Backoffice", default=0) for wk in WEEK_KEYS]

# ── ALERT TIMEBLOCK (W19 onwards) ────────────────────────────────────────────
def tb_get(week, block, key, default=0):
    return (tb_cache.get(week, {}).get("blocks", {}).get(block, {}).get(key) or default)

def tb_week_val(week, key, default=None):
    return tb_cache.get(week, {}).get(key, default)

tbDay_arr    = [tb_get(wk, "day",     "total")     for wk in WK19_KEYS]
tbEve_arr    = [tb_get(wk, "evening", "total")     for wk in WK19_KEYS]
tbNight_arr  = [tb_get(wk, "night",   "total")     for wk in WK19_KEYS]
tbDayW_arr   = [tb_get(wk, "day",     "waste_pct") for wk in WK19_KEYS]
tbEveW_arr   = [tb_get(wk, "evening", "waste_pct") for wk in WK19_KEYS]
tbNightW_arr = [tb_get(wk, "night",   "waste_pct") for wk in WK19_KEYS]
tbTotalW_arr = [tb_week_val(wk, "overall_waste_pct") for wk in WK19_KEYS]

# ── STAT CARD CALCULATIONS ───────────────────────────────────────────────────
cw_date = fmt_date_dmy(stat_week)

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
cw_p1_ack_rate = get(stat_week, "mtta", "P1", "ack_rate")
p1_mtta_delta_cls, p1_mtta_delta = delta_str(cw_p1_mtta, pw_p1_mtta, " min", higher_is_better=False)
p1_ack_pct = f"{int(round(cw_p1_ack_rate*100))}%" if cw_p1_ack_rate is not None else "—"
p1_ack_cls = "c-green" if cw_p1_ack_rate and cw_p1_ack_rate >= 1.0 else "c-amber"

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
inc_delta_cls, inc_delta = delta_str(cw_inc_total, pw_inc_total, "", higher_is_better=False, decimals=0)

cw_alerts = get(stat_week, "alert_volume", "total", default=0)
pw_alerts = get(stat_prev_week, "alert_volume", "total", default=0)
alerts_delta_cls, alerts_delta = delta_str(cw_alerts, pw_alerts, "", higher_is_better=False, decimals=0)
if cw_alerts == 0:
    alerts_cls = "c-muted"
elif cw_alerts <= 400:
    alerts_cls = "c-green"
elif cw_alerts <= 600:
    alerts_cls = "c-amber"
else:
    alerts_cls = "c-red"

cw_p1_ack_rate_s3 = get(stat_week, "mtta", "P1", "ack_rate")
pw_p1_ack_rate_s3 = get(stat_prev_week, "mtta", "P1", "ack_rate")
cw_ack_pct = f"{int(round(cw_p1_ack_rate_s3*100))}%" if cw_p1_ack_rate_s3 is not None else "—"
cw_ack_cls = "c-green" if cw_p1_ack_rate_s3 and cw_p1_ack_rate_s3 >= 1.0 else "c-amber"
if cw_p1_ack_rate_s3 and pw_p1_ack_rate_s3:
    ack_diff = round((cw_p1_ack_rate_s3 - pw_p1_ack_rate_s3)*100, 1)
    if abs(ack_diff) < 0.1:
        ack_delta_cls, ack_delta = "d-muted", f"0% vs wk {fmt_date_dmy(stat_prev_week)}"
    elif ack_diff > 0:
        ack_delta_cls, ack_delta = "d-green", f"+{ack_diff}% vs wk {fmt_date_dmy(stat_prev_week)}"
    else:
        ack_delta_cls, ack_delta = "d-red", f"−{abs(ack_diff)}% vs wk {fmt_date_dmy(stat_prev_week)}"
else:
    ack_delta_cls, ack_delta = "d-muted", f"— vs wk {fmt_date_dmy(stat_prev_week)}"

cw_conv_rate = round(cw_inc_total / cw_alerts * 100, 1) if cw_alerts else None
pw_conv_rate = round(pw_inc_total / pw_alerts * 100, 1) if pw_alerts else None
conv_delta_cls, conv_delta = delta_str(cw_conv_rate, pw_conv_rate, "%", higher_is_better=False)

# ── BREACH BLOCKS ────────────────────────────────────────────────────────────
week_label_long = f"Week of {fmt_date_dmy(stat_week)} {datetime.strptime(stat_week, '%Y-%m-%d').year}"

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

def _collect_all_relevant_p1s():
    seen = set()
    result = []
    for inc in (cache.get(stat_week, {}).get("true_p1_incidents") or []):
        ref = inc.get("reference", "")
        seen.add(ref)
        result.append(inc)
    for wk in reversed(WEEK_KEYS):
        if wk == stat_week:
            continue
        for inc in (cache.get(wk, {}).get("true_p1_incidents") or []):
            ref = inc.get("reference", "")
            if ref not in seen and _p1_status_cls(inc.get("status", "")) != "c-green":
                seen.add(ref)
                result.append(inc)
    return result

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

def _build_p1_full_cards(incidents):
    if not incidents:
        return '    <div class="p1-no-data c-muted">No True P1 incidents this week.</div>'
    cards = []
    for inc in incidents:
        status = inc.get("status", "—")
        sc = _p1_status_cls(status)
        status_label, _ = _exec_status(status)
        dt_str = _fmt_dt_short(inc.get("reported_at", ""))
        ref = inc.get("reference", "")
        name = inc.get("name", "")
        name = _clean_inc_name(name)
        href = inc.get("permalink", "")
        ref_html = f'<a href="{href}" target="_blank" class="p1-ref">{ref}</a>' if href else f'<span class="p1-ref">{ref}</span>'
        sections = _parse_summary_sections(inc.get("summary", ""))
        sections_html = ""
        for label, body in sections:
            if label:
                sections_html += f'      <div class="p1-section"><div class="p1-section-label">{label}</div><div class="p1-section-body">{body}</div></div>\n'
            else:
                sections_html += f'      <div class="p1-section"><div class="p1-section-body">{body}</div></div>\n'
        active_cls = " active" if not cards else ""
        cards.append(f'''    <div class="p1-full-card{active_cls}" data-ref="{ref}">
      <div class="p1-inc-header">
        {ref_html}
        <span class="p1-status-badge {sc}">{status_label}</span>
        <span class="p1-inc-date">{dt_str}</span>
      </div>
      <div class="p1-inc-title">{name}</div>
      <div class="p1-sections">
{sections_html}      </div>
    </div>''')
    return "\n".join(cards)

_all_p1s = _collect_all_relevant_p1s()
p1_full_cards_html = _build_p1_full_cards(_all_p1s)

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
pir_no_due_count = pir_cache.get("no_due_date_count", 0)
pir_no_due_pct   = pir_cache.get("no_due_date_pct", 0.0)
pir_teams        = pir_cache.get("teams", [])
pir_categories   = pir_cache.get("categories", {})

pir_comp_cls   = "c-green" if pir_comp_rate >= 85 else "c-amber" if pir_comp_rate >= 65 else "c-red"
pir_stale_cls  = "c-red" if pir_stale_pct >= 50 else "c-amber" if pir_stale_pct >= 25 else "c-green"
pir_no_due_cls = "c-red" if pir_no_due_pct >= 75 else "c-amber" if pir_no_due_pct >= 50 else "c-green"

pir_cat_labels  = list(pir_categories.keys())
pir_cat_open    = [v.get("open", 0)   if isinstance(v, dict) else v for v in pir_categories.values()]
pir_cat_closed  = [v.get("closed", 0) if isinstance(v, dict) else 0 for v in pir_categories.values()]

# Top 5 pain points — sorted by open count descending
_pir_cat_sorted = sorted(
    [(k, v.get("open", 0), v.get("closed", 0)) for k, v in pir_categories.items()],
    key=lambda x: x[1], reverse=True
)[:5]
pir_top5_labels = [x[0] for x in _pir_cat_sorted]
pir_top5_open   = [x[1] for x in _pir_cat_sorted]
pir_top5_done   = [x[2] for x in _pir_cat_sorted]

pir_teams_chart = sorted([t for t in pir_teams if t.get("open", 0) > 0], key=lambda t: t["open"], reverse=True)
pir_team_labels = [t["name"]      for t in pir_teams_chart]
pir_team_open   = [t["open"]      for t in pir_teams_chart]
pir_team_closed = [t["completed"] for t in pir_teams_chart]
pir_team_table_html = render_pir_team_table(pir_teams)

# ── PIR HISTORY — write current week snapshot & build chart arrays ────────────
_pir_snap_key = pir_cache.get("generated", current_week)
pir_history[_pir_snap_key] = {
    "open":      pir_open,
    "completed": pir_completed,
    "total":     pir_total,
    "rate":      round(pir_comp_rate, 1),
}
with open(PIR_HISTORY_FILE, "w") as _f:
    json.dump(dict(sorted(pir_history.items())), _f, indent=2)

_pir_hist_keys  = sorted(pir_history.keys())
pir_hist_labels = [fmt_week_label(k, False) for k in _pir_hist_keys]
pir_hist_rate   = [pir_history[k]["rate"] for k in _pir_hist_keys]

# ── P1 INCIDENT SLIDE GENERATION ─────────────────────────────────────────────
_p1_chunks    = [[inc] for inc in _all_p1s] if _all_p1s else [[]]
_n_p1_slides  = len(_p1_chunks)
_idx_p1perf   = 1
_idx_pir      = 2 + _n_p1_slides
_idx_partner  = _idx_pir + 1
_idx_ops      = _idx_partner + 1
_idx_eng      = _idx_ops + 1
_total_slides = _idx_eng + 1

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

def eng_weekly_series(week_keys, names):
    """Per-engineer per-week aggregates, computed from the raw tickets of each week."""
    series = {n: {"led": [], "closed": [], "open": [], "avg_h": []} for n in names}
    for wk in week_keys:
        tickets = ((cache.get(wk, {}) or {}).get("engineer_workload") or {}).get("tickets") or []
        eng, _ = compute_engineer_workload(tickets)
        for n in names:
            e = eng.get(n) or {}
            series[n]["led"].append(e.get("led", 0))
            series[n]["closed"].append(e.get("closed", 0))
            series[n]["open"].append(e.get("open", 0))
            avg = e.get("avg_resolve_min")
            series[n]["avg_h"].append(round(avg / 60.0, 1) if avg is not None else None)
    return series

eng_series    = eng_weekly_series(eng_week_keys, ENG_FOCUS)
eng_wk_labels = [datetime.strptime(k, "%Y-%m-%d").strftime("%-d %b") for k in eng_week_keys]

def render_engineer_workload_slide():
    if not eng_week_keys:
        body = '    <div class="p1-no-data c-muted">No engineer workload data yet.</div>'
        return f'''<!-- ═══ SLIDE — ENGINEER WORKLOAD ═══ -->
<div class="slide" id="sEng"><div class="page">
  <div class="group-label">Engineer Workload</div>
{body}
</div></div>'''

    last = len(eng_week_keys) - 1
    prev = last - 1 if len(eng_week_keys) >= 2 else None
    _latest_lbl = eng_wk_labels[last]

    def _delta(cur, prv):
        if prv is None or cur is None or cur == prv:
            return '<span style="color:#64748b;font-size:11px">&middot; WoW flat</span>'
        d = cur - prv
        arrow = "&#9650;" if d > 0 else "&#9660;"
        return f'<span style="color:#94a3b8;font-size:11px">&middot; {arrow}{abs(d)} WoW</span>'

    cards = []
    for n in ENG_FOCUS:
        s = eng_series[n]
        led = s["led"][last]; closed = s["closed"][last]; op = s["open"][last]
        avg = s["avg_h"][last]
        led_prev = s["led"][prev] if prev is not None else None
        open_cls = "c-red" if op >= 3 else "c-amber" if op >= 1 else "c-muted"
        if avg is None:
            avg_html = '<span class="c-muted">&mdash;</span>'
        else:
            acls = "c-red" if avg > 72 else "c-amber" if avg > 24 else "c-green"
            avg_html = f'<span class="{acls}">{avg:.1f}h</span>'
        cards.append(f'''      <div class="stat-card" style="border-left:3px solid {ENG_COLORS[n]}">
        <div style="display:flex;align-items:center;gap:7px;margin-bottom:6px">
          <span style="width:9px;height:9px;border-radius:50%;background:{ENG_COLORS[n]};display:inline-block"></span>
          <span style="font-size:13px;font-weight:700;color:#e2e8f0">{ENG_SHORT[n]}</span>
        </div>
        <div style="display:flex;align-items:baseline;gap:8px">
          <span style="font-family:'DM Mono',monospace;font-size:28px;font-weight:700;color:#e2e8f0">{led}</span>
          <span style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.05em">tickets led</span>
          {_delta(led, led_prev)}
        </div>
        <div style="display:flex;gap:14px;margin-top:8px;font-size:12px">
          <span><span class="c-green">{closed}</span> <span style="color:#64748b">closed</span></span>
          <span><span class="{open_cls}">{op}</span> <span style="color:#64748b">open</span></span>
          <span>{avg_html} <span style="color:#64748b">avg resolve</span></span>
        </div>
      </div>''')
    cards_html = "\n".join(cards)

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
    <div style="flex:1;min-width:0;display:flex;flex-direction:column;background:#0d1629;border:1px solid rgba(255,255,255,0.07);border-radius:8px;padding:12px 14px">
      <div style="font-size:12px;font-weight:700;color:#cbd5e1;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:8px;flex-shrink:0">Tickets Led per Week</div>
      <div class="chart-container"><canvas id="cEngLed" style="width:100%;height:100%"></canvas></div>
    </div>
    <div style="flex:1;min-width:0;display:flex;flex-direction:column;background:#0d1629;border:1px solid rgba(255,255,255,0.07);border-radius:8px;padding:12px 14px">
      <div style="font-size:12px;font-weight:700;color:#cbd5e1;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:8px;flex-shrink:0">Avg Resolution Time per Week</div>
      <div class="chart-container"><canvas id="cEngAvg" style="width:100%;height:100%"></canvas></div>
    </div>
  </div>
  <div style="font-size:11px;color:#475569;margin-top:8px">Source: incident.io IC-Ticket incidents (Intercom partner tickets), by Incident Lead. Avg Resolution = mean reported&rarr;resolved wall-clock; gaps = none resolved that week. Full all-team roster retained in cache.</div>
</div></div>'''

engineer_workload_slide_html = render_engineer_workload_slide()

# ── ENGINEER WORKLOAD CHART JS (pre-built to avoid f-string brace-escaping) ──
_eng_lbl_js = js_str_arr(eng_wk_labels)
eng_led_chart_js = (
    "new Chart(document.getElementById('cEngLed'),{type:'bar',data:{labels:" + _eng_lbl_js + ",datasets:["
    + ",".join(
        "{label:'" + ENG_SHORT[n] + "',data:" + js_arr(eng_series[n]["led"])
        + ",backgroundColor:'" + ENG_COLORS[n] + "',barPercentage:0.85,categoryPercentage:0.7}"
        for n in ENG_FOCUS)
    + "]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:LG,tooltip:TT},"
      "scales:{x:XA,y:YL(false)}}});"
) if eng_week_keys else ""
eng_avg_chart_js = (
    "new Chart(document.getElementById('cEngAvg'),{type:'line',data:{labels:" + _eng_lbl_js + ",datasets:["
    + ",".join(
        "{label:'" + ENG_SHORT[n] + "',data:" + js_arr(eng_series[n]["avg_h"])
        + ",borderColor:'" + ENG_COLORS[n] + "',backgroundColor:'transparent',tension:0.3,fill:false,"
          "spanGaps:true,pointRadius:4,pointBackgroundColor:'" + ENG_COLORS[n] + "'}"
        for n in ENG_FOCUS)
    + "]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:LG,tooltip:TT},"
      "scales:{x:XA,y:{type:'linear',min:0,ticks:{color:'#64748b',callback:function(v){return v+'h'}},"
      "grid:{color:'rgba(255,255,255,0.05)'}}}}});"
) if eng_week_keys else ""

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
        <span class="p1-inc-date">{dt_str}</span>
      </div>
      <div class="p1-inc-title">{name}</div>
      <div class="p1-sections">
{sections_html}      </div>
    </div>''')
    return "\n".join(cards)

p1_tab_btns_html = ""
p1_all_slides_html = ""
for _i, _chunk in enumerate(_p1_chunks):
    _si = 2 + _i
    _tab_lbl   = "P1 Incidents" if _n_p1_slides == 1 else f"P1 Incidents {_i+1}/{_n_p1_slides}"
    _grp_lbl   = "P1 Incidents" if _n_p1_slides == 1 else f"P1 Incidents · {_i+1} of {_n_p1_slides}"
    _chars     = sum(len(inc.get("summary", "")) for inc in _chunk)
    _fs        = 13 if _chars > 2000 else (14 if _chars > 1400 else 15)
    p1_tab_btns_html += f'    <button class="slide-tab" onclick="showSlide({_si})">{_tab_lbl}</button>\n'
    _cards = _build_p1_pair_cards(_chunk)
    p1_all_slides_html += f'''
<!-- ═══ P1 INCIDENTS {_i+1} ════════════════════════════════════ -->
<div class="slide" id="s1_{_i+1}"><div class="page">
  <div class="group-label">{_grp_lbl} · {cw_date}</div>
  <div class="p1-two-up" style="font-size: {_fs}px;">
{_cards}
  </div>
</div></div>
'''

# ── EXECUTIVE SUMMARY SLIDE (pre-built to avoid f-string brace-escaping) ─────
# Exec slide always reports on the last complete week (prev_week), not the partial current week
_ew         = prev_week
_ew_true_p1 = p1_quality_row(_ew)[0]
_ew_p1_frt  = get(_ew, "p1_frt_sla", "hit_rate")
_ew_csat    = get(_ew, "csat", "avg_score")
_ew_p23     = get(_ew, "p2p3_frt_sla", "hit_rate")
_ew_p1_incs = cache.get(_ew, {}).get("true_p1_incidents") or []
_ew_date    = fmt_date_dmy(_ew)
_ew_end     = fmt_date_dmy((datetime.strptime(_ew, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d"))
_ew_range   = f"{_ew_date} – {_ew_end}"

_p1_val_color  = 'c-green' if _ew_true_p1 == 0 else 'c-red'
_p1_frt_color  = color_pct(_ew_p1_frt)
_csat_color    = color_csat(_ew_csat)
_p23_color     = color_pct(_ew_p23)

# 12-week average for true P1s (all complete weeks before current)
_p1_12wk_keys = WEEK_KEYS[:-1]
_p1_12wk_vals = [p1_quality_row(wk)[0] for wk in _p1_12wk_keys]
_p1_12wk_vals = [v for v in _p1_12wk_vals if v is not None]
_p1_4wk_avg   = round(sum(_p1_12wk_vals) / len(_p1_12wk_vals), 1) if _p1_12wk_vals else None
_p1_12wk_n    = len(_p1_12wk_vals)

# 12-week averages for exec banner chips (all complete weeks before current)
_frt_prior   = [v for v in p1Rate_arr[:-1]  if v is not None]
_csat_prior  = [v for v in csA_arr[:-1]     if v is not None]
_p23_prior   = [v for v in p23Rate_arr[:-1] if v is not None]
_exec_frt_avg  = round(sum(_frt_prior)  / len(_frt_prior))  if _frt_prior  else None
_exec_csat_avg = round(sum(_csat_prior) / len(_csat_prior), 2) if _csat_prior else None
_exec_p23_avg  = round(sum(_p23_prior)  / len(_p23_prior))  if _p23_prior  else None
_exec_p1_avg   = round(sum(_p1_12wk_vals) / len(_p1_12wk_vals)) if _p1_12wk_vals else None

# Story narrative — two lines: incident quality headline + PIR concern
import math as _math
def _build_exec_narrative():
    _avg = _math.ceil(_p1_4wk_avg) if _p1_4wk_avg is not None else None
    _n   = _p1_12wk_n
    _active_n = sum(1 for inc in _ew_p1_incs
                    if inc.get("status", "").lower() not in ("closed", "resolved", "postmortem"))
    # Line 1: incident quality headline
    if _ew_true_p1 == 0:
        _l1 = "No True P1 incidents this week — all response and quality metrics are on target."
    elif _avg is not None and _ew_true_p1 <= _avg:
        _mon = (f" {_active_n} incident{'s' if _active_n != 1 else ''} still in Monitoring, awaiting resolution."
                if _active_n else "")
        _l1 = (f"Incident handling is in good shape — response times, SLAs, and CSAT are all on target "
               f"and trending in the right direction. P1 count is consistent with the {_n}-week average.{_mon}")
    else:
        _parts = []
        if _avg is not None and _ew_true_p1 > _avg:
            _parts.append(f"{_ew_true_p1} True P1s vs {_avg}/wk {_n}-week average")
        if _ew_p1_frt is not None and _ew_p1_frt < 0.90:
            _parts.append(f"P1 FRT SLA {fmt_rate(_ew_p1_frt, 0)}")
        if _ew_csat is not None and _ew_csat < 4.5:
            _parts.append(f"CSAT {fmt_csat(_ew_csat)}")
        _mon = (f" {_active_n} incident{'s' if _active_n != 1 else ''} still open."
                if _active_n else "")
        _l1 = (f"Elevated week — {'; '.join(_parts)}.{_mon}" if _parts
               else f"Elevated week — {_ew_true_p1} True P1s this week.{_mon}")
    # Line 2: PIR concern (shown when below 85% target)
    _l2 = ""
    if pir_comp_rate < 85:
        _pct = int(round(pir_comp_rate))
        _worst = sorted([t for t in pir_teams if t.get("open", 0) > 0],
                        key=lambda t: t.get("open", 0), reverse=True)
        if len(_worst) >= 2:
            _l2 = (f"The key concern remains PIR action completion — at {_pct}% against a target of 85%, "
                   f"this is a persistent gap. {_worst[0]['name']} ({_worst[0]['open']} open) and "
                   f"{_worst[1]['name']} ({_worst[1]['open']} open) are the largest contributors and need attention.")
        elif len(_worst) == 1:
            _l2 = (f"The key concern remains PIR action completion — at {_pct}% against a target of 85%. "
                   f"{_worst[0]['name']} ({_worst[0]['open']} open) is the largest contributor.")
        else:
            _l2 = f"PIR action completion is at {_pct}% vs 85% target — needs attention."
    return _l1, _l2
_exec_line1, _exec_line2 = _build_exec_narrative()

# Brands affected this week (exec week = prev_week)
_cw_brands_raw = cache.get(_ew, {}).get("p1_brands", {})
_cw_brand_list = sorted(
    [(b, c) for b, c in _cw_brands_raw.items() if b and b not in ("", "None", "No company")],
    key=lambda x: x[1], reverse=True
)[:5]
_brands_line = ""
if _cw_brand_list:
    _brands_line = "  ".join(
        f'<span style="background:rgba(56,189,248,0.1);border:1px solid rgba(56,189,248,0.2);border-radius:4px;padding:2px 8px;font-size:11px;color:#93c5fd">{b} <span style="font-family:DM Mono,monospace;font-weight:600">{c}</span></span>'
        for b, c in _cw_brand_list
    )

# Plain-English status with risk framing
# PIR worst offender (most open items, not at 100%)
_pir_worst_team = None
for _t in pir_teams:
    _tt = _t["open"] + _t["completed"]
    if _tt == 0 or _t["open"] == 0:
        continue
    if _pir_worst_team is None or _t["open"] > _pir_worst_team["open"]:
        _pir_worst_team = {**_t, "rate_pct": int(round(_t["completed"] / _tt * 100))}

# P1 incidents compact list — one header row + one detail line per incident
import re as _re
def _first_sentence(txt):
    m = _re.search(r'[.!?]', txt)
    return txt[:m.end()].strip() if m else txt.strip()

_p1_inc_n      = len(_ew_p1_incs)
_inc_detail_sz = "11px" if _p1_inc_n >= 3 else "12px"

_exec_inc_rows = ""
if _ew_p1_incs:
    for _inc in _ew_p1_incs[:6]:
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
    _n_more_exec = len(_ew_p1_incs) - 6
    if _n_more_exec > 0:
        _exec_inc_rows += f'<div style="font-size:12px;color:#475569;padding-top:8px">+{_n_more_exec} more — see P1 Incidents slides</div>'
else:
    _exec_inc_rows = '<div style="font-size:13px;color:#22c55e;padding:10px 0">No True P1 incidents this week.</div>'

# Overall RAG status for exec slide
# CRITICAL   = P1s still actively impacting users (not in Monitoring/Resolved)
# MONITORING = P1 count significantly above the rolling average
# STABLE     = P1s on trend, all in Monitoring or Resolved, or no P1s with prior risks
# ON TRACK   = no P1s at all this week
_current_week_refs   = {inc.get("reference", "") for inc in _ew_p1_incs}
_prior_open_p1s      = [inc for inc in _all_p1s if inc.get("reference", "") not in _current_week_refs]
_has_prior_risk      = len(_prior_open_p1s) > 0
_has_truly_active_p1 = any(
    inc.get("status", "").lower() not in ("closed", "resolved", "postmortem", "monitoring", "documenting")
    for inc in _ew_p1_incs
)
_p1_above_avg        = (
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

# P1 MTTA colour for exec card
_mtta_color   = "c-muted"
if cw_p1_mtta is not None:
    _mtta_color = "c-green" if cw_p1_mtta <= 15 else ("c-amber" if cw_p1_mtta <= 30 else "c-red")
_mtta_val_str = f"{round(cw_p1_mtta, 1)}" if cw_p1_mtta is not None else "—"

# Prior-week open P1 rows (Open Risks section)
_prior_risk_rows = ""
for _inc in _prior_open_p1s[:5]:
    _ref  = _inc.get("reference", "")
    _nm   = _inc.get("name", "")
    if _nm.startswith("[P1] Intercom Incident : "): _nm = _nm[25:]
    elif _nm.startswith("[P1] "): _nm = _nm[5:]
    _st_raw = _inc.get("status", "—")
    _st_label_r, _st_col_r = _exec_status(_st_raw)
    _href = _inc.get("permalink", "")
    _rh_r = (f'<a href="{_href}" target="_blank" style="font-family:DM Mono,monospace;font-size:11px;color:#38bdf8;text-decoration:none;font-weight:500;white-space:nowrap">{_ref}</a>'
             if _href else f'<span style="font-family:DM Mono,monospace;font-size:11px;color:#38bdf8;font-weight:500;white-space:nowrap">{_ref}</span>')
    _secs_r = {lbl: body for lbl, body in _parse_summary_sections(_inc.get("summary", ""))}
    _impact_r = _secs_r.get("Impact", _secs_r.get("Problem", ""))
    _prior_risk_rows += (
        f'<div style="padding:7px 0;border-bottom:1px solid rgba(255,255,255,0.04)">'
        f'<div style="display:flex;align-items:baseline;gap:7px;margin-bottom:3px">'
        f'{_rh_r}'
        f'<span style="flex:1;font-size:11px;color:#e2e8f0;font-weight:600;line-height:1.3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{_nm}">{_nm}</span>'
        f'<span style="font-size:10px;font-weight:700;padding:1px 6px;border-radius:3px;background:rgba(245,158,11,0.1);color:{_st_col_r};white-space:nowrap">{_st_label_r}</span>'
        f'</div>'
        + (f'<div style="font-size:10px;color:#64748b;line-height:1.4;padding-left:2px">{_impact_r[:120]}{"…" if len(_impact_r) > 120 else ""}</div>' if _impact_r else '')
        + f'</div>'
    )
if not _prior_risk_rows:
    _prior_risk_rows = '<div style="font-size:12px;color:#22c55e;padding:10px 0;display:flex;align-items:center;gap:6px"><span style="font-size:16px">✓</span> No open risks carried from prior weeks.</div>'

# Exec metric chips — 3-col grid in status banner
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
# PIR Completion
_pir_chip_color = "#22c55e" if pir_comp_rate >= 85 else ("#f59e0b" if pir_comp_rate >= 65 else "#ef4444")
_pir_chip_bg    = ("rgba(34,197,94,0.07)"  if pir_comp_rate >= 85 else
                   "rgba(245,158,11,0.07)" if pir_comp_rate >= 65 else "rgba(239,68,68,0.07)")
_pir_chip_bdr   = ("rgba(34,197,94,0.20)"  if pir_comp_rate >= 85 else
                   "rgba(245,158,11,0.25)" if pir_comp_rate >= 65 else "rgba(239,68,68,0.25)")
_pir_ctx_txt    = "target 85% ⚠" if pir_comp_rate < 85 else "target 85% ✓"
_pir_ctx_col    = "#f59e0b"       if pir_comp_rate < 85 else "#22c55e"
_exec_chips.append(_exec_chip("PIR Completion", fmt_rate(pir_comp_rate, 0), _pir_ctx_txt,
                               _pir_chip_color, _pir_chip_bg, _pir_chip_bdr, _pir_ctx_col))

_exec_chip_grid_html = (
    '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;'
    'padding-top:6px;border-top:1px solid rgba(255,255,255,0.05)">'
    + ''.join(_exec_chips)
    + '</div>'
)

# ── Dynamic exec body layout — no scrolling anywhere ─────────────────────────
# Both panels share the body via flex. Overflow is hidden (clips silently).
# P1 incidents flex grows with incident count so it gets more room when needed.
if _p1_inc_n == 0:
    _p1_inc_flex = "0 0 auto"   # just the "no incidents" message
elif _p1_inc_n == 1:
    _p1_inc_flex = "0.7"
elif _p1_inc_n == 2:
    _p1_inc_flex = "1.0"
else:
    _p1_inc_flex = "1.4"        # 3+ incidents, takes more of the body

# Detail row font: shrink when many incidents so rows fit in the allotted flex space
_inc_detail_sz = "11px" if _p1_inc_n >= 3 else "12px"

# Notes & Context layout
_notes_n     = len(exec_notes_data)
_notes_chars = sum(len(n.get("title","")) + len(n.get("body","")) for n in exec_notes_data)
# Column count: 1 note or long content → single column; otherwise 2 columns
if _notes_n <= 1 or _notes_chars > 650:
    _notes_cols = 1
else:
    _notes_cols = 2
# Font size: scale down as content grows
if _notes_chars > 800:
    _notes_title_sz, _notes_body_sz, _notes_lh = "12px", "11px", "1.5"
elif _notes_chars > 480:
    _notes_title_sz, _notes_body_sz, _notes_lh = "13px", "12px", "1.5"
else:
    _notes_title_sz, _notes_body_sz, _notes_lh = "13px", "13px", "1.6"

exec_slide_html = (
    '<!-- ═══ SLIDE 0 — EXECUTIVE SUMMARY ════════════════════════ -->\n'
    '<div class="slide active" id="sExec"><div class="page">\n'
    f'  <div class="group-label">Executive Summary · {_ew_range}</div>\n'

    # ── STATUS BANNER ──────────────────────────────────────────────────────────
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

    # ── SIDE-BY-SIDE BODY: P1 Incidents (left) | Notes & Context (right) ────
    '  <div style="flex:1;min-height:0;display:flex;flex-direction:row;gap:10px">\n'

    # Left — P1 Incidents This Week
    + f'    <div style="flex:1.1;min-width:0;min-height:0;overflow:hidden;display:flex;flex-direction:column;background:#0d1629;border:1px solid rgba(255,255,255,0.07);border-radius:8px;padding:12px 16px">\n'
    + f'      <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid rgba(255,255,255,0.05);flex-shrink:0">\n'
    + f'        <span style="font-size:13px;font-weight:700;color:#e2e8f0;letter-spacing:0.07em;text-transform:uppercase">P1 Incidents This Week</span>\n'
    + f'        <span style="font-size:12px;color:#475569">{_ew_range} · {_ew_true_p1} incident{"s" if _ew_true_p1 != 1 else ""}</span>\n'
    + f'      </div>\n'
    + _exec_inc_rows
    + '\n    </div>\n'

    # Right — Notes & Context
    + (
        f'    <div style="flex:1;min-width:0;min-height:0;overflow:hidden;display:flex;flex-direction:column;background:#0d1629;border:1px solid rgba(255,255,255,0.07);border-radius:8px;padding:12px 16px">\n'
        f'      <div style="font-size:13px;font-weight:700;color:#e2e8f0;letter-spacing:0.07em;text-transform:uppercase;margin-bottom:8px;flex-shrink:0">Notes & Context</div>\n'
        f'      <div style="display:flex;flex-direction:column;gap:10px">\n'
        + ''.join(
            f'        <div style="padding:10px 12px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:6px">'
            f'<div style="font-size:{_notes_title_sz};font-weight:700;color:#cbd5e1;margin-bottom:4px">{n["title"]}</div>'
            f'<div style="font-size:{_notes_body_sz};color:#94a3b8;line-height:{_notes_lh}">{n["body"]}</div>'
            f'</div>\n'
            for n in exec_notes_data
        )
        + f'      </div>\n'
        + f'    </div>\n'
        if exec_notes_data else
        f'    <div style="flex:1;min-width:0;min-height:0;display:flex;align-items:center;justify-content:center;background:#0d1629;border:1px solid rgba(255,255,255,0.07);border-radius:8px">'
        f'<span style="font-size:12px;color:#475569">No notes — add items to cache/exec_notes.json</span></div>\n'
    )

    + '  </div>\n'
    + '</div></div>\n'
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
pir_trend_chart_js = (
    "new Chart(document.getElementById('cPIRTrend'),{"
    "type:'line',data:{labels:" + _pir_hist_lbl_js + ",datasets:["
    "{label:'Completion %',data:" + _pir_hist_rate_js + ","
    "borderColor:'#a78bfa',backgroundColor:'rgba(167,139,250,0.08)',tension:0.3,fill:true,"
    "pointRadius:5,pointBackgroundColor:'#a78bfa',pointBorderColor:'#0d1629',pointBorderWidth:2},"
    "{label:'Target 85%',data:Array(" + str(len(pir_hist_rate)) + ").fill(85),"
    "borderColor:'#22c55e',borderDash:[5,4],borderWidth:2,pointRadius:0,fill:false,tension:0}"
    "]},options:{responsive:true,maintainAspectRatio:false,"
    "plugins:{legend:LG,tooltip:TT},"
    "scales:{x:{ticks:{color:'#64748b',font:{size:11}},grid:{color:'rgba(255,255,255,0.05)'}},"
    "y:{type:'linear',min:0,max:100,ticks:{color:'#64748b',stepSize:20,callback:function(v){return v+'%'}},grid:{color:'rgba(255,255,255,0.05)'}}}}"
    "});"
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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
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
    <button class="slide-tab" onclick="showSlide({_idx_eng})">Engineer Workload</button>
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
  <div class="stat-grid-3">
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
    <div class="stat-card">
      <div class="card-label">No Due Date Set</div>
      <div class="card-value {pir_no_due_cls}">{int(round(pir_no_due_pct))}%</div>
      <div class="card-subnote">{pir_no_due_count} of {pir_open} open items</div>
      <div class="card-subnote">Target: &lt;25% without date</div>
    </div>
  </div>
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
  <div class="stat-grid-4">
    <div class="stat-card">
      <div class="card-label">Incidents This Week ({cw_date})</div>
      <div class="card-value c-muted">{cw_inc_total}</div>
      <div class="card-subnote">P1: {cw_inc_p1} &middot; P2: {cw_inc_p2} &middot; P3: {cw_inc_p3}</div>
      <div class="card-delta {inc_delta_cls}">{inc_delta}</div>
    </div>
    <div class="stat-card">
      <div class="card-label">Alerts This Week ({cw_date})</div>
      <div class="card-value {alerts_cls}">{cw_alerts}</div>
      <div class="card-subnote">Target: &lt;400/wk</div>
      <div class="card-delta {alerts_delta_cls}">{alerts_delta}</div>
    </div>
    <div class="stat-card">
      <div class="card-label">P1 Ack Rate ({cw_date})</div>
      <div class="card-value {cw_ack_cls}">{cw_ack_pct}</div>
      <div class="card-delta {ack_delta_cls}">{ack_delta}</div>
    </div>
    <div class="stat-card">
      <div class="card-label">Alert&#x2192;Incident Rate ({cw_date})</div>
      <div class="card-value c-muted">{fmt_conv_rate(cw_conv_rate)}</div>
      <div class="card-delta {conv_delta_cls}">{conv_delta}</div>
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
        <div class="chart-title">MTTA by Severity</div>
        <div class="chart-note">incident.io &middot; {wk19_first_dt.day if wk19_first_dt else '4'} {wk19_first_dt.strftime('%b %Y') if wk19_first_dt else 'May 2026'} onwards &middot; Median min to ack &middot; P1/P2/P3</div>
        <div class="chart-container"><canvas id="cMTTA" style="width:100%;height:100%"></canvas></div>
      </div>
    </div>
    <div class="chart-row">
      <div class="chart-section">
        <div class="chart-title">Accepted & Declined by Time Block</div>
        <div class="chart-note">incident.io &middot; W19 onwards &middot; 8-hr UTC blocks &middot; Line = overall noise rate %</div>
        <div class="chart-container"><canvas id="cTBVol" style="width:100%;height:100%"></canvas></div>
      </div>
      <div class="chart-section">
        <div class="chart-title">Declined Rate by Time Block</div>
        <div class="chart-note">incident.io &middot; W19 onwards &middot; Declined as % of total per block per week</div>
        <div class="chart-container"><canvas id="cTBWaste" style="width:100%;height:100%"></canvas></div>
      </div>
    </div>
  </div>
</div></div>

{engineer_workload_slide_html}

</div><!-- /slides-wrap -->

<div class="slide-controls">
  <button class="slide-btn" onclick="showSlide(currentSlide-1)">&#8592; Prev</button>
  <span class="slide-counter" id="slide-counter">1 / {_total_slides}</span>
  <button class="slide-btn" onclick="showSlide(currentSlide+1)">Next &#8594;</button>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
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

const mP1 = {js_arr(mP1_arr)};
const mP2 = {js_arr(mP2_arr)};
const mP3 = {js_arr(mP3_arr)};

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
const aPD_SP  = {js_arr(aPD_SP_arr)};
const aPD_BO  = {js_arr(aPD_BO_arr)};

const tbDay    = {js_arr(tbDay_arr)};
const tbEve    = {js_arr(tbEve_arr)};
const tbNight  = {js_arr(tbNight_arr)};
const tbDayW   = {js_arr(tbDayW_arr)};
const tbEveW   = {js_arr(tbEveW_arr)};
const tbNightW = {js_arr(tbNightW_arr)};
const tbTotalW = {js_arr(tbTotalW_arr)};

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

new Chart(document.getElementById('cMTTA'),{{type:'line',data:{{labels:WK19,datasets:[
  {{label:'P1 Median',data:mP1.slice(-WK19.length),borderColor:'#ef4444',backgroundColor:'transparent',tension:0.3,fill:false,spanGaps:false,pointRadius:3,pointBackgroundColor:'#ef4444'}},
  {{label:'P2 Median',data:mP2.slice(-WK19.length),borderColor:'#f59e0b',backgroundColor:'transparent',tension:0.3,fill:false,spanGaps:false,pointRadius:3,pointBackgroundColor:'#f59e0b'}},
  {{label:'P3 Median',data:mP3.slice(-WK19.length),borderColor:'#3b82f6',backgroundColor:'transparent',tension:0.3,fill:false,spanGaps:false,pointRadius:3,pointBackgroundColor:'#3b82f6'}},
  {{label:'5-min target',data:Array(WK19.length).fill(5),borderColor:'rgba(167,139,250,0.4)',borderDash:[5,4],borderWidth:1.5,pointRadius:0,fill:false,tension:0}}
]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:LG,tooltip:TT}},scales:{{x:XA,y:{{type:'linear',beginAtZero:true,ticks:{{color:'#64748b',callback:v=>v+' min'}},grid:{{color:'rgba(255,255,255,0.05)'}}}}}}}}}});

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
  {{label:'Intercom',   data:aIcom.slice(-WK19.length),backgroundColor:'#64748b',stack:'a'}}
]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:LG,tooltip:TT}},scales:{{x:XA,y:YL(true)}}}}}});

new Chart(document.getElementById('cTBVol'),{{type:'bar',data:{{labels:WK19,datasets:[
  {{label:'Day (08–16 UTC)',    data:tbDay,   backgroundColor:'#38bdf8',stack:'tb'}},
  {{label:'Evening (16–00 UTC)',data:tbEve,   backgroundColor:'#f59e0b',stack:'tb'}},
  {{label:'Night (00–08 UTC)', data:tbNight, backgroundColor:'#64748b',stack:'tb'}},
  {{label:'Noise Rate %',type:'line',data:tbTotalW,borderColor:'#a78bfa',backgroundColor:'transparent',tension:0.3,fill:false,yAxisID:'rate',pointRadius:4,pointBackgroundColor:'#a78bfa'}}
]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:LG,tooltip:TT}},scales:{{x:XA,y:YL(true),rate:RA}}}}}});

new Chart(document.getElementById('cTBWaste'),{{type:'bar',data:{{labels:WK19,datasets:[
  {{label:'Day (08–16 UTC)',    data:tbDayW,   backgroundColor:'#38bdf8',barPercentage:0.8}},
  {{label:'Evening (16–00 UTC)',data:tbEveW,   backgroundColor:'#f59e0b',barPercentage:0.8}},
  {{label:'Night (00–08 UTC)', data:tbNightW, backgroundColor:'#64748b',barPercentage:0.8}}
]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:LG,tooltip:TT}},scales:{{x:XA,y:YPct}}}}}});

{pir_cat_chart_js}
{pir_trend_chart_js}
{eng_led_chart_js}
{eng_avg_chart_js}



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
