from django.contrib.gis.geos import Polygon
from rest_framework.filters import BaseFilterBackend


# Adapted from rest_framework_gis.filters.InBBoxFilter
class BboxFilterBackend(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        bbox_string = request.query_params.get("bbox", None)
        if not bbox_string:
            return queryset

        p1x, p1y, p2x, p2y = (float(n) for n in bbox_string.split(","))
        # TODO: take into account bbox-crs which may differ from the geom
        bbox = Polygon.from_bbox((p1x, p1y, p2x, p2y))
        # TODO: geom shouldn't be hardcoded here
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
