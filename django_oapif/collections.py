from typing import Any

from django.contrib.gis.db.models import Extent
from django.contrib.gis.geos import GEOSGeometry
from django.db.models import Model
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from ninja import Header, Query, Router
from ninja.errors import AuthorizationError, HttpError, ValidationError

from django_oapif.crs import CRS, CRS84_SRID, CRS84_URI, BBox
from django_oapif.geojson import (
    GenericFeature,
    GenericFeatureCollection,
    GenericFeaturePatch,
)
from django_oapif.handler import OapifCollection
from django_oapif.schema import (
    OAPIFCollection,
    OAPIFCollections,
    OAPIFExtent,
    OAPIFLink,
    OAPIFSpatialExtent,
)
from django_oapif.utils import replace_query_param


def get_page_links(request: HttpRequest, limit: int, offset: int, total_count: int) -> list[OAPIFLink]:
    links = [
        OAPIFLink(
            rel="self",
            title="items (self)",
            type="application/geo+json",
            href=request.build_absolute_uri(),
        )
    ]
    if offset > 0:
        links.append(
            OAPIFLink(
                rel="prev",
                title="items (prev)",
                type="application/geo+json",
                href=replace_query_param(request, offset=None if offset - limit <= 0 else offset - limit),
            )
        )
    if offset + limit < total_count:
        links.append(
            OAPIFLink(
                rel="next",
                title="items (next)",
                type="application/geo+json",
                href=replace_query_param(request, offset=offset + limit),
            )
        )
    return links


def get_related_object_or_raise(field: str, value: Any, related_model: type[Model]):
    try:
        return related_model.objects.get(pk=value)
    except related_model.DoesNotExist:
        raise ValidationError([
            {
                "loc": ["body", "feature", "properties", field],
                "msg": "Foreign key not found",
                "type": "value_error",
            },
        ])


def get_collection_response(request: HttpRequest, collection: OapifCollection):
    uri_prefix = "collections/" if request.get_full_path().endswith("collections") else ""
    response = OAPIFCollection(
        id=collection.id,
        title=collection.title,
        description=collection.description,
        itemType="feature",
        links=[
            OAPIFLink(
                rel="self",
                title="Collection",
                type="application/json",
                href=request.build_absolute_uri(f"{uri_prefix}{collection.id}"),
            ),
            OAPIFLink(
                rel="http://www.opengis.net/def/rel/ogc/1.0/schema",
                title="Collection schema",
                type="application/json",
                href=request.build_absolute_uri(f"{uri_prefix}{collection.id}/schema"),
            ),
            OAPIFLink(
                rel="items",
                title="Collection items",
                type="application/geo+json",
                href=request.build_absolute_uri(f"{uri_prefix}{collection.id}/items"),
            ),
        ],
    )

    if geom := collection.geometry_field:
        if collection.srid == CRS84_SRID:
            response.storageCrs = CRS84_URI
            response.crs = [CRS84_URI]
        else:
            crs_uri = f"http://www.opengis.net/def/crs/EPSG/0/{collection.srid}"
            response.storageCrs = crs_uri
            response.crs = [CRS84_URI, crs_uri]
        if extent := collection.model.objects.aggregate(extent=Extent(geom))["extent"]:
            response.extent = OAPIFExtent(spatial=OAPIFSpatialExtent(bbox=[extent], crs=response.storageCrs))

    return response


