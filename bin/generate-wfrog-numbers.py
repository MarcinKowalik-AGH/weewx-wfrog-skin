#!/usr/bin/env python3
# Copyright (C) 2026 Marcin Kowalik <mkowalik@agh.edu.pl>
# Portions based on the behavior and summary layout of wFrog:
# Copyright 2009 Laurent Bovet <laurent.bovet@windmaster.ch>
# Copyright 2009 Jordi Puigsegur <jordi.puigsegur@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later


import argparse
import math
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DB = Path('/var/lib/weewx/weewx.sdb')
OUT = Path('/var/www/html/wfrog')

PERIODS = {
    # Original wFrog summary logic used minute slices for 3 h. WeeWX archives
    # every 5 minutes here, so 5-minute buckets preserve all available data.
    'threehour': {'seconds': 3 * 3600, 'mode': 'fixed', 'bucket': 5 * 60},
    'day':       {'seconds': 24 * 3600, 'mode': 'fixed', 'bucket': 3600},
    'week':      {'seconds': 7 * 86400, 'mode': 'fixed', 'bucket': 3600},
    'month':     {'seconds': 30 * 86400, 'mode': 'day'},
    # Original wFrog 365-day details table uses monthly summaries.
    'year':      {'seconds': 365 * 86400, 'mode': 'month'},
}

COMPASS16 = [
    'N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
    'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW',
]

WEATHER_FIELDS = (
    'dateTime,usUnits,outTemp,outHumidity,barometer,'
    'windSpeed,windGust,windDir,rain,rainRate,UV,radiation'
)


def temp_c(v, u):
    if v is None:
        return None
    v = float(v)
    return (v - 32.0) * 5.0 / 9.0 if int(u) == 1 else v


def pressure_hpa(v, u):
    if v is None:
        return None
    v = float(v)
    return v * 33.8638866667 if int(u) == 1 else v


def wind_kmh(v, u):
    if v is None:
        return None
    v = float(v)
    u = int(u)
    if u == 1:
        return v * 1.609344
    if u == 16:
        return v
    if u == 17:
        return v * 3.6
    return v


def rain_mm(v, u):
    if v is None:
        return None
    v = float(v)
    u = int(u)
    if u == 1:
        return v * 25.4
    if u == 16:
        return v * 10.0
    if u == 17:
        return v
    return v


def number(v):
    if v in (None, ''):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def avg(values):
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def vmin(values):
    vals = [v for v in values if v is not None]
    return min(vals) if vals else None


def vmax(values):
    vals = [v for v in values if v is not None]
    return max(vals) if vals else None


def fmt(v, width, decimals=1):
    if v is None:
        return '-'.rjust(width)
    return f'{v:{width}.{decimals}f}'


def fmt_int(v, width):
    if v is None:
        return '-'.rjust(width)
    return f'{int(round(v)):{width}d}'


def direction_text(deg):
    if deg is None:
        return '-'
    return COMPASS16[int(round((float(deg) % 360.0) / 22.5)) % 16]


def predominant_direction(rows):
    sx = sy = 0.0
    have = False
    last_dir = None
    for row in rows:
        d = row.get('wind_dir')
        s = row.get('wind_avg')
        if d is not None:
            last_dir = d
        if d is None or s is None or s <= 0:
            continue
        a = math.radians(d)
        sx += s * math.sin(a)
        sy += s * math.cos(a)
        have = True
    if not have:
        return last_dir
    deg = math.degrees(math.atan2(sx, sy))
    return deg + 360.0 if deg < 0 else deg




def local_dt(ts):
    return datetime.fromtimestamp(ts)


