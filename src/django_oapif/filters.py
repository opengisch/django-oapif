from os import getenv

from django.contrib.gis.geos import Polygon
from pyproj import CRS, Transformer
from rest_framework.filters import BaseFilterBackend

from .crs_utils import get_crs_from_uri


# Adapted from rest_framework_gis.filters.InBBoxFilter
class BboxFilterBackend(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        bbox_string = request.query_params.get("bbox", None)
        if not bbox_string:
            return queryset

        coords = tuple(float(n) for n in bbox_string.split(","))
        user_crs = request.query_params.get("bbox-crs")

        if user_crs:
            user_crs = get_crs_from_uri(user_crs)
            api_crs = CRS.from_epsg(int(getenv("GEOMETRY_SRID", "2056")))
            transformer = Transformer.from_crs(user_crs, api_crs)
            LL = transformer.transform(coords[0], coords[1])
            UR = transformer.transform(coords[2], coords[3])
            bbox = Polygon.from_bbox([LL[0], LL[1], UR[0], UR[1]])

        else:
            bbox = Polygon.from_bbox(coords)

        return queryset.filter(geom__bboverlaps=bbox)

    def get_schema_operation_parameters(self, view):
        return [
            {
                "name": "bbox",
                "required": False,
                "in": "query",
                "description": "Specify a bounding box as filter: in_bbox=min_lon,min_lat,max_lon,max_lat",
                "schema": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 4,
                    "maxItems": 4,
                    "example": [0, 0, 10, 10],
                },
                "style": "form",
                "explode": False,
            },
        ]
