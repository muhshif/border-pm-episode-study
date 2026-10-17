from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

source = Path("data/processed/cams_surface_pm10.nc")
output = Path("docs/figures")
output.mkdir(parents=True, exist_ok=True)

with xr.open_dataset(source) as ds:
    field = ds["pm10"].sel(
        time=slice("2023-01-22", "2023-01-26T23:00:00")
    ).load()

expected = pd.date_range("2023-01-22", periods=120, freq="h")
if not pd.DatetimeIndex(field.time.values).equals(expected):
    raise ValueError("Expected 120 consecutive hourly timestamps.")

units = field.attrs.get("units", "").replace("µ", "u").replace("μ", "u")
if units not in {"ug/m3", "ug m-3"}:
    raise ValueError(f"Unexpected units: {units}")

field = field.where(np.isfinite(field) & (field >= 0))

daily = field.resample(time="1D").mean()
counts = field.resample(time="1D").count()
daily = daily.where(counts >= 18)

if not np.isfinite(daily.values).any():
    raise ValueError("No daily values meet the completeness requirement.")

vmax = max(5, float(np.ceil(daily.max().item() / 5) * 5))

fig, axes = plt.subplots(
    2, 3, figsize=(13, 9),
    sharex=True, sharey=True,
    subplot_kw={"projection": ccrs.PlateCarree()},
    layout="constrained"
)

for index, ax in enumerate(axes.flat):
    if index >= daily.sizes["time"]:
        ax.set_visible(False)
        continue

    day = daily.isel(time=index)
    image = ax.pcolormesh(
        day.longitude, day.latitude, day,
        cmap="magma_r", shading="auto",
        vmin=0, vmax=vmax
    )

    ax.scatter(
        14.334456, 51.746844,
        marker="*", s=110, color="cyan",
        edgecolor="black", linewidth=0.7
    )
    ax.annotate(
        "Cottbus", (14.334456, 51.746844),
        xytext=(6, 6), textcoords="offset points",
        fontsize=9
    )

    ax.set_title(pd.Timestamp(day.time.item()).strftime("%d January %Y"))
    ax.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=0.8, edgecolor="black")
    ax.set_xticks([12, 13, 14, 15, 16, 17], crs=ccrs.PlateCarree())
    ax.set_yticks([50, 51, 52, 53, 54], crs=ccrs.PlateCarree())
    ax.set_xlim(12, 17)
    ax.set_ylim(50, 54)
    ax.set_aspect(1 / np.cos(np.deg2rad(52)))
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")

fig.colorbar(
    image, ax=list(axes.flat[:5]),
    label="Daily mean surface PM₁₀ (µg/m³)",
    shrink=0.8
)
fig.suptitle(
    "CAMS PM₁₀ episode: 22–26 January 2023\n"
    "Means grouped by UTC timestamps; ≥18 valid hourly values per cell",
    fontsize=14
)

target = output / "daily_pm10_maps.png"
fig.savefig(target, dpi=180)
plt.close(fig)

weights = np.cos(np.deg2rad(daily.latitude))
summary = daily.weighted(weights).mean(
    ("latitude", "longitude")
).to_series().rename("domain_mean_pm10_ug_m3")

summary.to_csv(output / "daily_domain_means.csv")
print(summary)
print(f"\nSaved: {target}")
print(f"Shared colour scale: 0–{vmax:.0f} µg/m³")
