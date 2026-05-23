import json
from datetime import datetime, timezone, timedelta
from collections import defaultdict

CACHE_FILE = "/Users/andrea/Downloads/weekly_report_cache.json"
OUTPUT_FILE = "/Users/andrea/Downloads/weekly_report.html"

with open(CACHE_FILE) as f:
    cache = json.load(f)

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

# Week labels
WK = [fmt_week_label(k, k == current_week) for k in WEEK_KEYS]
# WK19 = weeks that have mtta data (incident.io era from 2026-05-04)
WK19_KEYS = [k for k in WEEK_KEYS if "mtta" in cache[k]]
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
        fmt = f"0{unit} vs wk {fmt_date_dmy(prev_week)}"
        return ("d-muted", fmt)
    sign = "+" if diff > 0 else "−"
    abs_diff = abs(diff)
    if decimals == 0:
        fmt_diff = str(int(round(abs_diff)))
    else:
        fmt_diff = f"{abs_diff:.{decimals}f}"
    fmt = f"{sign}{fmt_diff}{unit} vs wk {fmt_date_dmy(prev_week)}"
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

# P1 FRT SLA arrays
p1Hit_arr  = [get(wk, "p1_frt_sla", "hit", default=0) for wk in WEEK_KEYS]
p1Miss_arr = [get(wk, "p1_frt_sla", "missed", default=0) for wk in WEEK_KEYS]
p1Rate_arr = [get(wk, "p1_frt_sla", "hit_rate") for wk in WEEK_KEYS]

# MTTA — WK19 only
mP1_arr = [get(wk, "mtta", "P1", "median_mtta_min") for wk in WEEK_KEYS]
mP2_arr = [get(wk, "mtta", "P2", "median_mtta_min") for wk in WEEK_KEYS]
mP3_arr = [get(wk, "mtta", "P3", "median_mtta_min") for wk in WEEK_KEYS]

# Brands
top10 = cache.get("_p1_brands_top10", {"labels": [], "counts": []})
bL = top10["labels"]
bC = top10["counts"]

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

ptP1_arr   = [get(wk, "partner_tickets", "p1_responded", default=0) for wk in WEEK_KEYS]
ptP2_arr   = [get(wk, "partner_tickets", "p2_responded", default=0) for wk in WEEK_KEYS]
ptP3_arr   = [get(wk, "partner_tickets", "p3_responded", default=0) for wk in WEEK_KEYS]
ptOpen_arr = [sum([get(wk, "partner_tickets", "p1_open", default=0),
                   get(wk, "partner_tickets", "p2_open", default=0),
                   get(wk, "partner_tickets", "p3_open", default=0)]) for wk in WEEK_KEYS]
ptMed_arr  = [get(wk, "partner_tickets", "median_response_min") for wk in WEEK_KEYS]

# ── SECTION 3 — INCIDENT OPERATIONS ─────────────────────────────────────────
iP1_arr = [get(wk, "incident_volume", "P1", default=0) for wk in WEEK_KEYS]
iP2_arr = [get(wk, "incident_volume", "P2", default=0) for wk in WEEK_KEYS]
iP3_arr = [get(wk, "incident_volume", "P3", default=0) for wk in WEEK_KEYS]
iP4_arr = [get(wk, "incident_volume", "P4", default=0) for wk in WEEK_KEYS]

aDMS_arr  = [get(wk, "alert_volume", "by_source", "DMS", default=0) for wk in WEEK_KEYS]
aSOC_arr  = [get(wk, "alert_volume", "by_source", "Grafana SOC", default=0) for wk in WEEK_KEYS]
aHTTP_arr = [get(wk, "alert_volume", "by_source", "HTTP", default=0) for wk in WEEK_KEYS]
aGraf_arr = [get(wk, "alert_volume", "by_source", "Grafana", default=0) for wk in WEEK_KEYS]
aIcom_arr = [get(wk, "alert_volume", "by_source", "Intercom", default=0) for wk in WEEK_KEYS]
aFTML_arr = [get(wk, "alert_volume", "by_source", "HTTP DMS FTML", default=0) for wk in WEEK_KEYS]

# ── STAT CARD CALCULATIONS ───────────────────────────────────────────────────
cw_date = fmt_date_dmy(current_week)

# S1 cards
cw_true_p1, cw_false_p1, cw_unclass, cw_fp_rate = p1_quality_row(current_week)
pw_true_p1, pw_false_p1, pw_unclass, pw_fp_rate   = p1_quality_row(prev_week)

