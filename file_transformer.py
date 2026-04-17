from __future__ import annotations

import universal_transform
import csv

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

from pathlib import Path
from typing import Optional, Literal, Iterable, Union, List

import geopandas as gpd
import fiona
from shapely.ops import transform as shapely_transform

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

    return_type: str = None         # "xyz" | "llh" | "enu"
    ignore_errors: bool = False
    angle_return_type: Optional[str] = None  # "dd" | "ddm" | "dms" (LLH output only)

    # -------------------
    # Validation
    # -------------------
    def validate_basic(self):
        if self.plate_motion not in ("auto", "aus"):
            raise ValueError("plate_motion must be 'auto' or 'aus'")
    
        if self.return_type is not None and self.return_type.lower() not in ("xyz", "llh", "enu"):
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

def csv_transformation_xyz(df, csv_params, transform_params):
    xs = df[csv_params.x].to_numpy(dtype=float)
    ys = df[csv_params.y].to_numpy(dtype=float)
    zs = df[csv_params.z].to_numpy(dtype=float)

    kwargs = transform_params.to_kwargs()
    return_type = transform_params.return_type.lower()
    angle_return_type = transform_params.angle_return_type.lower() if transform_params.angle_return_type is not None else None

    results = [
        universal_transform.universal_transform(float(x), float(y), float(z), **kwargs)
        for x, y, z in zip(xs, ys, zs)
    ]
    results = np.array(results)  # shape (N, 3) or (N, 6) with VCV

    #create header array
    header_arr = [None] * len(df.columns)
    header_arr[csv_params.x] = "x"
    header_arr[csv_params.y] = "y"
    header_arr[csv_params.z] = "z"

    #Make correct output for return type
    if return_type == None or return_type == "xyz":

        df[len(df.columns)] = [r["coords"]["x"] for r in results]
        df[len(df.columns) + 1] = [r["coords"]["y"] for r in results]
        df[len(df.columns) + 2] = [r["coords"]["z"] for r in results]

        header_arr.append("x_transformed")
        header_arr.append("y_transformed")
        header_arr.append("z_transformed")


    if return_type == "llh":

        if angle_return_type == "dd":
            df[len(df.columns)] = [r["coords"]["lat"] for r in results]
            df[len(df.columns) + 1] = [r["coords"]["lon"] for r in results]
            df[len(df.columns) + 2] = [r["coords"]["el_height"] for r in results]

            header_arr.append("lat_transformed")
            header_arr.append("lon_transformed")
            header_arr.append("el_height_transformed")

        if angle_return_type == "ddm":
            def dd_to_ddm(dd):
                deg = int(dd)
                mins = abs(dd - deg) * 60
                return deg, round(mins,5)

            lat_ddm = [dd_to_ddm(r["coords"]["lat"]) for r in results]
            lon_ddm = [dd_to_ddm(r["coords"]["lon"]) for r in results]

            df[len(df.columns)] = [d[0] for d in lat_ddm]
            df[len(df.columns) + 1] = [d[1] for d in lat_ddm]
            df[len(df.columns) + 2] = [d[0] for d in lon_ddm]
            df[len(df.columns) + 3] = [d[1] for d in lon_ddm]
            df[len(df.columns) + 4] = [r["coords"]["el_height"] for r in results]

            header_arr.append("lat_deg_transformed")
            header_arr.append("lat_min_transformed")
            header_arr.append("lon_deg_transformed")
            header_arr.append("lon_min_transformed")
            header_arr.append("el_height_transformed")

        if angle_return_type == "dms":
            def dd_to_dms(dd):
                deg = int(dd)
                remainder = abs(dd - deg) * 60
                mins = int(remainder)
                secs = (remainder - mins) * 60
                return deg, mins, round(secs,4)

            lat_dms = [dd_to_dms(r["coords"]["lat"]) for r in results]
            lon_dms = [dd_to_dms(r["coords"]["lon"]) for r in results]

            df[len(df.columns)] = [d[0] for d in lat_dms]
            df[len(df.columns) + 1] = [d[1] for d in lat_dms]
            df[len(df.columns) + 2] = [d[2] for d in lat_dms]
            df[len(df.columns) + 3] = [d[0] for d in lon_dms]
            df[len(df.columns) + 4] = [d[1] for d in lon_dms]
            df[len(df.columns) + 5] = [d[2] for d in lon_dms]
            df[len(df.columns) + 6] = [r["coords"]["el_height"] for r in results]

            header_arr.append("lat_deg_transformed")
            header_arr.append("lat_min_transformed")
            header_arr.append("lat_sec_transformed")
            header_arr.append("lon_deg_transformed")
            header_arr.append("lon_min_transformed")
            header_arr.append("lon_sec_transformed")
            header_arr.append("el_height_transformed")

    if return_type == "enu":

        df[len(df.columns)] = [r["coords"]["east"] for r in results]
        df[len(df.columns) + 1] = [r["coords"]["north"] for r in results]
        df[len(df.columns) + 2] = [r["coords"]["el_height"] for r in results]
        df[len(df.columns) + 3] = [r["coords"]["zone"] for r in results]

        header_arr.append("east_transformed")
        header_arr.append("north_transformed")
        header_arr.append("el_height_transformed")
        header_arr.append("zone_transformed")
        
    df.columns = header_arr
    return df

