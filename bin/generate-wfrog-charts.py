#!/usr/bin/env python3
# Copyright (C) 2026 Marcin Kowalik <mkowalik@agh.edu.pl>
# Portions based on the behavior and rendering logic of wFrog:
# Copyright 2009 Laurent Bovet <laurent.bovet@windmaster.ch>
# Copyright 2009 Jordi Puigsegur <jordi.puigsegur@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

DB = Path("/var/lib/weewx/weewx.sdb")
OUT = Path("/var/www/html/wfrog")

PERIODS = {
    "threehour": (3 * 3600, 5 * 60),
    "day": (24 * 3600, 3600),
    "week": (7 * 86400, 3600),
    "month": (30 * 86400, 86400),
    "year": (365 * 86400, 7 * 86400),
}

# Original wFrog palette.
GREEN = "#008000"
TEXT = "#8d7641"
TAN = "#d2b48c"
WHEAT = "#f5deb3"
DARKRED = "#8b0000"
DARKBLUE = "#483d8b"
GRID = "#eadfcd"
WHITE = "#ffffff"
SECTOR_GREEN = "#00af00"

COMPASS16 = [
    "N", "NNE", "NE", "ENE",
    "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW",
    "W", "WNW", "NW", "NNW",
]

FIELDS = (
    "dateTime,usUnits,outTemp,dewpoint,outHumidity,barometer,"
    "windSpeed,windGust,windDir,rain,rainRate,UV,radiation,inTemp,inHumidity"
)


def c(v):
    return None if v is None else float(v)


def temperature_c(v, u):
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


def wind_mps(v, u):
    x = wind_kmh(v, u)
    return None if x is None else x / 3.6


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


def normalize(row):
    (ts, u, out_t, dew, hum, press, wind, gust, wdir,
     rain, rain_rate, uv, radiation, in_t, in_hum) = row
    return {
        "ts": int(ts),
        "outTemp": temperature_c(out_t, u),
        "dewpoint": temperature_c(dew, u),
        "outHumidity": c(hum),
        "barometer": pressure_hpa(press, u),
        "windSpeed": wind_kmh(wind, u),
        "windGust": wind_kmh(gust, u),
        "windDir": c(wdir),
        "rain": rain_mm(rain, u),
        "rainRate": rain_mm(rain_rate, u),
        "UV": c(uv),
        "radiation": c(radiation),
        "inTemp": temperature_c(in_t, u),
        "inHumidity": c(in_hum),
    }


def mean(values):
    vals = [x for x in values if x is not None]
    return sum(vals) / len(vals) if vals else None


def vmin(values):
    vals = [x for x in values if x is not None]
    return min(vals) if vals else None


def vmax(values):
    vals = [x for x in values if x is not None]
    return max(vals) if vals else None


def vector_direction(rows):
    sx = sy = 0.0
    weight = 0.0
    for r in rows:
        d = r["windDir"]
        s = r["windSpeed"]
        if d is None or s is None or s <= 0:
            continue
        a = math.radians(d)
        sx += s * math.sin(a)
        sy += s * math.cos(a)
        weight += s
    if weight <= 0:
        vals = [r["windDir"] for r in rows if r["windDir"] is not None]
        return vals[-1] if vals else None
    deg = math.degrees(math.atan2(sx, sy))
    return deg + 360.0 if deg < 0 else deg


def aggregate(rows, interval):
    if not rows:
        return []
    buckets = {}
    for r in rows:
        key = (r["ts"] // interval) * interval
        buckets.setdefault(key, []).append(r)

    out = []
    for key in sorted(buckets):
        b = buckets[key]
        out.append({
            "ts": key + interval // 2,
            "temp_avg": mean([r["outTemp"] for r in b]),
            "temp_min": vmin([r["outTemp"] for r in b]),
            "temp_max": vmax([r["outTemp"] for r in b]),
            "dew_avg": mean([r["dewpoint"] for r in b]),
            "hum_avg": mean([r["outHumidity"] for r in b]),
            "press_avg": mean([r["barometer"] for r in b]),
            "wind_avg": mean([r["windSpeed"] for r in b]),
            "gust_max": vmax([
                r["windGust"] if r["windGust"] is not None else r["windSpeed"]
                for r in b
            ]),
            "wind_dir": vector_direction(b),
            "rain_sum": sum(r["rain"] or 0.0 for r in b),
            "rain_rate_max": vmax([r["rainRate"] for r in b]),
            "uv_max": vmax([r["UV"] for r in b]),
            "rad_avg": mean([r["radiation"] for r in b]),
            "rad_min": vmin([r["radiation"] for r in b]),
            "rad_max": vmax([r["radiation"] for r in b]),
        })
    return out


def boundary_record(ts):
    return {
        "ts": int(ts),
        "outTemp": None,
        "dewpoint": None,
        "outHumidity": None,
        "barometer": None,
        "windSpeed": None,
        "windGust": None,
        "windDir": None,
        "rain": None,
        "rainRate": None,
        "UV": None,
        "radiation": None,
        "inTemp": None,
        "inHumidity": None,
    }


def direction_text(deg):
    if deg is None:
        return ""
    return COMPASS16[int(round((float(deg) % 360.0) / 22.5)) % 16]


def svg_text(x, y, text, size=9, color=TEXT, anchor="middle", weight="normal"):
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}" '
        f'fill="{color}" font-family="Arial,Helvetica,sans-serif" '
        f'font-size="{size}" font-weight="{weight}">{escape(str(text))}</text>'
    )