true_p1_delta_cls, true_p1_delta = delta_str(cw_true_p1, pw_true_p1, "", higher_is_better=False, decimals=0)
fp_rate_delta_cls, fp_rate_delta = delta_str(cw_fp_rate, pw_fp_rate, "%", higher_is_better=False)

cw_p1_frt_rate = get(current_week, "p1_frt_sla", "hit_rate")
pw_p1_frt_rate = get(prev_week, "p1_frt_sla", "hit_rate")
cw_p1_med_frt  = get(current_week, "p1_frt_sla", "median_frt_min")
pw_p1_med_frt  = get(prev_week, "p1_frt_sla", "median_frt_min")

p1_frt_delta_cls, p1_frt_delta = delta_str(cw_p1_frt_rate, pw_p1_frt_rate, "%")
p1_med_delta_cls, p1_med_delta = delta_str(cw_p1_med_frt, pw_p1_med_frt, " min", higher_is_better=False)

cw_p1_mtta     = get(current_week, "mtta", "P1", "median_mtta_min")
pw_p1_mtta     = get(prev_week, "mtta", "P1", "median_mtta_min")
cw_p1_ack_rate = get(current_week, "mtta", "P1", "ack_rate")
p1_mtta_delta_cls, p1_mtta_delta = delta_str(cw_p1_mtta, pw_p1_mtta, " min", higher_is_better=False)
p1_ack_pct = f"{int(round(cw_p1_ack_rate*100))}%" if cw_p1_ack_rate is not None else "—"
p1_ack_cls = "c-green" if cw_p1_ack_rate and cw_p1_ack_rate >= 1.0 else "c-amber"

# S2 cards
cw_p23_rate = get(current_week, "p2p3_frt_sla", "hit_rate")
pw_p23_rate = get(prev_week, "p2p3_frt_sla", "hit_rate")
p23_delta_cls, p23_delta = delta_str(cw_p23_rate, pw_p23_rate, "%")

cw_csat_avg = get(current_week, "csat", "avg_score")
pw_csat_avg = get(prev_week, "csat", "avg_score")
csat_delta_cls, csat_delta = delta_str(cw_csat_avg, pw_csat_avg, "")

cw_pt_resp = pt_responded(current_week)
pw_pt_resp = pt_responded(prev_week)
cw_pt_p1 = get(current_week, "partner_tickets", "p1_responded", default=0)
cw_pt_p2 = get(current_week, "partner_tickets", "p2_responded", default=0)
cw_pt_p3 = get(current_week, "partner_tickets", "p3_responded", default=0)
pt_delta_cls, pt_delta = delta_str(cw_pt_resp, pw_pt_resp, "", higher_is_better=False, decimals=0)

cw_pt_med = get(current_week, "partner_tickets", "median_response_min")
pw_pt_med = get(prev_week, "partner_tickets", "median_response_min")
pt_med_delta_cls, pt_med_delta = delta_str(cw_pt_med, pw_pt_med, " min", higher_is_better=False)

# S3 cards
cw_inc_total = get(current_week, "incident_volume", "total", default=0)
pw_inc_total = get(prev_week, "incident_volume", "total", default=0)
cw_inc_p1 = get(current_week, "incident_volume", "P1", default=0)
cw_inc_p2 = get(current_week, "incident_volume", "P2", default=0)
cw_inc_p3 = get(current_week, "incident_volume", "P3", default=0)
inc_delta_cls, inc_delta = delta_str(cw_inc_total, pw_inc_total, "", higher_is_better=False, decimals=0)

cw_alerts = get(current_week, "alert_volume", "total", default=0)
pw_alerts = get(prev_week, "alert_volume", "total", default=0)
alerts_delta_cls, alerts_delta = delta_str(cw_alerts, pw_alerts, "", higher_is_better=False, decimals=0)