def csv_transformation_llh(df, csv_params, transform_params):
    
    angle_format = csv_params.angle_format.lower() if csv_params.angle_format is not None else None
    angle_return_type = transform_params.angle_return_type.lower() if transform_params.angle_return_type is not None else None
    kwargs = transform_params.to_kwargs()
    return_type = transform_params.return_type.lower()

    # Build decimal-degree lat/lon regardless of input angle format
    if angle_format == "dd":
        lats = df[csv_params.lat_deg].to_numpy(dtype=float)
        lons = df[csv_params.lon_deg].to_numpy(dtype=float)

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

    # Create header array
    header_arr = [None] * len(df.columns)
    if angle_format == "dd":
        header_arr[csv_params.lat_deg] = "lat"
        header_arr[csv_params.lon_deg] = "lon"
        header_arr[csv_params.el_height] = "el_height"
    elif angle_format == "ddm":
        header_arr[csv_params.lat_deg] = "lat_deg"
        header_arr[csv_params.lat_min] = "lat_min"
        header_arr[csv_params.lon_deg] = "lon_deg"
        header_arr[csv_params.lon_min] = "lon_min"
        header_arr[csv_params.el_height] = "el_height"
    elif angle_format == "dms":
        header_arr[csv_params.lat_deg] = "lat_deg"
        header_arr[csv_params.lat_min] = "lat_min"
        header_arr[csv_params.lat_sec] = "lat_sec"
        header_arr[csv_params.lon_deg] = "lon_deg"
        header_arr[csv_params.lon_min] = "lon_min"
        header_arr[csv_params.lon_sec] = "lon_sec"
        header_arr[csv_params.el_height] = "el_height"
    else:
        raise ValueError(
            "angle_format must be one of: 'dd', 'ddm', 'dms'"
        )
    
    #Make correct output for return type
    if return_type == "xyz":

        df[len(df.columns)] = [r["coords"]["x"] for r in results]
        df[len(df.columns) + 1] = [r["coords"]["y"] for r in results]
        df[len(df.columns) + 2] = [r["coords"]["z"] for r in results]

        header_arr.append("x_transformed")
        header_arr.append("y_transformed")
        header_arr.append("z_transformed")


    if return_type is None or return_type == "llh":

        if angle_return_type == "dd":
            df[len(df.columns)] = [r["coords"]["lat"] for r in results]
            df[len(df.columns) + 1] = [r["coords"]["lon"] for r in results]
            df[len(df.columns) + 2] = [r["coords"]["el_height"] for r in results]

            header_arr.append("lat_transformed")
            header_arr.append("lon_transformed")
            header_arr.append("el_height_transformed")

        if angle_return_type == "ddm":
            def dd_to_ddm(dd):
                deg = int(dd)
                mins = abs(dd - deg) * 60
                return deg, round(mins,5)

            lat_ddm = [dd_to_ddm(r["coords"]["lat"]) for r in results]
            lon_ddm = [dd_to_ddm(r["coords"]["lon"]) for r in results]

            df[len(df.columns)] = [d[0] for d in lat_ddm]
            df[len(df.columns) + 1] = [d[1] for d in lat_ddm]
            df[len(df.columns) + 2] = [d[0] for d in lon_ddm]
            df[len(df.columns) + 3] = [d[1] for d in lon_ddm]
            df[len(df.columns) + 4] = [r["coords"]["el_height"] for r in results]

            header_arr.append("lat_deg_transformed")
            header_arr.append("lat_min_transformed")
            header_arr.append("lon_deg_transformed")
            header_arr.append("lon_min_transformed")
            header_arr.append("el_height_transformed")

        if angle_return_type == "dms":
            def dd_to_dms(dd):
                deg = int(dd)
                remainder = abs(dd - deg) * 60
                mins = int(remainder)
                secs = (remainder - mins) * 60
                return deg, mins, round(secs,4)

            lat_dms = [dd_to_dms(r["coords"]["lat"]) for r in results]
            lon_dms = [dd_to_dms(r["coords"]["lon"]) for r in results]

            df[len(df.columns)] = [d[0] for d in lat_dms]
            df[len(df.columns) + 1] = [d[1] for d in lat_dms]
            df[len(df.columns) + 2] = [d[2] for d in lat_dms]
            df[len(df.columns) + 3] = [d[0] for d in lon_dms]
            df[len(df.columns) + 4] = [d[1] for d in lon_dms]
            df[len(df.columns) + 5] = [d[2] for d in lon_dms]
            df[len(df.columns) + 6] = [r["coords"]["el_height"] for r in results]

            header_arr.append("lat_deg_transformed")
            header_arr.append("lat_min_transformed")
            header_arr.append("lat_sec_transformed")
            header_arr.append("lon_deg_transformed")
            header_arr.append("lon_min_transformed")
            header_arr.append("lon_sec_transformed")
            header_arr.append("el_height_transformed")

    if return_type == "enu":

        df[len(df.columns)] = [r["coords"]["east"] for r in results]
        df[len(df.columns) + 1] = [r["coords"]["north"] for r in results]
        df[len(df.columns) + 2] = [r["coords"]["el_height"] for r in results]
        df[len(df.columns) + 3] = [r["coords"]["zone"] for r in results]

        header_arr.append("east_transformed")
        header_arr.append("north_transformed")
        header_arr.append("el_height_transformed")
        header_arr.append("zone_transformed")
        
    df.columns = header_arr
    return df

