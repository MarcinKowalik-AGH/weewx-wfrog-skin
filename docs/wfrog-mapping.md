# Mapping classic wFrog behavior to WeeWX

Maintainer: **Marcin Kowalik <mkowalik@agh.edu.pl>**

This document records the mapping used by the WeeWX port. The reference implementation is the classic wFrog repository at <https://github.com/wfrog/wfrog>, especially:

- `wfrender/config/default/charts.yaml`
- `wfrender/config/default/chart_accumulator.yaml`
- `wfrender/config/default/current.yaml`
- `wfrender/config/wfrender.yaml`
- `wfrender/renderer/chart.py`
- `wfrender/templates/default/main.html`

## Period aggregation

| View | Classic wFrog | WeeWX wFrog Skin |
|---|---:|---:|
| 3 Hours | 1 minute | 5 minutes (matches the typical WeeWX archive interval used during development) |
| 24 Hours | 1 hour | 1 hour |
| 7 Days | 1 hour | 1 hour |
| 30 Days | 1 day | 1 day |
| 365 Days | 1 week for charts | 1 week for charts |
| 365 Days numbers | 1 month | 1 month |

## Charts

### Temperature and Dew Point

Classic wFrog:

- temperature average: green/default series;
- temperature min/max: wheat envelope;
- period maximum: dark red marker;
- period minimum: dark slate blue marker;
- dew point average: brown `#8D7641`, dashed;
- zero line: brown when the range crosses 0 °C.

### Humidity

The accumulator calculates average/minimum/maximum, but the default classic chart displays only the **average** humidity series.

### Pressure

The accumulator calculates average/minimum/maximum, but the default classic chart displays only the **average** pressure series.

### Wind and Gusts

- average wind: green;
- maximum gust per bucket: tan;
- area from gust to average: wheat;
- maximum gust marker: dark red;
- predominant direction labels are attached to the gust series.

### Wind Direction

The radar combines:

- direction frequency as green sector intensity;
- average wind by sector;
- maximum gust by sector;
- logarithmic radial scaling from the original renderer (`median=2.5`, `radius=18`).

### Rain

`rain.fall` is the **sum** within each bucket. The Rain chart then accumulates the bucket sums over the selected period and marks the final accumulated value in dark red.

### Rain Rate

`rain.rate` is the **maximum rain rate** within each bucket and is a separate chart.

### UV Index

The optional classic wFrog UV configuration uses the **maximum UV value** in each bucket.

### Solar Radiation

The optional classic wFrog solar configuration uses bucket **minimum and maximum** values, a wheat min/max envelope, and a dark red period-maximum marker.

## Current wind widget

Classic wFrog displays a large Beaufort digit in wheat and an arrow/radar presentation. The WeeWX port retains the Beaufort digit and direction behavior.

The project contains one deliberate ENVMON enhancement requested during development:

- thick green line = current/average wind;
- thin tan line = gust;
- both use the current reported wind direction.

This differs from the exact semantic meaning of the historical wFrog tan tail and is documented here intentionally.