def bucket_key(ts, spec):
    dt = local_dt(ts)
    mode = spec['mode']
    if mode == 'fixed':
        seconds = spec['bucket']
        return (ts // seconds) * seconds
    if mode == 'day':
        return int(datetime(dt.year, dt.month, dt.day).timestamp())
    if mode == 'month':
        return (dt.year, dt.month)
    raise ValueError(mode)


def bucket_label(key, prefix):
    if prefix == 'year':
        year, month = key
        return f'{year:04d}-{month:02d}'
    dt = local_dt(key)
    if prefix == 'threehour':
        return dt.strftime('%H:%M')
    if prefix in ('day', 'week'):
        return dt.strftime('%m/%d %H')
    if prefix == 'month':
        return dt.strftime('%m/%d')
    return str(key)


def load_weather(conn, start_ts, end_ts):
    rows = []
    sql = f'''SELECT {WEATHER_FIELDS}
              FROM archive
              WHERE dateTime >= ? AND dateTime <= ?
              ORDER BY dateTime'''
    for rec in conn.execute(sql, (start_ts, end_ts)):
        (ts, u, temp, hum, press, wind, gust, wdir,
         rain, rain_rate, uv, radiation) = rec
        rows.append({
            'ts': int(ts),
            'temp': temp_c(temp, u),
            'hum': number(hum),
            'press': pressure_hpa(press, u),
            'wind_avg': wind_kmh(wind, u),
            'wind_gust': wind_kmh(gust, u),
            'wind_dir': number(wdir),
            'rain': rain_mm(rain, u),
            'rain_rate': rain_mm(rain_rate, u),
            'uv': number(uv),
            'radiation': number(radiation),
        })
    return rows






def grouped(rows, spec):
    buckets = defaultdict(list)
    for row in rows:
        buckets[bucket_key(row['ts'], spec)].append(row)
    return buckets


def weather_summary(rows):
    return {
        'temp_max': vmax([r['temp'] for r in rows]),
        'temp_min': vmin([r['temp'] for r in rows]),
        'temp_avg': avg([r['temp'] for r in rows]),
        'hum_max': vmax([r['hum'] for r in rows]),
        'hum_min': vmin([r['hum'] for r in rows]),
        'hum_avg': avg([r['hum'] for r in rows]),
        'press_max': vmax([r['press'] for r in rows]),
        'press_min': vmin([r['press'] for r in rows]),
        'press_avg': avg([r['press'] for r in rows]),
        'rain_fall': sum((r['rain'] or 0.0) for r in rows),
        'rain_rate': vmax([r['rain_rate'] for r in rows]),
        'wind_avg': avg([r['wind_avg'] for r in rows]),
        'wind_max': vmax([
            r['wind_gust'] if r['wind_gust'] is not None else r['wind_avg']
            for r in rows
        ]),
        'wind_dir': predominant_direction(rows),
        'uv_max': vmax([r['uv'] for r in rows]),
        'solar_max': vmax([r['radiation'] for r in rows]),
    }








def weather_table(prefix, keys, wg):
    lines = [
        'Weather',
        '            Temp. °C          Humidity %        Pressure hPa      Rain mm        Wind km/h        UV   Solar',
        'Period      max   min   avg     max  min  avg      max    min    avg    fall  rate     avg    max  dir     max   W/m²',
    ]

    for key in keys:
        if key not in wg:
            continue
        s = weather_summary(wg[key])
        label = bucket_label(key, prefix).rjust(10)
        lines.append(
            f'{label}'
            f'{fmt(s["temp_max"],6,1)}{fmt(s["temp_min"],6,1)}{fmt(s["temp_avg"],6,1)}'
            f'{fmt(s["hum_max"],6,0)}{fmt(s["hum_min"],5,0)}{fmt(s["hum_avg"],5,0)}'
            f'{fmt(s["press_max"],9,1)}{fmt(s["press_min"],7,1)}{fmt(s["press_avg"],7,1)}'
            f'{fmt(s["rain_fall"],8,1)}{fmt(s["rain_rate"],6,1)}'
            f'{fmt(s["wind_avg"],8,1)}{fmt(s["wind_max"],7,1)}'
            f' {direction_text(s["wind_dir"]):>4}'
            f'{fmt(s["uv_max"],8,1)}{fmt_int(s["solar_max"],7)}'
        )

    if len(lines) == 3:
        lines.append('No weather summary data for this period.')
    return lines






def generate():
    global DB, OUT
    parser = argparse.ArgumentParser(description='Generate classic wFrog-style numeric summaries from a WeeWX SQLite archive.')
    parser.add_argument('--database', default=str(DB), help='Path to WeeWX SQLite archive')
    parser.add_argument('--output', default=str(OUT), help='HTML output directory')
    args = parser.parse_args()
    DB = Path(args.database)
    OUT = Path(args.output)
    OUT.mkdir(parents=True, exist_ok=True)
    if not DB.exists():
        raise SystemExit(f'Missing WeeWX database: {DB}')

    conn = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    try:
        row = conn.execute('SELECT MAX(dateTime) FROM archive').fetchone()
        latest = int(row[0]) if row and row[0] else int(datetime.now(timezone.utc).timestamp())
    finally:
        conn.close()

    for prefix, spec in PERIODS.items():
        start = latest - spec['seconds']

        conn = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
        try:
            weather = load_weather(conn, start, latest)
        finally:
            conn.close()

        wg = grouped(weather, spec)
        keys = sorted(wg.keys(), reverse=True)

        lines = []
        lines.extend(weather_table(prefix, keys, wg))

        (OUT / f'{prefix}numbers_wfrog.txt').write_text(
            "\\n".join(lines) + "\\n",
            encoding='utf-8',
        )


if __name__ == '__main__':
    generate()