cw_p1_ack_rate_s3 = get(current_week, "mtta", "P1", "ack_rate")
pw_p1_ack_rate_s3 = get(prev_week, "mtta", "P1", "ack_rate")
cw_ack_pct = f"{int(round(cw_p1_ack_rate_s3*100))}%" if cw_p1_ack_rate_s3 is not None else "—"
cw_ack_cls = "c-green" if cw_p1_ack_rate_s3 and cw_p1_ack_rate_s3 >= 1.0 else "c-amber"
if cw_p1_ack_rate_s3 and pw_p1_ack_rate_s3:
    ack_diff = round((cw_p1_ack_rate_s3 - pw_p1_ack_rate_s3)*100, 1)
    if abs(ack_diff) < 0.1:
        ack_delta_cls, ack_delta = "d-muted", f"0% vs wk {fmt_date_dmy(prev_week)}"
    elif ack_diff > 0:
        ack_delta_cls, ack_delta = "d-green", f"+{ack_diff}% vs wk {fmt_date_dmy(prev_week)}"
    else:
        ack_delta_cls, ack_delta = "d-red", f"−{abs(ack_diff)}% vs wk {fmt_date_dmy(prev_week)}"
else:
    ack_delta_cls, ack_delta = "d-muted", f"— vs wk {fmt_date_dmy(prev_week)}"

cw_conv_rate = round(cw_inc_total / cw_alerts * 100, 1) if cw_alerts else None
pw_conv_rate = round(pw_inc_total / pw_alerts * 100, 1) if pw_alerts else None
conv_delta_cls, conv_delta = delta_str(cw_conv_rate, pw_conv_rate, "%", higher_is_better=False)

