from __future__ import annotations

import universal_transform

from dataclasses import dataclass
from typing import Optional, Union
import datetime as dt

import numpy as np
import pandas as pd
import numpy as np
from pathlib import Path

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
    angle_return_type: Optional[str] = None  # "dd" | "ddm" | "dms" (LLH output only)

    ignore_errors: bool = False
    verbose: bool = False

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
            verbose=self.verbose
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
    try:
        input_path = Path(file_path.name)
    except:
        input_path = Path(file_path)
    output_path = input_path.with_stem(input_path.stem + "_transformed")
    df.to_csv(output_path, index=False)

    print(f"Transformed {len(df)} rows to: {output_path}")
    return str(output_path)

params_xyz = TransformParams("ITRF2014", "MGA94", dt.date(2014,1,1), plate_motion="aus", return_type="enu")
params_llh = TransformParams("ITRF2014", "GDA94", dt.date(2014,1,1), plate_motion="aus", return_type="xyz")
params_enu = TransformParams("MGA94", "MGA2020", dt.date(2014,1,1), plate_motion="aus", return_type="enu")
params_shp = TransformParams("ITRF2014", "GDA94", dt.date(2014,1,1), plate_motion="aus", ignore_errors=False)

csv_xyz = CSVCoordinateMapping("xyz", None, 1, 2, 3)
csv_llh_dd = CSVCoordinateMapping("llh", "dd", lat_deg=1,lon_deg=2,el_height=3)
csv_llh_ddm = CSVCoordinateMapping("llh", "ddm", lat_deg=1,lat_min=2, lon_deg=3, lon_min=4, el_height=5)
csv_llh_dms = CSVCoordinateMapping("llh", "dms", lat_deg=1,lat_min=2,lat_sec=3, lon_deg=4, lon_min=5,lon_sec=6, el_height=7)
csv_enu = CSVCoordinateMapping("enu", None, zone=4, east=1, north=2, el_height=3)

#print(csv_transformation("/home/ubuntu/tests/Points_260412_1000pts.csv", csv_enu, params_enu))
#print(csv_transformation("/home/ubuntu/URFT/test_files/test_llh_dd.csv", csv_llh_dd, params_llh))
#print(csv_transformation("/home/ubuntu/URFT/test_files/test_llh_ddm.csv", csv_llh_ddm, params_llh))
#print(csv_transformation("/home/ubuntu/URFT/test_files/test_llh_dms.csv", csv_llh_dms, params_llh))
#print(csv_transformation("/home/ubuntu/URFT/test_files/test_enu.csv", csv_enu, params_enu))