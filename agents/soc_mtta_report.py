import json
import os
from datetime import datetime, timezone

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOC_CACHE_FILE = os.path.join(_ROOT, "cache", "soc_mtta_cache.json")
OUTPUT_FILE    = os.path.join(_ROOT, "cache", "soc_mtta_report.html")

with open(SOC_CACHE_FILE) as f:
    soc_cache = json.load(f)

soc_weeks_data = soc_cache.get("weeks", {})
SOC_WEEK_KEYS  = sorted(soc_weeks_data.keys())

SOC_PERSONS = ["Joachim Farrugia", "Matteo Rapisarda", "Gérard E. Pelayo", "Nazareno Scibilia"]
SOC_SHORT   = {"Joachim Farrugia": "Joachim", "Matteo Rapisarda": "Matteo",
               "Gérard E. Pelayo": "Gérard",  "Nazareno Scibilia": "Nazareno"}
SOC_COLORS  = {"Joachim Farrugia": "#ef4444", "Matteo Rapisarda": "#22c55e",
               "Gérard E. Pelayo": "#64748b", "Nazareno Scibilia": "#3b82f6"}

today_str = datetime.now(tz=timezone.utc).strftime("%-d %B %Y")

if len(SOC_WEEK_KEYS) < 2:
    raise RuntimeError("soc_mtta_cache.json needs at least 2 weeks of data")

cw_iso = SOC_WEEK_KEYS[-1]
pw_iso = SOC_WEEK_KEYS[-2]
pw_iso_label = pw_iso.split("-")[1]

def soc_get(iso_week, person, *keys, default=None):
    obj = soc_weeks_data.get(iso_week, {}).get(person, {})
    for k in keys:
        if obj is None: return default
        obj = obj.get(k) if isinstance(obj, dict) else None
    return obj if obj is not None else default

SOC_MTTA_WEEK_KEYS = [w for w in SOC_WEEK_KEYS
    if any(soc_get(w, p, "mtta", "mean_mtta_min") is not None for p in SOC_PERSONS)]
SOC_MTTA_WK = [w.split("-")[1] for w in SOC_MTTA_WEEK_KEYS]

soc_mtta_arr = {p: [soc_get(w, p, "mtta", "mean_mtta_min") for w in SOC_MTTA_WEEK_KEYS] for p in SOC_PERSONS}

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

def color_mtta(v):
    if v is None: return "c-muted"
    if v <= 5: return "c-green"
    return "c-red"

def soc_delta(current, prev, unit="", higher_is_better=False, decimals=1):
    if current is None or prev is None:
        return ("d-muted", "—")
    diff = current - prev
    if abs(diff) < 0.05:
        return ("d-muted", f"0{unit} vs {pw_iso_label}")
    sign = "+" if diff > 0 else "−"
    fmt_diff = str(int(round(abs(diff)))) if decimals == 0 else f"{abs(diff):.{decimals}f}"
    good = diff > 0 if higher_is_better else diff < 0
    return ("d-green" if good else "d-red", f"{sign}{fmt_diff}{unit} vs {pw_iso_label}")

soc_cards = {}
for p in SOC_PERSONS:
    cw_mtta = soc_get(cw_iso, p, "mtta", "mean_mtta_min")
    pw_mtta = soc_get(pw_iso, p, "mtta", "mean_mtta_min")
    acked   = soc_get(cw_iso, p, "mtta", "acked_count", default=0)
    sample  = soc_get(cw_iso, p, "mtta", "sample_size", default=0)
    ack_rate = (acked / sample) if sample > 0 else None
    mtta_d_cls, mtta_d = soc_delta(cw_mtta, pw_mtta, " min", higher_is_better=False)
    low_ack = ack_rate is not None and ack_rate < 0.5
    if low_ack:
        mtta_cls = "c-red"
        ack_pct  = int(round(ack_rate * 100))
        subnote  = f'<span class="c-red">{acked}/{sample} acked ({ack_pct}%)</span> · target &lt;5 min'
    elif sample:
        mtta_cls = color_mtta(cw_mtta)
        subnote  = f"{acked}/{sample} acked · target &lt;5 min"
    else:
        mtta_cls = color_mtta(cw_mtta)
        subnote  = "No data · target &lt;5 min"
    soc_cards[p] = {
        "mtta_val":   f"{cw_mtta:.2f}" if cw_mtta is not None else "—",
        "mtta_cls":   mtta_cls,
        "subnote":    subnote,
        "mtta_d_cls": mtta_d_cls,
        "mtta_d":     mtta_d,
    }

stat_cards_html = "".join(
    f'    <div class="stat-card">\n'
    f'      <div class="card-label">{SOC_SHORT[p]} &middot; Avg MTTA ({cw_iso.split("-")[1]})</div>\n'
    f'      <div class="card-value {soc_cards[p]["mtta_cls"]}">{soc_cards[p]["mtta_val"]} <span class="unit">min</span></div>\n'
    f'      <div class="card-subnote d-muted">{soc_cards[p]["subnote"]}</div>\n'
    f'      <div class="card-delta {soc_cards[p]["mtta_d_cls"]}">{soc_cards[p]["mtta_d"]}</div>\n'
    f'    </div>\n'
    for p in SOC_PERSONS
)

