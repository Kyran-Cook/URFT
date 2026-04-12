from __future__ import annotations
import os

import unniversal_transform

from dataclasses import dataclass, field
from typing import Literal, Optional, Union
import datetime as dt

import numpy as np

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
    # Decimal degrees
    lat: Optional[Column] = None
    lon: Optional[Column] = None

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
    height: Optional[Column] = None
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
            if None in (self.lat, self.lon):
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
        if None in (self.east, self.north, self.height, self.zone):
            raise ValueError(
                "ENU mapping requires east, north, height, and zone columns"
            )


def csv_transformation(file_path, csv_params, transform_params):
    # Placeholder for CSV transformation logic
    print(f"Transforming CSV file at {file_path} with params: {transform_params}")
    # Here you would read the CSV, apply transformations, and write the output
    pass


def file_transformation(file_type, file_path, transform_params):

    if file_type == "csv":
        csv_transformation(file_path, transform_params)

    pass




params = TransformParams("ITRF2014", "GDA94", dt.date(2014,1,1), plate_motion="aus", return_type="xyz")

params.validate_basic()

out = unniversal_transform.universal_transform(-4130636.759, 2894953.142, -3890530.249, **params.to_kwargs())
print(out)