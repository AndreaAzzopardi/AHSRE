#!/bin/sh
# Open the latest management-attention report: pull, then open.
cd "$(dirname "$0")" || exit 1
git pull --rebase --quiet
python3 - <<'EOF'
import json
d = json.load(open("cache/management_attention_cache.json"))["meta"].get("last_digest", {})
print(f"latest digest: {d.get('generated_at', '?')} — {d.get('under_control', '?')}")
EOF
open cache/management_attention_report.html
