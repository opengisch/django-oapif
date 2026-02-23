import re
from dataclasses import dataclass
from typing import Any

from pydantic import GetCoreSchemaHandler, ValidationInfo
from pydantic_core import PydanticCustomError, core_schema

# taken from https://github.com/geopython/pygeoapi/blob/953b6fa74d2ce292d8f566c4f4d3bcb4161d6e95/pygeoapi/util.py#L90

CRS84_SRID = 4979
CRS84_URI = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"

CRS_URI_PATTERN = re.compile(r"^http://www.opengis\.net/def/crs/(?P<auth>EPSG|OGC)/[\d|\.]+?/(?P<code>\w+?)$")


@dataclass
class CRS:
    auth: str
    srid: int

    @classmethod
    def __get_pydantic_core_schema__(cls, _source: Any, _handler: GetCoreSchemaHandler):

        def validate_crs(uri: str):
            if result := CRS_URI_PATTERN.match(uri):
                auth, code = result.groups()
                if auth == "OGC" and code in ("CRS84", "CRS84h"):
                    return cls(auth=auth, srid=CRS84_SRID)
                if auth == "EPSG" and code.isnumeric():
                    return cls(auth=auth, srid=int(code))
            raise PydanticCustomError(
                "crs_format",
                "CRS could not be identified from URI. CRS URIs must follow the format "
                "'http://www.opengis.net/def/crs/{authority}/{version}/{code}'",
            )

        return core_schema.no_info_after_validator_function(
            validate_crs,
            core_schema.str_schema(),
        )


@dataclass
class BBox:
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @classmethod
    def __get_pydantic_core_schema__(cls, _source: Any, _handler: GetCoreSchemaHandler):

        def validate_bbox(value: str, info: ValidationInfo):
            try:
                xmin, ymin, xmax, ymax = map(float, value.split(","))
                return cls(xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)
            except Exception:
                raise PydanticCustomError("bbox_format", "Invalid BBOX. Expected format: xmin,ymin,xmax,ymax")

        return core_schema.with_info_after_validator_function(
            validate_bbox,
            core_schema.str_schema(),
        )