def csv_transformation_enu(df, csv_params, transform_params):
        
    angle_return_type = transform_params.angle_return_type.lower() if transform_params.angle_return_type is not None else None
    kwargs = transform_params.to_kwargs()
    return_type = transform_params.return_type.lower()
        
    easts  = df[csv_params.east].to_numpy(dtype=float)
    norths = df[csv_params.north].to_numpy(dtype=float)
    heights = df[csv_params.el_height].to_numpy(dtype=float)
    zones  = df[csv_params.zone].to_numpy()

    results = [
        universal_transform.universal_transform_enu(float(e), float(n), float(h), int(z), **kwargs)
        for e, n, h, z in zip(easts, norths, heights, zones)
    ]
    results = np.array(results)

    # Create header array
    header_arr = [None] * len(df.columns)
    header_arr[csv_params.east] = "east"
    header_arr[csv_params.north] = "north"
    header_arr[csv_params.el_height] = "el_height"
    header_arr[csv_params.zone] = "zone"

    # Make correct output for return type
    if return_type == "xyz":

        df[len(df.columns)] = [r["coords"]["x"] for r in results]
        df[len(df.columns) + 1] = [r["coords"]["y"] for r in results]
        df[len(df.columns) + 2] = [r["coords"]["z"] for r in results]

        header_arr.append("x_transformed")
        header_arr.append("y_transformed")
        header_arr.append("z_transformed")


    if return_type == "llh":

        if angle_return_type == "dd":
            df[len(df.columns)] = [r["coords"]["lat"] for r in results]
            df[len(df.columns) + 1] = [r["coords"]["lon"] for r in results]
            df[len(df.columns) + 2] = [r["coords"]["el_height"] for r in results]

            header_arr.append("lat_transformed")
            header_arr.append("lon_transformed")
            header_arr.append("el_height_transformed")

        if angle_return_type == "ddm":
            def dd_to_ddm(dd):
                deg = int(dd)
                mins = abs(dd - deg) * 60
                return deg, round(mins,5)

            lat_ddm = [dd_to_ddm(r["coords"]["lat"]) for r in results]
            lon_ddm = [dd_to_ddm(r["coords"]["lon"]) for r in results]

            df[len(df.columns)] = [d[0] for d in lat_ddm]
            df[len(df.columns) + 1] = [d[1] for d in lat_ddm]
            df[len(df.columns) + 2] = [d[0] for d in lon_ddm]
            df[len(df.columns) + 3] = [d[1] for d in lon_ddm]
            df[len(df.columns) + 4] = [r["coords"]["el_height"] for r in results]

            header_arr.append("lat_deg_transformed")
            header_arr.append("lat_min_transformed")
            header_arr.append("lon_deg_transformed")
            header_arr.append("lon_min_transformed")
            header_arr.append("el_height_transformed")

        if angle_return_type == "dms":
            def dd_to_dms(dd):
                deg = int(dd)
                remainder = abs(dd - deg) * 60
                mins = int(remainder)
                secs = (remainder - mins) * 60
                return deg, mins, round(secs,4)

            lat_dms = [dd_to_dms(r["coords"]["lat"]) for r in results]
            lon_dms = [dd_to_dms(r["coords"]["lon"]) for r in results]

            df[len(df.columns)] = [d[0] for d in lat_dms]
            df[len(df.columns) + 1] = [d[1] for d in lat_dms]
            df[len(df.columns) + 2] = [d[2] for d in lat_dms]
            df[len(df.columns) + 3] = [d[0] for d in lon_dms]
            df[len(df.columns) + 4] = [d[1] for d in lon_dms]
            df[len(df.columns) + 5] = [d[2] for d in lon_dms]
            df[len(df.columns) + 6] = [r["coords"]["el_height"] for r in results]

            header_arr.append("lat_deg_transformed")
            header_arr.append("lat_min_transformed")
            header_arr.append("lat_sec_transformed")
            header_arr.append("lon_deg_transformed")
            header_arr.append("lon_min_transformed")
            header_arr.append("lon_sec_transformed")
            header_arr.append("el_height_transformed")

    if return_type is None or return_type == "enu":

        df[len(df.columns)] = [r["coords"]["east"] for r in results]
        df[len(df.columns) + 1] = [r["coords"]["north"] for r in results]
        df[len(df.columns) + 2] = [r["coords"]["el_height"] for r in results]
        df[len(df.columns) + 3] = [r["coords"]["zone"] for r in results]

        header_arr.append("east_transformed")
        header_arr.append("north_transformed")
        header_arr.append("el_height_transformed")
        header_arr.append("zone_transformed")
        
    df.columns = header_arr
    return df

