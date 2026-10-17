import argparse
from pathlib import Path

import xarray as xr

parser = argparse.ArgumentParser()
parser.add_argument("--input", type=Path, required=True)
args = parser.parse_args()

target = Path("data/processed/cams_surface_pm10.nc")
target.parent.mkdir(parents=True, exist_ok=True)

with xr.open_dataset(args.input) as ds:
    subset = ds[["pm10"]].sortby("lat").sortby("lon").sel(
        lat=slice(50, 54), lon=slice(12, 17)
    ).rename({"lat": "latitude", "lon": "longitude"})
    if not subset.sizes["latitude"] or not subset.sizes["longitude"]:
        raise ValueError("Empty geographical selection.")
    subset.attrs["original_file"] = args.input.name
    subset.attrs["processing"] = (
        "Selected 50–54 degrees north, 12–17 degrees east; "
        "renamed geographical coordinates; no unit conversion."
    )
    subset.to_netcdf(
        target, encoding={"pm10": {"zlib": True, "complevel": 4}}
    )

print(f"Saved: {target}")
