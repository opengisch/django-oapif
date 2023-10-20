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
            api_crs = CRS.from_epsg(queryset.model.crs)  # TODO support CRS84, not only EPSG codes
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
                    # maxItems should be 4, no idea why conformance wants 6 here
                    # https://github.com/opengeospatial/ets-ogcapi-features10/blob/c557c227729715836cb32925b6a7bd67d1ae213f/src/main/java/org/opengis/cite/ogcapifeatures10/conformance/core/collections/FeaturesBBox.java#L123C20-L125C44
                    "maxItems": 6,
                    "example": [0, 0, 10, 10],
                },
                "style": "form",
                "explode": False,
            },
        ]
