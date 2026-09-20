# v0.1.0 — Initial public release

**Release date:** 2026-09-20  
**Maintainer:** Marcin Kowalik <mkowalik@agh.edu.pl>  
**License:** GPL-3.0-or-later

Initial public release of the WeeWX wFrog Skin.

## Highlights

- Classic wFrog-style skin for WeeWX 5.x.
- Source-faithful chart semantics derived from the historical wFrog configuration and renderer.
- European units: °C, hPa, km/h, mm, mm/h, W/m².
- 3 Hours / 24 Hours / 7 Days / 30 Days / 365 Days views.
- Classic `numbers` summary table.
- Temperature/dew point min/avg/max envelope.
- Wind/gust envelope, direction labels, wind radar, and Beaufort display.
- Cumulative Rain plus separate Rain Rate chart.
- UV maximum-per-bucket and Solar Radiation min/max behavior.
- systemd refresh timer and installer/uninstaller.
- Optional Radioactive@Home and QCN ENVMON extension.
- Original wFrog GPL attribution retained.

## Artwork

The classic logo is copied verbatim from upstream:

- repository: <https://github.com/wfrog/wfrog>
- path: `wfrender/config/logo.png`
- upstream blob SHA: `c9a30d970fd89a3ba8789745c4acf1ea360272a4`

The artwork is not claimed as an original work of Marcin Kowalik.

## Validation

GitHub Actions validates:

- Python syntax,
- Bash syntax,
- generator smoke test.
