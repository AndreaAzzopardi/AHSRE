#!/usr/bin/env python3
"""Render cache/management_attention_cache.json into a self-contained HTML report.

Deterministic: all judgment lives in the cache (written by the management-attention
agent); this script only lays it out. No external assets, light/dark aware,
phone-friendly. Run from anywhere: paths resolve relative to the repo root.
"""
import html
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, check=True).stdout.strip())
CACHE = REPO / "cache" / "management_attention_cache.json"
OUT = REPO / "cache" / "management_attention_report.html"

TIERS = [
    ("🚨", "Escalate now", "critical"),
    ("🔴", "Needs attention", "serious"),
    ("🟡", "Watch", "warning"),
    ("🟢", "Under control", "good"),
]
SEV_ORDER = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}

# docs/incident-handling-guidelines.md — code → short meaning (tooltips + legend)
GUIDELINES = {
    "A1": "Every incident has an owner and Head-of-SRE-level visibility",
    "A2": "No incident is “just closed” — every problem gets an action",
    "A3": "“It's just 10/30 minutes” is never an acceptable rationale",
    "A4": "Recurring problems are escalated to the owning team for a long-term fix",
    "B5": "Escalate early — not after hours without recovery",
    "B6": "Security incidents are P1 until de-escalated",
    "B7": "Critical-path failures are top priority",
    "B8": "Night and handover incidents must not be lost — assign, don't just mention",
    "C9": "Inform partners fast, even before root cause is known",
    "C10": "Close the loop — recovery comms sent, partner questions answered",
    "C11": "Comms accurate and crystal clear on impact",
    "D12": "Informed decisions over passive waiting",
    "D13": "Runbooks followed, basic checks done",
    "D14": "Don't close while partner-side work remains open",
    "D15": "The incident record is self-contained and phone-readable",
    "E16": "Digest answers: under control? urgent vs smaller? new bugs? how many open?",
}
_CODE_RE = re.compile(r"\b([A-E]1?\d)\b")


def esc_codes(s):
    """Escape text, then wrap guideline codes in <abbr> tooltips."""
    return _CODE_RE.sub(
        lambda m: (f'<abbr title="{html.escape(GUIDELINES[m.group(1)])}">{m.group(1)}</abbr>'
                   if m.group(1) in GUIDELINES else m.group(0)),
        html.escape(str(s)))


def esc(s):
    return html.escape(str(s)) if s is not None else ""


