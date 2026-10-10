"""export_wind_timeseries.py — Per-second in-flight wind table
(time / position / height / wind speed / wind direction) + time-series plot.

Usage:
    python export_wind_timeseries.py flight_data.csv -o wind_timeseries.csv --plot wind_timeseries.png
"""

import argparse

import matplotlib.pyplot as plt
import numpy as np

from dji_wind import DEFAULT_K, load_hover_samples, wind_timeseries, write_timeseries_csv


def main() -> None:
    ap = argparse.ArgumentParser(description="Hover-attitude wind inversion: per-second wind export")
    ap.add_argument("csv", help="flight-log CSV (decrypted dji-log output or Airdata export)")
    ap.add_argument("-o", "--output", default="wind_timeseries.csv", help="output CSV path")
    ap.add_argument("--k", type=float, default=DEFAULT_K,
                    help=f"tilt-to-wind coefficient in m/s per degree (default {DEFAULT_K})")
    ap.add_argument("--plot", default="", help="optional: time-series figure path (e.g. wind_timeseries.png)")
    args = ap.parse_args()

    samples = load_hover_samples(args.csv)
    series = wind_timeseries(samples, k=args.k)
    write_timeseries_csv(series, args.output)
    print(f"valid hover frames: {len(samples)}, per-second records: {len(series)}")
    print(f"saved: {args.output}")

    if args.plot:
        t = np.array([o["sec"] for o in series])
        h = np.array([o["height"] for o in series])
        ws = np.array([o["wind_speed"] for o in series])
        wd = np.array([o["wind_dir"] for o in series])

        fig, ax = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
        ax[0].plot(t, h, color="#1f77b4")
        ax[0].set_ylabel("Height (m)")
        ax[0].grid(alpha=0.3)
        ax[0].set_title(f"In-flight wind vs time, per second (hover-attitude inversion, k={args.k})")
        ax[1].plot(t, ws, color="#2ca02c", lw=1)
        ax[1].axhline(ws.mean(), color="gray", ls="--", lw=1, label=f"mean {ws.mean():.2f} m/s")
        ax[1].set_ylabel("Wind speed est. (m/s)")
        ax[1].legend()
        ax[1].grid(alpha=0.3)
        ax[1].set_ylim(0, ws.max() * 1.25)
        ax[2].scatter(t, wd, s=8, c="#9467bd")
        ax[2].set_ylabel("Wind direction (from, °)")
        ax[2].set_yticks([0, 90, 180, 270, 360])
        ax[2].set_yticklabels(["0°N", "90°E", "180°S", "270°W", "360°N"])
        ax[2].grid(alpha=0.3)
        ax[2].set_xlabel("Flight time (s)")
        fig.tight_layout()
        fig.savefig(args.plot, bbox_inches="tight", dpi=120)
        print(f"saved: {args.plot}")


if __name__ == "__main__":
    main()
