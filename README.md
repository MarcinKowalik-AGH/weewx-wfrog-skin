# WeeWX wFrog Skin

A modern **WeeWX 5.x** skin that recreates the visual style and chart logic of the classic **wFrog** weather-station interface.

**Author / maintainer:** Marcin Kowalik — <mkowalik@agh.edu.pl>  
**License:** GPL-3.0-or-later  
**Version:** 0.1.0

The project began as a migration of a WH3080-era home weather-station environment to WeeWX. It keeps the compact tan/wheat/green wFrog appearance while using a current Python 3 / WeeWX stack.

## Attribution

This project intentionally reproduces behavior from the original wFrog project:

- Laurent Bovet — <laurent.bovet@windmaster.ch>
- Jordi Puigsegur — <jordi.puigsegur@gmail.com>
- Original repository: <https://github.com/wfrog/wfrog>

Classic wFrog is licensed under GNU GPL version 3 or later. The port therefore uses **GPL-3.0-or-later** and preserves the upstream attribution. See `LICENSE`, `NOTICE`, and `AUTHORS.md`.

WeeWX is a separate project; this repository is an independent skin and chart generator for it.

## Features

- Classic wFrog-inspired layout and palette.
- WeeWX 5.x / Python 3 implementation.
- European weather units: **°C, hPa, km/h, mm, mm/h, W/m²**.
- Views for **3 Hours, 24 Hours, 7 Days, 30 Days, and 365 Days**.
- `charts` and classic-style monospace `numbers` views.
- Temperature / dew point with average, min/max envelope, maximum and minimum markers.
- Average humidity and pressure behavior matching the default wFrog charts.
- Wind average / gust envelope, direction labels, wind-direction radar, and Beaufort display.
- Cumulative Rain and separate Rain Rate charts.
- UV maximum-per-bucket behavior.
- Solar-radiation min/max envelope.
- systemd chart refresh timer.
- Optional `extras/envmon` support for Radioactive@Home and QCN histories.

## Tested environment

Initial development and validation were performed with:

- WeeWX 5.5.1
- Debian 13 (Trixie)
- Python 3
- SQLite WeeWX archive
- nginx serving the generated report directory

Other WeeWX 5.x installations should work, but have not all been tested.

## Installation

Clone the repository and run the installer as root:

```bash
git clone https://github.com/MarcinKowalik-AGH/weewx-wfrog-skin.git
cd weewx-wfrog-skin
sudo ./install.sh
```

Default paths:

```text
WeeWX configuration: /etc/weewx/weewx.conf
WeeWX archive:       /var/lib/weewx/weewx.sdb
Skin:                /etc/weewx/skins/Wfrog
Generated report:    /var/www/html/wfrog
Generators:          /opt/weewx-wfrog
```

The installer:

1. backs up `weewx.conf`;
2. installs the `Wfrog` skin;
3. registers `WfrogReport` under `StdReport`;
4. installs the SVG and numeric-summary generators;
5. installs and enables `weewx-wfrog-charts.timer`;
6. generates the initial report.

### Custom paths

Override defaults with environment variables:

```bash
sudo WEEWX_DB=/path/to/weewx.sdb \
     HTML_ROOT=/var/www/html/weather \
     WEEWX_CONF=/etc/weewx/weewx.conf \
     ./install.sh
```

## Web server

The skin generates static content. Point nginx, Apache, Caddy, or another web server at the configured `HTML_ROOT`.

For the default installation, browse to the URL mapped to:

```text
/var/www/html/wfrog
```

## Chart semantics

The goal is not merely to make charts *look* like wFrog. Aggregation was mapped from the historical wFrog configuration. See [`docs/wfrog-mapping.md`](docs/wfrog-mapping.md) for the exact mapping.

Examples:

- Rain = accumulated `fall`.
- Rain Rate = bucket maximum rate.
- Wind = average wind plus max-gust envelope.
- Solar radiation = min/max envelope rather than a simple average.
- UV = bucket maximum.

## Numeric summary

The `numbers` tab follows the old wFrog details-table concept and includes:

- temperature max / min / average;
- humidity max / min / average;
- pressure max / min / average;
- rain fall / maximum rate;
- wind average / maximum / predominant direction;
- UV maximum;
- solar-radiation maximum.

For the 365-day numeric view, monthly buckets are used, matching the historical wFrog details-table design.

## Optional ENVMON extension

`extras/envmon` contains the additional generator developed for the original installation:

- Radioactive@Home CPM and dose history;
- QCN Max Step;
- QCN Peak-to-Peak X/Y/Z.

It is deliberately optional so a normal WeeWX installation has no dependency on these sensors.

## Uninstall

```bash
sudo ./uninstall.sh
```

Generated web content is preserved by default. To remove it too:

```bash
sudo REMOVE_HTML=1 ./uninstall.sh
```

## Artwork

The repository includes the classic frog-under-umbrella image used during development. It is not claimed as an original work of Marcin Kowalik. See `ASSET-NOTICE.md` for the asset-specific provenance note.

## License

GPL-3.0-or-later. See `LICENSE`.

Copyright (C) 2026 Marcin Kowalik <mkowalik@agh.edu.pl>.

Original wFrog attribution and copyright notices are retained in `NOTICE` and source headers where the implementation closely follows wFrog behavior.
