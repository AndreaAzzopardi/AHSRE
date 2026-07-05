#!/usr/bin/env python3
"""
Export weekly_report.html to a PDF slide-deck.
Each HTML slide becomes one landscape page (16:9, 1280 × 720 px).

Strategy:
  - Add class="pdf-export" to <html> so all slides are visible when JS runs.
    Chart.js reads canvas dimensions at creation time; hidden canvases have
    zero dimensions and render blank even after becoming visible.
  - Disable Chart.js animations (duration:0) so charts draw synchronously.
  - Inject @media print rules for page breaks and page size.

Usage:
    python3 agents/export_pdf.py
    python3 agents/export_pdf.py --out /path/to/output.pdf
"""
import os
import subprocess
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_IN = os.path.join(_ROOT, "cache", "weekly_report.html")
PDF_OUT = os.path.join(_ROOT, "cache", "weekly_report.pdf")

if "--out" in sys.argv:
    idx = sys.argv.index("--out")
    PDF_OUT = sys.argv[idx + 1]

# ── CSS injected unconditionally (active when Chart.js initialises) ────────
# Slides must be *visible* (not display:none) when new Chart() runs so
# canvas elements have non-zero dimensions.
SCREEN_CSS = """<style id="pdf-screen">
html.pdf-export body {
  height: auto !important;
  overflow: visible !important;
}
html.pdf-export .topbar,
html.pdf-export .slide-tabs,
html.pdf-export .slide-controls { display: none !important; }
html.pdf-export .slides-wrap {
  overflow: visible !important;
  position: static !important;
  height: auto !important;
  flex: none !important;
}
html.pdf-export .slide {
  display: flex !important;
  position: static !important;
  width: 1280px !important;
  height: 720px !important;
  overflow: hidden !important;
  box-sizing: border-box !important;
}
</style>"""

# ── @media print: page size + breaks ──────────────────────────────────────
PRINT_CSS = """<style id="pdf-print">
@media print {
  @page { size: 1280px 720px; margin: 0; }
  body {
    background: #080f1e !important;
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }
  html.pdf-export .slide {
    break-after: page !important;
    page-break-after: always !important;
  }
  html.pdf-export .slide:last-of-type {
    break-after: avoid !important;
    page-break-after: avoid !important;
  }
}
</style>"""

# ── JS: disable Chart.js animations before charts are created ─────────────
ANIM_PATCH = "Chart.defaults.animation={duration:0};\n"

# ── Read and patch the HTML ────────────────────────────────────────────────
with open(HTML_IN, "r", encoding="utf-8") as fh:
    html = fh.read()

# 1. Mark <html> so the unconditional CSS selectors activate
html = html.replace("<html", '<html class="pdf-export"', 1)

# 2. Inject both CSS blocks in <head>
head_inject = SCREEN_CSS + "\n" + PRINT_CSS
html = html.replace("</head>", head_inject + "\n</head>", 1)

# 3. Disable animations at the very start of the inline chart script block.
#    Chart.js is vendored inline (no CDN tag since 2026-07-05), so anchor on
#    the chart-config script itself, which opens with the WK labels array.
CHART_SCRIPT_START = "<script>\nconst WK"
assert CHART_SCRIPT_START in html, "chart-config script anchor not found — did the generator layout change?"
html = html.replace(
    CHART_SCRIPT_START,
    f"<script>\n{ANIM_PATCH}const WK",
    1,
)

# ── Write patched HTML to a temp file ─────────────────────────────────────
tmp = tempfile.NamedTemporaryFile(
    mode="w", suffix=".html", delete=False, dir="/tmp", encoding="utf-8"
)
tmp.write(html)
tmp.close()
tmp_path = tmp.name

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
cmd = [
    CHROME,
    "--headless=new",
    "--no-sandbox",
    "--disable-gpu",
    "--disable-extensions",
    "--run-all-compositor-stages-before-draw",
    "--virtual-time-budget=4000",
    "--window-size=1280,720",
    f"--print-to-pdf={PDF_OUT}",
    "--print-to-pdf-no-header",
    "--no-margins",
    f"file://{tmp_path}",
]

print(f"Rendering {HTML_IN} → {PDF_OUT}")
try:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
finally:
    os.unlink(tmp_path)

if result.returncode == 0 and os.path.exists(PDF_OUT):
    size_kb = os.path.getsize(PDF_OUT) // 1024
    print(f"Done — {PDF_OUT} ({size_kb} KB)")
else:
    print("Export failed.")
    if result.stderr:
        print("Chrome stderr (last 2000 chars):")
        print(result.stderr[-2000:])
    sys.exit(1)
