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

WEEK_KEYS = [k for k in sorted(cache.keys()) if not k.startswith("_")]
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

# When the current week has no ticket data (e.g. early Monday), show last complete week in stat cards
_no_cw_data = (
    (CW.get("p1_frt_sla") or {}).get("total", 0) == 0 and
    (CW.get("csat") or {}).get("total", 0) == 0
)
stat_week      = prev_week        if _no_cw_data else current_week
stat_prev_week = WEEK_KEYS[-3]   if _no_cw_data else prev_week

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
aFTML_arr = [get(wk, "alert_volume", "by_source", "HTTP DMS FTML", default=0) for wk in WEEK_KEYS]
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
        status_cls = "c-green" if status == "Closed" else "c-amber"
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
            continue
        rate_cls = "c-green" if rate >= 75 else "c-amber" if rate >= 40 else "c-red"
        open_cls = "c-red" if op >= 20 else "c-amber" if op >= 8 else "c-muted"
        rows.append(f'''      <tr style="border-bottom:1px solid rgba(255,255,255,0.05)">
        <td style="padding:11px 14px;color:#e2e8f0;font-size:13px">{name}</td>
        <td style="padding:11px 14px;text-align:right;font-family:'DM Mono',monospace;font-size:13px" class="{open_cls}">{op}</td>
        <td style="padding:11px 14px;text-align:right;font-family:'DM Mono',monospace;font-size:13px;color:#22c55e">{comp}</td>
        <td style="padding:11px 14px;text-align:right;font-family:'DM Mono',monospace;font-size:13px" class="{rate_cls}">{rate}%</td>
      </tr>''')
    rows_html = "\n".join(rows)
    return f'''    <div style="flex:1;min-height:0;overflow-y:auto;background:#0d1629;border:1px solid rgba(255,255,255,0.07);border-radius:8px;margin-top:12px">
      <table style="width:100%;border-collapse:collapse">
        <thead>
          <tr style="border-bottom:1px solid rgba(255,255,255,0.1)">
            <th style="padding:10px 14px;text-align:left;font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.06em">Team</th>
            <th style="padding:10px 14px;text-align:right;font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.06em">Open</th>
            <th style="padding:10px 14px;text-align:right;font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.06em">Done</th>
            <th style="padding:10px 14px;text-align:right;font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.06em">Rate</th>
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
    return "c-green" if s in ("closed", "resolved", "postmortem") else "c-amber"

def _build_p1_cards(incidents):
    if not incidents:
        return '    <div class="p1-no-data c-muted">No True P1 incidents this week.</div>'
    cards = []
    for inc in incidents:
        status  = inc.get("status", "—")
        sc      = _p1_status_cls(status)
        dt_str  = _fmt_dt_short(inc.get("reported_at", ""))
        cause   = inc.get("cause", "")
        ref     = inc.get("reference", "")
        name    = inc.get("name", "")
        if name.startswith("[P1] Intercom Incident : "):
            name = name[len("[P1] Intercom Incident : "):]
        elif name.startswith("[P1] "):
            name = name[5:]
        summary = inc.get("summary", "")
        href    = inc.get("permalink", "")
        ref_html   = f'<a href="{href}" target="_blank" class="p1-ref">{ref}</a>' if href else f'<span class="p1-ref">{ref}</span>'
        cause_html = f'<span class="p1-cause">{cause}</span>' if cause else ""
        cards.append(f'''    <div class="p1-inc-card">
      <div class="p1-inc-header">
        {ref_html}
        <span class="p1-status-badge {sc}">{status}</span>
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
        dt_str = _fmt_dt_short(inc.get("reported_at", ""))
        ref = inc.get("reference", "")
        name = inc.get("name", "")
        if name.startswith("[P1] Intercom Incident : "):
            name = name[len("[P1] Intercom Incident : "):]
        elif name.startswith("[P1] "):
            name = name[5:]
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
        <span class="p1-status-badge {sc}">{status}</span>
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

pir_teams_chart = sorted([t for t in pir_teams if t.get("open", 0) > 0], key=lambda t: t["open"], reverse=True)
pir_team_labels = [t["name"]      for t in pir_teams_chart]
pir_team_open   = [t["open"]      for t in pir_teams_chart]
pir_team_closed = [t["completed"] for t in pir_teams_chart]
pir_team_table_html = render_pir_team_table(pir_teams)