def csv_transformation(file_path, csv_params, transform_params):
    
    """
    Reads a CSV, transforms each coordinate row, and writes a new CSV
    with a _transformed suffix. All original columns are preserved;
    coordinate columns are overwritten with transformed values.

    Returns the output file path.
    """
    
    #print(f"Transforming CSV file at {file_path} with params: {transform_params}")
    # Here you would read the CSV, apply transformations, and write the output
    csv_params.validate()
    transform_params.validate_basic()

    df = pd.read_csv(file_path, header=None)
    coord_type = csv_params.coord_type.lower()

    # --- Extract coordinates as numpy arrays ---
    if coord_type == "xyz":
        df = csv_transformation_xyz(df, csv_params, transform_params)

    elif coord_type == "llh":
        df = csv_transformation_llh(df, csv_params, transform_params)

    elif coord_type == "enu":
        df = csv_transformation_enu(df, csv_params, transform_params)

    # --- Write output ---
    input_path = Path(file_path.name)
    output_path = input_path.with_stem(input_path.stem + "_transformed")
    df.to_csv(output_path, index=False)

    print(f"Transformed {len(df)} rows to: {output_path}")
    return str(output_path)



# ---------------------------
# Helpers
# ---------------------------

def _is_geographic_crs(gdf: gpd.GeoDataFrame) -> bool:
    """True if CRS exists and is geographic (lat/lon)."""
    if gdf.crs is None:
        return False
    try:
        return bool(getattr(gdf.crs, "is_geographic", False))
    except Exception:
        return False


