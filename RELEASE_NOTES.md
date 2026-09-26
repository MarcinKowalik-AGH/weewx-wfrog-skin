# v0.1.1 — Current-wind rendering refinement

**Release date:** 2026-09-26  
**Maintainer:** Marcin Kowalik <mkowalik@agh.edu.pl>  
**License:** GPL-3.0-or-later

Maintenance release of the WeeWX wFrog Skin.

## Changes

- Refined the compact current-wind compass geometry.
- Beaufort 0 / wind below 0.3 m/s is treated as calm, so no artificial green arrow is drawn.
- The green arrow head is smaller and proportional to the current-wind vector.
- The tan gust line now represents only the extra gust range beyond the green wind vector.
- The large wheat Beaufort digit and classic wFrog compass styling are preserved.
- Original wFrog attribution and GPL licensing are unchanged.

## Validation

GitHub Actions validates:

- Python syntax,
- Bash syntax,
- generator smoke test.

The release is based on the current `main` branch after successful validation.
