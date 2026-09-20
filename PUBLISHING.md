# Publishing to GitHub

Maintainer: **Marcin Kowalik <mkowalik@agh.edu.pl>**

Recommended repository metadata:

- Owner: `MarcinKowalik-AGH`
- Repository: `weewx-wfrog-skin`
- Visibility: public
- Description: `Classic wFrog-style skin and chart renderer for WeeWX 5.x`
- License: GPL-3.0-or-later
- Default branch: `main`
- First release/tag: `v0.1.0`
- Topics: `weewx`, `wfrog`, `weather-station`, `meteorology`, `weather-dashboard`, `python`, `wh3080`

The local Git history in the release bundle already contains:

- author: `Marcin Kowalik <mkowalik@agh.edu.pl>`;
- branch: `main`;
- annotated tag: `v0.1.0`.

After creating an empty GitHub repository, a local clone of the bundle can be pushed with:

```bash
git clone weewx-wfrog-skin-v0.1.0.bundle weewx-wfrog-skin
cd weewx-wfrog-skin
git remote add origin git@github.com:MarcinKowalik-AGH/weewx-wfrog-skin.git
git push -u origin main
git push origin v0.1.0
```

The software preserves original wFrog attribution in `NOTICE`, `AUTHORS.md`, and the source headers. Review `ASSET-NOTICE.md` before public redistribution of the historical frog artwork.
