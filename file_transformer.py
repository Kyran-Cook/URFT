from __future__ import annotations

import universal_transform

from dataclasses import dataclass, field
from typing import Literal, Optional, Union
import datetime as dt

import numpy as np

import pandas as pd
import os
import numpy as np
from pathlib import Path

from shapely.geometry import (
    Point, LineString, Polygon,
    MultiPoint, MultiLineString, MultiPolygon,
    GeometryCollection
)
from shapely.geometry.base import BaseGeometry
import geopandas as gpd

# This file will transform different file types between referene frames.
# The supprted files types are as follows:
# - .csv
# - .shp
# - .json
# - .tif
# - .dxf(maybe)

# These files are returned in the same format they are given

@dataclass(slots=True)
class TransformParams:
    """
    Holds transformation parameters that are NOT coordinates.

    This object is reusable for many points.
    Coordinates are supplied separately at call time.
    """

    from_ref: str
    to_ref: str

    from_epoch: Optional[dt.date] = None
    to_epoch: Optional[dt.date] = None

    plate_motion: str = "auto"      # "auto" | "aus"
    vcv: Optional[np.ndarray] = None

    return_type: str = "xyz"         # "xyz" | "llh" | "enu"
    ignore_errors: bool = False

    # -------------------
    # Validation
    # -------------------
    def validate_basic(self):
        if self.plate_motion not in ("auto", "aus"):
            raise ValueError("plate_motion must be 'auto' or 'aus'")

        if self.return_type.lower() not in ("xyz", "llh", "enu"):
            raise ValueError("return_type must be 'xyz', 'llh', or 'enu'")

        if self.vcv is not None:
            if not isinstance(self.vcv, np.ndarray):
                raise TypeError("vcv must be a numpy array")
            if self.vcv.shape != (3, 3):
                raise ValueError(f"vcv must be shape (3,3), got {self.vcv.shape}")

    # -------------------
    # Helper to build kwargs
    # -------------------
    def to_kwargs(self):
        return dict(
            from_ref=self.from_ref,
            to_ref=self.to_ref,
            from_epoch=self.from_epoch,
            to_epoch=self.to_epoch,
            plate_motion=self.plate_motion,
            vcv=self.vcv,
            return_type=self.return_type,
            ignore_errors=self.ignore_errors,
        )


Column = Union[int, str]  # column index or header name

@dataclass(slots=True)
class CSVCoordinateMapping:
    """
    Unified CSV mapping for coordinate inputs.

    coord_type:
        - "xyz"
        - "llh"
        - "enu"

    angle_format (LLH only):
        - "dd"   (decimal degrees)
        - "ddm"  (degrees decimal minutes)
        - "dms"  (degrees minutes seconds)
    """

    # -------------------------
    # Coordinate system control
    # -------------------------
    coord_type: str                   # "xyz" | "llh" | "enu"
    angle_format: Optional[str] = None  # "dd" | "ddm" | "dms" (LLH only)

    # -------------------------
    # XYZ columns
    # -------------------------
    x: Optional[Column] = None
    y: Optional[Column] = None
    z: Optional[Column] = None

    # -------------------------
    # LLH columns
    # -------------------------

    # Degrees / minutes / seconds OR decimal minutes
    lat_deg: Optional[Column] = None
    lat_min: Optional[Column] = None
    lat_sec: Optional[Column] = None

    lon_deg: Optional[Column] = None
    lon_min: Optional[Column] = None
    lon_sec: Optional[Column] = None

    el_height: Optional[Column] = None

    # -------------------------
    # ENU columns
    # -------------------------
    east: Optional[Column] = None
    north: Optional[Column] = None
    zone: Optional[Column] = None


    # -------------------------
    # Validation
    # -------------------------
    def validate(self):
        coord_type = self.coord_type.lower()

        if coord_type == "xyz":
            self._validate_xyz()

        elif coord_type == "llh":
            self._validate_llh()

        elif coord_type == "enu":
            self._validate_enu()

        else:
            raise ValueError(
                "coord_type must be one of: 'xyz', 'llh', 'enu'"
            )

    # -------------------------
    # Internal validators
    # -------------------------
    def _validate_xyz(self):
        if None in (self.x, self.y, self.z):
            raise ValueError("XYZ mapping requires x, y, and z columns")

    def _validate_llh(self):
        if self.angle_format is None:
            raise ValueError("LLH mapping requires angle_format")

        angle_format = self.angle_format.lower()

        if self.el_height is None:
            raise ValueError("LLH mapping requires el_height column")

        if angle_format == "dd":
            if None in (self.lat_deg, self.lon_deg):
                raise ValueError(
                    "LLH 'dd' format requires lat and lon columns"
                )

        elif angle_format == "ddm":
            if None in (
                self.lat_deg, self.lat_min,
                self.lon_deg, self.lon_min
            ):
                raise ValueError(
                    "LLH 'ddm' format requires deg and min columns"
                )

        elif angle_format == "dms":
            if None in (
                self.lat_deg, self.lat_min, self.lat_sec,
                self.lon_deg, self.lon_min, self.lon_sec
            ):
                raise ValueError(
                    "LLH 'dms' format requires deg, min and sec columns"
                )

        else:
            raise ValueError(
                "angle_format must be one of: 'dd', 'ddm', 'dms'"
            )

    def _validate_enu(self):
        if None in (self.east, self.north, self.el_height, self.zone):
            raise ValueError(
                "ENU mapping requires east, north, height, and zone columns"
            )


