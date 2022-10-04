from django.contrib.gis.db.models import Extent
from rest_framework.response import Response

from django_wfs3.urls import wfs3_router


class WFS3DescribeModelViewSetMixin:
    """
    Adds describe endpoint used by WFS3 routers
    """

    def _describe(self, request, base_url):
        # retrieve the key under which this viewset was registered in the wfs3 router
        key = None
        for prefix, viewset, basename in wfs3_router.registry:
            if viewset is self.__class__:
                key = prefix
                break
        else:
            raise Exception(f"Did not find {self} in {wfs3_router.registry}")

        # retrieve wfs3 config defined on the viewset
        title = getattr(self, "wfs3_title", f"Layer {key}")
        description = getattr(self, "wfs3_description", "No description")
        srid = getattr(self, "wfs3_srid", 4326)
        extents = self.get_queryset().aggregate(e=Extent(self.wfs3_geom_lookup))["e"]

        # return the wfs3 layer description as an object
        return {
            "id": key,
            "title": title,
            "description": description,
            "extent": {
                "spatial": {
                    "bbox": [extents],
                    "crs": f"http://www.opengis.net/def/crs/EPSG/0/{srid}",  # seems this isn't recognized by QGIS ?
                },
            },
            "crs": [
                f"http://www.opengis.net/def/crs/EPSG/0/{srid}",  # seems this isn't recognized by QGIS ?
            ],
            "links": [
                {
                    "href": request.build_absolute_uri(f"{base_url}{key}"),
                    "rel": "self",
                    "type": "application/geo+json",
                    "title": "This document as JSON",
                },
                {
                    "href": request.build_absolute_uri(f"{base_url}{key}/items"),
                    "rel": "items",
                    "type": "application/geo+json",
                    "title": key,
                },
            ],
        }

    def describe(self, request, *args, **kwargs):
        """Implementation of the `describe` endpoint"""
        return Response(self._describe(request, base_url=""))
