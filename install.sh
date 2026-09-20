#!/bin/bash
# Copyright (C) 2026 Marcin Kowalik <mkowalik@agh.edu.pl>
# Portions conceptually based on wFrog by Laurent Bovet and Jordi Puigsegur.
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEEWX_CONF="${WEEWX_CONF:-/etc/weewx/weewx.conf}"
SKIN_ROOT="${SKIN_ROOT:-/etc/weewx/skins}"
WEEWX_DB="${WEEWX_DB:-/var/lib/weewx/weewx.sdb}"
HTML_ROOT="${HTML_ROOT:-/var/www/html/wfrog}"
INSTALL_ROOT="${INSTALL_ROOT:-/opt/weewx-wfrog}"
REPORT_NAME="${REPORT_NAME:-WfrogReport}"
WEEWX_USER="${WEEWX_USER:-weewx}"
WEEWX_GROUP="${WEEWX_GROUP:-weewx}"
STAMP="$(date +%Y%m%d-%H%M%S)"

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: run with sudo/root."
    exit 1
fi

if [ ! -f "$WEEWX_CONF" ]; then
    echo "ERROR: WeeWX configuration not found: $WEEWX_CONF"
    exit 1
fi

if [ ! -f "$WEEWX_DB" ]; then
    echo "ERROR: WeeWX SQLite archive not found: $WEEWX_DB"
    echo "Set WEEWX_DB=/path/to/weewx.sdb before running install.sh."
    exit 1
fi

if ! id "$WEEWX_USER" >/dev/null 2>&1; then
    echo "WARNING: user '$WEEWX_USER' does not exist; using root for the chart service."
    WEEWX_USER="root"
    WEEWX_GROUP="root"
fi

if ! getent group "$WEEWX_GROUP" >/dev/null 2>&1; then
    WEEWX_GROUP="$(id -gn "$WEEWX_USER")"
fi

if ! python3 -c 'import configobj' >/dev/null 2>&1; then
    echo "ERROR: Python module 'configobj' is required."
    echo "On Debian/Ubuntu install package python3-configobj."
    exit 1
fi

if ! command -v weectl >/dev/null 2>&1; then
    echo "ERROR: weectl was not found in PATH."
    exit 1
fi

echo "=== WeeWX wFrog Skin installer ==="
echo "Author: Marcin Kowalik <mkowalik@agh.edu.pl>"
echo

echo "[1/8] Backing up WeeWX configuration..."
cp -a "$WEEWX_CONF" "$WEEWX_CONF.before-wfrog-$STAMP"

echo "[2/8] Installing skin..."
rm -rf "$SKIN_ROOT/Wfrog"
install -d -m 0755 "$SKIN_ROOT/Wfrog"
cp -a "$PROJECT_DIR/skins/Wfrog/." "$SKIN_ROOT/Wfrog/"
chmod -R a+rX "$SKIN_ROOT/Wfrog"

echo "[3/8] Installing generators..."
install -d -o root -g root -m 0755 "$INSTALL_ROOT"
install -o root -g root -m 0755 "$PROJECT_DIR/bin/generate-wfrog-charts.py" "$INSTALL_ROOT/generate-wfrog-charts.py"
install -o root -g root -m 0755 "$PROJECT_DIR/bin/generate-wfrog-numbers.py" "$INSTALL_ROOT/generate-wfrog-numbers.py"

echo "[4/8] Creating output directory..."
install -d -o "$WEEWX_USER" -g "$WEEWX_GROUP" -m 2775 "$HTML_ROOT"

echo "[5/8] Registering WfrogReport in weewx.conf..."
python3 - "$WEEWX_CONF" "$REPORT_NAME" "$HTML_ROOT" <<'PY'
from configobj import ConfigObj
import sys

conf_path, report_name, html_root = sys.argv[1:4]
config = ConfigObj(conf_path, encoding='utf-8')
std = config.setdefault('StdReport', {})
report = std.setdefault(report_name, {})
report['skin'] = 'Wfrog'
report['enable'] = 'true'
report['lang'] = 'en'
report['unit_system'] = 'METRICWX'
report['HTML_ROOT'] = html_root
config.write()
print(f'Configured StdReport/{report_name} -> {html_root}')
PY

echo "[6/8] Installing systemd service and timer..."
sed \
    -e "s|@WEEWX_USER@|$WEEWX_USER|g" \
    -e "s|@WEEWX_GROUP@|$WEEWX_GROUP|g" \
    "$PROJECT_DIR/systemd/weewx-wfrog-charts.service" \
    > /etc/systemd/system/weewx-wfrog-charts.service
install -o root -g root -m 0644 "$PROJECT_DIR/systemd/weewx-wfrog-charts.timer" /etc/systemd/system/weewx-wfrog-charts.timer

cat > /etc/default/weewx-wfrog <<ENV
# WeeWX wFrog runtime configuration
# Maintainer: Marcin Kowalik <mkowalik@agh.edu.pl>
WEEWX_DB=$WEEWX_DB
HTML_ROOT=$HTML_ROOT
ENV

echo "[7/8] Generating report and charts..."
weectl report run "$REPORT_NAME" --config="$WEEWX_CONF"
sudo -u "$WEEWX_USER" "$INSTALL_ROOT/generate-wfrog-charts.py" --database "$WEEWX_DB" --output "$HTML_ROOT"
sudo -u "$WEEWX_USER" "$INSTALL_ROOT/generate-wfrog-numbers.py" --database "$WEEWX_DB" --output "$HTML_ROOT"

echo "[8/8] Enabling automatic refresh..."
systemctl daemon-reload
systemctl enable --now weewx-wfrog-charts.timer
systemctl restart weewx 2>/dev/null || true
systemctl start weewx-wfrog-charts.service

echo
for file in index.html wfrog.css frog_umbrella.svg weather-current.json wind_current.svg daytemp_wfrog.svg daynumbers_wfrog.txt; do
    test -s "$HTML_ROOT/$file" || {
        echo "ERROR: expected file missing: $HTML_ROOT/$file"
        exit 1
    }
done

echo "SUCCESS"
echo "Skin:       $SKIN_ROOT/Wfrog"
echo "Output:     $HTML_ROOT"
echo "Database:   $WEEWX_DB"
echo "Report:     $REPORT_NAME"
echo "Timer:      weewx-wfrog-charts.timer"
echo "Backup:     $WEEWX_CONF.before-wfrog-$STAMP"