def csv_transformation(file_path, csv_params, transform_params):
    
    """
    Reads a CSV, transforms each coordinate row, and writes a new CSV
    with a _transformed suffix. All original columns are preserved;
    coordinate columns are overwritten with transformed values.

    Returns the output file path.
    """
    
    print(f"Transforming CSV file at {file_path} with params: {transform_params}")
    # Here you would read the CSV, apply transformations, and write the output
    csv_params.validate()
    transform_params.validate_basic()

    df = pd.read_csv(file_path, header=None)
    kwargs = transform_params.to_kwargs()
    coord_type = csv_params.coord_type.lower()

    # --- Extract coordinates as numpy arrays ---
    if coord_type == "xyz":
        xs = df[csv_params.x].to_numpy(dtype=float)
        ys = df[csv_params.y].to_numpy(dtype=float)
        zs = df[csv_params.z].to_numpy(dtype=float)

        results = [
            universal_transform.universal_transform(float(x), float(y), float(z), **kwargs)
            for x, y, z in zip(xs, ys, zs)
        ]
        results = np.array(results)  # shape (N, 3) or (N, 6) with VCV

        df[csv_params.x] = [r["coords"]["x"] for r in results]
        df[csv_params.y] = [r["coords"]["y"] for r in results]
        df[csv_params.z] = [r["coords"]["z"] for r in results]

    elif coord_type == "llh":
        angle_format = csv_params.angle_format.lower()

        # Build decimal-degree lat/lon regardless of input angle format
        if angle_format == "dd":
            lats = df[csv_params.lat_deg].to_numpy(dtype=float)
            lons = df[csv_params.lon_deg].to_numpy(dtype=float)
            
            print(lats)
            print(lons)

        elif angle_format == "ddm":
            lats = df[csv_params.lat_deg].to_numpy(dtype=float) + \
                   df[csv_params.lat_min].to_numpy(dtype=float) / 60.0
            lons = df[csv_params.lon_deg].to_numpy(dtype=float) + \
                   df[csv_params.lon_min].to_numpy(dtype=float) / 60.0

        elif angle_format == "dms":
            lats = df[csv_params.lat_deg].to_numpy(dtype=float) + \
                   df[csv_params.lat_min].to_numpy(dtype=float) / 60.0 + \
                   df[csv_params.lat_sec].to_numpy(dtype=float) / 3600.0
            lons = df[csv_params.lon_deg].to_numpy(dtype=float) + \
                   df[csv_params.lon_min].to_numpy(dtype=float) / 60.0 + \
                   df[csv_params.lon_sec].to_numpy(dtype=float) / 3600.0

        heights = df[csv_params.el_height].to_numpy(dtype=float)

        results = [
                universal_transform.universal_transform_llh(float(lat), float(lon), float(h), **kwargs)
                for lat, lon, h in zip(lats, lons, heights)
            ]

        out_lats = [r["coords"]["lat"] for r in results]
        out_lons = [r["coords"]["lon"] for r in results]
        out_heights = [r["coords"]["el_height"] for r in results]

        df[csv_params.el_height] = out_heights

        if angle_format == "dd":
            df[csv_params.lat_deg] = out_lats
            df[csv_params.lon_deg] = out_lons

        elif angle_format == "ddm":
            def dd_to_ddm(dd):
                deg = int(dd)
                mins = abs(dd - deg) * 60
                return deg, round(mins,5)

            lat_ddm = [dd_to_ddm(lat) for lat in out_lats]
            lon_ddm = [dd_to_ddm(lon) for lon in out_lons]

            df[csv_params.lat_deg] = [d[0] for d in lat_ddm]
            df[csv_params.lat_min] = [d[1] for d in lat_ddm]
            df[csv_params.lon_deg] = [d[0] for d in lon_ddm]
            df[csv_params.lon_min] = [d[1] for d in lon_ddm]

        elif angle_format == "dms":
            def dd_to_dms(dd):
                deg = int(dd)
                remainder = abs(dd - deg) * 60
                mins = int(remainder)
                secs = (remainder - mins) * 60
                return deg, mins, round(secs,4)

            lat_dms = [dd_to_dms(lat) for lat in out_lats]
            lon_dms = [dd_to_dms(lon) for lon in out_lons]

            df[csv_params.lat_deg] = [d[0] for d in lat_dms]
            df[csv_params.lat_min] = [d[1] for d in lat_dms]
            df[csv_params.lat_sec] = [d[2] for d in lat_dms]
            df[csv_params.lon_deg] = [d[0] for d in lon_dms]
            df[csv_params.lon_min] = [d[1] for d in lon_dms]
            df[csv_params.lon_sec] = [d[2] for d in lon_dms]

    elif coord_type == "enu":
        easts  = df[csv_params.east].to_numpy(dtype=float)
        norths = df[csv_params.north].to_numpy(dtype=float)
        heights = df[csv_params.el_height].to_numpy(dtype=float)
        zones  = df[csv_params.zone].to_numpy()

        results = [
            universal_transform.universal_transform_enu(float(e), float(n), float(h), int(z), **kwargs)
            for e, n, h, z in zip(easts, norths, heights, zones)
        ]
        results = np.array(results)

        df[csv_params.east]   = [r["coords"]["east"]   for r in results]
        df[csv_params.north]  = [r["coords"]["north"]  for r in results]
        df[csv_params.el_height] = [r["coords"]["height"] for r in results]
        df[csv_params.zone]   = [r["coords"]["zone"]   for r in results]

    # --- Write output ---
    input_path = Path(file_path)
    output_path = input_path.with_stem(input_path.stem + "_transformed")
    df.to_csv(output_path, index=False, header=None)

    print(f"Transformed {len(df)} rows to: {output_path}")
    return str(output_path)

