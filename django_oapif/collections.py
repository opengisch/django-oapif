from typing import Any

from functools import cache

from django.contrib.gis.db.models import Extent
from django.contrib.gis.geos import GEOSException, GEOSGeometry
from django.contrib.gis.geos.libgeos import geos_version_tuple
from django.db.models import Model
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from ninja import Header, Query, Router, Schema
from ninja.errors import AuthorizationError, HttpError, ValidationError

from django_oapif import jsonfg
from django_oapif.crs import CRS, CRS84_SRID, CRS84_URI, BBox
from django_oapif.geojson import (
    CircularStringParts,
    GenericFeature,
    GenericFeatureCollection,
    GenericFeaturePatch,
)
from django_oapif.handler import ARROW_AVAILABLE, OapifCollection, ReprojectedExtent, parse_box2d
from django_oapif.schema import (
    OAPIFCollection,
    OAPIFCollections,
    OAPIFExtent,
    OAPIFLink,
    OAPIFSpatialExtent,
)
from django_oapif.utils import replace_query_param

ARROW_STREAM_MEDIA_TYPE = "application/vnd.apache.arrow.stream"
GEOJSON_MEDIA_TYPE = "application/geo+json"
JSON_MEDIA_TYPE = "application/json"

ACCEPTED_TYPES = [
    JSON_MEDIA_TYPE,
    GEOJSON_MEDIA_TYPE,
    ARROW_STREAM_MEDIA_TYPE,
]

DEFAULT_CRS = CRS("OGC", CRS84_SRID)


def get_page_links(
    request: HttpRequest,
    limit: int,
    offset: int,
    total_count: int,
    media_type: str = GEOJSON_MEDIA_TYPE,
) -> list[OAPIFLink]:
    links = [
        OAPIFLink(
            rel="self",
            title="items (self)",
            type=media_type,
            href=request.build_absolute_uri(),
        )
    ]
    if offset > 0:
        links.append(
            OAPIFLink(
                rel="prev",
                title="items (prev)",
                type=media_type,
                href=replace_query_param(request, offset=None if offset - limit <= 0 else offset - limit),
            )
        )
    if offset + limit < total_count:
        links.append(
            OAPIFLink(
                rel="next",
                title="items (next)",
                type=media_type,
                href=replace_query_param(request, offset=offset + limit),
            )
        )
    return links


def geojson_response(geojson: Schema, crs: CRS) -> HttpResponse:
    """
    Serialized by pydantic: returned as they are, ninja would validate the features all over again, and
    render them with json.dumps, which takes ten times as long.
    """
    response = HttpResponse(geojson.model_dump_json(), content_type=GEOJSON_MEDIA_TYPE)
    response["Content-Crs"] = crs.uri_header()
    return response


def link_header(links: list[OAPIFLink]) -> str:
    """Serialize links as a RFC 8288 Link header, for responses that cannot carry them in the payload."""
    return ", ".join(f'<{link.href}>; rel="{link.rel}"; type="{link.type}"' for link in links)


def accepts_geoarrow(request: HttpRequest) -> bool:
    if request.get_preferred_type(ACCEPTED_TYPES) == ARROW_STREAM_MEDIA_TYPE:
        if ARROW_AVAILABLE:
            return True
        raise HttpError(406, "Arrow content type not supported")
    return False


def validate_crs_or_raise(collection: OapifCollection, crs: CRS, parameter: str) -> None:
    """Reject a CRS the collection does not advertise, as the coordinates could not be trusted."""
    supported = collection.supported_crs()
    if not supported or crs in supported:
        return
    raise HttpError(
        400,
        f"Unsupported {parameter} '{crs.uri()}'. Supported: {', '.join(c.uri() for c in supported)}",
    )


def get_item_or_404(collection: OapifCollection, request: HttpRequest, item_id: str):
    """Fetch an item to act on, leaving the geometry in the database: GEOS cannot deserialize curves."""
    query = collection.get_queryset(request)
    if geom_field := collection.geometry_field:
        query = query.defer(geom_field)
    return get_object_or_404(query, pk=item_id)


def primary_keys(collection: OapifCollection) -> set[str]:
    """
    The primary key of the model, and those of the models it inherits from. An item to replace or update is
    the one of the URL: taking its key from the payload would save another row, even a copy of it, as the
    input schema gives a key with a default a fresh value.
    """
    keys = [collection.opts.pk, *(parent._meta.pk for parent in collection.opts.get_parent_list())]
    return {name for key in keys for name in (key.name, key.attname)}