def write_svg(name, body, width=330, height=210):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
        f'<rect width="100%" height="100%" fill="{WHITE}"/>{body}</svg>\n',
        encoding="utf-8",
    )


def chart_geometry():
    width, height = 330, 210
    left, top, right, bottom = 39, 18, 12, 28
    return width, height, left, top, right, bottom, width-left-right, height-top-bottom


def nice_range(values, include_zero=False):
    vals = [v for v in values if v is not None]
    if not vals:
        return 0.0, 1.0
    lo, hi = min(vals), max(vals)
    if include_zero:
        lo = min(lo, 0.0)
        hi = max(hi, 0.0)
    if abs(hi - lo) < 1e-9:
        pad = max(abs(hi) * 0.05, 0.5)
    else:
        pad = (hi - lo) * 0.08
    return lo - pad, hi + pad


def time_label(ts, total_seconds):
    dt = datetime.fromtimestamp(ts)
    if total_seconds <= 86400:
        return dt.strftime("%H:%M")
    if total_seconds <= 7 * 86400:
        return dt.strftime("%d %H")
    if total_seconds <= 45 * 86400:
        return dt.strftime("%d/%m")
    return dt.strftime("%m/%y")


def base_chart(values, total_seconds, ylo=None, yhi=None, include_zero=False, unit=""):
    width, height, left, top, right, bottom, pw, ph = chart_geometry()
    if ylo is None or yhi is None:
        ylo, yhi = nice_range(values, include_zero)
    if yhi <= ylo:
        yhi = ylo + 1.0

    body = ""
    for i in range(6):
        frac = i / 5.0
        y = top + ph * frac
        val = yhi - (yhi-ylo) * frac
        body += f'<line x1="{left}" y1="{y:.2f}" x2="{left+pw}" y2="{y:.2f}" stroke="{GRID}" stroke-width="1"/>'
        body += svg_text(left-5, y+3, f"{val:.1f}", size=8, color="#a08b5b", anchor="end")
    return (width, height, left, top, right, bottom, pw, ph, ylo, yhi, body)


def points(series, left, top, pw, ph, ylo, yhi, t0, t1):
    out = []
    for ts, val in series:
        if val is None:
            out.append(None)
            continue
        x = left + (ts-t0) / float(max(1, t1-t0)) * pw
        y = top + ph - (val-ylo) / float(yhi-ylo) * ph
        out.append((x, y))
    return out


def polyline_segments(pts, color, width=2, dash=None):
    body = ""
    current = []
    for p in pts + [None]:
        if p is None:
            if len(current) >= 2:
                ds = f' stroke-dasharray="{dash}"' if dash else ""
                body += (
                    f'<polyline points="{" ".join(f"{x:.2f},{y:.2f}" for x,y in current)}" '
                    f'fill="none" stroke="{color}" stroke-width="{width}"{ds}/>'
                )
            current = []
        else:
            current.append(p)
    return body


def x_grid_and_labels(rows, total_seconds, left, top, pw, ph, height):
    if not rows:
        return ""
    t0, t1 = rows[0]["ts"], rows[-1]["ts"]
    if t1 <= t0:
        t1 = t0 + 1
    body = ""
    for i in range(6):
        x = left + pw * i / 5.0
        ts = int(t0 + (t1-t0) * i / 5.0)
        body += f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top+ph}" stroke="{GRID}" stroke-width="1"/>'
        body += svg_text(x, height-9, time_label(ts, total_seconds), size=8, color="#a08b5b")
    return body