# Build JS separately to avoid brace-doubling in f-string
n = len(SOC_MTTA_WK)
js_datasets = ",\n  ".join(
    "{label:'" + SOC_SHORT[p] + "',data:" + js_arr(soc_mtta_arr[p]) +
    ",backgroundColor:'" + SOC_COLORS[p] + "',barPercentage:0.6}"
    for p in SOC_PERSONS
)
js_block = (
    "const SOCMTTAWK = " + js_str_arr(SOC_MTTA_WK) + ";\n"
    + "\n".join(
        "const socMtta" + SOC_SHORT[p].replace("é", "e").split()[0] + " = " + js_arr(soc_mtta_arr[p]) + ";"
        for p in SOC_PERSONS
    )
    + """

const TT = { backgroundColor:'#0d1629', borderColor:'rgba(255,255,255,0.1)', borderWidth:1, titleColor:'#e2e8f0', bodyColor:'#e2e8f0', padding:8 };
const LG = { position:'top', labels:{ color:'#e2e8f0', boxWidth:12, padding:10, font:{size:11} } };
const XA = { ticks:{ color:'#64748b', font:{size:11} }, grid:{ color:'rgba(255,255,255,0.05)' } };

new Chart(document.getElementById('cSOCMTTA'), {type:'bar', data:{labels:SOCMTTAWK, datasets:[
  """
    + js_datasets
    + """,
  {label:'Target (5 min)',type:'line',data:Array(SOCMTTAWK.length).fill(5),borderColor:'#f59e0b',borderDash:[5,4],borderWidth:1.5,pointRadius:0,fill:false,tension:0}
]}, options:{responsive:true, maintainAspectRatio:false, plugins:{legend:LG, tooltip:TT}, scales:{x:XA, y:{type:'linear', beginAtZero:true, ticks:{color:'#64748b', callback:v=>v+' min'}, grid:{color:'rgba(255,255,255,0.05)'}}}}
}});"""
)

wk_range = f"{SOC_MTTA_WK[0] if SOC_MTTA_WK else '—'} – {SOC_MTTA_WK[-1] if SOC_MTTA_WK else '—'}"

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>SOC Member Performance — {cw_iso}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #080f1e; color: #e2e8f0; font-family: 'DM Sans', sans-serif; min-height: 100vh; }}
    .page {{ max-width: 900px; margin: 0 auto; padding: 40px 24px 80px; }}
    .header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 32px; padding-bottom: 24px; border-bottom: 1px solid rgba(255,255,255,0.07); }}
    .header-left h1 {{ font-size: 26px; font-weight: 700; color: #e2e8f0; letter-spacing: -0.5px; }}
    .header-left .subtitle {{ font-size: 13px; color: #64748b; margin-top: 4px; }}
    .header-right {{ font-size: 13px; color: #64748b; padding-top: 4px; }}
    .group-label {{ font-size: 11px; color: #64748b; letter-spacing: 0.1em; text-transform: uppercase; font-weight: 600; margin-bottom: 14px; }}
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
    .footer {{ text-align: center; padding-top: 40px; font-size: 11px; color: #64748b; line-height: 1.9; }}
  </style>
</head>
<body>
<div class="page">

  <div class="header">
    <div class="header-left">
      <h1>SOC Member Performance</h1>
      <div class="subtitle">Escalation acknowledgment &middot; {cw_iso}</div>
    </div>
    <div class="header-right">{today_str}</div>
  </div>

  <div class="group-label">Escalation Acknowledgment</div>

  <div class="stat-grid-4">
{stat_cards_html}  </div>

  <div class="chart-section">
    <div class="chart-title">SOC Member Avg MTTA — Week on Week</div>
    <div class="chart-note">Source: incident.io &middot; escalation_show &middot; Mean minutes from escalation created to ack &middot; Target: &lt;5 min</div>
    <div class="chart-container" style="height:280px"><canvas id="cSOCMTTA"></canvas></div>
  </div>

  <div class="footer">
    Generated {today_str} &middot; Fast Track SRE &middot; Data: incident.io<br>
    Weeks: {wk_range} &middot; All times UTC
  </div>

</div>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
{js_block}
</script>
</body>
</html>"""

with open(OUTPUT_FILE, "w") as f:
    f.write(html)

print(f"Report written to {OUTPUT_FILE}")
print(f"Current week: {cw_iso}  Previous: {pw_iso}")
print(f"Weeks in chart: {SOC_MTTA_WK}")
for p in SOC_PERSONS:
    print(f"  {SOC_SHORT[p]}: {soc_cards[p]['mtta_val']} min  ({soc_cards[p]['mtta_d']})")
