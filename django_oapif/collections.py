from typing import Dict, NamedTuple

# ninja_ogc/routers.py
from uuid import UUID

from django.contrib.gis.db.models import Extent
from django.contrib.gis.db.models.functions import AsGeoJSON
from django.contrib.gis.geos import Polygon
from django.db import models
from django.db.models.functions import Cast
from django.http import Http404, HttpRequest
from django.shortcuts import get_object_or_404
from geojson_pydantic import Feature, FeatureCollection
from ninja import Query, Router

from django_oapif.schema import (
    OAPIFCollection,
    OAPIFCollections,
    OAPIFExtent,
    OAPIFLink,
    OAPIFSpatialExtent,
)


class OAPIFCollectionEntry(NamedTuple):
    model_class: models.Model
    id: str
    title: str
    description: str
    geometry_field: str = "geom"
    properties_fields: list[str] = []


def get_collection_crs(collection: OAPIFCollectionEntry):
    if (geom := collection.geometry_field):
        srid = collection.model_class._meta.get_field(geom).srid
        if srid not in (0, None):
            return [f"http://www.opengis.net/def/crs/EPSG/0/{srid}"]


def get_collection_extent(collection: OAPIFCollectionEntry):
    if (geom := collection.geometry_field):
        extent = collection.model_class.objects.aggregate(extent=Extent(geom))["extent"]
        return OAPIFExtent(
            spatial=OAPIFSpatialExtent(bbox=extent)
        )


def create_collections_router(collections: Dict[str, OAPIFCollectionEntry]):
    router = Router()

    @router.get("")
    def list_collections(request: HttpRequest):
        return OAPIFCollections(
            links=[
                OAPIFLink(
                    href = request.build_absolute_uri(""),
                    rel = "self",
                    type = "application/json",
                    title = "this document",
                )
            ],
            collections=[
                OAPIFCollection(
                    id = collection.id,
                    title = collection.title,
                    description = collection.description,
                    crs = get_collection_crs(collection),
                    extent = get_collection_extent(collection),
                    links = [
                        OAPIFLink(
                            href = request.build_absolute_uri(f"collections/{collection.id}"),
                            rel = "self",
                            type = "application/json",
                        ),
                        OAPIFLink(
                            href = request.build_absolute_uri(f"collections/{collection.id}/items"),
                            rel = "items",
                            type = "application/geo+json",
                        )
                    ]
                )
                for collection in collections.values()
            ]
        )

    @router.get("/{collection_id}")
    def get_collection(request, collection_id: str):
        collection = collections.get(collection_id)
        if collection is None:
            raise Http404(f'Collection "{collection_id}" not found.')
        return OAPIFCollection(
            id=collection.id,
            title=collection.title,
            description=collection.description,
            crs = get_collection_crs(collection),
            extent = get_collection_extent(collection),
            links=[
                OAPIFLink(
                    href = request.build_absolute_uri(f"{collection_id}"),
                    rel = "self",
                    type = "application/json"
                ),
                OAPIFLink(
                    href = request.build_absolute_uri(f"{collection_id}/items"),
                    rel = "items",
                    type = "application/geo+json"
                )
            ],
        )
    
    @router.get("/{collection_id}/items")
    def get_items(request, collection_id: str, limit: int | None = None, offset: int | None = None, bbox: str = Query(None, description="BBOX in the format: minx,miny,maxx,maxy")):
        collection = collections.get(collection_id)
        if collection is None:
            raise Http404(f'Collection "{collection_id}" not found.')
        qs = collection.model_class.objects.only("id", *collection.properties_fields)
        if (geom := collection.geometry_field):
            qs = qs.annotate(geometry=Cast(AsGeoJSON(geom, False, False), models.JSONField()))
            if bbox:
                try:
                    minx, miny, maxx, maxy = map(float, bbox.split(","))
                    bbox_geom = Polygon.from_bbox((minx, miny, maxx, maxy))
                    qs = qs.filter(**{f"{geom}__intersects": bbox_geom})
                except ValueError:
                    return router.create_response(
                        request, {"error": "Invalid bbox parameter. Expected format: minx,miny,maxx,maxy"}, status=400
                    )
        if limit is not None:
            qs = qs[offset:limit]
        return FeatureCollection(
            type="FeatureCollection",
            features=[
                Feature(
                    type="Feature",
                    id=str(obj.id),
                    geometry=None if not collection.geometry_field else obj.geometry,
                    properties={field: getattr(obj, field) for field in collection.properties_fields}
                )
                for obj in qs
            ],
        )

    @router.get("/{collection_id}/items/{item_id}")
    def get_item(request, collection_id: str, item_id: UUID):
        collection = collections.get(collection_id)
        if collection is None:
            raise Http404(f'Collection "{collection_id}" not found.')
        qs = collection.model_class.objects.only(collection.properties_fields)
        if collection.geometry_field:
            qs = qs.annotate(geometry=Cast(AsGeoJSON(collection.geometry_field, False, False), models.JSONField()))
        obj = get_object_or_404(qs, pk=item_id)
        return Feature(
            type="Feature",
            id=str(obj.id),
            geometry=None if not collection.geometry_field else obj.geometry,
            properties={field: getattr(obj, field) for field in collection.properties_fields}
        )

    return router