def marker_vertical(x, y, bottom_y, label, color, side="right"):
    dx = 5 if side == "right" else -5
    anchor = "start" if side == "right" else "end"
    return (
        f'<line x1="{x:.2f}" y1="{bottom_y:.2f}" x2="{x:.2f}" y2="{y:.2f}" stroke="{color}" stroke-width="1"/>'
        + svg_text(x+dx, max(12, y-4), label, size=9, color=color, anchor=anchor, weight="bold")
    )


def temperature_chart(prefix, rows, total_seconds):
    if not rows:
        write_svg(f"{prefix}temp_wfrog.svg", svg_text(165,105,"No temperature data",12))
        return
    vals = []
    for r in rows:
        vals += [r["temp_min"], r["temp_max"], r["dew_avg"]]
    geo = base_chart(vals, total_seconds)
    width,height,left,top,right,bottom,pw,ph,ylo,yhi,body = geo
    body += x_grid_and_labels(rows,total_seconds,left,top,pw,ph,height)
    t0,t1=rows[0]["ts"],rows[-1]["ts"]
    if t1<=t0: t1=t0+1

    avg = [(r["ts"], r["temp_avg"]) for r in rows]
    tmin = [(r["ts"], r["temp_min"]) for r in rows]
    tmax = [(r["ts"], r["temp_max"]) for r in rows]
    dew = [(r["ts"], r["dew_avg"]) for r in rows]

    avgp=points(avg,left,top,pw,ph,ylo,yhi,t0,t1)
    minp=points(tmin,left,top,pw,ph,ylo,yhi,t0,t1)
    maxp=points(tmax,left,top,pw,ph,ylo,yhi,t0,t1)
    dewp=points(dew,left,top,pw,ph,ylo,yhi,t0,t1)

    toppts=[p for p in maxp if p is not None]
    botpts=[p for p in reversed(minp) if p is not None]
    if toppts and botpts and len(toppts)==len(botpts):
        area=toppts+botpts
        body += f'<path d="M {" L ".join(f"{x:.2f},{y:.2f}" for x,y in area)} Z" fill="{WHEAT}" fill-opacity="0.35" stroke="none"/>'

    body += polyline_segments(avgp,GREEN,2)
    body += polyline_segments(dewp,TEXT,1.3,"3 3")

    validmax=[(i,r["temp_max"]) for i,r in enumerate(rows) if r["temp_max"] is not None]
    validmin=[(i,r["temp_min"]) for i,r in enumerate(rows) if r["temp_min"] is not None]
    if validmax:
        imax,v=max(validmax,key=lambda x:x[1]); p=maxp[imax]
        if p: body += marker_vertical(p[0],p[1],top+ph,f"{v:.1f}",DARKRED,"right")
    if validmin:
        imin,v=min(validmin,key=lambda x:x[1]); p=minp[imin]
        if p: body += marker_vertical(p[0],p[1],top+ph,f"{v:.1f}",DARKBLUE,"left")

    write_svg(f"{prefix}temp_wfrog.svg",body,width,height)


def simple_line_chart(prefix, name, rows, field, total_seconds, unit="", include_zero=False):
    vals=[r[field] for r in rows]
    if not rows or not any(v is not None for v in vals):
        write_svg(f"{prefix}{name}_wfrog.svg",svg_text(165,105,"No data",12))
        return
    geo=base_chart(vals,total_seconds,include_zero=include_zero)
    width,height,left,top,right,bottom,pw,ph,ylo,yhi,body=geo
    body += x_grid_and_labels(rows,total_seconds,left,top,pw,ph,height)
    t0,t1=rows[0]["ts"],rows[-1]["ts"]
    if t1<=t0:t1=t0+1
    pts=points([(r["ts"],r[field]) for r in rows],left,top,pw,ph,ylo,yhi,t0,t1)
    body += polyline_segments(pts,GREEN,2)
    write_svg(f"{prefix}{name}_wfrog.svg",body,width,height)


