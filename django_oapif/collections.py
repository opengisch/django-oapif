from typing import Dict, Literal, NamedTuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

# ninja_ogc/routers.py
from django.contrib.gis.db.models import Extent
from django.contrib.gis.db.models.functions import AsGeoJSON, Transform
from django.contrib.gis.geos import Polygon
from django.db import models
from django.db.models.functions import Cast
from django.http import Http404, HttpRequest
from django.shortcuts import get_object_or_404
from geojson_pydantic import Feature
from ninja import Query, Router
from ninja.errors import AuthorizationError

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
    geometry_field: str
    properties_fields: list[str]


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
        srid = collection.model_class._meta.get_field(geom).srid
        crs_uri = f"http://www.opengis.net/def/crs/EPSG/0/{srid}"
        extent = collection.model_class.objects.aggregate(extent=Extent(geom))["extent"]
        response.extent = OAPIFExtent(spatial=OAPIFSpatialExtent(bbox=extent, crs=crs_uri))
        response.storageCrs = crs_uri
        response.crs = [CRS84_URI, crs_uri]
    
    return response


def perm(permission: Literal["view", "add", "delete", "edit"], collection: OAPIFCollectionEntry):
    return f"{collection.model_class._meta.app_label}.{permission}_{collection.model_class._meta.model_name}"


def create_collections_router(collections: Dict[str, OAPIFCollectionEntry]):
    router = Router()

    def get_collection_authenticated(request: HttpRequest, collection_id: str):
        collection = collections.get(collection_id)
        if collection is None:
            raise Http404(f'Collection "{collection_id}" not found.')
        if not request.user.has_perm(perm("view", collection)):
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
        bbox: str = Query(None, description="BBOX in the format: minx,miny,maxx,maxy"),
    ):
        collection = get_collection_authenticated(request, collection_id)
        
        qs = collection.model_class.objects.only("id", *collection.properties_fields)
        output_srid = get_srid_from_uri(crs)
        

        if (geom := collection.geometry_field):
            collection_srid = collection.model_class._meta.get_field(geom).srid
            if output_srid != collection_srid:
                qs = qs.annotate(geometry=Cast(AsGeoJSON(Transform(geom, output_srid)), models.JSONField()))
            else:
                qs = qs.annotate(geometry=Cast(AsGeoJSON(geom), models.JSONField()))
            if bbox:
                try:
                    minx, miny, maxx, maxy = map(float, bbox.split(","))
                    bbox_geom: Polygon = Polygon.from_bbox((minx, miny, maxx, maxy))
                    bbox_geom.srid = get_srid_from_uri(bbox_crs)
                    if bbox_geom.srid == collection_srid:
                        qs = qs.filter(**{f"{geom}__intersects": bbox_geom})
                    else:
                        qs = qs.filter(**{f"{geom}__intersects": Transform(bbox_geom, collection_srid)})
                except ValueError:
                    return router.create_response(
                        request, {"error": "Invalid bbox parameter. Expected format: minx,miny,maxx,maxy"}, status=400
                    )

        paginated_qs = qs[offset: offset + limit]

        total_count = qs.count()
        result_count = len(paginated_qs)

        return OAPIFPagedFeatureCollection(
            type="FeatureCollection",
            features=[
                Feature(
                    type="Feature",
                    id=str(obj.pk),
                    geometry=None if not collection.geometry_field else obj.geometry,
                    properties={field: getattr(obj, field) for field in collection.properties_fields}
                )
                for obj in paginated_qs
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
    
        qs = collection.model_class.objects.only(collection.properties_fields)
        output_srid = get_srid_from_uri(crs)
        if (geom := collection.geometry_field):
            collection_srid = collection.model_class._meta.get_field(geom).srid
            if output_srid != collection_srid:
                qs = qs.annotate(geometry=Cast(AsGeoJSON(Transform(geom, output_srid)), models.JSONField()))
            else:
                qs = qs.annotate(geometry=Cast(AsGeoJSON(geom), models.JSONField()))
        obj = get_object_or_404(qs, pk=item_id)
        return Feature(
            type="Feature",
            id=str(obj.pk),
            geometry=None if not collection.geometry_field else obj.geometry,
            properties={field: getattr(obj, field) for field in collection.properties_fields}
        )

    return router
