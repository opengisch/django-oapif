from functools import cached_property
from typing import Dict, Literal, NamedTuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

# ninja_ogc/routers.py
from django.contrib.gis.db.models import Extent
from django.contrib.gis.db.models.functions import AsGeoJSON, Transform
from django.contrib.gis.geos import GEOSGeometry, Polygon
from django.db import models
from django.db.models.functions import Cast
from django.http import Http404, HttpRequest
from django.shortcuts import get_object_or_404
from geojson_pydantic import Feature
from ninja import Header, Query, Router
from ninja.errors import HttpError

from django_oapif.crs import CRS84_URI, get_srid_from_uri
from django_oapif.schema import (
    OAPIFCollection,
    OAPIFCollections,
    OAPIFExtent,
    OAPIFLink,
    OAPIFPagedFeatureCollection,
    OAPIFSpatialExtent,
)


class OAPIFCollectionEntry(NamedTuple):
    model_class: models.Model
    id: str
    title: str
    description: str
    geometry_field: str | None
    properties_fields: list[str]

    @cached_property
    def srid(self):
        if not self.geometry_field:
            return None
        return self.model_class._meta.get_field(self.geometry_field).srid


def replace_query_param(request, **kwargs):
    url = request.build_absolute_uri()
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    # Update or remove parameters
    for k, v in kwargs.items():
        if v is None:
            query.pop(k)
        else:
            query[k] = [str(v)]
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def get_page_links(request: HttpRequest, limit: int, offset: int, total_count: int, returned_count: int):
    links = [
        OAPIFLink(
            rel="self",
            title="items (self)",
            type="application/geo+json",
            href=request.build_absolute_uri()
        )
    ]
    if offset > 0:
        links.append(
            OAPIFLink(
                rel="prev",
                title="items (prev)",
                type="application/geo+json",
                href=replace_query_param(request, offset= None if offset - limit <= 0 else offset - limit)
            )
        )
    if offset + limit < total_count:
        links.append(
            OAPIFLink(
                rel="next",
                title="items (next)",
                type="application/geo+json",
                href=replace_query_param(request, offset=offset + limit)
            )
        )
    return links


def get_collection_response(request: HttpRequest, collection: OAPIFCollectionEntry):
    uri_prefix = "collections/" if request.get_full_path().endswith("collections") else ""
    response = OAPIFCollection(
        id = collection.id,
        title = collection.title,
        description = collection.description,
        links = [
            OAPIFLink(
                href = request.build_absolute_uri(f"{uri_prefix}{collection.id}"),
                rel = "self",
                type = "application/json",
            ),
            OAPIFLink(
                href = request.build_absolute_uri(f"{uri_prefix}{collection.id}/items"),
                rel = "items",
                type = "application/geo+json",
            )
        ]
    )
    
    if (geom := collection.geometry_field):
        crs_uri = f"http://www.opengis.net/def/crs/EPSG/0/{collection.srid}"
        extent = collection.model_class.objects.aggregate(extent=Extent(geom))["extent"]
        response.extent = OAPIFExtent(spatial=OAPIFSpatialExtent(bbox=extent, crs=crs_uri))
        response.storageCrs = crs_uri
        response.crs = [CRS84_URI, crs_uri]
    
    return response

def to_feature(collection: OAPIFCollectionEntry, obj):
    return Feature(
        type="Feature",
        id=str(obj.pk),
        geometry=getattr(obj, "_oapif_geometry", None),
        properties={field: getattr(obj, field) for field in collection.properties_fields}
    )

def operation_for_method(http_method: str):
    match http_method:
        case "GET": return "view"
        case "POST": return "create"
        case "PUT" | "PATCH": return "change"
        case "POST": return "add"


def perm(permission: Literal["view", "add", "delete", "edit"], collection: OAPIFCollectionEntry):
    return f"{collection.model_class._meta.app_label}.{permission}_{collection.model_class._meta.model_name}"


def query_collection(collection: OAPIFCollectionEntry, crs: str, bbox: str | None = None, bbox_crs: str | None = None):
    output_srid = get_srid_from_uri(crs)
    qs = collection.model_class.objects.only("id", *collection.properties_fields)
    if (geom_field := collection.geometry_field):
        if output_srid != collection.srid:
            qs = qs.annotate(_oapif_geometry=Cast(AsGeoJSON(Transform(geom_field, output_srid)), models.JSONField()))
        else:
            qs = qs.annotate(_oapif_geometry=Cast(AsGeoJSON(geom_field), models.JSONField()))
        if bbox:
            try:
                minx, miny, maxx, maxy = map(float, bbox.split(","))
                bbox_geom: Polygon = Polygon.from_bbox((minx, miny, maxx, maxy))
                bbox_geom.srid = get_srid_from_uri(bbox_crs)
                if bbox_geom.srid == collection.srid:
                    qs = qs.filter(**{f"{geom_field}__intersects": bbox_geom})
                else:
                    qs = qs.filter(**{f"{geom_field}__intersects": Transform(bbox_geom, collection.srid)})
            except ValueError:
                return HttpError(
                    400, "Invalid bbox parameter. Expected format: minx,miny,maxx,maxy"
                )
    return qs


