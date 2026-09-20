# Optional ENVMON extension

**Maintainer:** Marcin Kowalik <mkowalik@agh.edu.pl>  
**License:** GPL-3.0-or-later

This directory contains the optional chart generator used in the original ENVMON deployment that led to the WeeWX wFrog Skin.

It is **not required** for a normal WeeWX installation.

Supported external sources:

- Radioactive@Home CSV history (`measurements.csv`)
- QCN summary CSV history (`summary.csv`)

The generator creates wFrog-style SVG files for all standard periods:

- Radioactive dose: average plus tan min/max envelope, red period maximum, blue period minimum
- Radioactive CPM: average plus tan min/max envelope, red period maximum, blue period minimum
- QCN Max Step
- QCN Peak-to-Peak X/Y/Z (X green, Y blue, Z red)

Example:

```bash
sudo -u weewx ./generate-envmon-sensor-charts.py \
  --radioactive-csv /var/lib/envmon/radioactive/measurements.csv \
  --qcn-csv /var/lib/envmon/qcn/summary.csv \
  --output /var/www/html/wfrog
```

The base skin deliberately does not insert these graphs into `index.html.tmpl`, because most WeeWX installations do not have these sensors. The ENVMON deployment can add them as extra `.wf-graph` blocks using the generated names:

- `dayradioactive_dose_wfrog.svg`
- `dayradioactive_cpm_wfrog.svg`
- `dayqcn_maxstep_wfrog.svg`
- `dayqcn_p2p_wfrog.svg`

Replace the `day` prefix with `threehour`, `week`, `month`, or `year` through the same period-selection JavaScript used by the base skin.