def age(first_seen, now):
    try:
        t = datetime.fromisoformat(str(first_seen).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return ""
    d = now - t
    if d.days >= 2:
        return f"{d.days}d"
    h = int(d.total_seconds() // 3600)
    return f"{h}h" if h >= 2 else f"{int(d.total_seconds() // 60)}m"


def inc_links(ref, entry):
    num = ref.split("-")[-1]
    out = (f'<a href="https://app.incident.io/fasttrack-solutions/incidents/{esc(num)}"'
           f' target="_blank">{esc(ref)}</a>')
    ch = entry.get("slack_channel_id")
    if ch:
        out += (f' <a class="chip" href="https://fasttrack-solutions.slack.com/archives/{esc(ch)}"'
                f' target="_blank">slack</a>')
    if entry.get("intercom_conversation_id"):
        out += (f' <a class="chip" href="https://app.eu.intercom.com/a/inbox/m0cwp22u/inbox/shared/all/'
                f'conversation/{esc(entry["intercom_conversation_id"])}" target="_blank">intercom</a>')
    return out


def li_list(items):
    return "".join(f"<li>{esc(i)}</li>" for i in items)


def card(ref, entry, now, collapsed):
    syn = entry.get("synthesis") or {}
    name = entry.get("name") or (syn.get("summary") or "")[:90] or ref
    head = (f'<div class="card-head">{inc_links(ref, entry)}'
            f'<span class="sev">{esc(entry.get("severity", "?"))}</span>'
            f'<span class="age">open {esc(age(entry.get("first_seen"), now))}</span></div>'
            f'<div class="card-name">{esc(name)}</div>')
    body = ""
    for n in entry.get("management_notes") or []:
        body += (f'<div class="mnote">📝 <strong>Management note ({esc(n.get("at", ""))})</strong> '
                 f'{esc(n.get("note", ""))}</div>')
    if syn.get("why"):
        body += f'<p class="why">{esc_codes(syn["why"])}</p>'
    if syn.get("summary") and syn.get("summary") != name:
        body += f'<p class="sum">{esc(syn["summary"])}</p>'
    if syn.get("open_breaches"):
        body += ('<div class="lbl">Open breaches</div><ul>'
                 + "".join(f"<li>{esc_codes(i)}</li>" for i in syn["open_breaches"]) + "</ul>")
    if syn.get("proposals"):
        body += f'<div class="lbl">Proposed / pending</div><ul>{li_list(syn["proposals"])}</ul>'
    p = syn.get("partner") or {}
    if p:
        bits = []
        if p.get("first_reported"):
            bits.append(f"first reported {esc(str(p['first_reported'])[:16])}")
        if p.get("answered") is False:
            bits.append("<strong>last partner message unanswered</strong>")
        bits += [esc(x) for x in (p.get("promises") or [])]
        if bits:
            body += f'<div class="lbl">Partner view</div><ul>{"".join(f"<li>{b}</li>" for b in bits)}</ul>'
    if syn.get("key_events"):
        body += (f'<details><summary>Timeline ({len(syn["key_events"])})</summary>'
                 f'<ul>{li_list(syn["key_events"])}</ul></details>')
    if syn.get("suggested_action"):
        body += f'<p class="action">→ {esc_codes(syn["suggested_action"])}</p>'
    if collapsed:
        return (f'<details class="card"><summary>{head}</summary>'
                f'<div class="card-body">{body}</div></details>')
    return f'<div class="card">{head}<div class="card-body">{body}</div></div>'


def kv_rows(pairs):
    return "".join(f'<div class="kv"><span>{esc(k)}</span><span>{v}</span></div>'
                   for k, v in pairs if v)


def main():
    data = json.loads(CACHE.read_text())
    meta = data.get("meta", {})
    dg = meta.get("last_digest", {})
    incidents = data.get("incidents", {})
    now = datetime.now(timezone.utc)
    gen = dg.get("generated_at") or meta.get("last_run_at") or now.isoformat()

    tiles = ""
    pages = ""
    navs = ['<button class="nav-btn active" data-page="overview">Overview</button>']
    for icon, label, cls in TIERS:
        refs = sorted((r for r, e in incidents.items() if e.get("classification") == icon),
                      key=lambda r: (SEV_ORDER.get(incidents[r].get("severity"), 9),
                                     str(incidents[r].get("first_seen", ""))))
        tiles += (f'<div class="tile {cls}" data-page="{cls}" role="button" tabindex="0">'
                  f'<div class="tile-n">{len(refs)}</div>'
                  f'<div class="tile-l">{icon} {esc(label)}</div></div>')
        navs.append(f'<button class="nav-btn {cls}" data-page="{cls}">{icon} {esc(label)} '
                    f'<span class="count">{len(refs)}</span></button>')
        cards = "".join(card(r, incidents[r], now, collapsed=(icon in "🟡🟢")) for r in refs)
        extra = ""
        if icon == "🟢" and dg.get("green_note"):
            extra = f'<p class="note">{esc(dg["green_note"])}</p>'
        pages += (f'<section class="page {cls}" id="page-{cls}" hidden>'
                  f'<h2>{icon} {esc(label)} <span class="count">{len(refs)}</span></h2>'
                  f'{extra}{cards or "<p class=note>none</p>"}</section>')

    lists = ""
    for key, title in (("new", "🆕 New since last digest"),
                       ("resolved", "✅ Resolved since last digest"),
                       ("handover", "📋 Overnight handover")):
        items = dg.get(key)
        if items is None:
            continue
        rows = "".join(
            f'<li><strong>{esc(i.get("ref") or i.get("item"))}</strong> — '
            f'{esc(i.get("note") or i.get("status"))}</li>'
            for i in items) or "<li>none</li>"
        lists += f'<div class="mini"><h3>{title}</h3><ul>{rows}</ul></div>'
    if dg.get("not_assessed"):
        lists += ('<div class="mini"><h3>⚠ Not assessed this run</h3><ul><li>'
                  + esc(", ".join(dg["not_assessed"])) + "</li></ul></div>")

    header = kv_rows([
        ("Under control?", esc(dg.get("under_control"))),
        ("Urgent vs smaller", esc(dg.get("urgent_vs_smaller"))),
        ("Total open (active, excl. triage)",
         esc(f"{meta.get('total_open', '?')} {dg.get('total_open_delta', '')}".strip())),
    ])

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Management Attention — {esc(str(gen)[:16])}</title>
<style>
:root {{ --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --line:#e1e0d9; --good:#0ca30c; --warning:#fab219; --serious:#ec835a; --critical:#d03b3b; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --page:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink2:#c3c2b7; --line:#2c2c2a; }} }}
* {{ box-sizing:border-box; margin:0 }}
body {{ background:var(--page); color:var(--ink); font:15px/1.5 -apple-system,'Segoe UI',Roboto,sans-serif;
  max-width:880px; margin:0 auto; padding:20px 14px 60px }}
h1 {{ font-size:1.25rem; margin-bottom:2px }}
.gen {{ color:var(--muted); font-size:.8rem; margin-bottom:14px }}
.kv {{ display:flex; gap:10px; padding:3px 0; font-size:.95rem }}
.kv span:first-child {{ color:var(--ink2); min-width:210px; flex-shrink:0 }}
.nav {{ position:sticky; top:0; z-index:5; display:flex; gap:6px; flex-wrap:wrap;
  background:var(--page); padding:8px 0 10px; border-bottom:1px solid var(--line); margin-bottom:12px }}
.nav-btn {{ font:inherit; font-size:.85rem; color:var(--ink2); background:var(--surface);
  border:1px solid var(--line); border-radius:16px; padding:4px 12px; cursor:pointer }}
.nav-btn.active {{ color:var(--ink); font-weight:600; border-color:var(--muted) }}
.nav-btn.critical.active {{ border-color:var(--critical) }} .nav-btn.serious.active {{ border-color:var(--serious) }}
.nav-btn.warning.active {{ border-color:var(--warning) }} .nav-btn.good.active {{ border-color:var(--good) }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:8px; margin:16px 0 }}
.tile {{ background:var(--surface); border:1px solid var(--line); border-left:4px solid var(--muted);
  border-radius:6px; padding:10px 12px; cursor:pointer }}
.tile-n {{ font-size:1.6rem; font-weight:700 }}
.tile-l {{ font-size:.78rem; color:var(--ink2) }}
.tile.critical {{ border-left-color:var(--critical) }} .tile.serious {{ border-left-color:var(--serious) }}
.tile.warning {{ border-left-color:var(--warning) }} .tile.good {{ border-left-color:var(--good) }}
.mini {{ background:var(--surface); border:1px solid var(--line); border-radius:6px;
  padding:10px 14px; margin:8px 0 }}
.mini h3 {{ font-size:.9rem; margin-bottom:4px }}
.mini ul {{ padding-left:18px; font-size:.88rem; color:var(--ink2) }}
section.page {{ margin-top:10px }}
h2 {{ font-size:1.05rem; padding-bottom:5px; border-bottom:2px solid var(--line) }}
.count {{ color:var(--muted); font-weight:400 }}
.card {{ background:var(--surface); border:1px solid var(--line); border-radius:6px;
  padding:12px 14px; margin:10px 0 }}
section.critical .card {{ border-left:4px solid var(--critical) }}
section.serious .card {{ border-left:4px solid var(--serious) }}
section.warning .card {{ border-left:4px solid var(--warning) }}
section.good .card {{ border-left:4px solid var(--good) }}
.card-head {{ display:flex; align-items:baseline; gap:10px; font-weight:600 }}
.card-head a {{ color:inherit }}
.sev {{ font-size:.75rem; border:1px solid var(--line); border-radius:4px; padding:0 6px }}
.age {{ color:var(--muted); font-size:.8rem; font-weight:400 }}
.chip {{ font-size:.72rem; color:var(--ink2)!important; border:1px solid var(--line);
  border-radius:9px; padding:0 7px; text-decoration:none; font-weight:400 }}
.card-name {{ color:var(--ink2); font-size:.92rem; margin:2px 0 6px }}
.card-body p, .card-body ul {{ margin:6px 0; font-size:.9rem }}
.card-body ul {{ padding-left:18px; color:var(--ink2) }}
.mnote {{ background:color-mix(in srgb, var(--warning) 12%, var(--surface)); border:1px solid var(--warning);
  border-radius:6px; padding:8px 10px; margin:8px 0; font-size:.9rem }}
.why {{ font-weight:500 }}
.sum {{ color:var(--ink2) }}
.lbl {{ font-size:.72rem; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); margin-top:8px }}
.action {{ border-top:1px solid var(--line); padding-top:6px; font-weight:600 }}
details.card > summary {{ cursor:pointer; list-style:none }}
details.card > summary::-webkit-details-marker {{ display:none }}
details summary {{ cursor:pointer; font-size:.88rem; color:var(--ink2) }}
.note {{ color:var(--muted); font-size:.88rem; margin-top:6px }}
abbr {{ text-decoration:underline dotted var(--muted); cursor:help }}
</style></head><body>
<h1>🎯 Management Attention</h1>
<div class="gen">generated {esc(str(gen).replace("T", " ")[:16])} UTC · guidelines: docs/incident-handling-guidelines.md</div>
<nav class="nav">{"".join(navs)}</nav>
<section class="page" id="page-overview">
{header}
<div class="tiles">{tiles}</div>
{lists}
<details class="mini"><summary><strong>Guideline codes legend</strong> (docs/incident-handling-guidelines.md)</summary>
<ul>{"".join(f"<li><strong>{k}</strong> — {esc(v)}</li>" for k, v in GUIDELINES.items())}</ul></details>
</section>
{pages}
<script>
(function () {{
  var pages = document.querySelectorAll('.page');
  var btns = document.querySelectorAll('.nav-btn');
  function show(name) {{
    pages.forEach ? null : 0;
    Array.prototype.forEach.call(pages, function (p) {{ p.hidden = (p.id !== 'page-' + name); }});
    Array.prototype.forEach.call(btns, function (b) {{
      b.classList.toggle('active', b.dataset.page === name); }});
    if (history.replaceState) history.replaceState(null, '', '#' + name);
    window.scrollTo(0, 0);
  }}
  Array.prototype.forEach.call(document.querySelectorAll('[data-page]'), function (el) {{
    el.addEventListener('click', function () {{ show(el.dataset.page); }});
    el.addEventListener('keydown', function (e) {{
      if (e.key === 'Enter' || e.key === ' ') {{ e.preventDefault(); show(el.dataset.page); }} }});
  }});
  var h = location.hash.replace('#', '');
  show(document.getElementById('page-' + h) ? h : 'overview');
}})();
</script>
</body></html>"""
    OUT.write_text(page)
    n = len(incidents)
    print(f"OK: {OUT.relative_to(REPO)} — {n} incidents, "
          + ", ".join(f"{i}{sum(1 for e in incidents.values() if e.get('classification') == i)}"
                      for i, _, _ in TIERS))


if __name__ == "__main__":
    sys.exit(main())