def create_collections_router(collections: Dict[str, OAPIFCollectionEntry]):
    router = Router()

    def get_collection_authenticated(request: HttpRequest, collection_id: str):
        collection = collections.get(collection_id)
        if collection is None:
            raise Http404(f'Collection "{collection_id}" not found.')
        operation = operation_for_method(request.method)
        if not request.user.has_perm(perm(operation, collection)):
            raise AuthorizationError()
        return collection


    @router.get("")
    def list_collections(request: HttpRequest):
        return OAPIFCollections(
            links=[
                OAPIFLink(
                    href = request.build_absolute_uri(),
                    rel = "self",
                    type = "application/json",
                    title = "this document",
                )
            ],
            collections=[
                get_collection_response(request, collection)
                for collection in collections.values()
                if request.user.has_perm(perm("view", collection))
            ]
        )

    @router.get("/{collection_id}")
    def get_collection(request, collection_id: str):
        collection = get_collection_authenticated(request, collection_id)
        return get_collection_response(request, collection)
    
    @router.get("/{collection_id}/items")
    def get_items(
        request: HttpRequest,
        collection_id: str,
        limit: int = 1000,
        offset: int = 0,
        crs: str = CRS84_URI,
        bbox_crs: str = Query(CRS84_URI, alias="bbox-crs"),
        bbox: str | None = Query(None, description="BBOX in the format: minx,miny,maxx,maxy"),
    ):
        collection = get_collection_authenticated(request, collection_id)
        query = query_collection(collection, crs, bbox, bbox_crs)
        paginated_query = query[offset: offset + limit]

        total_count = query.count()
        result_count = len(paginated_query)

        return OAPIFPagedFeatureCollection(
            type="FeatureCollection",
            features=[
                to_feature(collection, obj)
                for obj in paginated_query
            ],
            numberMatched=total_count,
            numberReturned=result_count,
            links=get_page_links(request, limit, offset, total_count, result_count)
        )

    @router.get("/{collection_id}/items/{item_id}")
    def get_item(
        request: HttpRequest,
        collection_id: str,
        item_id: str,
        crs: str = CRS84_URI,
    ):
        collection = get_collection_authenticated(request, collection_id)
    
        query = query_collection(collection, crs)
        item = get_object_or_404(query, pk=item_id)
        return to_feature(collection, item)

    @router.post("/{collection_id}/items")
    def create_item(
        request: HttpRequest,
        collection_id: str,
        feature: Feature,
        crs: str | None = Header(alias="Content-Crs", default=CRS84_URI),
    ):
        collection = get_collection_authenticated(request, collection_id)
        input = feature.properties or {}
        if (geom_field := collection.geometry_field) and feature.geometry:
            geometry = GEOSGeometry(feature.geometry.model_dump_json())
            geometry.srid = get_srid_from_uri(crs)
            input[geom_field] = geometry
        item = collection.model_class.objects.create(**input)
        item.save()
        item = query_collection(collection, CRS84_URI).get(pk=item.pk)
        return to_feature(collection, item)
    
    @router.patch("/{collection_id}/items/{item_id}")
    def update_item(
        request: HttpRequest,
        collection_id: str,
        item_id: str,
        feature: Feature,
        crs: str | None = Header(alias="Content-Crs", default=CRS84_URI),
    ):
        collection = get_collection_authenticated(request, collection_id)
        item = get_object_or_404(collection.model_class, pk=item_id)
        for property, value in (feature.properties or {}).items():
            setattr(item, property, value)
        if (geom_field := collection.geometry_field) and feature.geometry:
            geometry = GEOSGeometry(feature.geometry.model_dump_json())
            geometry.srid = get_srid_from_uri(crs)
            setattr(item, geom_field, geometry)
        item.save()
        item = query_collection(collection, CRS84_URI).get(pk=item_id)
        return to_feature(collection, item)
    
    @router.put("/{collection_id}/items/{item_id}")
    def replace_item(
        request: HttpRequest,
        collection_id: str,
        item_id: str,
        feature: Feature,
        crs: str | None = Header(alias="Content-Crs", default=CRS84_URI),
    ):
        collection = get_collection_authenticated(request, collection_id)
        item = get_object_or_404(collection.model_class, pk=item_id)
        input = feature.properties or {}
        for field in collection.properties_fields:
            setattr(item, field, input.get(field))
        if (geom_field := collection.geometry_field) and feature.geometry:
            geometry = GEOSGeometry(feature.geometry.model_dump_json())
            geometry.srid = get_srid_from_uri(crs)
            input[geom_field] = geometry
        item.save()
        item = query_collection(collection, CRS84_URI).get(pk=item_id)
        return to_feature(collection, item)
    
    @router.delete("/{collection_id}/items/{item_id}")
    def delete_item(
        request: HttpRequest,
        collection_id: str,
        item_id: str,
    ):
        collection = get_collection_authenticated(request, collection_id)
        obj = get_object_or_404(collection.model_class, pk=item_id)
        obj.delete()
        
        
    return router
