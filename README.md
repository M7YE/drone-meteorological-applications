# DJI Wind Estimator

Estimate **wind speed and direction experienced by a DJI drone** from its flight log,
using **hover-attitude inversion** — no anemometer required.

Inputs: decrypted DJI Fly flight-record CSV, or an Airdata-exported CSV (both auto-detected).

Outputs:

- Altitude-layered wind speed & direction chart (Airdata-style, with rotated direction arrows)
- Per-second in-flight wind table (time / latitude / longitude / height / wind speed / wind direction)
- Wind speed & direction time-series plots

[中文版说明](README.zh-CN.md)

## Method

A drone carries no wind sensor. But in GPS position-hold hover, wind is the only external
force that requires a **persistent tilt** to counteract:

```
horizontal: F_wind = T·sin(θ)
vertical:   m·g    = T·cos(θ)
=>          F_wind = m·g·tan(θ)
```

- **Wind direction** = the direction the airframe tilts toward (pure geometry, high confidence);
- **Wind speed** = converted from tilt angle via the empirical linear relation `v = k · θ`.

### The coefficient k

A pure drag model `v = √(2·m·g·tanθ / (ρ·C_d·A))` systematically underestimates wind speed
for small multirotors (no official C_d·A; rotor slipstream and airframe effects reduce the
effective drag). This tool defaults to **k = 0.78 m/s per degree**, reverse-calibrated from
one DJI Mini 3's measured tilt angles against Airdata's own analysis of the same flight
(12 altitude layers, implied k ranging 0.68–0.96).

**Recommended:** re-calibrate k with ground truth (wind tunnel / wind wall / anemometer).
If true wind speed `v_true` and the corresponding tilt `θ` at a steady hover are known,
then `k = v_true / θ`. Pass your calibrated value via `--k`.

## Getting the flight-log CSV

DJI Fly `.txt` flight records (v13/v14) are AES-encrypted and must be decrypted first:

1. Create an app at [DJI Developer](https://developer.dji.com/user/) (App Type: Open API or
   Mobile SDK), activate it via email, and copy your **App Key** (ApiKey);
2. Download the open-source decoder [dji-log-parser](https://github.com/lvauvillier/dji-log-parser)
   (MIT license) and run:

```bash
dji-log.exe "DJIFlightRecord_2026-09-23_[15-26-15].txt" \
    --api-key YOUR_API_KEY \
    --csv flight_data.csv --kml track.kml --geojson track.geojson
```

Airdata-exported CSVs are also supported directly (both column-name conventions are auto-detected,
including Airdata's leading-space quirk).

## Install

```bash
pip install -r requirements.txt
```

## Usage

### 1. Altitude-layered wind chart

```bash
python plot_wind_profile.py flight_data.csv -o wind_by_altitude.png
# custom coefficient and layers
python plot_wind_profile.py flight_data.csv --k 0.78 --bins 0,10,25,50,75,100,150,200,300
```

### 2. Per-second in-flight wind table + time-series plot

```bash
python export_wind_timeseries.py flight_data.csv -o wind_timeseries.csv --plot wind_timeseries.png
```

Output CSV columns: `time_s, datetime_utc, latitude, longitude, height_m, wind_speed_ms, wind_dir_deg`
(wind direction is meteorological "from" direction, 0° = north, clockwise).

## Caveats

- Only **hover frames** are used (horizontal ground speed < 0.6 m/s in GPSAtti/P-GPS state);
  maneuvering frames are excluded;
- Wind direction is aggregated per layer via **vector averaging** (robust to angle wrap-around);
- Direction is a pure geometric result (high confidence); speed depends on k
  (±20% absolute error if uncalibrated);
- Below ~2 m, ground effect degrades accuracy;
- Very small tilt (< 1°, light wind) has low signal-to-noise ratio.

## License

MIT. The decryption tool dji-log-parser is owned by its author (MIT).

## References

- [lvauvillier/dji-log-parser](https://github.com/lvauvillier/dji-log-parser) — DJI .txt log decryption
- Airdata UAV — reference for the layered wind presentation style
