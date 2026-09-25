import re
from dataclasses import dataclass
from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import PydanticCustomError, core_schema

CRS84_SRID = 4326
CRS84_URI = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"

# taken from https://github.com/geopython/pygeoapi/blob/953b6fa74d2ce292d8f566c4f4d3bcb4161d6e95/pygeoapi/util.py#L90
CRS_URI_PATTERN = re.compile(r"^http://www.opengis\.net/def/crs/(?P<auth>EPSG|OGC)/[\d|\.]+?/(?P<code>\w+?)$")


class CRS:
    def __init__(self, auth: str, srid: int) -> None:
        self.auth = auth
        self.srid = srid

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CRS):
            return NotImplemented
        return (self.auth, self.srid) == (other.auth, other.srid)

    def __repr__(self) -> str:
        return f"CRS(auth={self.auth!r}, srid={self.srid!r})"

    @classmethod
    def __get_pydantic_core_schema__(cls, _source: Any, _handler: GetCoreSchemaHandler):

        def validate_crs(uri: str):
            # a Content-Crs header has the URI in angle brackets, as the responses send it, and so may the
            # clients that write back what they read
            if uri.startswith("<") and uri.endswith(">"):
                uri = uri[1:-1]
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
            serialization=core_schema.plain_serializer_function_ser_schema(cls.uri),
        )

    def uri(self) -> str:
        if self.auth == "OGC" and self.srid == CRS84_SRID:
            return CRS84_URI
        return f"http://www.opengis.net/def/crs/EPSG/0/{self.srid}"

    def uri_header(self) -> str:
        return f"<{self.uri()}>"

    def auth_code(self) -> str:
        """Authority code, as GeoArrow expects it in the CRS metadata of a geometry column."""
        if self.auth == "OGC" and self.srid == CRS84_SRID:
            return "OGC:CRS84"
        return f"EPSG:{self.srid}"


@dataclass
class BBox:
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @classmethod
    def __get_pydantic_core_schema__(cls, _source: Any, _handler: GetCoreSchemaHandler):

        def validate_bbox(value: str):
            try:
                xmin, ymin, xmax, ymax = map(float, value.split(","))
                return cls(xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)
            except (ValueError, TypeError):
                raise PydanticCustomError("bbox_format", "Invalid BBOX. Expected format: xmin,ymin,xmax,ymax")

        return core_schema.no_info_after_validator_function(
            validate_bbox,
            core_schema.str_schema(),
        )
