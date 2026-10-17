from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
import cartopy.crs as ccrs
import cartopy.feature as cfeature

output = Path("docs/figures")
output.mkdir(parents=True, exist_ok=True)

with xr.open_dataset("data/processed/cams_surface_pm10.nc") as ds:
    field = ds.pm10.sel(
        time=slice("2023-01-22", "2023-01-26T23:00:00")
    ).transpose("time", "latitude", "longitude").load()

expected = pd.date_range("2023-01-22", periods=120, freq="h")
if not pd.DatetimeIndex(field.time.values).equals(expected):
    raise ValueError("Expected 120 consecutive hourly timestamps.")

units = field.attrs.get("units", "").replace("µ", "u").replace("μ", "u")
if units not in {"ug/m3", "ug m-3"}:
    raise ValueError(f"Unexpected units: {units}")

field = field.where(np.isfinite(field) & (field >= 0))
if not np.isfinite(field.values).any():
    raise ValueError("No valid concentrations.")

vmax = max(5, float(np.ceil(field.max().item() / 5) * 5))

fig, ax = plt.subplots(
    figsize=(8, 7),
    subplot_kw={"projection": ccrs.PlateCarree()},
    layout="constrained"
)

mesh = ax.pcolormesh(
    field.longitude, field.latitude, field.isel(time=0),
    transform=ccrs.PlateCarree(),
    shading="auto", cmap="magma_r", vmin=0, vmax=vmax
)

ax.add_feature(
    cfeature.BORDERS.with_scale("10m"),
    linewidth=0.8, edgecolor="black"
)
ax.set_extent([12, 17, 50, 54], crs=ccrs.PlateCarree())
ax.set_xticks([12, 13, 14, 15, 16, 17], crs=ccrs.PlateCarree())
ax.set_yticks([50, 51, 52, 53, 54], crs=ccrs.PlateCarree())
ax.set_aspect(1 / np.cos(np.deg2rad(52)))
ax.set_xlabel("Longitude (°E)", labelpad=8)
ax.set_ylabel("Latitude (°N)")

ax.scatter(
    14.334456, 51.746844, marker="*", s=130,
    color="cyan", edgecolor="black",
    transform=ccrs.PlateCarree(), zorder=5
)
ax.text(
    14.45, 51.82, "Cottbus",
    transform=ccrs.PlateCarree(), fontsize=10
)

fig.colorbar(mesh, ax=ax, label="Surface PM₁₀ (µg/m³)", shrink=0.85)
fig.text(
    0.5, 0.01,
    "CAMS validated reanalysis ensemble median | Borders: Natural Earth",
    ha="center", fontsize=8
)
title = ax.set_title("")

def update(index):
    mesh.set_array(
        np.ma.masked_invalid(field.isel(time=index).values).ravel()
    )
    timestamp = pd.Timestamp(field.time.values[index])
    title.set_text(
        "Regional PM₁₀ episode\n"
        + timestamp.strftime("%d January %Y, %H:%M UTC")
    )
    return mesh, title

animation = FuncAnimation(
    fig, update, frames=field.sizes["time"], blit=False
)

target = output / "pm10_episode_hourly.gif"
fig.set_layout_engine(None)
ax.set_position([0.12, 0.16, 0.62, 0.72])
fig.axes[1].set_position([0.80, 0.20, 0.035, 0.64])
animation.save(target, writer=PillowWriter(fps=8), dpi=100)
plt.close(fig)

print(f"Saved: {target}")
print(f"Fixed colour scale: 0–{vmax:.0f} µg/m³")