def rain_chart(prefix, rows, total_seconds):
    if not rows:
        write_svg(f"{prefix}rain_wfrog.svg",svg_text(165,105,"No rain data",12))
        return
    cumulative=[]
    total=0.0
    for r in rows:
        total += r["rain_sum"] or 0.0
        cumulative.append((r["ts"],total))
    vals=[v for _,v in cumulative]
    geo=base_chart(vals,total_seconds,include_zero=True)
    width,height,left,top,right,bottom,pw,ph,ylo,yhi,body=geo
    body += x_grid_and_labels(rows,total_seconds,left,top,pw,ph,height)
    t0,t1=rows[0]["ts"],rows[-1]["ts"]
    if t1<=t0:t1=t0+1
    pts=points(cumulative,left,top,pw,ph,ylo,yhi,t0,t1)
    body += polyline_segments(pts,GREEN,2)
    last=next((p for p in reversed(pts) if p),None)
    if last:
        body += marker_vertical(last[0],last[1],top+ph,f"{total:.1f}",DARKRED,"left")
    write_svg(f"{prefix}rain_wfrog.svg",body,width,height)


def solar_chart(prefix, rows, total_seconds):
    vals=[]
    for r in rows:
        vals += [r["rad_min"], r["rad_max"]]
    if not rows or not any(v is not None for v in vals):
        write_svg(f"{prefix}radiation_wfrog.svg",svg_text(165,105,"No solar data",12))
        return
    geo=base_chart(vals,total_seconds,include_zero=True)
    width,height,left,top,right,bottom,pw,ph,ylo,yhi,body=geo
    body += x_grid_and_labels(rows,total_seconds,left,top,pw,ph,height)
    t0,t1=rows[0]["ts"],rows[-1]["ts"]
    if t1<=t0:t1=t0+1
    minp=points([(r["ts"],r["rad_min"]) for r in rows],left,top,pw,ph,ylo,yhi,t0,t1)
    maxp=points([(r["ts"],r["rad_max"]) for r in rows],left,top,pw,ph,ylo,yhi,t0,t1)
    lo=[p for p in minp if p is not None]
    hi=[p for p in maxp if p is not None]
    if lo and hi and len(lo)==len(hi):
        area=hi+list(reversed(lo))
        body += f'<path d="M {" L ".join(f"{x:.2f},{y:.2f}" for x,y in area)} Z" fill="{WHEAT}" fill-opacity="0.7" stroke="none"/>'
    body += polyline_segments(minp,WHEAT,1.0)
    body += polyline_segments(maxp,GREEN,1.5)
    valid=[(i,r["rad_max"]) for i,r in enumerate(rows) if r["rad_max"] is not None]
    if valid:
        imax,v=max(valid,key=lambda x:x[1]); p=maxp[imax]
        if p: body += marker_vertical(p[0],p[1],top+ph,f"{v:.1f}",DARKRED,"right")
    write_svg(f"{prefix}radiation_wfrog.svg",body,width,height)


