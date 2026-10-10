"""plot_wind_profile.py — Altitude-layered wind speed & direction chart
(Airdata style: bars + rotated direction arrows).

Usage:
    python plot_wind_profile.py flight_data.csv -o wind_by_altitude.png
    python plot_wind_profile.py flight_data.csv --k 0.78 --bins 0,10,25,50,75,100,150,200,300
"""

import argparse
import math

import matplotlib.pyplot as plt
import numpy as np

from dji_wind import DEFAULT_K, load_hover_samples, wind_by_altitude


def main() -> None:
    ap = argparse.ArgumentParser(description="Hover-attitude wind inversion: layered wind chart")
    ap.add_argument("csv", help="flight-log CSV (decrypted dji-log output or Airdata export)")
    ap.add_argument("-o", "--output", default="wind_by_altitude.png", help="output image path")
    ap.add_argument("--k", type=float, default=DEFAULT_K,
                    help=f"tilt-to-wind coefficient in m/s per degree (default {DEFAULT_K})")
    ap.add_argument("--bins", default="0,10,25,50,75,100,150,200,250,300,350,400,450",
                    help="altitude layer edges in meters, comma-separated")
    ap.add_argument("--title", default="", help="chart title (auto-generated if omitted)")
    args = ap.parse_args()

    bin_edges = [float(x) for x in args.bins.split(",")]
    samples = load_hover_samples(args.csv)
    layers = wind_by_altitude(samples, bin_edges, k=args.k)
    if not layers:
        raise SystemExit("No altitude layer has enough samples")

    print(f"valid hover frames: {len(samples)}")
    for L in layers:
        print(f"{L['layer']:>10}  n={L['n']:>5}  mean tilt {L['tilt_deg']:>5.1f} deg  "
              f"dir {L['wind_dir']:>5.0f} deg  speed ~{L['wind_speed']:.2f} m/s")

    labels = [L["layer"] for L in layers]
    speeds = [L["wind_speed"] for L in layers]
    dirs = [L["wind_dir"] for L in layers]

    y = np.arange(len(labels))
    x_arrow = max(speeds) * 1.35 + 0.8
    fig, ax = plt.subplots(figsize=(11, max(5, 0.65 * len(labels) + 2)))
    ax.barh(y, speeds, height=0.55, color="#5b9bd5")
    for i, (v, dr) in enumerate(zip(speeds, dirs)):
        ax.text(v + max(speeds) * 0.01, i, f"{v:.2f}", va="center", fontsize=10)
        rad = math.radians(dr)
        L = max(speeds) * 0.12
        ax.annotate("", xy=(x_arrow + math.sin(rad) * L, i + math.cos(rad) * L * 0.55),
                    xytext=(x_arrow, i),
                    arrowprops=dict(arrowstyle="-|>", color="#2e75b6", lw=2.5, mutation_scale=17))
        ax.text(x_arrow, i + 0.52, f"{dr:.0f}°", ha="center", fontsize=10,
                fontweight="bold", color="#1f4e79")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_ylim(len(labels) - 0.2, -0.8)
    ax.set_xlim(0, x_arrow + max(speeds) * 0.28)
    ax.set_xlabel("Average wind speed (m/s)")
    ax.set_title(args.title or
                 f"Wind speed & direction by altitude (hover-attitude inversion, "
                 f"arrows point to wind-from direction, 0°=N, k={args.k})")
    ax.grid(axis="x", alpha=0.3)
    fig.savefig(args.output, bbox_inches="tight", dpi=120)
    print(f"saved: {args.output}")


if __name__ == "__main__":
    main()
