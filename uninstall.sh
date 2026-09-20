#!/bin/bash
# Copyright (C) 2026 Marcin Kowalik <mkowalik@agh.edu.pl>
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

WEEWX_CONF="${WEEWX_CONF:-/etc/weewx/weewx.conf}"
SKIN_ROOT="${SKIN_ROOT:-/etc/weewx/skins}"
INSTALL_ROOT="${INSTALL_ROOT:-/opt/weewx-wfrog}"
HTML_ROOT="${HTML_ROOT:-/var/www/html/wfrog}"
REPORT_NAME="${REPORT_NAME:-WfrogReport}"
REMOVE_HTML="${REMOVE_HTML:-0}"
STAMP="$(date +%Y%m%d-%H%M%S)"

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: run with sudo/root."
    exit 1
fi

systemctl disable --now weewx-wfrog-charts.timer 2>/dev/null || true
rm -f /etc/systemd/system/weewx-wfrog-charts.timer
rm -f /etc/systemd/system/weewx-wfrog-charts.service
rm -f /etc/default/weewx-wfrog
systemctl daemon-reload

rm -rf "$INSTALL_ROOT"
rm -rf "$SKIN_ROOT/Wfrog"

if [ -f "$WEEWX_CONF" ] && python3 -c 'import configobj' >/dev/null 2>&1; then
    cp -a "$WEEWX_CONF" "$WEEWX_CONF.before-wfrog-uninstall-$STAMP"
    python3 - "$WEEWX_CONF" "$REPORT_NAME" <<'PY'
from configobj import ConfigObj
import sys

path, report = sys.argv[1:3]
config = ConfigObj(path, encoding='utf-8')
std = config.get('StdReport', {})
if report in std:
    del std[report]
    config.write()
    print(f'Removed StdReport/{report}')
PY
fi

if [ "$REMOVE_HTML" = "1" ]; then
    rm -rf "$HTML_ROOT"
    echo "Removed generated HTML: $HTML_ROOT"
else
    echo "Generated HTML preserved: $HTML_ROOT"
    echo "Use REMOVE_HTML=1 sudo -E ./uninstall.sh to remove it as well."
fi

echo "Uninstall complete."