def _list_layers(path: Union[str, Path]) -> List[str]:
    """List layers for multi-layer datasets (e.g., GeoPackage)."""
    try:
        return list(fiona.listlayers(str(path)))
    except Exception:
        return []


def _infer_mga_zone_from_epsg(epsg: Optional[int]) -> Optional[int]:
    """
    Best-effort inference for MGA zone from common EPSG patterns.

    Examples:
      - GDA94 / MGA zone 56  -> EPSG:28356 -> zone = 56
      - GDA2020 / MGA zone 56 -> EPSG:7856 -> zone = 56

    Returns None if it can't infer.
    """
    if epsg is None:
        return None

    # GDA94 MGA zones: EPSG 28300 + zone (e.g., 28356 => 56)
    if 28300 <= epsg <= 28399:
        zone = epsg - 28300
        if 1 <= zone <= 60:
            return zone

    # GDA2020 MGA zones: commonly EPSG 7800 + zone (e.g., 7856 => 56)
    if 7800 <= epsg <= 7899:
        zone = epsg - 7800
        if 1 <= zone <= 60:
            return zone

    return None


# ---------------------------
# Transform one GeoDataFrame
# ---------------------------

def transform_geodataframe(
    gdf: gpd.GeoDataFrame,
    transform_params: "TransformParams",
    *,
    coord_type: Literal["auto", "llh", "enu", "xyz"] = "auto",
    height_default: float = 0.0,
    zone: Optional[int] = None,
    zone_from_crs: bool = True,
    out_crs: Optional[str] = None,
    default_if_unknown: Literal["llh", "enu"] = "enu",
) -> gpd.GeoDataFrame:
    """
    Transform geometries in a GeoDataFrame using your Geodepy-based functions.

    coord_type:
      - "auto": geographic CRS -> llh, projected CRS -> enu, CRS missing -> default_if_unknown
      - "llh" : interpret x=lon, y=lat (degrees)
      - "enu" : interpret x=east, y=north (requires MGA zone)
      - "xyz" : interpret x,y,z as geocentric XYZ (rare for GIS data)

    out_crs:
      Sets CRS metadata after transformation (does NOT reproject using pyproj).
      Use this if you are doing a datum/ref-frame change and want to update the tag.
    """
    transform_params.validate_basic()
    kwargs = transform_params.to_kwargs()
    print(kwargs)

    gdf_out = gdf.copy()
    print(gdf_out)

    # Decide coordinate interpretation
    ct = coord_type.lower()
    if ct == "auto":
        if _is_geographic_crs(gdf_out):
            ct = "llh"
        elif gdf_out.crs is None:
            ct = default_if_unknown
        else:
            ct = "enu"

    # Determine MGA zone if ENU
    used_zone = zone
    if ct == "enu" and used_zone is None and zone_from_crs and gdf_out.crs is not None:
        try:
            epsg = gdf_out.crs.to_epsg()
        except Exception:
            epsg = None
        used_zone = _infer_mga_zone_from_epsg(epsg)

    if ct == "enu" and used_zone is None:
        raise ValueError(
            "ENU transformation requires an MGA zone. Provide zone=..., "
            "or ensure CRS EPSG allows inference (e.g., EPSG:28356 / EPSG:7856)."
        )

    # Coordinate function for shapely.ops.transform
    #
    # Shapely/GIS coordinate order is (x, y) = (lon/east, lat/north)
    # Your universal_transform_llh expects (lat, lon, h) -> so we swap x/y on input/output.
    def _coord_func(x, y, z=None):
        has_z = z is not None
        h = float(z) if has_z else float(height_default)
        x = float(x)
        y = float(y)

        if ct == "llh":
            print(x, y)
            res = universal_transform.universal_transform_llh(float(y), float(x), h, **kwargs)
            print(res)
            lon2 = res["coords"]["lon"]
            lat2 = res["coords"]["lat"]
            h2   = res["coords"]["el_height"]
            return (lon2, lat2, h2) if has_z else (lon2, lat2)

        if ct == "enu":
            res = universal_transform.universal_transform_enu(float(x), float(y), h, int(used_zone), **kwargs)
            e2 = res["coords"]["east"]
            n2 = res["coords"]["north"]
            h2 = res["coords"]["height"]
            return (e2, n2, h2) if has_z else (e2, n2)

        if ct == "xyz":
            # xyz needs 3D; if missing Z, use height_default as best-effort Z
            if z is None:
                z = float(height_default)
                has_z = True
            res = universal_transform.universal_transform(float(x), float(y), float(z), **kwargs)
            x2 = res["coords"]["x"]
            y2 = res["coords"]["y"]
            z2 = res["coords"]["z"]
            return (x2, y2, z2) if has_z else (x2, y2)

        raise ValueError("coord_type must be 'auto', 'llh', 'enu', or 'xyz'")

    def _transform_geom(geom):
        if geom is None or geom.is_empty:
            return geom
        return shapely_transform(_coord_func, geom)

    gdf_out["geometry"] = gdf_out["geometry"].apply(_transform_geom)

    # Update CRS metadata if requested (no reprojection performed)
    if out_crs is not None:
        gdf_out = gdf_out.set_crs(out_crs, allow_override=True)

    return gdf_out