def create_collections_router(collections: dict[str, OapifCollection]):
    router = Router()

    def get_collection_by_id(collection_id: str, request: HttpRequest):
        collection = collections.get(collection_id)
        if collection is None:
            raise HttpError(404, "Collection not found")
        if not collection.has_view_permission(request):
            raise AuthorizationError()
        return collection

    @router.get("", response=OAPIFCollections, operation_id="get_collections")
    def list_collections(request: HttpRequest):
        return OAPIFCollections(
            links=[
                OAPIFLink(
                    href=request.build_absolute_uri(),
                    rel="self",
                    type="application/json",
                    title="this document",
                )
            ],
            collections=[
                get_collection_response(request, collection)
                for collection in collections.values()
                if collection.has_view_permission(request)
            ],
        )

    @router.get(
        "/{collection_id}",
        response=OAPIFCollection,
        operation_id="get_collection",
    )
    def get_collection(request, collection_id: str):
        collection = get_collection_by_id(collection_id, request)
        return get_collection_response(request, collection)

    @router.get(
        "/{collection_id}/schema",
        operation_id="get_collection_schema",
    )
    def get_schema(request: HttpRequest, collection_id: str):
        collection = get_collection_by_id(collection_id, request)
        schema = collection.get_json_schema(request)
        schema["$id"] = request.build_absolute_uri()
        return schema

    @router.get(
        "/{collection_id}/items",
        operation_id="get_collection_items",
        response=GenericFeatureCollection,
    )
    def get_items(
        request: HttpRequest,
        collection_id: str,
        limit: int = 100,
        offset: int = 0,
        crs: CRS = CRS("OGC", CRS84_SRID),
        bbox_crs: CRS = Query(CRS("OGC", CRS84_SRID), alias="bbox-crs"),
        bbox: BBox | None = Query(None, alias="bbox", description="BBOX in the format: minx,miny,maxx,maxy"),
    ):
        collection = get_collection_by_id(collection_id, request)

        query = collection.query(request, crs, bbox, bbox_crs)
        paginated_query = query[offset : offset + limit]

        total_count = query.count()

        feature_collection = collection.queryset_to_featurecollection(request, paginated_query)
        feature_collection.numberMatched = total_count
        feature_collection.links = get_page_links(request, limit, offset, total_count)
        return feature_collection

    @router.api_operation(
        ["OPTIONS"],
        "/{collection_id}/items",
        operation_id="get_collection_items_rights",
    )
    def options_items(
        request: HttpRequest,
        collection_id: str,
        response: HttpResponse,
    ):
        collection = get_collection_by_id(collection_id, request)
        allowed = ["OPTIONS"]
        allowed.append("GET")
        if collection.has_add_permission(request):
            allowed.append("POST")
        response.headers["Allow"] = ", ".join(allowed)  # type: ignore

    @router.get(
        "/{collection_id}/items/{item_id}",
        operation_id="get_collection_item",
        response=GenericFeature,
    )
    def get_item(
        request: HttpRequest,
        collection_id: str,
        item_id: str,
        crs: CRS = CRS("OGC", CRS84_SRID),
    ):
        collection = get_collection_by_id(collection_id, request)
        query = collection.query(request, crs)
        item = get_object_or_404(query, pk=item_id)
        if not collection.has_view_permission(request, item):
            raise AuthorizationError()
        return collection.model_to_feature(request, item)

    @router.post(
        "/{collection_id}/items",
        response={201: GenericFeature},
        operation_id="create_collection_item",
    )
    def create_item(
        request: HttpRequest,
        response: HttpResponse,
        collection_id: str,
        feature: GenericFeature,
        crs: CRS = Header(CRS("OGC", CRS84_SRID), alias="Content-Crs"),
    ):
        collection = get_collection_by_id(collection_id, request)
        feature = collection.validate_feature_input_or_raise(request, feature)
        item_properties = feature.properties.model_dump() or {}
        if (geom_field := collection.geometry_field) and feature.geometry:
            geometry = GEOSGeometry(feature.geometry.model_dump_json())
            geometry.srid = crs.srid
            item_properties[geom_field] = geometry
        for field, value in feature.properties.model_dump().items():
            if value is not None and (related_model := collection.foreign_key_fields.get(field)):
                item_properties[field] = get_related_object_or_raise(field, value, related_model)

        item = collection.model(**item_properties)
        if not collection.has_add_permission(request, item):
            raise AuthorizationError()
        collection.save_model(request, item, False)
        item = collection.query(request, CRS("OGC", CRS84_SRID)).get(pk=item.pk)
        response.headers["Location"] = request.build_absolute_uri(f"items/{item.pk}")  # type: ignore
        return 201, collection.model_to_feature(request, item)

    @router.api_operation(
        ["OPTIONS"],
        "/{collection_id}/items/{item_id}",
        operation_id="create_collection_item_rights",
    )
    def options_item(
        request: HttpRequest,
        response: HttpResponse,
        collection_id: str,
        item_id: str,
    ):
        collection = get_collection_by_id(collection_id, request)
        query = collection.get_queryset(request)
        item = get_object_or_404(query, pk=item_id)
        allowed = ["OPTIONS"]
        if collection.has_view_permission(request, item):
            allowed.append("GET")
        if collection.has_change_permission(request, item):
            allowed.append("PUT")
            allowed.append("PATCH")
        if collection.has_delete_permission(request, item):
            allowed.append("DELETE")
        response.headers["Allow"] = ", ".join(allowed)  # type: ignore

    @router.put(
        "/{collection_id}/items/{item_id}",
        operation_id="replace_collection_item",
        response=GenericFeature,
    )
    def replace_item(
        request: HttpRequest,
        collection_id: str,
        item_id: str,
        feature: GenericFeature,
        crs: CRS = Header(CRS("OGC", CRS84_SRID), alias="Content-Crs"),
    ):
        collection = get_collection_by_id(collection_id, request)
        query = collection.get_queryset(request)
        item = get_object_or_404(query, pk=item_id)
        if not collection.has_change_permission(request, item):
            raise AuthorizationError()
        feature = collection.validate_feature_input_or_raise(request, feature)
        for field, value in feature.properties.model_dump().items():
            if value is not None and (related_model := collection.foreign_key_fields.get(field)):
                value = get_related_object_or_raise(field, value, related_model)
            setattr(item, field, value)
        if geom_field := collection.geometry_field:
            if feature.geometry:
                geometry = GEOSGeometry(feature.geometry.model_dump_json())
                geometry.srid = crs.srid
            else:
                geometry = None
            setattr(item, geom_field, geometry)
        collection.save_model(request, item, True)
        item = collection.query(request, CRS("OGC", CRS84_SRID)).get(pk=item_id)
        return collection.model_to_feature(request, item)

    @router.patch(
        "/{collection_id}/items/{item_id}",
        operation_id="update_collection_item",
        response=GenericFeature,
    )
    def update_item(
        request: HttpRequest,
        collection_id: str,
        item_id: str,
        feature: GenericFeaturePatch,
        crs: CRS = Header(CRS("OGC", CRS84_SRID), alias="Content-Crs"),
    ):
        collection = get_collection_by_id(collection_id, request)
        query = collection.get_queryset(request)
        item = get_object_or_404(query, pk=item_id)
        if not collection.has_change_permission(request, item):
            raise AuthorizationError()
        feature = collection.validate_feature_patch_or_raise(request, feature)
        if feature.properties is not None:
            for field, value in feature.properties.model_dump(exclude_unset=True).items():
                if value is not None and (related_model := collection.foreign_key_fields.get(field)):
                    value = get_related_object_or_raise(field, value, related_model)
                setattr(item, field, value)
        if (geom_field := collection.geometry_field) and "geometry" in feature.model_fields_set:
            if feature.geometry:
                geometry = GEOSGeometry(feature.geometry.model_dump_json())
                geometry.srid = crs.srid
            else:
                geometry = None
            setattr(item, geom_field, geometry)
        collection.save_model(request, item, True)
        item = collection.query(request, CRS("OGC", CRS84_SRID)).get(pk=item_id)
        return collection.model_to_feature(request, item)

    @router.delete("/{collection_id}/items/{item_id}", operation_id="delete_collection_item")
    def delete_item(
        request: HttpRequest,
        collection_id: str,
        item_id: str,
    ):
        collection = get_collection_by_id(collection_id, request)
        query = collection.get_queryset(request)
        item = get_object_or_404(query, pk=item_id)
        if not collection.has_view_permission(request, item):
            raise AuthorizationError()
        collection.delete_model(request, item)

    return router
