#!/usr/bin/env python3
"""
Export soc-backfill-matteo-ceo.html to a PDF slide-deck.
Each slide becomes one landscape page (16:9, 1280 × 720 px).

Usage:
    python3 agents/export_ceo_deck.py
    python3 agents/export_ceo_deck.py --out /path/to/output.pdf
"""
import os
import subprocess
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_IN = os.path.join(_ROOT, "soc-backfill-matteo-ceo.html")
PDF_OUT = os.path.join(_ROOT, "cache", "soc-backfill-matteo-ceo.pdf")

if "--out" in sys.argv:
    idx = sys.argv.index("--out")
    PDF_OUT = sys.argv[idx + 1]

# Make all slides visible and lay them out vertically for print.
# The deck uses position:fixed .stage + display:none .slide / .slide.active.
SCREEN_CSS = """<style id="pdf-screen">
html.pdf-export body {
  height: auto !important;
  overflow: visible !important;
  background: #14091A !important;
}
html.pdf-export .stage {
  position: static !important;
  display: block !important;
  padding: 0 !important;
  height: auto !important;
}
html.pdf-export .slide {
  display: block !important;
  width: 1280px !important;
  height: 720px !important;
  padding-bottom: 0 !important;
  max-width: none !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  margin: 0 !important;
}
html.pdf-export .slide-inner {
  position: absolute !important;
  inset: 0 !important;
}
html.pdf-export .nav,
html.pdf-export .nav-p { display: none !important; }
</style>"""

PRINT_CSS = """<style id="pdf-print">
@media print {
  @page { size: 1280px 720px; margin: 0; }
  body {
    background: #14091A !important;
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

with open(HTML_IN, "r", encoding="utf-8") as fh:
    html = fh.read()

html = html.replace("<html", '<html class="pdf-export"', 1)
html = html.replace("</head>", SCREEN_CSS + "\n" + PRINT_CSS + "\n</head>", 1)

tmp = tempfile.NamedTemporaryFile(
    mode="w", suffix=".html", delete=False, dir="/tmp", encoding="utf-8"
)
tmp.write(html)
tmp.close()

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
    f"file://{tmp.name}",
]

print(f"Rendering {HTML_IN} → {PDF_OUT}")
try:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
finally:
    os.unlink(tmp.name)

if result.returncode == 0 and os.path.exists(PDF_OUT):
    size_kb = os.path.getsize(PDF_OUT) // 1024
    print(f"Done — {PDF_OUT} ({size_kb} KB)")
else:
    print("Export failed.")
    if result.stderr:
        print("Chrome stderr (last 2000 chars):")
        print(result.stderr[-2000:])
    sys.exit(1)