# CRS lookup for common reference frames - extend as needed
CRS_LOOKUP = {
    "GDA2020":  "EPSG:7844",
    "GDA94":    "EPSG:4283",
    "ITRF2014": "EPSG:9000",
    "WGS84":    "EPSG:4326",
}

def _get_coord_type(gdf: gpd.GeoDataFrame) -> str:
    """Determine coordinate type from the GeoDataFrame's CRS."""
    if gdf.crs is None:
        raise ValueError("Shapefile has no CRS defined, cannot determine coordinate type.")
    
    if gdf.crs.is_geographic:
        return "llh"
    elif gdf.crs.is_projected:
        return "enu"
    else:
        return "xyz"  # fallback for ECEF/cartesian


def _transform_coords(coords, transform_func, coord_type):
    """Transform a list of (x, y) or (x, y, z) coordinate tuples."""
    transformed = []
    for coord in coords:
        if len(coord) == 2:
            x, y = coord
            z = 0.0
        else:
            x, y, z = coord

        if coord_type == "llh":
            # Shapely stores (lon, lat) so swap to (lat, lon) for the function
            result = transform_func(float(y), float(x), float(z))
            c = result["coords"]
            transformed.append((c["lon"], c["lat"], c["el_height"]))

        elif coord_type == "enu":
            result = transform_func(float(x), float(y), float(z))
            c = result["coords"]
            transformed.append((c["east"], c["north"], c["height"]))

        else:  # xyz
            result = transform_func(float(x), float(y), float(z))
            c = result["coords"]
            transformed.append((c["x"], c["y"], c["z"]))

    return transformed

