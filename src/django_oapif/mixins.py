import os

import pyproj
from django.contrib.gis.db.models import Extent
from rest_framework.response import Response

from django_oapif.urls import oapif_router

from .parsers import GeojsonParser, JSONMergePatchParser


class OAPIFDescribeModelViewSetMixin:
    """
    Adds describe endpoint used by OAPIF routers
    """

    def _describe(self, request, base_url):
        # retrieve the key under which this viewset was registered in the oapif router
        key = None
        for prefix, viewset, basename in oapif_router.registry:
            if viewset is self.__class__:
                key = prefix
                break
        else:
            raise Exception(f"Did not find {self} in {oapif_router.registry}")

        # retrieve oapif config defined on the viewset
        # distinguishing between geometric and non-geometric models
        geom_lookup = getattr(self, "oapif_geom_lookup", "geom")
        title = getattr(self, "oapif_title", f"Layer {key}")
        description = getattr(self, "oapif_description", "No description")
        meta_model = self.get_queryset().model._meta
        extents = None

        if geom_lookup:
            srid = meta_model.get_field(geom_lookup).srid
            extents = self.get_queryset().aggregate(e=Extent(geom_lookup))["e"]
        else:
            srid = os.getenv("GEOMETRY_SRID")

        if not extents:
            extents = pyproj.CRS(srid).area_of_use.bounds

        # return the oapif layer description as an object
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

    def get_parsers(self):
        # Prepends the geojson parser to the list of parsers
        return [
            JSONMergePatchParser(),
            GeojsonParser(),
            *super().get_parsers(),
        ]
