from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import cartopy.crs as ccrs
import cartopy.feature as cfeature

output = Path("docs/figures")
output.mkdir(parents=True, exist_ok=True)

with xr.open_dataset("data/processed/cams_surface_pm10.nc") as ds:
    field = ds["pm10"].sel(
        time=slice("2023-01-22", "2023-01-26T23:00:00")
    ).load()

expected = pd.date_range("2023-01-22", periods=120, freq="h")
if not pd.DatetimeIndex(field.time.values).equals(expected):
    raise ValueError("Expected 120 consecutive hourly timestamps.")

units = field.attrs.get("units", "").replace("µ", "u").replace("μ", "u")
if units not in {"ug/m3", "ug m-3", "ug/m³"}:
    raise ValueError(f"Unexpected concentration units: {units}")

field = field.where(np.isfinite(field) & (field >= 0))

boxes = {
    "Western box": (12.0, 14.0, 51.0, 53.0),
    "Eastern box": (15.0, 17.0, 51.0, 53.0),
}
colours = {"Western box": "tab:blue", "Eastern box": "tab:orange"}

hourly = pd.DataFrame(index=expected)
hourly.index.name = "time_utc"
coverage = hourly.copy()
metadata = []

for name, (west, east, south, north) in boxes.items():
    region = field.where(
        (field.longitude >= west) & (field.longitude < east)
        & (field.latitude >= south) & (field.latitude < north),
        drop=True,
    )
    if region.sizes["latitude"] == 0 or region.sizes["longitude"] == 0:
        raise ValueError(f"Empty selection: {name}")

    weights = np.cos(np.deg2rad(region.latitude))
    area_fraction = region.notnull().weighted(weights).mean(
        ("latitude", "longitude")
    )
    mean = region.weighted(weights).mean(("latitude", "longitude"))
    hourly[name] = mean.where(area_fraction >= 0.90).values
    coverage[name] = area_fraction.values

    metadata.append({
        "region": name,
        "west": west, "east_exclusive": east,
        "south": south, "north_exclusive": north,
        "grid_cells": region.sizes["latitude"] * region.sizes["longitude"],
        "minimum_valid_area_fraction": float(area_fraction.min()),
    })

daily = hourly.resample("1D").mean().where(
    hourly.resample("1D").count() >= 18
)

hourly.to_csv(output / "regional_hourly_pm10.csv")
daily.to_csv(output / "regional_daily_pm10.csv")
coverage.to_csv(output / "regional_valid_area_fraction.csv")
pd.DataFrame(metadata).to_csv(output / "regional_boxes.csv", index=False)

fig = plt.figure(figsize=(12, 5), layout="constrained")
grid = fig.add_gridspec(1, 2, width_ratios=[1, 1.7])
map_ax = fig.add_subplot(grid[0, 0], projection=ccrs.PlateCarree())
time_ax = fig.add_subplot(grid[0, 1])

map_ax.set_extent([12, 17, 50, 54], crs=ccrs.PlateCarree())
map_ax.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=0.8)
map_ax.set_xticks([12, 13, 14, 15, 16, 17], crs=ccrs.PlateCarree())
map_ax.set_yticks([50, 51, 52, 53, 54], crs=ccrs.PlateCarree())
map_ax.set_xlabel("Longitude (°E)")
map_ax.set_ylabel("Latitude (°N)")
map_ax.set_title("Comparison boxes")

for name, (west, east, south, north) in boxes.items():
    colour = colours[name]
    map_ax.add_patch(Rectangle(
        (west, south), east - west, north - south,
        facecolor=colour, edgecolor=colour, alpha=0.25,
        transform=ccrs.PlateCarree(),
    ))
    map_ax.text(
        (west + east) / 2, (south + north) / 2,
        name.replace(" ", "\n"), ha="center", va="center",
        transform=ccrs.PlateCarree(),
    )
    time_ax.plot(
        hourly.index, hourly[name], color=colour,
        label=name, linewidth=1.8,
    )

map_ax.plot(
    14.334456, 51.746844, "*", color="black",
    markersize=9, transform=ccrs.PlateCarree(),
)
map_ax.set_aspect(1 / np.cos(np.deg2rad(52)))

time_ax.set_title("Area-weighted hourly PM₁₀")
time_ax.set_ylabel("PM₁₀ (µg/m³)")
time_ax.set_xlabel("January 2023 — UTC timestamps")
time_ax.xaxis.set_major_locator(mdates.DayLocator())
time_ax.xaxis.set_major_formatter(mdates.DateFormatter("%d Jan"))
time_ax.grid(alpha=0.25)
time_ax.legend()
time_ax.set_ylim(bottom=0)

fig.suptitle(
    "CAMS regional episode: 22–26 January 2023\n"
    "Cosine-latitude weighting; ≥90% valid area per hourly mean",
    fontsize=12,
)
fig.savefig(output / "regional_pm10_timeseries.png", dpi=180)
plt.close(fig)

print("Daily regional means (µg/m³; ≥18 valid hours):")
print(daily.round(2).to_string())
print("\nBox definitions and coverage:")
print(pd.DataFrame(metadata).to_string(index=False))
print("\nSaved figure and CSV files in docs/figures/")