# ---------------------------
# Read/Write vector files
# ---------------------------

LayerSpec = Union[Literal["auto", "all"], str, Iterable[str], None]

def transform_vector_file(
    file_path: str,
    transform_params: "TransformParams",
    *,
    coord_type: Literal["auto", "llh", "enu", "xyz"] = "auto",
    height_default: float = 0.0,
    zone: Optional[int] = None,
    zone_from_crs: bool = True,
    out_crs: Optional[str] = None,
    layers: LayerSpec = "auto",
    default_if_unknown: Literal["llh", "enu"] = "enu",
) -> str:
    """
    Transform SHP, GeoJSON, or GeoPackage.

    - SHP/GeoJSON: typically single-layer (layers ignored)
    - GPKG: can have multiple layers:
        layers="auto" -> all layers if multiple exist, else the default layer
        layers="all"  -> all layers
        layers="roads" or ["roads","parcels"] -> specific layer(s)

    Writes output alongside input with suffix "_transformed".
    Returns output path.
    """
    in_path = Path(file_path)
    if not in_path.exists():
        raise FileNotFoundError(file_path)

    ext = in_path.suffix.lower()
    supported = {".shp", ".geojson", ".json", ".gpkg"}
    if ext not in supported:
        raise ValueError(f"Unsupported file type '{ext}'. Supported: {sorted(supported)}")

    out_path = in_path.with_name(in_path.stem + "_transformed" + in_path.suffix)

    # --- SHP / GeoJSON (single layer) ---
    if ext in {".shp", ".geojson", ".json"}:
        gdf = gpd.read_file(in_path)
        gdf_t = transform_geodataframe(
            gdf,
            transform_params,
            coord_type=coord_type,
            height_default=height_default,
            zone=zone,
            zone_from_crs=zone_from_crs,
            out_crs=out_crs,
            default_if_unknown=default_if_unknown,
        )
        gdf_t.to_file(out_path)  # driver inferred from extension
        return str(out_path)

    # --- GPKG (potentially multi-layer) ---
    available_layers = _list_layers(in_path)

    # Choose which layers to process
    if layers in (None, "auto"):
        layer_list = available_layers if len(available_layers) > 0 else [None]
    elif layers == "all":
        layer_list = available_layers if len(available_layers) > 0 else [None]
    elif isinstance(layers, str):
        layer_list = [layers]
    else:
        layer_list = list(layers)

    # If output exists, remove it so we can write layers cleanly
    if out_path.exists():
        out_path.unlink()

    for i, lyr in enumerate(layer_list):
        gdf = gpd.read_file(in_path, layer=lyr) if isinstance(lyr, str) else gpd.read_file(in_path)
        gdf_t = transform_geodataframe(
            gdf,
            transform_params,
            coord_type=coord_type,
            height_default=height_default,
            zone=zone,
            zone_from_crs=zone_from_crs,
            out_crs=out_crs,
            default_if_unknown=default_if_unknown,
        )

        layer_name = lyr if isinstance(lyr, str) else "layer"
        mode = "w" if i == 0 else "a"

        # GeoPandas supports mode for GPKG in modern stacks.
        # If your stack errors on mode, we can adjust (tell me your geopandas version).
        gdf_t.to_file(out_path, layer=layer_name, driver="GPKG", mode=mode)

    return str(out_path)