def windgust_chart(prefix, rows, total_seconds):
    if not rows:
        write_svg(f"{prefix}windgust_wfrog.svg",svg_text(165,105,"No wind data",12))
        return
    vals=[]
    for r in rows:
        vals += [r["wind_avg"],r["gust_max"]]
    geo=base_chart(vals,total_seconds,include_zero=True)
    width,height,left,top,right,bottom,pw,ph,ylo,yhi,body=geo
    body += x_grid_and_labels(rows,total_seconds,left,top,pw,ph,height)
    t0,t1=rows[0]["ts"],rows[-1]["ts"]
    if t1<=t0:t1=t0+1
    avgp=points([(r["ts"],r["wind_avg"]) for r in rows],left,top,pw,ph,ylo,yhi,t0,t1)
    gustp=points([(r["ts"],r["gust_max"]) for r in rows],left,top,pw,ph,ylo,yhi,t0,t1)

    gpts=[p for p in gustp if p]
    apts=[p for p in reversed(avgp) if p]
    if gpts and apts and len(gpts)==len(apts):
        area=gpts+apts
        body += f'<path d="M {" L ".join(f"{x:.2f},{y:.2f}" for x,y in area)} Z" fill="{WHEAT}" fill-opacity="0.8" stroke="none"/>'
    body += polyline_segments(gustp,TAN,1.3)
    body += polyline_segments(avgp,GREEN,2)

    step=max(1,len(rows)//9)
    for i in range(0,len(rows),step):
        r=rows[i]
        if r["wind_dir"] is None or gustp[i] is None:
            continue
        x,y=gustp[i]
        body += svg_text(x,max(top+9,y-4),direction_text(r["wind_dir"]),size=8,color="#b39a65")

    vg=[(i,r["gust_max"]) for i,r in enumerate(rows) if r["gust_max"] is not None]
    if vg:
        imax,v=max(vg,key=lambda x:x[1]); p=gustp[imax]
        if p: body += marker_vertical(p[0],p[1],top+ph,f"{v:.1f}",DARKRED,"right")

    write_svg(f"{prefix}windgust_wfrog.svg",body,width,height)


def wfrog_scale(value, median=2.5, radius=18.0):
    if value is None or value <= 0:
        return 0.0
    a = radius / median - 2.0
    if a <= 0:
        return value
    return (median / math.log(a + 1.0)) * math.log((a / median) * value + 1.0)


def polar(cx,cy,r,bearing):
    a=math.radians(bearing-90.0)
    return cx+r*math.cos(a), cy+r*math.sin(a)


def sector_path(cx,cy,r,start,end):
    x1,y1=polar(cx,cy,r,start); x2,y2=polar(cx,cy,r,end)
    return f"M {cx},{cy} L {x1:.2f},{y1:.2f} A {r},{r} 0 0 1 {x2:.2f},{y2:.2f} Z"


def windrose_chart(prefix, raw_rows):
    width,height=330,210
    cx,cy=165,101
    rmax=72.0
    count=[0]*16; avgs=[[] for _ in range(16)]; gusts=[[] for _ in range(16)]
    for r in raw_rows:
        d=r["windDir"]; s=r["windSpeed"]; g=r["windGust"]
        if d is None or s is None or s<=0: continue
        i=int(round((d%360.0)/22.5))%16
        count[i]+=1; avgs[i].append(s/3.6); gusts[i].append((g if g is not None else s)/3.6)
    total=sum(count)
    avg=[mean(x) or 0.0 for x in avgs]
    gust=[vmax(x) or 0.0 for x in gusts]
    freq=[x/float(total) if total else 0.0 for x in count]

    body=""
    for i,f in enumerate(freq):
        if f<=0: continue
        opacity=min(1.0,3.0*f)
        body += f'<path d="{sector_path(cx,cy,rmax,i*22.5-11.25,i*22.5+11.25)}" fill="{SECTOR_GREEN}" fill-opacity="{opacity:.3f}"/>'
    for frac in (0.33,0.66,1.0):
        body += f'<circle cx="{cx}" cy="{cy}" r="{rmax*frac:.2f}" fill="none" stroke="{GRID}" stroke-width="1"/>'

    maxscale=5.0
    avgpts=[]; gustpts=[]
    for i in range(16):
        ar=rmax*min(maxscale,wfrog_scale(avg[i]))/maxscale
        gr=rmax*min(maxscale,wfrog_scale(gust[i]))/maxscale
        avgpts.append(polar(cx,cy,ar,i*22.5))
        gustpts.append(polar(cx,cy,gr,i*22.5))
    if any(gust):
        body += f'<path d="M {" L ".join(f"{x:.2f},{y:.2f}" for x,y in gustpts)} Z" fill="{WHEAT}" fill-opacity="0.85" stroke="{TAN}" stroke-width="1.2"/>'
    if any(avg):
        body += f'<path d="M {" L ".join(f"{x:.2f},{y:.2f}" for x,y in avgpts)} Z" fill="{GREEN}" fill-opacity="0.95" stroke="{GREEN}" stroke-width="1.2"/>'
    for label,deg in [("N",0),("NE",45),("E",90),("SE",135),("S",180),("SW",225),("W",270),("NW",315)]:
        x,y=polar(cx,cy,rmax+16,deg)
        body += svg_text(x,y+4,label,12,TEXT)
    if not total:
        body += svg_text(cx,cy+4,"Calm / no directional samples",10,TEXT)
    write_svg(f"{prefix}windrose_wfrog.svg",body,width,height)


def beaufort(mps):
    limits=[0.3,1.6,3.4,5.5,8.0,10.8,13.9,17.2,20.8,24.5,28.5,32.7]
    for i,l in enumerate(limits):
        if mps<l:return i
    return 12


def current_wind_svg(latest):
    w=h=76; cx=cy=38
    if not latest:
        write_svg("wind_current.svg",svg_text(38,41,"-",12,TEXT),w,h); return
    wind_kmh=float(latest.get("windSpeed") or 0.0)
    gust_kmh=float(latest.get("windGust") or wind_kmh)
    speed=wind_kmh/3.6
    gust=gust_kmh/3.6
    deg=float(latest.get("windDir") or 0.0)%360.0
    bft=beaufort(speed)

    body=""
    for label,d in [("N",0),("NE",45),("E",90),("SE",135),("S",180),("SW",225),("W",270),("NW",315)]:
        x,y=polar(cx,cy,31,d)
        body += svg_text(x,y+2,label,5,"#b39a65")

    body += svg_text(cx,cy+14,bft,45,WHEAT,"middle","bold")

    if speed>0 or gust>0:
        wind_scaled=min(5.0,wfrog_scale(speed))
        gust_scaled=min(5.0,wfrog_scale(gust))
        wind_len=8.0+(wind_scaled/5.0)*20.0
        gust_len=max(wind_len,8.0+(gust_scaled/5.0)*20.0)
        wx,wy=polar(cx,cy,wind_len,deg)
        gx,gy=polar(cx,cy,gust_len,deg)
        body += f'<line x1="{cx}" y1="{cy}" x2="{gx:.2f}" y2="{gy:.2f}" stroke="{TAN}" stroke-width="1.25" stroke-linecap="round"/>'
        body += f'<line x1="{cx}" y1="{cy}" x2="{wx:.2f}" y2="{wy:.2f}" stroke="{GREEN}" stroke-width="2.5" stroke-linecap="round"/>'
        l=polar(wx,wy,5,deg+150); r=polar(wx,wy,5,deg-150)
        body += f'<polygon points="{wx:.2f},{wy:.2f} {l[0]:.2f},{l[1]:.2f} {r[0]:.2f},{r[1]:.2f}" fill="{GREEN}"/>'
    write_svg("wind_current.svg",body,w,h)

def latest_weather_json(latest):
    data={
        "temperature_c":latest.get("outTemp"),
        "humidity_pct":latest.get("outHumidity"),
        "pressure_hpa":latest.get("barometer"),
        "inside_temperature_c":latest.get("inTemp"),
        "inside_humidity_pct":latest.get("inHumidity"),
        "wind_kmh":latest.get("windSpeed"),
        "gust_kmh":latest.get("windGust"),
        "wind_direction_deg":latest.get("windDir"),
        "rain_rate_mm_h":latest.get("rainRate"),
        "uv_index":latest.get("UV"),
        "radiation_w_m2":latest.get("radiation"),
        "timestamp_local":datetime.fromtimestamp(latest["ts"]).isoformat(timespec="seconds"),
        "units":{
            "temperature":"°C",
            "pressure":"hPa",
            "wind":"km/h",
            "rain_rate":"mm/h",
            "radiation":"W/m²"
        }
    }
    (OUT/"weather-current.json").write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")


def fetch_raw(conn,start,end):
    cur=conn.execute(f"SELECT {FIELDS} FROM archive WHERE dateTime>=? AND dateTime<=? ORDER BY dateTime",(start,end))
    return [normalize(r) for r in cur.fetchall()]


def main():
    global DB, OUT
    parser=argparse.ArgumentParser(description="Generate wFrog-style SVG charts from a WeeWX SQLite archive.")
    parser.add_argument("--database", default=str(DB), help="Path to WeeWX SQLite archive")
    parser.add_argument("--output", default=str(OUT), help="HTML output directory")
    args=parser.parse_args()
    DB=Path(args.database)
    OUT=Path(args.output)
    if not DB.exists():
        raise SystemExit(f"Database not found: {DB}")
    OUT.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(f"file:{DB}?mode=ro",uri=True)
    try:
        row=conn.execute(f"SELECT {FIELDS} FROM archive ORDER BY dateTime DESC LIMIT 1").fetchone()
        if not row:
            raise SystemExit("No archive records")
        latest=normalize(row)
        latest_weather_json(latest)
        current_wind_svg(latest)
        end=latest["ts"]

        for prefix,(seconds,interval) in PERIODS.items():
            start=end-seconds
            raw=fetch_raw(conn,start,end)
            raw_for_plot=[boundary_record(start)] + raw + [boundary_record(end)]
            agg=aggregate(raw_for_plot,interval)
            temperature_chart(prefix,agg,seconds)
            simple_line_chart(prefix,"humidity",agg,"hum_avg",seconds)
            simple_line_chart(prefix,"pressure",agg,"press_avg",seconds)
            windgust_chart(prefix,agg,seconds)
            windrose_chart(prefix,raw)
            rain_chart(prefix,agg,seconds)
            simple_line_chart(prefix,"rain_rate",agg,"rain_rate_max",seconds,include_zero=True)
            simple_line_chart(prefix,"uv",agg,"uv_max",seconds,include_zero=True)
            solar_chart(prefix,agg,seconds)
    finally:
        conn.close()


if __name__=="__main__":
    main()