# ── BREACH BLOCKS ────────────────────────────────────────────────────────────
week_label_long = f"Week of {fmt_date_dmy(current_week)} {datetime.strptime(current_week, '%Y-%m-%d').year}"

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
        opened = fmt_ts(b["opened_ts"])
        first_reply = fmt_ts(b["opened_ts"] + b["sre_real_rt_s"])
        items.append(f'''      <div class="breach-item">
        <div class="breach-header">
          <span class="breach-conv-id">#{b["conv_id"]}</span>
          <span class="breach-meta">{b["brand"]} &middot; {b["priority"]}</span>
          <span class="breach-frt">{b["sre_oh_min"]} min</span>
          <span class="breach-ts">Opened {opened} &middot; First reply {first_reply}</span>
        </div>
        <div class="breach-summary">{b["summary"]}</div>
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
        opened = fmt_ts(b["opened_ts"])
        first_reply = fmt_ts(b["opened_ts"] + b["sre_real_rt_s"])
        items.append(f'''      <div class="breach-item">
        <div class="breach-header">
          <span class="breach-conv-id">#{b["conv_id"]}</span>
          <span class="breach-meta">{b["brand"]} &middot; {b["priority"]}</span>
          <span class="breach-frt">{b["sre_oh_min"]} min</span>
          <span class="breach-ts">Opened {opened} &middot; First reply {first_reply}</span>
        </div>
        <div class="breach-summary">{b["summary"]}</div>
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
        items.append(f'''      <div class="breach-item">
        <div class="breach-header">
          <span class="breach-conv-id">#{b["conv_id"]}</span>
          <span class="breach-meta">{b["brand"]} &middot; {b["priority"]}</span>
          <span class="breach-frt">&#9733; {b["rating"]}</span>
        </div>
        <div class="breach-summary">{b["summary"]}</div>
      </div>''')
    items_html = "\n".join(items)
    return f'''    <div class="breach-block">
      <div class="breach-list-title">Low CSAT Scores — {week_label_long}</div>
{items_html}
    </div>'''

p1_breach_html  = render_p1_breach_block(current_week)
p23_breach_html = render_p23_breach_block(current_week)
csat_breach_html = render_csat_breach_block(current_week)

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
brand_note = f"Source: Intercom &middot; P1 Incident tag &middot; {first_dt.day} {first_dt.strftime('%b')} – {today.day} {today.strftime('%b')} {today.year} &middot; Top 10 brands"

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

# ── HTML GENERATION ──────────────────────────────────────────────────────────
wk_label_cur = fmt_week_label(current_week, True).rstrip("*")
title_date   = datetime.strptime(current_week, "%Y-%m-%d").strftime("%-d %B %Y")

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Weekly SRE Report — {title_date}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #080f1e; color: #e2e8f0; font-family: 'DM Sans', sans-serif; min-height: 100vh; }}
    .page {{ max-width: 1100px; margin: 0 auto; padding: 40px 24px 80px; }}

    .header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 32px; padding-bottom: 24px; border-bottom: 1px solid rgba(255,255,255,0.07); }}
    .header-left h1 {{ font-size: 26px; font-weight: 700; color: #e2e8f0; letter-spacing: -0.5px; }}
    .header-left .subtitle {{ font-size: 13px; color: #64748b; margin-top: 4px; }}
    .header-right {{ font-size: 13px; color: #64748b; padding-top: 4px; }}

    .group-label {{ font-size: 11px; color: #64748b; letter-spacing: 0.1em; text-transform: uppercase; font-weight: 600; margin-bottom: 14px; }}
    .group-divider {{ border: none; border-top: 1px solid rgba(255,255,255,0.07); margin: 36px 0; }}

    .stat-grid-5 {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 24px; }}
    .stat-grid-4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 24px; }}
    .stat-card {{ background: #0d1629; border: 1px solid rgba(255,255,255,0.07); border-radius: 8px; padding: 14px 16px; }}
    .card-label {{ font-size: 11px; color: #64748b; margin-bottom: 8px; font-weight: 500; line-height: 1.4; }}
    .card-value {{ font-family: 'DM Mono', monospace; font-size: 26px; font-weight: 500; line-height: 1; margin-bottom: 4px; }}
    .card-value .unit {{ font-size: 13px; font-weight: 400; }}
    .card-subnote {{ font-size: 11px; color: #64748b; margin-bottom: 4px; }}
    .card-delta {{ font-family: 'DM Mono', monospace; font-size: 11px; margin-top: 4px; }}

    .c-red   {{ color: #ef4444; }}
    .c-amber {{ color: #f59e0b; }}
    .c-green {{ color: #22c55e; }}
    .c-muted {{ color: #94a3b8; }}
    .d-red   {{ color: #ef4444; }}
    .d-green {{ color: #22c55e; }}
    .d-muted {{ color: #475569; }}

    .chart-section {{ background: #0d1629; border: 1px solid rgba(255,255,255,0.07); border-radius: 8px; padding: 18px 20px; margin-bottom: 14px; }}
    .chart-title {{ font-size: 13px; font-weight: 600; color: #e2e8f0; margin-bottom: 3px; }}
    .chart-note  {{ font-size: 11px; color: #64748b; margin-bottom: 14px; }}
    .chart-container {{ position: relative; }}

    .breach-block {{ margin-top: 14px; border-top: 1px solid rgba(255,255,255,0.07); padding-top: 10px; }}
    .breach-list-title {{ font-size: 10px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #64748b; margin-bottom: 8px; }}
    .breach-clean {{ font-size: 13px; }}
    .breach-item {{ background: #121e36; border: 1px solid rgba(255,255,255,0.07); border-radius: 6px; padding: 9px 12px; margin-bottom: 8px; }}
    .breach-header {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
    .breach-conv-id {{ font-family: 'DM Mono', monospace; font-size: 11px; color: #38bdf8; }}
    .breach-meta {{ font-size: 12px; color: #94a3b8; }}
    .breach-frt  {{ font-family: 'DM Mono', monospace; font-size: 12px; color: #ef4444; font-weight: 500; }}
    .breach-ts   {{ font-size: 11px; color: #64748b; }}
    .breach-summary {{ font-size: 12px; color: #94a3b8; margin-top: 5px; line-height: 1.5; }}

    .footer {{ text-align: center; padding-top: 40px; font-size: 11px; color: #64748b; line-height: 1.9; }}
  </style>
</head>
<body>
<div class="page">

  <div class="header">
    <div class="header-left">
      <h1>Weekly SRE Report</h1>
      <div class="subtitle">P1 Performance &middot; Partner Tickets &middot; Incident Operations</div>
    </div>
    <div class="header-right">{today_str}</div>
  </div>

  <!-- ═══ SECTION 1 — P1 PERFORMANCE ═══════════════════════════════ -->
  <div class="group-label">P1 Performance</div>

  <div class="stat-grid-5">
    <div class="stat-card">
      <div class="card-label">True P1s This Week ({cw_date})</div>
      <div class="card-value c-red">{cw_true_p1}</div>
      <div class="card-delta {true_p1_delta_cls}">{true_p1_delta}</div>
    </div>
    <div class="stat-card">
      <div class="card-label">False P1 Rate ({cw_date})</div>
      <div class="card-value {color_pct(cw_fp_rate and 100-cw_fp_rate if cw_fp_rate is not None else None) if False else 'c-amber' if cw_fp_rate and cw_fp_rate >= 50 else 'c-green' if cw_fp_rate is not None else 'c-muted'}">{fmt_rate(cw_fp_rate, 1) if cw_fp_rate else '—'}</div>
      <div class="card-delta {fp_rate_delta_cls}">{fp_rate_delta}</div>
    </div>
    <div class="stat-card">
      <div class="card-label">SOC/SRE P1 FRT SLA ({cw_date})</div>
      <div class="card-value {color_pct(cw_p1_frt_rate)}">{fmt_rate(cw_p1_frt_rate, 0) if cw_p1_frt_rate is not None else '—'}</div>
      <div class="card-delta {p1_frt_delta_cls}">{p1_frt_delta}</div>
    </div>
    <div class="stat-card">
      <div class="card-label">SOC/SRE P1 Median FRT ({cw_date})</div>
      <div class="card-value c-muted">{fmt_min(cw_p1_med_frt)} <span class="unit">min</span></div>
      <div class="card-delta {p1_med_delta_cls}">{p1_med_delta}</div>
    </div>
    <div class="stat-card">
      <div class="card-label">P1 Median MTTA ({cw_date})</div>
      <div class="card-value c-muted">{fmt_min(cw_p1_mtta) if cw_p1_mtta else '—'} <span class="unit">min</span></div>
      <div class="card-subnote">Ack rate: {p1_ack_pct}</div>
      <div class="card-delta {p1_mtta_delta_cls}">{p1_mtta_delta}</div>
    </div>
  </div>

  <div class="chart-section">
    <div class="chart-title">P1 Incident Quality — Week on Week</div>
    <div class="chart-note">{p1q_note}</div>
    <div class="chart-container" style="height:320px"><canvas id="cP1Q"></canvas></div>
  </div>

  <div class="chart-section">
    <div class="chart-title">SOC/SRE P1 First Response SLA — Week on Week</div>
    <div class="chart-note">Source: Intercom &middot; P1 Incident SLA only &middot; 30-min target &middot; excludes downgraded and unanswered tickets</div>
    <div class="chart-container" style="height:280px"><canvas id="cP1F"></canvas></div>
{p1_breach_html}
  </div>

  <div class="chart-section">
    <div class="chart-title">P1 MTTA — Week on Week</div>
    <div class="chart-note">Source: incident.io &middot; W19 ({wk19_first_dt.day if wk19_first_dt else '4'} {wk19_first_dt.strftime('%b %Y') if wk19_first_dt else 'May 2026'}) onwards &middot; Median minutes from incident reported to acknowledged</div>
    <div class="chart-container" style="height:280px"><canvas id="cMTTA"></canvas></div>
  </div>

  <div class="chart-section">
    <div class="chart-title">P1 Tickets by Brand — 12-Week Cumulative</div>
    <div class="chart-note">{brand_note}</div>
    <div class="chart-container" style="height:320px"><canvas id="cBrand"></canvas></div>
  </div>

  <div class="group-divider"></div>

  <!-- ═══ SECTION 2 — PARTNER TICKETS ══════════════════════════════ -->
  <div class="group-label">Partner Tickets</div>

  <div class="stat-grid-4">
    <div class="stat-card">
      <div class="card-label">SOC/SRE P2/P3 FRT SLA ({cw_date})</div>
      <div class="card-value {color_pct(cw_p23_rate)}">{fmt_rate(cw_p23_rate, 1) if cw_p23_rate is not None else '—'}</div>
      <div class="card-delta {p23_delta_cls}">{p23_delta}</div>
    </div>
    <div class="stat-card">
      <div class="card-label">SOC/SRE CSAT Score ({cw_date})</div>
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
      <div class="card-value c-muted">{fmt_min(cw_pt_med)} <span class="unit">min</span></div>
      <div class="card-delta {pt_med_delta_cls}">{pt_med_delta}</div>
    </div>
  </div>

  <div class="chart-section">
    <div class="chart-title">SOC/SRE P2/P3 First Response SLA — Week on Week</div>
    <div class="chart-note">Source: Intercom &middot; P2/P3 Incident tagged tickets assigned to SRE &middot; 2-hour target, office hours &middot; Slack-handled excluded</div>
    <div class="chart-container" style="height:280px"><canvas id="cP23F"></canvas></div>
{p23_breach_html}
  </div>

  <div class="chart-section">
    <div class="chart-title">SOC/SRE CSAT — Week on Week</div>
    <div class="chart-note">Source: Intercom &middot; All SRE conversations &middot; 1–5 scale</div>
    <div class="chart-container" style="height:280px"><canvas id="cCSAT"></canvas></div>
{csat_breach_html}
  </div>

  <div class="chart-section">
    <div class="chart-title">Partner Ticket Volume — Week on Week</div>
    <div class="chart-note">Source: Intercom &middot; P1/P2/P3 Incident tagged tickets assigned to SRE &middot; Slack-handled excluded</div>
    <div class="chart-container" style="height:280px"><canvas id="cPVol"></canvas></div>
  </div>

  <div class="chart-section">
    <div class="chart-title">Partner Ticket Response Time — Week on Week</div>
    <div class="chart-note">Source: Intercom &middot; Office hours only &middot; Slack-handled excluded &middot; Solid = median</div>
    <div class="chart-container" style="height:280px"><canvas id="cPRT"></canvas></div>
  </div>

  <div class="group-divider"></div>

  <!-- ═══ SECTION 3 — INCIDENT OPERATIONS ══════════════════════════ -->
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
      <div class="card-value c-muted">{cw_alerts}</div>
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

  <div class="chart-section">
    <div class="chart-title">Incident Volume by Severity — Week on Week</div>
    <div class="chart-note">Source: incident.io &middot; W19 onwards</div>
    <div class="chart-container" style="height:280px"><canvas id="cIVol"></canvas></div>
  </div>

  <div class="chart-section">
    <div class="chart-title">Alert Volume by Source — Week on Week</div>
    <div class="chart-note">Source: incident.io &middot; W19 onwards</div>
    <div class="chart-container" style="height:280px"><canvas id="cAVol"></canvas></div>
  </div>

  <div class="footer">
    Generated {today_str} &middot; Fast Track SRE &middot; Data: ClickHouse &middot; incident.io &middot; Intercom<br>
    12-week rolling window ({fmt_date_dmy(WEEK_KEYS[0])} – {fmt_week_label(current_week, True)}) &middot; All times UTC
  </div>

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

const bL = {js_str_arr(bL)};
const bC = {js_arr(bC)};

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
const ptOpen = {js_arr(ptOpen_arr)};
const ptMed  = {js_arr(ptMed_arr)};

const iP1 = {js_arr(iP1_arr)};
const iP2 = {js_arr(iP2_arr)};
const iP3 = {js_arr(iP3_arr)};
const iP4 = {js_arr(iP4_arr)};

const aDMS  = {js_arr(aDMS_arr)};
const aSOC  = {js_arr(aSOC_arr)};
const aHTTP = {js_arr(aHTTP_arr)};
const aGraf = {js_arr(aGraf_arr)};
const aIcom = {js_arr(aIcom_arr)};
const aFTML = {js_arr(aFTML_arr)};

const TT = {{ backgroundColor:'#0d1629', borderColor:'rgba(255,255,255,0.1)', borderWidth:1, titleColor:'#e2e8f0', bodyColor:'#e2e8f0', padding:8 }};
const LG = {{ position:'top', labels:{{ color:'#e2e8f0', boxWidth:12, padding:10, font:{{size:11}} }} }};
const XA = {{ ticks:{{ color:'#64748b', font:{{size:11}} }}, grid:{{ color:'rgba(255,255,255,0.05)' }} }};
const YL = (s=false) => ({{ type:'linear', position:'left', min:0, stacked:s, ticks:{{ color:'#64748b', precision:0 }}, grid:{{ color:'rgba(255,255,255,0.05)' }} }});
const RA = {{ type:'linear', position:'right', min:0, max:100, ticks:{{ color:'#a78bfa', callback:v=>v+'%' }}, grid:{{ display:false }} }};
const T90 = Array(13).fill(90);
const noT = item => item.text !== '90% target';
const no45= item => item.text !== '4.5 target';

new Chart(document.getElementById('cP1Q'),{{type:'bar',data:{{labels:WK,datasets:[
  {{label:'True P1',     data:trueP1,  backgroundColor:'#ef4444',stack:'q'}},
  {{label:'False P1',    data:falseP1, backgroundColor:'#f59e0b',stack:'q'}},
  {{label:'Unclassified',data:unclassP,backgroundColor:'#64748b',stack:'q'}},
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
  {{label:'P3 Median',data:mP3.slice(-WK19.length),borderColor:'#3b82f6',backgroundColor:'transparent',tension:0.3,fill:false,spanGaps:false,pointRadius:3,pointBackgroundColor:'#3b82f6'}}
]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:LG,tooltip:TT}},scales:{{x:XA,y:{{type:'linear',beginAtZero:true,ticks:{{color:'#64748b',callback:v=>v+' min'}},grid:{{color:'rgba(255,255,255,0.05)'}}}}}}}}});

new Chart(document.getElementById('cBrand'),{{type:'bar',data:{{labels:bL,datasets:[
  {{label:'P1 Tickets',data:bC,backgroundColor:'#38bdf8',borderWidth:0,borderRadius:3}}
]}},options:{{responsive:true,maintainAspectRatio:false,indexAxis:'y',plugins:{{legend:{{display:false}},tooltip:TT}},scales:{{
  x:{{type:'linear',beginAtZero:true,ticks:{{color:'#64748b',stepSize:1,precision:0}},grid:{{color:'rgba(255,255,255,0.05)'}}}},
  y:{{reverse:true,ticks:{{color:'#94a3b8'}},grid:{{display:false}}}}
}}}}}});

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
  {{label:'4.5 target',type:'line',data:Array(13).fill(4.5),borderColor:'rgba(167,139,250,0.3)',borderDash:[5,5],pointRadius:0,fill:false,yAxisID:'rate'}}
]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{...LG,labels:{{...LG.labels,filter:no45}}}},tooltip:TT}},scales:{{x:XA,y:YL(true),rate:{{type:'linear',position:'right',min:0,max:5,ticks:{{color:'#a78bfa',callback:v=>v.toFixed(1)}},grid:{{display:false}}}}}}}}}});

new Chart(document.getElementById('cPVol'),{{type:'bar',data:{{labels:WK,datasets:[
  {{label:'P1',        data:ptP1,  backgroundColor:'#ef4444',stack:'t'}},
  {{label:'P2',        data:ptP2,  backgroundColor:'#f59e0b',stack:'t'}},
  {{label:'P3',        data:ptP3,  backgroundColor:'#3b82f6',stack:'t'}},
  {{label:'Still Open',data:ptOpen,backgroundColor:'rgba(226,232,240,0.25)',stack:'t'}}
]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:LG,tooltip:TT}},scales:{{x:XA,y:YL(true)}}}}}});

new Chart(document.getElementById('cPRT'),{{type:'line',data:{{labels:WK,datasets:[
  {{label:'Median Response (min)',data:ptMed,borderColor:'#38bdf8',backgroundColor:'rgba(56,189,248,0.1)',tension:0.3,fill:true,pointRadius:3,pointBackgroundColor:'#38bdf8',spanGaps:false}}
]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:LG,tooltip:TT}},scales:{{x:XA,y:{{type:'linear',beginAtZero:true,ticks:{{color:'#64748b',callback:v=>v+' min'}},grid:{{color:'rgba(255,255,255,0.05)'}}}}}}}}});

new Chart(document.getElementById('cIVol'),{{type:'bar',data:{{labels:WK19,datasets:[
  {{label:'P1',data:iP1.slice(-WK19.length),backgroundColor:'#ef4444',stack:'i'}},
  {{label:'P2',data:iP2.slice(-WK19.length),backgroundColor:'#f59e0b',stack:'i'}},
  {{label:'P3',data:iP3.slice(-WK19.length),backgroundColor:'#3b82f6',stack:'i'}},
  {{label:'P4',data:iP4.slice(-WK19.length),backgroundColor:'#64748b',stack:'i'}}
]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:LG,tooltip:TT}},scales:{{x:XA,y:YL(true)}}}}}});

new Chart(document.getElementById('cAVol'),{{type:'bar',data:{{labels:WK19,datasets:[
  {{label:'DMS',          data:aDMS.slice(-WK19.length), backgroundColor:'#38bdf8',stack:'a'}},
  {{label:'Grafana SOC',  data:aSOC.slice(-WK19.length), backgroundColor:'#a78bfa',stack:'a'}},
  {{label:'HTTP',         data:aHTTP.slice(-WK19.length),backgroundColor:'#22c55e',stack:'a'}},
  {{label:'Grafana',      data:aGraf.slice(-WK19.length),backgroundColor:'#f59e0b',stack:'a'}},
  {{label:'Intercom',     data:aIcom.slice(-WK19.length),backgroundColor:'#64748b',stack:'a'}},
  {{label:'HTTP DMS FTML',data:aFTML.slice(-WK19.length),backgroundColor:'#818cf8',stack:'a'}}
]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:LG,tooltip:TT}},scales:{{x:XA,y:YL(true)}}}}}});
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
