#!/usr/bin/env python3
# Optional ENVMON extension for WeeWX wFrog Skin
# Copyright (C) 2026 Marcin Kowalik <mkowalik@agh.edu.pl>
# Portions reproduce classic wFrog chart semantics.
# Original wFrog: Copyright 2009 Laurent Bovet <laurent.bovet@windmaster.ch>
#                 Copyright 2009 Jordi Puigsegur <jordi.puigsegur@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later


import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

RADIOACTIVE_CSV = Path("/var/lib/envmon/radioactive/measurements.csv")
QCN_CSV = Path("/var/lib/envmon/qcn/summary.csv")
OUT = Path("/var/www/html/wfrog")

PERIODS = {
    "threehour": (3 * 3600, 5 * 60),
    "day": (24 * 3600, 5 * 60),
    "week": (7 * 86400, 3600),
    "month": (30 * 86400, 3 * 3600),
    "year": (365 * 86400, 86400),
}

GREEN = "#008000"
TEXT = "#8d7641"
TAN = "#d2b48c"
DARKRED = "#8b0000"
DARKBLUE = "#483d8b"
GRID = "#eadfcd"
WHITE = "#ffffff"


def parse_utc(value):
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def f(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def mean(values):
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def min_value(values):
    vals = [v for v in values if v is not None]
    return min(vals) if vals else None


def max_value(values):
    vals = [v for v in values if v is not None]
    return max(vals) if vals else None


def latest_timestamp(rad_rows, qcn_rows):
    values = [r["ts"] for r in rad_rows] + [r["ts"] for r in qcn_rows]
    return max(values) if values else int(datetime.now(timezone.utc).timestamp())


def normalize_radioactive(rows):
    out = []
    for row in rows:
        if row.get("status") != "ok":
            continue
        try:
            ts = parse_utc(row["timestamp_utc"])
        except Exception:
            continue

        cpm = f(row.get("cpm"))
        dose = f(row.get("dose_uSv_h_est"))
        if cpm is None and dose is None:
            continue

        out.append({
            "ts": ts,
            "cpm": cpm,
            "dose": dose,
        })
    return out


def normalize_qcn(rows):
    out = []
    for row in rows:
        try:
            ts = parse_utc(row["timestamp_utc"])
        except Exception:
            continue

        out.append({
            "ts": ts,
            "max_step": f(row.get("max_step")),
            "p2p_x": f(row.get("p2p_x")),
            "p2p_y": f(row.get("p2p_y")),
            "p2p_z": f(row.get("p2p_z")),
        })
    return out


def filter_period(rows, start_ts, end_ts):
    return [r for r in rows if start_ts <= r["ts"] <= end_ts]


def aggregate_radioactive(rows, interval):
    buckets = {}
    for row in rows:
        key = (row["ts"] // interval) * interval
        buckets.setdefault(key, []).append(row)

    result = []
    for key in sorted(buckets):
        group = buckets[key]
        item = {"ts": key + interval // 2}

        for field in ("cpm", "dose"):
            values = [r.get(field) for r in group]
            item[f"{field}_avg"] = mean(values)
            item[f"{field}_min"] = min_value(values)
            item[f"{field}_max"] = max_value(values)

        result.append(item)

    return result


def aggregate_qcn(rows, interval):
    buckets = {}
    for row in rows:
        key = (row["ts"] // interval) * interval
        buckets.setdefault(key, []).append(row)

    result = []
    for key in sorted(buckets):
        group = buckets[key]
        item = {"ts": key + interval // 2}

        for field in ("max_step", "p2p_x", "p2p_y", "p2p_z"):
            item[field] = mean([r.get(field) for r in group])

        result.append(item)

    return result


def svg_text(x, y, text, size=9, color=TEXT, anchor="middle", weight="normal"):
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}" '
        f'fill="{color}" font-family="Arial,Helvetica,sans-serif" '
        f'font-size="{size}" font-weight="{weight}">{text}</text>'
    )


def write_svg(name, body, width=330, height=210):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {height}">'
        f'<rect width="100%" height="100%" fill="{WHITE}"/>'
        f'{body}</svg>\n',
        encoding="utf-8",
    )


def geometry():
    width, height = 330, 210
    left, top, right, bottom = 39, 18, 12, 28
    return (
        width, height, left, top, right, bottom,
        width - left - right,
        height - top - bottom,
    )


def nice_range(values, include_zero=False):
    vals = [v for v in values if v is not None]
    if not vals:
        return 0.0, 1.0

    lo, hi = min(vals), max(vals)

    if include_zero:
        lo = min(lo, 0.0)
        hi = max(hi, 0.0)

    if abs(hi - lo) < 1e-12:
        pad = max(abs(hi) * 0.05, 0.1)
    else:
        pad = (hi - lo) * 0.08

    return lo - pad, hi + pad


def time_label(ts, seconds):
    dt = datetime.fromtimestamp(ts)

    if seconds <= 86400:
        return dt.strftime("%H:%M")
    if seconds <= 7 * 86400:
        return dt.strftime("%d %H")
    if seconds <= 45 * 86400:
        return dt.strftime("%d/%m")

    return dt.strftime("%m/%y")


def base_axes(values, start_ts, end_ts, seconds, include_zero=False):
    (
        width, height, left, top, right, bottom, pw, ph
    ) = geometry()

    ylo, yhi = nice_range(values, include_zero)
    if yhi <= ylo:
        yhi = ylo + 1.0

    body = ""

    for i in range(6):
        frac = i / 5.0
        y = top + ph * frac
        val = yhi - (yhi - ylo) * frac

        body += (
            f'<line x1="{left}" y1="{y:.2f}" '
            f'x2="{left + pw}" y2="{y:.2f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        body += svg_text(
            left - 5, y + 3, f"{val:.3f}",
            size=8, color="#a08b5b", anchor="end",
        )

    for i in range(6):
        x = left + pw * i / 5.0
        ts = int(start_ts + (end_ts - start_ts) * i / 5.0)

        body += (
            f'<line x1="{x:.2f}" y1="{top}" '
            f'x2="{x:.2f}" y2="{top + ph}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        body += svg_text(
            x, height - 9,
            time_label(ts, seconds),
            size=8, color="#a08b5b",
        )

    return (
        width, height, left, top, pw, ph,
        ylo, yhi, body,
    )


def points(rows, field, left, top, pw, ph, ylo, yhi, start_ts, end_ts):
    result = []
    span = max(1, end_ts - start_ts)

    for row in rows:
        value = row.get(field)

        if value is None:
            result.append(None)
            continue

        x = left + (row["ts"] - start_ts) / float(span) * pw
        y = top + ph - (value - ylo) / float(yhi - ylo) * ph
        result.append((x, y))

    return result


def segments(pts, color, width=2.0, dash=None):
    body = ""
    current = []

    for p in pts + [None]:
        if p is None:
            if len(current) >= 2:
                dash_attr = (
                    f' stroke-dasharray="{dash}"'
                    if dash else ""
                )
                body += (
                    f'<polyline points="'
                    f'{" ".join(f"{x:.2f},{y:.2f}" for x, y in current)}" '
                    f'fill="none" stroke="{color}" '
                    f'stroke-width="{width}"{dash_attr}/>'
                )
            current = []
        else:
            current.append(p)

    return body


def fill_between(low_pts, high_pts, color=TAN, opacity=0.20):
    body = ""
    low_segment = []
    high_segment = []

    def flush():
        nonlocal body, low_segment, high_segment

        if len(low_segment) >= 2 and len(high_segment) >= 2:
            polygon = high_segment + list(reversed(low_segment))

            body += (
                f'<polygon points="'
                f'{" ".join(f"{x:.2f},{y:.2f}" for x, y in polygon)}" '
                f'fill="{color}" fill-opacity="{opacity}" '
                f'stroke="none"/>'
            )

        low_segment = []
        high_segment = []

    pairs = list(zip(low_pts, high_pts))
    pairs.append((None, None))

    for low, high in pairs:
        if low is None or high is None:
            flush()
        else:
            low_segment.append(low)
            high_segment.append(high)

    return body


def marker(x, y, bottom_y, label, color, side="right"):
    dx = 5 if side == "right" else -5
    anchor = "start" if side == "right" else "end"

    return (
        f'<line x1="{x:.2f}" y1="{bottom_y:.2f}" '
        f'x2="{x:.2f}" y2="{y:.2f}" '
        f'stroke="{color}" stroke-width="1"/>'
        + svg_text(
            x + dx, max(12, y - 4), label,
            size=9, color=color,
            anchor=anchor, weight="bold",
        )
    )


def radioactive_range_chart(
    filename,
    rows,
    field_prefix,
    start_ts,
    end_ts,
    seconds,
    decimals,
    include_zero=False,
):
    avg_field = f"{field_prefix}_avg"
    min_field = f"{field_prefix}_min"
    max_field = f"{field_prefix}_max"

    values = []

    for row in rows:
        values.extend([
            row.get(min_field),
            row.get(avg_field),
            row.get(max_field),
        ])

    if not rows or not any(v is not None for v in values):
        write_svg(
            filename,
            svg_text(165, 105, "No Radioactive data", 12),
        )
        return

    (
        width, height, left, top, pw, ph,
        ylo, yhi, body,
    ) = base_axes(
        values,
        start_ts,
        end_ts,
        seconds,
        include_zero,
    )

    pts_min = points(
        rows, min_field,
        left, top, pw, ph, ylo, yhi,
        start_ts, end_ts,
    )
    pts_avg = points(
        rows, avg_field,
        left, top, pw, ph, ylo, yhi,
        start_ts, end_ts,
    )
    pts_max = points(
        rows, max_field,
        left, top, pw, ph, ylo, yhi,
        start_ts, end_ts,
    )

    body += fill_between(
        pts_min, pts_max,
        color=TAN,
        opacity=0.22,
    )

    body += segments(
        pts_min,
        color=TAN,
        width=1.15,
    )
    body += segments(
        pts_max,
        color=TAN,
        width=1.15,
    )
    body += segments(
        pts_avg,
        color=GREEN,
        width=2.0,
    )

    x = left + 4

    body += (
        f'<line x1="{x}" y1="10" '
        f'x2="{x + 14}" y2="10" '
        f'stroke="{GREEN}" stroke-width="2"/>'
    )
    body += svg_text(
        x + 18, 13, "avg",
        size=8, color=GREEN,
        anchor="start", weight="bold",
    )

    x += 42

    body += (
        f'<line x1="{x}" y1="10" '
        f'x2="{x + 14}" y2="10" '
        f'stroke="{TAN}" stroke-width="1.2"/>'
    )
    body += svg_text(
        x + 18, 13, "min/max",
        size=8, color=TEXT,
        anchor="start", weight="bold",
    )

    valid_max = [
        (i, row.get(max_field))
        for i, row in enumerate(rows)
        if row.get(max_field) is not None
    ]
    valid_min = [
        (i, row.get(min_field))
        for i, row in enumerate(rows)
        if row.get(min_field) is not None
    ]

    if valid_max:
        imax, maxv = max(valid_max, key=lambda x: x[1])
        p = pts_max[imax]

        if p:
            body += marker(
                p[0], p[1], top + ph,
                f"{maxv:.{decimals}f}",
                DARKRED,
                "right",
            )

    if valid_min:
        imin, minv = min(valid_min, key=lambda x: x[1])
        p = pts_min[imin]

        if p:
            body += marker(
                p[0], p[1], top + ph,
                f"{minv:.{decimals}f}",
                DARKBLUE,
                "left",
            )

    write_svg(filename, body, width, height)


def single_series_chart(
    filename,
    rows,
    field,
    start_ts,
    end_ts,
    seconds,
    decimals=3,
    include_zero=False,
):
    values = [r.get(field) for r in rows]

    if not rows or not any(v is not None for v in values):
        write_svg(filename, svg_text(165, 105, "No data", 12))
        return

    (
        width, height, left, top, pw, ph,
        ylo, yhi, body,
    ) = base_axes(
        values,
        start_ts,
        end_ts,
        seconds,
        include_zero,
    )

    pts = points(
        rows, field,
        left, top, pw, ph, ylo, yhi,
        start_ts, end_ts,
    )

    body += segments(
        pts,
        color=GREEN,
        width=2.0,
    )

    valid = [
        (i, r.get(field))
        for i, r in enumerate(rows)
        if r.get(field) is not None
    ]

    if valid:
        imax, maxv = max(valid, key=lambda x: x[1])
        imin, minv = min(valid, key=lambda x: x[1])

        if pts[imax]:
            body += marker(
                pts[imax][0], pts[imax][1],
                top + ph,
                f"{maxv:.{decimals}f}",
                DARKRED,
                "right",
            )

        if pts[imin]:
            body += marker(
                pts[imin][0], pts[imin][1],
                top + ph,
                f"{minv:.{decimals}f}",
                DARKBLUE,
                "left",
            )

    write_svg(filename, body, width, height)


def qcn_p2p_chart(
    filename,
    rows,
    start_ts,
    end_ts,
    seconds,
):
    fields = [
        ("p2p_x", GREEN, None, "X"),
        ("p2p_y", DARKBLUE, None, "Y"),
        ("p2p_z", DARKRED, None, "Z"),
    ]

    values = []

    for field, _, _, _ in fields:
        values.extend(
            r.get(field)
            for r in rows
        )

    if not rows or not any(v is not None for v in values):
        write_svg(
            filename,
            svg_text(165, 105, "No QCN data", 12),
        )
        return

    (
        width, height, left, top, pw, ph,
        ylo, yhi, body,
    ) = base_axes(
        values,
        start_ts,
        end_ts,
        seconds,
        True,
    )

    for field, color, dash, _ in fields:
        body += segments(
            points(
                rows, field,
                left, top, pw, ph, ylo, yhi,
                start_ts, end_ts,
            ),
            color,
            1.8,
            dash,
        )

    x = left + 5

    for _, color, _, label in fields:
        body += (
            f'<line x1="{x}" y1="10" '
            f'x2="{x + 13}" y2="10" '
            f'stroke="{color}" stroke-width="2"/>'
        )

        body += svg_text(
            x + 17, 13, label,
            size=8, color=color,
            anchor="start", weight="bold",
        )

        x += 38

    write_svg(filename, body, width, height)


def generate():
    global RADIOACTIVE_CSV, QCN_CSV, OUT
    parser = argparse.ArgumentParser(description="Generate optional Radioactive@Home and QCN wFrog-style charts.")
    parser.add_argument("--radioactive-csv", default=str(RADIOACTIVE_CSV))
    parser.add_argument("--qcn-csv", default=str(QCN_CSV))
    parser.add_argument("--output", default=str(OUT))
    args = parser.parse_args()
    RADIOACTIVE_CSV = Path(args.radioactive_csv)
    QCN_CSV = Path(args.qcn_csv)
    OUT = Path(args.output)

    radioactive = normalize_radioactive(
        read_csv(RADIOACTIVE_CSV)
    )
    qcn = normalize_qcn(
        read_csv(QCN_CSV)
    )

    end_ts = latest_timestamp(
        radioactive,
        qcn,
    )

    for prefix, (seconds, interval) in PERIODS.items():
        start_ts = end_ts - seconds

        rad_period = filter_period(
            radioactive,
            start_ts,
            end_ts,
        )

        qcn_period = filter_period(
            qcn,
            start_ts,
            end_ts,
        )

        rad_agg = aggregate_radioactive(
            rad_period,
            interval,
        )

        qcn_agg = aggregate_qcn(
            qcn_period,
            interval,
        )

        radioactive_range_chart(
            f"{prefix}radioactive_dose_wfrog.svg",
            rad_agg,
            "dose",
            start_ts,
            end_ts,
            seconds,
            decimals=4,
            include_zero=True,
        )

        radioactive_range_chart(
            f"{prefix}radioactive_cpm_wfrog.svg",
            rad_agg,
            "cpm",
            start_ts,
            end_ts,
            seconds,
            decimals=2,
            include_zero=True,
        )

        single_series_chart(
            f"{prefix}qcn_maxstep_wfrog.svg",
            qcn_agg,
            "max_step",
            start_ts,
            end_ts,
            seconds,
            decimals=3,
            include_zero=True,
        )

        qcn_p2p_chart(
            f"{prefix}qcn_p2p_wfrog.svg",
            qcn_agg,
            start_ts,
            end_ts,
            seconds,
        )


if __name__ == "__main__":
    generate()
