#!/usr/bin/env python3
# Copyright (C) 2026 Marcin Kowalik <mkowalik@agh.edu.pl>
# SPDX-License-Identifier: GPL-3.0-or-later

import math
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def create_archive(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE archive (
            dateTime INTEGER PRIMARY KEY,
            usUnits INTEGER,
            outTemp REAL,
            dewpoint REAL,
            outHumidity REAL,
            barometer REAL,
            windSpeed REAL,
            windGust REAL,
            windDir REAL,
            rain REAL,
            rainRate REAL,
            UV REAL,
            radiation REAL,
            inTemp REAL,
            inHumidity REAL
        )"""
    )

    end = int(time.time())
    start = end - 10 * 86400

    for i, ts in enumerate(range(start, end + 1, 300)):
        out_temp = 8 + 7 * math.sin(i / 40)
        dewpoint = out_temp - 2.5
        humidity = 70 + 15 * math.sin(i / 33)
        pressure = 1015 + 8 * math.sin(i / 150)
        wind_kmh = max(0, 7 + 6 * math.sin(i / 19))
        gust_kmh = wind_kmh + max(0, 4 * math.sin(i / 7) + 3)
        wind_dir = (i * 11) % 360
        rain = 0.1 if i % 173 == 0 else 0.0
        rain_rate = 3.2 if rain else 0.0
        uv = max(0, 5 * math.sin((i % 288) / 288 * math.pi))
        radiation = max(0, 600 * math.sin((i % 288) / 288 * math.pi))

        conn.execute(
            "INSERT INTO archive VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                ts,
                17,
                out_temp,
                dewpoint,
                humidity,
                pressure,
                wind_kmh / 3.6,
                gust_kmh / 3.6,
                wind_dir,
                rain,
                rain_rate,
                uv,
                radiation,
                21.5,
                45,
            ),
        )

    conn.commit()
    conn.close()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="wfrog-test-") as tmp:
        tmp = Path(tmp)
        db = tmp / "weewx.sdb"
        out = tmp / "html"
        out.mkdir()
        create_archive(db)

        subprocess.run(
            [
                sys.executable,
                str(ROOT / "bin/generate-wfrog-charts.py"),
                "--database",
                str(db),
                "--output",
                str(out),
            ],
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "bin/generate-wfrog-numbers.py"),
                "--database",
                str(db),
                "--output",
                str(out),
            ],
            check=True,
        )

        required = [
            "weather-current.json",
            "wind_current.svg",
            "daytemp_wfrog.svg",
            "dayrain_wfrog.svg",
            "dayrain_rate_wfrog.svg",
            "dayradiation_wfrog.svg",
            "daynumbers_wfrog.txt",
            "yeartemp_wfrog.svg",
            "yearnumbers_wfrog.txt",
        ]

        missing = [name for name in required if not (out / name).is_file()]
        if missing:
            raise RuntimeError(f"Missing generated files: {missing}")

    print("Smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
