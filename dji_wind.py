"""dji_wind.py — Core library for wind estimation from DJI drone hover attitude.

Supported CSV inputs (auto-detected):
1. Decrypted DJI Fly log from dji-log-parser (columns: OSD.pitch / OSD.roll / OSD.yaw ...)
2. Airdata export (columns: pitch(degrees) / roll(degrees) / compass_heading(degrees) ...;
   note Airdata pads some column names with leading spaces — handled here).

Physics:
    hover equilibrium  F_wind = m * g * tan(theta)
    wind speed         v = k * theta(deg)   (empirical linear form; k must be calibrated,
                                             default 0.78 m/s/deg)

Wind direction is a purely geometric result (the airframe tilts INTO the wind),
independent of k.
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

# Default empirical coefficient, reverse-calibrated from a DJI Mini 3's measured tilt
# vs. Airdata's official analysis of the same flight (12 layers, implied k = 0.68–0.96).
DEFAULT_K = 0.78  # m/s per degree

# Hover-frame filtering thresholds
MAX_HOVER_SPEED = 0.6   # m/s; frames with higher horizontal ground speed are maneuvering
MIN_HEIGHT = 1.0        # m; below this, ground effect distorts the estimate
MIN_LAYER_SAMPLES = 20  # minimum samples required per altitude layer


@dataclass
class HoverSample:
    """One valid hover sample (single frame)."""
    t: float          # relative flight time (s)
    dt: str           # UTC timestamp string (if available)
    lat: float
    lon: float
    height: float     # height above takeoff (m)
    tilt: float       # sin-combined tilt (≈ tan(theta) at small angles)
    direction: float  # wind-from direction (deg, 0=north, clockwise)


def _get(row: dict, *names: str, default: float = 0.0) -> float:
    """Fetch a numeric value from a CSV row, tolerating Airdata's leading-space column names."""
    for name in names:
        for key in (name, " " + name):
            if key in row:
                try:
                    return float((row[key] or "").strip() or default)
                except (ValueError, AttributeError):
                    return default
    return default


def _tilt_and_direction(pitch: float, roll: float, yaw: float) -> tuple[float, float]:
    """Attitude angles -> (wind-from direction in deg, sin-combined tilt).

    DJI conventions: negative pitch = nose down (forward tilt); positive roll = right tilt;
    yaw 0° = north, clockwise positive.
    Body-frame tilt vector (a_fwd, a_right) = (-sin(pitch), sin(roll)),
    rotated into the earth frame (north-east) by yaw, then combined via atan2.
    """
    a_fwd = -math.sin(math.radians(pitch))
    a_right = math.sin(math.radians(roll))
    yr = math.radians(yaw)
    a_north = a_fwd * math.cos(yr) - a_right * math.sin(yr)
    a_east = a_fwd * math.sin(yr) + a_right * math.cos(yr)
    direction = math.degrees(math.atan2(a_east, a_north)) % 360
    tilt = math.hypot(a_north, a_east)
    return direction, tilt


def load_hover_samples(csv_path: str) -> list[HoverSample]:
    """Load a flight-log CSV, filter valid hover frames, solve direction & tilt per frame."""
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"Empty or unparsable file: {csv_path}")

    # Auto-detect format: dji-log columns start with "OSD.", Airdata uses lowercase names
    dji_log_format = any(k.strip().startswith("OSD.") for k in rows[0])

    samples: list[HoverSample] = []
    for r in rows:
        state = (r.get("OSD.flycState") or r.get("flycState") or "").strip()
        if state not in ("GPSAtti", "P-GPS"):
            continue
        if dji_log_format:
            h = _get(r, "OSD.height")
            spd = math.hypot(_get(r, "OSD.xSpeed"), _get(r, "OSD.ySpeed"))
            lat, lon = _get(r, "OSD.latitude"), _get(r, "OSD.longitude")
            pitch, roll, yaw = _get(r, "OSD.pitch"), _get(r, "OSD.roll"), _get(r, "OSD.yaw")
            t = _get(r, "OSD.flyTime")
        else:
            h = _get(r, "height_above_takeoff(meters)")
            spd = _get(r, "speed(m/s)")
            lat, lon = _get(r, "latitude"), _get(r, "longitude")
            pitch = _get(r, "pitch(degrees)")
            roll = _get(r, "roll(degrees)")
            yaw = _get(r, "compass_heading(degrees)")
            t = _get(r, "time(millisecond)") / 1000.0
        if h < MIN_HEIGHT or spd > MAX_HOVER_SPEED or abs(lat) < 0.001:
            continue
        direction, tilt = _tilt_and_direction(pitch, roll, yaw)
        samples.append(HoverSample(
            t=t, dt=r.get("CUSTOM.dateTime") or r.get("datetime(utc)") or "",
            lat=lat, lon=lon, height=h, tilt=tilt, direction=direction,
        ))
    if not samples:
        raise ValueError("No valid hover frames found (check GPS state / speed / height filters)")
    return samples