# ── P1 INCIDENT SLIDE GENERATION ─────────────────────────────────────────────
_p1_chunks    = [_all_p1s[i:i+2] for i in range(0, len(_all_p1s), 2)] or [[]]
_n_p1_slides  = len(_p1_chunks)
_idx_pir      = 1 + _n_p1_slides
_idx_partner  = _idx_pir + 1
_idx_ops      = _idx_partner + 1
_total_slides = _idx_ops + 1

def _build_p1_pair_cards(chunk):
    if not chunk:
        return '    <div class="p1-no-data c-muted">No True P1 incidents this week.</div>'
    cards = []
    for inc in chunk:
        status = inc.get("status", "—")
        sc = _p1_status_cls(status)
        dt_str = _fmt_dt_short(inc.get("reported_at", ""))
        ref = inc.get("reference", "")
        name = inc.get("name", "")
        if name.startswith("[P1] Intercom Incident : "):
            name = name[len("[P1] Intercom Incident : "):]
        elif name.startswith("[P1] "):
            name = name[5:]
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
        <span class="p1-status-badge {sc}">{status}</span>
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
    _si = 1 + _i
    _tab_lbl   = "P1 Incidents" if _n_p1_slides == 1 else f"P1 Incidents {_i+1}/{_n_p1_slides}"
    _grp_lbl   = "P1 Incidents" if _n_p1_slides == 1 else f"P1 Incidents · {_i+1} of {_n_p1_slides}"
    p1_tab_btns_html += f'    <button class="slide-tab" onclick="showSlide({_si})">{_tab_lbl}</button>\n'
    _cards = _build_p1_pair_cards(_chunk)
    p1_all_slides_html += f'''
<!-- ═══ P1 INCIDENTS {_i+1} ════════════════════════════════════ -->
<div class="slide" id="s1_{_i+1}"><div class="page">
  <div class="group-label">{_grp_lbl} · {cw_date}</div>
  <div class="p1-two-up">
{_cards}
  </div>
</div></div>
'''

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
    .group-label {{ font-size: 11px; color: #64748b; letter-spacing: 0.1em; text-transform: uppercase; font-weight: 600; margin-bottom: 8px; flex-shrink: 0; }}
    .stat-grid-4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 10px; flex-shrink: 0; }}
    .stat-card {{ background: #0d1629; border: 1px solid rgba(255,255,255,0.07); border-radius: 8px; padding: 10px 14px; }}
    .card-label {{ font-size: 10px; color: #64748b; margin-bottom: 5px; font-weight: 500; line-height: 1.3; }}
    .card-value {{ font-family: 'DM Mono', monospace; font-size: 22px; font-weight: 500; line-height: 1; margin-bottom: 3px; }}
    .card-value .unit {{ font-size: 12px; font-weight: 400; }}
    .card-subnote {{ font-size: 10px; color: #64748b; margin-bottom: 2px; }}
    .card-delta {{ font-family: 'DM Mono', monospace; font-size: 10px; margin-top: 3px; }}
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
    .chart-title {{ font-size: 12px; font-weight: 600; color: #e2e8f0; margin-bottom: 2px; flex-shrink: 0; }}
    .chart-note  {{ font-size: 10px; color: #64748b; margin-bottom: 8px; flex-shrink: 0; }}
    .chart-container {{ flex: 1; min-height: 0; position: relative; }}
    .stat-grid-2 {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 10px; flex-shrink: 0; }}
    .stat-grid-3 {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 10px; flex-shrink: 0; }}
    .p1-inc-area {{ flex: 1.4; display: flex; flex-direction: column; gap: 8px; min-height: 0; margin-bottom: 8px; }}
    .p1-inc-card {{ background: #0d1629; border: 1px solid rgba(255,255,255,0.07); border-radius: 8px; padding: 12px 16px; flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }}
    .p1-inc-header {{ display: flex; align-items: center; gap: 10px; flex-shrink: 0; margin-bottom: 6px; flex-wrap: wrap; }}
    .p1-ref {{ font-family: 'DM Mono', monospace; font-size: 12px; color: #38bdf8; font-weight: 500; text-decoration: none; }}
    .p1-ref:hover {{ text-decoration: underline; }}
    .p1-status-badge {{ font-size: 10px; font-weight: 600; padding: 2px 7px; border-radius: 4px; background: rgba(255,255,255,0.06); }}
    .p1-inc-date {{ font-size: 11px; color: #64748b; margin-left: auto; }}
    .p1-cause {{ font-size: 11px; color: #94a3b8; }}
    .p1-inc-title {{ font-size: 15px; font-weight: 700; color: #e2e8f0; margin-bottom: 8px; flex-shrink: 0; line-height: 1.3; }}
    .p1-inc-overview {{ font-size: 12px; color: #94a3b8; line-height: 1.6; overflow: hidden; }}
    .p1-no-data {{ font-size: 13px; padding: 16px 0; }}
    .brand-strip {{ display: flex; align-items: center; gap: 10px; padding: 6px 0 8px; flex-shrink: 0; border-bottom: 1px solid rgba(255,255,255,0.06); margin-bottom: 10px; flex-wrap: wrap; }}
    .brand-strip-label {{ font-size: 10px; color: #475569; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; white-space: nowrap; margin-right: 4px; }}
    .brand-pill {{ display: inline-flex; align-items: center; gap: 6px; background: #0d1629; border: 1px solid rgba(255,255,255,0.07); border-radius: 6px; padding: 4px 10px; }}
    .brand-pill-rank {{ font-family: 'DM Mono', monospace; font-size: 10px; color: #475569; }}
    .brand-pill-name {{ font-size: 12px; color: #e2e8f0; }}
    .brand-pill-count {{ font-family: 'DM Mono', monospace; font-size: 13px; font-weight: 600; color: #38bdf8; }}
    .brand-strip-note {{ font-size: 10px; color: #475569; margin-left: auto; white-space: nowrap; }}
    .p1-two-up {{ flex: 1; display: flex; gap: 14px; min-height: 0; }}
    .p1-full-card {{ flex: 1; min-height: 0; display: flex; flex-direction: column; background: #0d1629; border: 1px solid rgba(255,255,255,0.07); border-radius: 8px; padding: 20px 24px; overflow: hidden; }}
    .p1-sections {{ display: flex; flex-direction: column; gap: 14px; margin-top: 14px; flex-shrink: 0; }}
    .p1-section {{ }}
    .p1-section-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: #38bdf8; font-weight: 700; border-bottom: 1px solid rgba(56,189,248,0.15); padding-bottom: 5px; margin-bottom: 7px; }}
    .p1-section-body {{ font-size: 13px; color: #94a3b8; line-height: 1.7; }}
  </style>
</head>
<body>

<div class="topbar">
  <div class="topbar-title">Weekly Incident Report</div>
  <div class="slide-tabs">
    <button class="slide-tab active" onclick="showSlide(0)">P1 Performance</button>
{p1_tab_btns_html}    <button class="slide-tab" onclick="showSlide({_idx_pir})">PIR Actions</button>
    <button class="slide-tab" onclick="showSlide({_idx_partner})">Partner Tickets</button>
    <button class="slide-tab" onclick="showSlide({_idx_ops})">Incident Ops</button>
  </div>
  <div class="topbar-meta">{today_str}</div>
</div>

<div class="slides-wrap">

<!-- ═══ SLIDE 0 — P1 PERFORMANCE ════════════════════════════════════ -->
<div class="slide active" id="s0"><div class="page">
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
{pir_team_table_html}
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
      <div class="card-label">SOC & SRE CSAT Score ({cw_date})</div>
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
      <div class="card-label">Partner Tickets Response Time ({cw_date})</div>
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
    </div>
    <div class="chart-row">
      <div class="chart-section">
        <div class="chart-title">Partner Ticket Volume — Week on Week</div>
        <div class="chart-note">Source: Intercom &middot; All P1/P2/P3 Incident tagged tickets assigned to SRE</div>
        <div class="chart-container"><canvas id="cPVol" style="width:100%;height:100%"></canvas></div>
        <div style="margin-top:8px;padding:7px 12px;background:rgba(56,189,248,0.08);border-left:3px solid #38bdf8;border-radius:4px;font-size:11px;color:#93c5fd;line-height:1.5;">&#9432;&nbsp; From w/c 25 May 2026, Partner Support agreed to route all partner incidents directly to SRE.</div>
      </div>
    </div>
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
  {{label:'False P1 Rate %',type:'line',data:fpRate,borderColor:'#a78bfa',backgroundColor:'transparent',tension:0.3,fill:false,yAxisID:'rate',pointRadius:3,pointBackgroundColor:'#a78bfa'}}
]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:LG,tooltip:TT}},scales:{{x:XA,y:YL(true),rate:RA}}}}}});

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