params_xyz = TransformParams("ITRF2014", "MGA94", dt.date(2014,1,1), plate_motion="aus", return_type="enu")
params_llh = TransformParams("ITRF2014", "GDA94", dt.date(2014,1,1), plate_motion="aus", return_type="xyz")
params_enu = TransformParams("MGA94", "MGA2020", dt.date(2014,1,1), plate_motion="aus", return_type="enu")
params_shp = TransformParams("ITRF2014", "GDA94", dt.date(2014,1,1), plate_motion="aus", ignore_errors=False)

csv_xyz = CSVCoordinateMapping("xyz", None, 1, 2, 3)
csv_llh_dd = CSVCoordinateMapping("llh", "dd", lat_deg=1,lon_deg=2,el_height=3)
csv_llh_ddm = CSVCoordinateMapping("llh", "ddm", lat_deg=1,lat_min=2, lon_deg=3, lon_min=4, el_height=5)
csv_llh_dms = CSVCoordinateMapping("llh", "dms", lat_deg=1,lat_min=2,lat_sec=3, lon_deg=4, lon_min=5,lon_sec=6, el_height=7)
csv_enu = CSVCoordinateMapping("enu", None, zone=1, east=2, north=3, el_height=4)

#params.validate_basic()

#out = universal_transform.universal_transform(-4130636.759, 2894953.142, -3890530.249, **params_xyz.to_kwargs())
#print(out)

#print(csv_transformation("/home/ubuntu/URFT/test_files/test_xyz.csv", csv_xyz, params_xyz))
#print(csv_transformation("/home/ubuntu/URFT/test_files/test_llh_dd.csv", csv_llh_dd, params_llh))
#print(csv_transformation("/home/ubuntu/URFT/test_files/test_llh_ddm.csv", csv_llh_ddm, params_llh))
#print(csv_transformation("/home/ubuntu/URFT/test_files/test_llh_dms.csv", csv_llh_dms, params_llh))
#print(csv_transformation("/home/ubuntu/URFT/test_files/test_enu.csv", csv_enu, params_enu))
#print(transform_vector_file("./test_files/test_point_xyz.shp", params_shp, coord_type="llh", out_crs="EPSG:4283"))