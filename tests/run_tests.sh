#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Beibit Sakhanov
# Самопроверки без внешних данных; с APPLY=путь/к/apply.py — ещё и сквозная проверка с redkollegiya.
set -e
here="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$here/tools/kk_clean.py" --selftest
python3 "$here/tools/kk_lint.py" --selftest
python3 "$here/tools/kk_parity.py" --selftest
python3 "$here/tools/kk_usage.py" --selftest
python3 "$here/tools/kk_lint.py" "$here/tests/sample_kk.md" --glossary "$here/data/glossary.yaml" --json /tmp/kk_layers.json >/dev/null
python3 -c "import json; f = json.load(open('/tmp/kk_layers.json'))['findings']; assert f and all(x.get('layer') for x in f), 'у находки нет слоя'; print('слои в находках: ok')"
if [ -n "$APPLY" ]; then
  python3 "$here/tools/kk_lint.py" "$here/tests/sample_kk.md" --glossary "$here/data/glossary.yaml" --json /tmp/kk_findings.json >/dev/null
  python3 "$APPLY" --text "$here/tests/sample_kk.md" --findings /tmp/kk_findings.json --out /tmp/kk_out.md --report /tmp/kk_report.json
  grep -q "ҚР Үкіметі" /tmp/kk_out.md && grep -q "ЖШС" /tmp/kk_out.md && echo "сквозная проверка с apply.py: ok"
fi