def tilt_to_wind_speed(tilt: float, k: float = DEFAULT_K) -> float:
    """Sin-combined tilt -> estimated wind speed in m/s (empirical linear form)."""
    theta_deg = math.degrees(math.asin(min(1.0, tilt)))
    return k * theta_deg


def wind_by_altitude(samples: list[HoverSample], bin_edges: list[float],
                     k: float = DEFAULT_K) -> list[dict]:
    """Aggregate by altitude layer. Direction uses vector averaging (robust to angle
    wrap-around); speed = layer-mean tilt × k."""
    result = []
    for lo, hi in zip(bin_edges[:-1], bin_edges[1:]):
        sel = [s for s in samples if lo <= s.height < hi]
        if len(sel) < MIN_LAYER_SAMPLES:
            continue
        n_comp = np.mean([s.tilt * math.cos(math.radians(s.direction)) for s in sel])
        e_comp = np.mean([s.tilt * math.sin(math.radians(s.direction)) for s in sel])
        mean_dir = math.degrees(math.atan2(e_comp, n_comp)) % 360
        mean_tilt = float(np.mean([s.tilt for s in sel]))
        result.append({
            "layer": f"{lo:g}-{hi:g} m", "lo": lo, "hi": hi,
            "n": len(sel),
            "tilt_deg": math.degrees(math.asin(min(1.0, mean_tilt))),
            "wind_speed": tilt_to_wind_speed(mean_tilt, k),
            "wind_dir": mean_dir,
        })
    return result


def wind_timeseries(samples: list[HoverSample], k: float = DEFAULT_K) -> list[dict]:
    """Aggregate into a per-second wind series (with position)."""
    buckets: dict[int, list[HoverSample]] = defaultdict(list)
    for s in samples:
        buckets[int(s.t)].append(s)
    t0 = min(buckets)
    out = []
    for sec in sorted(buckets):
        g = buckets[sec]
        n_comp = np.mean([s.tilt * math.cos(math.radians(s.direction)) for s in g])
        e_comp = np.mean([s.tilt * math.sin(math.radians(s.direction)) for s in g])
        wd = math.degrees(math.atan2(e_comp, n_comp)) % 360
        mean_tilt = float(np.mean([s.tilt for s in g]))
        out.append({
            "sec": sec - t0, "datetime_utc": g[len(g) // 2].dt,
            "lat": float(np.mean([s.lat for s in g])),
            "lon": float(np.mean([s.lon for s in g])),
            "height": float(np.mean([s.height for s in g])),
            "wind_speed": tilt_to_wind_speed(mean_tilt, k),
            "wind_dir": wd,
        })
    return out


def write_timeseries_csv(series: list[dict], out_path: str) -> None:
    """Write the per-second wind series to CSV (utf-8-sig so Excel opens it cleanly)."""
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["time_s", "datetime_utc", "latitude", "longitude", "height_m",
                    "wind_speed_ms", "wind_dir_deg"])
        for o in series:
            w.writerow([o["sec"], o["datetime_utc"], f"{o['lat']:.7f}",
                        f"{o['lon']:.7f}", f"{o['height']:.1f}",
                        f"{o['wind_speed']:.2f}", f"{o['wind_dir']:.1f}"])