def _transform_geometry(geom: BaseGeometry, transform_func) -> BaseGeometry:
    if geom is None or geom.is_empty:
        return geom

    if isinstance(geom, Point):
        coords = list(geom.coords)
        return Point(transform_func(*coords[0]))

    elif isinstance(geom, LineString):
        return LineString([transform_func(*c) for c in geom.coords])

    elif isinstance(geom, Polygon):
        exterior = [transform_func(*c) for c in geom.exterior.coords]
        interiors = [
            [transform_func(*c) for c in ring.coords]
            for ring in geom.interiors
        ]
        return Polygon(exterior, interiors)

    elif isinstance(geom, MultiPoint):
        return MultiPoint([_transform_geometry(p, transform_func) for p in geom.geoms])

    elif isinstance(geom, MultiLineString):
        return MultiLineString([_transform_geometry(l, transform_func) for l in geom.geoms])

    elif isinstance(geom, MultiPolygon):
        return MultiPolygon([_transform_geometry(p, transform_func) for p in geom.geoms])

    elif isinstance(geom, GeometryCollection):
        return GeometryCollection([_transform_geometry(g, transform_func) for g in geom.geoms])

    else:
        raise TypeError(f"Unsupported geometry type: {type(geom)}")

def shp_transformation(file_path: str, transform_params: TransformParams) -> str:
    transform_params.validate_basic()
    kwargs = transform_params.to_kwargs()

    gdf = gpd.read_file(file_path)
    coord_type = _get_coord_type(gdf)

    # Select the correct transform function based on input coord type
    if coord_type == "llh":
        def transform_func(lat, lon, h):
            return universal_transform.universal_transform_llh(lat, lon, h, **kwargs)

    elif coord_type == "enu":
        def transform_func(e, n, h):
            return universal_transform.universal_transform_enu(e, n, h, **kwargs)

    else:
        def transform_func(x, y, z):
            return universal_transform.universal_transform(x, y, z, **kwargs)

    gdf["geometry"] = gdf["geometry"].apply(
        lambda geom: _transform_geometry(
            geom,
            lambda *c: _transform_coords([c], transform_func, coord_type)[0]
        )
    )

    # Update CRS metadata if target reference is known
    target_crs = CRS_LOOKUP.get(transform_params.to_ref)
    if target_crs:
        gdf = gdf.set_crs(target_crs, allow_override=True)
    else:
        print(f"Warning: CRS for '{transform_params.to_ref}' not in lookup table, metadata not updated.")

    output_path = Path(file_path).with_stem(Path(file_path).stem + "_transformed")
    gdf.to_file(output_path)

    print(f"Transformed {len(gdf)} features → {output_path}")
    return str(output_path)

params_xyz = TransformParams("ITRF2014", "GDA94", dt.date(2014,1,1), plate_motion="aus", return_type="xyz")
params_llh = TransformParams("ITRF2014", "GDA94", dt.date(2014,1,1), plate_motion="aus", return_type="llh")
params_enu = TransformParams("MGA94", "MGA2020", dt.date(2014,1,1), plate_motion="aus", return_type="enu")
params_shp = TransformParams("ITRF2014", "GDA94", dt.date(2014,1,1), plate_motion="auto", ignore_errors=True)

csv_xyz = CSVCoordinateMapping("xyz", None, 1, 2, 3)
csv_llh_dd = CSVCoordinateMapping("llh", "dd", lat_deg=1,lon_deg=2,el_height=3)
csv_llh_ddm = CSVCoordinateMapping("llh", "ddm", lat_deg=1,lat_min=2, lon_deg=3, lon_min=4, el_height=5)
csv_llh_dms = CSVCoordinateMapping("llh", "dms", lat_deg=1,lat_min=2,lat_sec=3, lon_deg=4, lon_min=5,lon_sec=6, el_height=7)
csv_enu = CSVCoordinateMapping("enu", None, zone=1, east=2, north=3, el_height=4)

#params.validate_basic()

#out = universal_transform.universal_transform(-4130636.759, 2894953.142, -3890530.249, **params_xyz.to_kwargs())
#print(out)

#print(csv_transformation(r"C:\Users\User\Documents\Repositories\URFT\test_files\test_xyz.csv", csv_xyz, params_xyz))
#print(csv_transformation(r"C:\Users\User\Documents\Repositories\URFT\test_files\test_llh_dd.csv", csv_llh_dd, params_llh))
#print(csv_transformation(r"C:\Users\User\Documents\Repositories\URFT\test_files\test_llh_ddm.csv", csv_llh_ddm, params_llh))
#print(csv_transformation(r"C:\Users\User\Documents\Repositories\URFT\test_files\test_llh_dms.csv", csv_llh_dms, params_llh))
#print(csv_transformation(r"C:\Users\User\Documents\Repositories\URFT\test_files\test_enu.csv", csv_enu, params_enu))
print(shp_transformation(r"C:\Users\User\Documents\Repositories\URFT\test_files\corner.shp", params_shp))