# the geometry types of GeoJSON, the only ones GEOS knew before its 3.13
GEOJSON_TYPES = {
    "Point",
    "MultiPoint",
    "LineString",
    "MultiLineString",
    "Polygon",
    "MultiPolygon",
    "GeometryCollection",
}


def is_geojson(geometry) -> bool:
    if geometry.type not in GEOJSON_TYPES:
        return False
    return geometry.type != "GeometryCollection" or all(is_geojson(member) for member in geometry.geometries)


@cache
def writes_curves() -> bool:
    """Whether curves can be written: it takes GEOS 3.13, and a Django whose GEOS bindings know them."""
    try:
        from django.contrib.gis.geos import CircularString  # noqa: F401
    except ImportError:
        return False
    return geos_version_tuple() >= (3, 13, 0)


def geometry_to_save(geometry, crs: CRS) -> GEOSGeometry | None:
    """
    The GEOS geometry to store for a feature geometry. It is built from WKB, which GEOS reads for every
    type it knows, where GDAL only reads the GeoJSON ones from JSON.
    """
    if geometry is None:
        return None
    if not is_geojson(geometry) and not writes_curves():
        raise HttpError(501, "Curves can only be written with GEOS 3.13 or newer and a Django that supports them")
    # a CircularString served in parts goes back into its column as one
    data = geometry.circular_string() if isinstance(geometry, CircularStringParts) else geometry.model_dump()
    try:
        return GEOSGeometry(memoryview(jsonfg.dumps(data)), srid=crs.srid)
    except GEOSException:
        # GEOS checks what the schema cannot, such as the closing of the rings
        raise HttpError(422, "Invalid geometry")


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
        response.crs = [crs.uri() for crs in collection.supported_crs()]
        if storage_crs := collection.storage_crs():
            response.storageCrs = storage_crs.uri()
        if collection.srid == CRS84_SRID:
            extent = collection.model.objects.aggregate(extent=Extent(geom))["extent"]
        else:
            box = collection.model.objects.aggregate(extent=ReprojectedExtent(geom, collection.srid, CRS84_SRID))
            extent = parse_box2d(box["extent"]) if box["extent"] else None
        if extent:
            response.extent = OAPIFExtent(spatial=OAPIFSpatialExtent(bbox=[extent], crs=CRS84_URI))

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
        crs: CRS = DEFAULT_CRS,
        bbox_crs: CRS = Query(DEFAULT_CRS, alias="bbox-crs"),
        bbox: BBox | None = Query(None, alias="bbox", description="BBOX in the format: minx,miny,maxx,maxy"),
    ):
        collection = get_collection_by_id(collection_id, request)
        validate_crs_or_raise(collection, crs, "crs")
        validate_crs_or_raise(collection, bbox_crs, "bbox-crs")

        query = collection.query(request, crs, bbox, bbox_crs)
        paginated_query = query[offset : offset + limit]

        total_count = query.count()

        if accepts_geoarrow(request):
            stream = collection.queryset_to_arrow_stream(request, paginated_query, crs)
            arrow_response = HttpResponse(stream.getvalue().to_pybytes(), content_type=ARROW_STREAM_MEDIA_TYPE)
            arrow_response["Content-Crs"] = crs.uri_header()
            # an Arrow stream has nowhere to put them, and the row count is the only one a client
            # cannot work out from the table itself
            arrow_response["Link"] = link_header(
                get_page_links(request, limit, offset, total_count, ARROW_STREAM_MEDIA_TYPE)
            )
            arrow_response["OGC-NumberMatched"] = str(total_count)
            return arrow_response

        feature_collection = collection.queryset_to_featurecollection(
            request,
            paginated_query,
            number_matched=total_count,
            links=get_page_links(request, limit, offset, total_count),
        )
        return geojson_response(feature_collection, crs)

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
        crs: CRS = DEFAULT_CRS,
    ):
        collection = get_collection_by_id(collection_id, request)
        validate_crs_or_raise(collection, crs, "crs")
        query = collection.query(request, crs)
        item = get_object_or_404(query, pk=item_id)
        if not collection.has_view_permission(request, item):
            raise AuthorizationError()
        if accepts_geoarrow(request):
            stream = collection.queryset_to_arrow_stream(request, query.filter(pk=item_id), crs)
            arrow_response = HttpResponse(stream.getvalue().to_pybytes(), content_type=ARROW_STREAM_MEDIA_TYPE)
            arrow_response["Content-Crs"] = crs.uri_header()
            return arrow_response
        return geojson_response(collection.model_to_feature(request, item), crs)

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
        crs: CRS = Header(DEFAULT_CRS, alias="Content-Crs"),
    ):
        collection = get_collection_by_id(collection_id, request)
        validate_crs_or_raise(collection, crs, "Content-Crs")
        feature = collection.validate_feature_input_or_raise(request, feature)
        item_properties = feature.properties.model_dump() or {}
        for field, value in item_properties.items():
            if value is not None and (related_model := collection.foreign_key_fields.get(field)):
                item_properties[field] = get_related_object_or_raise(field, value, related_model)
        if (geom_field := collection.geometry_field) and feature.geometry:
            item_properties[geom_field] = geometry_to_save(feature.geometry, crs)
        item = collection.model(**item_properties)
        if not collection.has_add_permission(request, item):
            raise AuthorizationError()
        collection.save_model(request, item, False)
        item = collection.query(request, DEFAULT_CRS).get(pk=item.pk)
        response.headers["Location"] = request.build_absolute_uri(f"items/{item.pk}")  # type: ignore
        response["Content-Crs"] = DEFAULT_CRS.uri_header()
        response["Content-Type"] = GEOJSON_MEDIA_TYPE
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
        item = get_item_or_404(collection, request, item_id)
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
        response: HttpResponse,
        collection_id: str,
        item_id: str,
        feature: GenericFeature,
        crs: CRS = Header(DEFAULT_CRS, alias="Content-Crs"),
    ):
        collection = get_collection_by_id(collection_id, request)
        validate_crs_or_raise(collection, crs, "Content-Crs")
        item = get_item_or_404(collection, request, item_id)
        if not collection.has_change_permission(request, item):
            raise AuthorizationError()
        feature = collection.validate_feature_input_or_raise(request, feature)
        for field, value in feature.properties.model_dump().items():
            if field in primary_keys(collection):
                continue
            if value is not None and (related_model := collection.foreign_key_fields.get(field)):
                value = get_related_object_or_raise(field, value, related_model)
            setattr(item, field, value)
        if geom_field := collection.geometry_field:
            setattr(item, geom_field, geometry_to_save(feature.geometry, crs))
        collection.save_model(request, item, True)
        item = collection.query(request, DEFAULT_CRS).get(pk=item_id)
        response["Content-Crs"] = DEFAULT_CRS.uri_header()
        response["Content-Type"] = GEOJSON_MEDIA_TYPE
        return collection.model_to_feature(request, item)

    @router.patch(
        "/{collection_id}/items/{item_id}",
        operation_id="update_collection_item",
        response=GenericFeature,
    )
    def update_item(
        request: HttpRequest,
        response: HttpResponse,
        collection_id: str,
        item_id: str,
        feature: GenericFeaturePatch,
        crs: CRS = Header(DEFAULT_CRS, alias="Content-Crs"),
    ):
        collection = get_collection_by_id(collection_id, request)
        validate_crs_or_raise(collection, crs, "Content-Crs")
        item = get_item_or_404(collection, request, item_id)
        if not collection.has_change_permission(request, item):
            raise AuthorizationError()
        feature = collection.validate_feature_patch_or_raise(request, feature)
        if feature.properties is not None:
            for field, value in feature.properties.model_dump(exclude_unset=True).items():
                if field in primary_keys(collection):
                    continue
                if value is not None and (related_model := collection.foreign_key_fields.get(field)):
                    value = get_related_object_or_raise(field, value, related_model)
                setattr(item, field, value)
        if (geom_field := collection.geometry_field) and "geometry" in feature.model_fields_set:
            setattr(item, geom_field, geometry_to_save(feature.geometry, crs))
        collection.save_model(request, item, True)
        item = collection.query(request, DEFAULT_CRS).get(pk=item_id)
        response["Content-Crs"] = DEFAULT_CRS.uri_header()
        response["Content-Type"] = GEOJSON_MEDIA_TYPE
        return collection.model_to_feature(request, item)

    @router.delete("/{collection_id}/items/{item_id}", operation_id="delete_collection_item")
    def delete_item(
        request: HttpRequest,
        collection_id: str,
        item_id: str,
    ):
        collection = get_collection_by_id(collection_id, request)
        item = get_item_or_404(collection, request, item_id)
        if not collection.has_delete_permission(request, item):
            raise AuthorizationError()
        collection.delete_model(request, item)

    return router
