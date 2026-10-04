import json
from functools import cache
from typing import Any, Literal
from urllib.parse import quote

from django.contrib.gis.db.models import Extent
from django.contrib.gis.geos import GEOSException, GEOSGeometry
from django.contrib.gis.geos.libgeos import geos_version_tuple
from django.core.exceptions import FieldError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import ForeignKey, Model, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.cache import patch_vary_headers
from ninja import Header, Query, Router, Schema
from ninja.errors import AuthorizationError, HttpError, ValidationError
from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from django_oapif import cql2, jsonfg
from django_oapif.crs import CRS, CRS84_SRID, CRS84_URI, BBox
from django_oapif.geojson import (
    CircularStringParts,
    GenericFeature,
    GenericFeatureCollection,
    GenericFeatureInput,
    GenericFeaturePatch,
    JsonFgDocument,
)
from django_oapif.handler import ARROW_AVAILABLE, OapifCollection, ReprojectedExtent, parse_box2d
from django_oapif.html import HTML_MEDIA_TYPE, as_text, html_response, schema_properties
from django_oapif.jsonfg import Profile
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
SCHEMA_MEDIA_TYPE = "application/schema+json"

ACCEPTED_TYPES = [
    JSON_MEDIA_TYPE,
    GEOJSON_MEDIA_TYPE,
    ARROW_STREAM_MEDIA_TYPE,
]

DEFAULT_CRS = CRS("OGC", CRS84_SRID)
PROFILE_DESCRIPTION = "GeoJSON profile: rfc7946 for GeoJSON, the default, or jsonfg for JSON-FG, which has the curves"
LINEARIZE_DESCRIPTION = (
    "Whether GeoJSON has the curves linearized, in the CRS asked for, instead of refusing them. Not with the "
    "jsonfg profile, which has the curves as they are"
)
CRS_ADAPTER = TypeAdapter(CRS)


def get_page_links(
    request: HttpRequest,
    limit: int,
    offset: int,
    total_count: int,
    media_type: str = GEOJSON_MEDIA_TYPE,
    profile: Profile | None = None,
) -> list[OAPIFLink]:
    """The links of a page of items. Those to pages give the GeoJSON profile asked for, which the others have too."""
    profiles = [profile.uri] if profile else None
    links = [
        OAPIFLink(
            rel="self",
            title="items (self)",
            type=media_type,
            href=request.build_absolute_uri(),
            profile=profiles,
        ),
        html_link(replace_query_param(request, f="html"), "items (as HTML)"),
    ]
    if offset > 0:
        links.append(
            OAPIFLink(
                rel="prev",
                title="items (prev)",
                type=media_type,
                href=replace_query_param(request, offset=None if offset - limit <= 0 else offset - limit),
                profile=profiles,
            )
        )
    if offset + limit < total_count:
        links.append(
            OAPIFLink(
                rel="next",
                title="items (next)",
                type=media_type,
                href=replace_query_param(request, offset=offset + limit),
                profile=profiles,
            )
        )
    return links


def curves_not_acceptable(request: HttpRequest) -> HttpResponse:
    """
    The answer to a request of curves in GeoJSON, which cannot carry them: a 406, linking them in JSON-FG, and in
    GeoJSON linearized.
    """
    links = [
        OAPIFLink(
            rel="alternate",
            title="This document as JSON-FG",
            type=GEOJSON_MEDIA_TYPE,
            href=replace_query_param(request, profile=Profile.JSONFG),
            profile=[Profile.JSONFG.uri],
        ),
        OAPIFLink(
            rel="alternate",
            title="This document as GeoJSON, the curves linearized",
            type=GEOJSON_MEDIA_TYPE,
            href=replace_query_param(request, linearize="true"),
        ),
    ]
    body = {
        "detail": "GeoJSON cannot carry curves: ask for them in JSON-FG, with profile=jsonfg, or linearized, with "
        "linearize=true",
        "links": [link.model_dump() for link in links],
    }
    response = HttpResponse(json.dumps(body), status=406, content_type=JSON_MEDIA_TYPE)
    patch_vary_headers(response, ["Accept"])
    return response


def encoding_of(profile: Profile | None, linearize: bool) -> Profile | None:
    """
    The GeoJSON profile features are encoded in: JSON-FG as asked for, GeoJSON when their curves are linearized,
    and otherwise JSON-FG with curves, which a request of GeoJSON is then refused.
    """
    if profile is Profile.JSONFG and linearize:
        raise HttpError(400, "linearize=true asks for GeoJSON: JSON-FG has the curves as they are")
    if profile is Profile.JSONFG:
        return profile
    return Profile.RFC7946 if linearize else None


def geojson_response(geojson: Schema, crs: CRS) -> HttpResponse:
    """
    Serialized by pydantic: returned as they are, ninja would validate the features all over again, and
    render them with json.dumps, which takes ten times as long.
    """
    response = HttpResponse(geojson.model_dump_json(), content_type=GEOJSON_MEDIA_TYPE)
    response["Content-Crs"] = crs.uri_header()
    # the profile of the document, which Part 5 links from the response
    profile = Profile.JSONFG if isinstance(geojson, JsonFgDocument) else Profile.RFC7946
    response["Link"] = f'<{profile.uri}>; rel="profile"'
    # the same URL serves GeoArrow too: a cache must not hand one encoding to a request for the other
    patch_vary_headers(response, ["Accept"])
    return response


def arrow_response(stream, crs: CRS) -> HttpResponse:
    response = HttpResponse(stream.getvalue().to_pybytes(), content_type=ARROW_STREAM_MEDIA_TYPE)
    response["Content-Crs"] = crs.uri_header()
    patch_vary_headers(response, ["Accept"])
    return response


def html_link(href: str, title: str) -> OAPIFLink:
    """The link to the HTML encoding of a resource, which asks for it with `f=html`, for any client to get it."""
    return OAPIFLink(rel="alternate", title=title, type=HTML_MEDIA_TYPE, href=href)


def link_header(links: list[OAPIFLink]) -> str:
    """
    Serialize links as a RFC 8288 Link header, for responses that cannot carry them in the payload, and for the
    clients that read them there only, as QGIS does of JSON-FG.
    """
    return ", ".join(
        f'<{link.href}>; rel="{link.rel}"; type="{link.type}"'
        + (f'; profile="{" ".join(link.profile)}"' if link.profile else "")
        for link in links
    )


def accepted_profiles(request: HttpRequest) -> list[str]:
    """The profiles of the GeoJSON the Accept header of a request asks for, by preference."""
    return [
        media_type.params["profile"]
        for media_type in request.accepted_types
        if (media_type.main_type, media_type.sub_type) == ("application", "geo+json") and "profile" in media_type.params
    ]


def offered_types(request: HttpRequest, *media_types: str) -> list[str]:
    """
    The media types to negotiate between, and the profiled GeoJSON the request accepts: Django matches an accepted
    type that has parameters only to an offered one with the same, and would prefer any other to it.
    """
    profiled = [f'{GEOJSON_MEDIA_TYPE}; profile="{profile}"' for profile in accepted_profiles(request)]
    return [*media_types, *profiled]


def requested_profile(request: HttpRequest, profile: str | None) -> Profile | None:
    """
    The GeoJSON profile a request asks for: in the profile query parameter of Part 5, a list of tokens or URIs, or
    else as the parameter of the media type it accepts. Those of other formats are left out, as Part 5 recommends
    that no profile fails a request.
    """
    requested = profile.split(",") if profile else accepted_profiles(request)
    return next((known for value in requested if (known := Profile.parse(value))), None)


def accepts_html(request: HttpRequest) -> bool:
    """
    Whether to answer with the HTML page of a resource, which a browser asks for: `f=html` or `f=json` choose,
    and otherwise the Accept header, a request that accepts any type getting the JSON.
    """
    if f := request.GET.get("f"):
        return f == "html"
    return request.get_preferred_type(offered_types(request, *ACCEPTED_TYPES, HTML_MEDIA_TYPE)) == HTML_MEDIA_TYPE


def accepts_geoarrow(request: HttpRequest) -> bool:
    if request.get_preferred_type(offered_types(request, *ACCEPTED_TYPES)) == ARROW_STREAM_MEDIA_TYPE:
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


def filter_or_raise(
    collection: OapifCollection, request: HttpRequest, query: QuerySet, filter_expr: str, filter_crs: CRS
) -> QuerySet:
    """
    The items matching a CQL2 filter. A filter that cannot be applied is a client error: one naming what is not a
    queryable, but also one comparing a property with a value of another type, which Django finds out as it builds
    the lookups.
    """
    fields = {name: collection.opts.get_field(name) for name in collection.get_queryables(request)}
    try:
        return query.filter(cql2.to_q(filter_expr, fields, filter_crs.srid))
    except DjangoValidationError as e:
        raise HttpError(400, f"Invalid filter: {' '.join(e.messages)}")
    except (cql2.FilterError, FieldError, ValueError, TypeError) as e:
        raise HttpError(400, f"Invalid filter: {e}")


def take_jsonfg_members_or_raise(feature: GenericFeatureInput | GenericFeaturePatch, crs: CRS) -> None:
    """
    JSON-FG writes the geometries GeoJSON cannot carry, like the ones with arcs, in "place", its "geometry" being
    then their linearized fallback or null: a "place" is the geometry to store. Coordinates are read in the
    Content-Crs, so a coordRefSys naming another CRS is refused.
    """
    if feature.coordRefSys is not None:
        try:
            coord_ref_sys = CRS_ADAPTER.validate_python(feature.coordRefSys)
        except PydanticValidationError:
            raise HttpError(400, f"Unsupported coordRefSys '{feature.coordRefSys}'")
        if coord_ref_sys != crs:
            raise HttpError(400, f"coordRefSys '{coord_ref_sys.uri()}' differs from the Content-Crs '{crs.uri()}'")
    if feature.place is not None:
        feature.geometry = feature.place


def referenced_collections(
    request: HttpRequest, field: ForeignKey, collections: dict[str, OapifCollection]
) -> list[OapifCollection]:
    """
    The collections a foreign key references, in the reference role of Part 5, those of the model it references that
    the user may view: served as the primary key of a row, it is the id of a feature of theirs. A key to another
    field, or to a model without a collection, references no feature, and the primary key keeps its role of id.
    """
    if field.primary_key or not field.target_field.primary_key:
        return []
    model = field.related_model
    return [other for other in collections.values() if other.model is model and other.has_view_permission(request)]


def add_references(
    request: HttpRequest, collection: OapifCollection, collections: dict[str, OapifCollection], schema: dict
) -> None:
    """Give a foreign key the reference role of Part 5, to the collections it references."""
    for name in collection.foreign_key_fields:
        if name not in schema["properties"]:
            continue
        ids = [other.id for other in referenced_collections(request, collection.opts.get_field(name), collections)]
        if ids:
            schema["properties"][name]["x-ogc-role"] = "reference"
            schema["properties"][name]["x-ogc-collectionId"] = ids[0] if len(ids) == 1 else ids


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


def validate_new_key_or_raise(collection: OapifCollection, item: Model) -> None:
    """
    Refuse to create an item under the key of an existing row, of its model or of one it inherits from. Django saves
    an item whose key has no default, such as an AutoField, over that row, even one the collection hides, and one
    whose key has a default fails on the duplicate.
    """
    tables = (collection.model, *collection.opts.get_parent_list())
    links = [link for table in tables for link in table._meta.parents.values() if link]
    # not item.pk alone: the one of a model inheriting from another is the link to its parent, which a collection
    # may leave out of writes and still take the key of the parent, and a parent without a key takes the one of the
    # link, which is not the key of a child that has its own
    keys = {getattr(item, field.attname) for field in (*(table._meta.pk for table in tables), *links)} - {None}
    if any(table._base_manager.filter(pk__in=keys).exists() for table in tables):
        raise HttpError(409, "A feature with this id already exists")


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
    # a CircularString served in parts goes back into its column as one
    data = geometry.circular_string() if isinstance(geometry, CircularStringParts) else geometry.model_dump()
    if not jsonfg.is_geojson(data) and not writes_curves():
        raise HttpError(501, "Curves can only be written with GEOS 3.13 or newer and a Django that supports them")
    try:
        return GEOSGeometry(memoryview(jsonfg.dumps(data)), srid=crs.srid)
    except GEOSException:
        # GEOS checks what the schema cannot, such as the closing of the rings
        raise HttpError(422, "Invalid geometry")


def get_related_object_or_raise(
    request: HttpRequest, field: ForeignKey, value: Any, collections: dict[str, OapifCollection]
):
    """
    The row a foreign key references, by the value of the field it references, which the key is served as. A
    reference has to be to a feature that its collections serve the user: any row would let them link to one hidden
    from them, such as someone else's, and tell which exist. Another key takes any row of its model.
    """
    lookup = {field.target_field.name: value}
    querysets = [other.get_queryset(request) for other in referenced_collections(request, field, collections)]
    for queryset in querysets or [field.related_model._default_manager]:
        if (row := queryset.filter(**lookup).first()) is not None:
            return row
    raise ValidationError([
        {
            "loc": ["body", "feature", "properties", field.name],
            "msg": "Foreign key not found",
            "type": "value_error",
        },
    ])


def get_collection_response(
    request: HttpRequest, collection: OapifCollection, uri_prefix: str = "", *, with_extent: bool = True
):
    """
    The description of a collection, its links resolved against the path of the request: that of the collection,
    or with `uri_prefix="collections/"` that of the list of collections.
    """
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
            html_link(request.build_absolute_uri(f"{uri_prefix}{collection.id}?f=html"), "Collection as HTML"),
            OAPIFLink(
                rel="http://www.opengis.net/def/rel/ogc/1.0/schema",
                title="Collection schema",
                type=SCHEMA_MEDIA_TYPE,
                href=request.build_absolute_uri(f"{uri_prefix}{collection.id}/schema"),
            ),
            OAPIFLink(
                rel="http://www.opengis.net/def/rel/ogc/1.0/queryables",
                title="Collection queryables",
                type=SCHEMA_MEDIA_TYPE,
                href=request.build_absolute_uri(f"{uri_prefix}{collection.id}/queryables"),
            ),
        ],
    )
    items_url = request.build_absolute_uri(f"{uri_prefix}{collection.id}/items")
    if collection.geometry_field:
        # before the GeoJSON one: QGIS 4.0 takes the last link of a type, and knows no profiles
        response.links.append(
            OAPIFLink(
                rel="items",
                title="Collection items as JSON-FG",
                type=GEOJSON_MEDIA_TYPE,
                href=f"{items_url}?profile={Profile.JSONFG}",
                profile=[Profile.JSONFG.uri],
            )
        )
    response.links.append(OAPIFLink(rel="items", title="Collection items", type=GEOJSON_MEDIA_TYPE, href=items_url))
    if ARROW_AVAILABLE:
        # the same URL, negotiated with the Accept header: clients only pick an encoding the collection lists
        response.links.append(
            OAPIFLink(rel="items", title="Collection items as GeoArrow", type=ARROW_STREAM_MEDIA_TYPE, href=items_url)
        )

    if geom := collection.geometry_field:
        response.crs = [crs.uri() for crs in collection.supported_crs()]
        if storage_crs := collection.storage_crs():
            response.storageCrs = storage_crs.uri()
    if geom and with_extent:
        # the rows the collection serves, which may be fewer than those of its model
        rows = collection.get_queryset(request)
        if collection.srid == CRS84_SRID:
            extent = rows.aggregate(extent=Extent(geom))["extent"]
        else:
            box = rows.aggregate(extent=ReprojectedExtent(geom, collection.srid, CRS84_SRID))
            extent = parse_box2d(box["extent"]) if box["extent"] else None
        if extent:
            response.extent = OAPIFExtent(spatial=OAPIFSpatialExtent(bbox=[extent], crs=CRS84_URI))

    return response


def create_collections_router(collections: dict[str, OapifCollection], *, title: str):
    router = Router()

    def get_collection_by_id(collection_id: str, request: HttpRequest):
        collection = collections.get(collection_id)
        if collection is None:
            raise HttpError(404, "Collection not found")
        if not collection.has_view_permission(request):
            raise AuthorizationError()
        return collection

    # ninja would write the members a collection has no value for as null, which OGC API - Features does not allow
    @router.get("", response=OAPIFCollections, operation_id="get_collections", exclude_none=True)
    def list_collections(request: HttpRequest):
        html = accepts_html(request)
        response = OAPIFCollections(
            links=[
                OAPIFLink(
                    href=request.build_absolute_uri(),
                    rel="self",
                    type="application/json",
                    title="this document",
                ),
                html_link(replace_query_param(request, f="html"), "this document as HTML"),
            ],
            collections=[
                # the page shows no extent, which takes a query per collection
                get_collection_response(request, collection, uri_prefix="collections/", with_extent=not html)
                for collection in collections.values()
                if collection.has_view_permission(request)
            ],
        )
        if html:
            return html_response(request, "collections.html", {"collections": response.collections}, title=title)
        return response

    @router.get(
        "/{collection_id}",
        response=OAPIFCollection,
        operation_id="get_collection",
        exclude_none=True,
    )
    def get_collection(request, collection_id: str):
        collection = get_collection_by_id(collection_id, request)
        response = get_collection_response(request, collection)
        if accepts_html(request):
            return html_response(request, "collection.html", {"collection": response}, title=title)
        return response

    @router.get(
        "/{collection_id}/schema",
        operation_id="get_collection_schema",
    )
    def get_schema(request: HttpRequest, collection_id: str):
        collection = get_collection_by_id(collection_id, request)
        schema = collection.get_json_schema(request)
        schema["$id"] = request.build_absolute_uri(request.path)
        add_references(request, collection, collections, schema)
        if accepts_html(request):
            context = {"collection": collection, "properties": schema_properties(schema)}
            return html_response(request, "schema.html", context, title=title)
        # the titles are the verbose names of the fields, which ninja leaves lazy when they are translated
        response = HttpResponse(json.dumps(schema, cls=DjangoJSONEncoder), content_type=SCHEMA_MEDIA_TYPE)
        # the same URL serves an HTML page to a browser
        patch_vary_headers(response, ["Accept"])
        return response

    @router.get(
        "/{collection_id}/queryables",
        operation_id="get_collection_queryables",
    )
    def get_queryables(request: HttpRequest, collection_id: str):
        collection = get_collection_by_id(collection_id, request)
        schema = collection.get_queryables_schema(request)
        schema["$id"] = request.build_absolute_uri(request.path)
        if accepts_html(request):
            context = {"collection": collection, "properties": schema_properties(schema)}
            return html_response(request, "queryables.html", context, title=title)
        response = HttpResponse(json.dumps(schema, cls=DjangoJSONEncoder), content_type=SCHEMA_MEDIA_TYPE)
        patch_vary_headers(response, ["Accept"])
        return response

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
        filter_expr: str | None = Query(None, alias="filter", description="CQL2 expression the items must match"),
        filter_lang: Literal["cql2-text"] = Query("cql2-text", alias="filter-lang"),
        filter_crs: CRS = Query(DEFAULT_CRS, alias="filter-crs"),
        profile: str | None = Query(None, description=PROFILE_DESCRIPTION),
        linearize: bool = Query(False, description=LINEARIZE_DESCRIPTION),
    ):
        collection = get_collection_by_id(collection_id, request)
        validate_crs_or_raise(collection, crs, "crs")
        validate_crs_or_raise(collection, bbox_crs, "bbox-crs")
        validate_crs_or_raise(collection, filter_crs, "filter-crs")

        html = accepts_html(request)
        arrow = not html and accepts_geoarrow(request)
        # a page draws the curves itself, and GeoArrow has them as they are
        profile = None if html or arrow else requested_profile(request, profile)
        asks_geojson = not html and not arrow and profile is not Profile.JSONFG
        encoding = None if html or arrow else encoding_of(profile, linearize)
        # whatever the page, even without a feature
        if asks_geojson and not linearize and collection.curved:
            return curves_not_acceptable(request)

        query = collection.query(request, crs, bbox, bbox_crs)
        if filter_expr is not None:
            query = filter_or_raise(collection, request, query, filter_expr, filter_crs)
        if asks_geojson and linearize:
            query = collection.linearize(query, crs)
        paginated_query = query[offset : offset + limit]

        total_count = query.count()

        if arrow:
            stream = collection.queryset_to_arrow_stream(request, paginated_query, crs)
            response = arrow_response(stream, crs)
            # an Arrow stream has nowhere to put them, and the row count is the only one a client
            # cannot work out from the table itself
            response["Link"] = link_header(get_page_links(request, limit, offset, total_count, ARROW_STREAM_MEDIA_TYPE))
            response["OGC-NumberMatched"] = str(total_count)
            return response

        feature_collection = collection.queryset_to_featurecollection(
            request,
            paginated_query,
            number_matched=total_count,
            links=get_page_links(request, limit, offset, total_count, profile=profile),
            crs=crs,
            profile=encoding,
        )
        if html:
            geojson = json.loads(feature_collection.model_dump_json())
            properties = list(geojson["features"][0]["properties"]) if geojson["features"] else []
            # the primary key is the id of the features already
            pk = collection.opts.pk.name
            columns = [name for name in properties if name != pk]
            features = [
                {
                    "href": request.build_absolute_uri(f"items/{quote(feature['id'], safe='')}"),
                    "id": feature["id"],
                    "values": [as_text(feature["properties"][column]) for column in columns],
                }
                for feature in geojson["features"]
            ]
            context = {
                "collection": collection,
                "id_column": pk if pk in properties else "id",
                "columns": columns,
                "features": features,
                "first": offset + 1,
                "last": offset + len(features),
                "number_matched": total_count,
                "pages": {link.rel: link.href for link in feature_collection.links},
                # the map has its coordinates in CRS84 only
                "geojson": geojson if collection.geometry_field and crs == DEFAULT_CRS else None,
            }
            return html_response(request, "items.html", context, title=title)
        # a page with a curve, of a column of any geometry
        if asks_geojson and isinstance(feature_collection, JsonFgDocument):
            return curves_not_acceptable(request)
        response = geojson_response(feature_collection, crs)
        # where QGIS reads the pages of JSON-FG, as it does those of GeoArrow
        response["Link"] += ", " + link_header(feature_collection.links)
        response["OGC-NumberMatched"] = str(total_count)
        return response

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
        profile: str | None = Query(None, description=PROFILE_DESCRIPTION),
        linearize: bool = Query(False, description=LINEARIZE_DESCRIPTION),
    ):
        collection = get_collection_by_id(collection_id, request)
        validate_crs_or_raise(collection, crs, "crs")
        html = accepts_html(request)
        arrow = not html and accepts_geoarrow(request)
        profile = None if html or arrow else requested_profile(request, profile)
        asks_geojson = not html and not arrow and profile is not Profile.JSONFG
        encoding = None if html or arrow else encoding_of(profile, linearize)
        query = collection.query(request, crs)
        if asks_geojson and linearize:
            query = collection.linearize(query, crs)
        item = get_object_or_404(query, pk=item_id)
        if not collection.has_view_permission(request, item):
            raise AuthorizationError()
        if arrow:
            stream = collection.queryset_to_arrow_stream(request, query.filter(pk=item_id), crs)
            return arrow_response(stream, crs)
        feature = collection.model_to_feature(request, item, crs=crs, profile=encoding)
        if html:
            geojson = json.loads(feature.model_dump_json())
            context = {
                "collection": collection,
                "feature": geojson,
                "properties": [(name, as_text(value)) for name, value in geojson["properties"].items()],
                "geojson": geojson if collection.geometry_field and crs == DEFAULT_CRS else None,
            }
            return html_response(request, "item.html", context, title=title)
        # a curve, of any column
        if asks_geojson and isinstance(feature, JsonFgDocument):
            return curves_not_acceptable(request)
        return geojson_response(feature, crs)

    @router.post(
        "/{collection_id}/items",
        response={201: GenericFeature},
        operation_id="create_collection_item",
    )
    def create_item(
        request: HttpRequest,
        collection_id: str,
        feature: GenericFeatureInput,
        crs: CRS = Header(DEFAULT_CRS, alias="Content-Crs"),
    ):
        collection = get_collection_by_id(collection_id, request)
        validate_crs_or_raise(collection, crs, "Content-Crs")
        take_jsonfg_members_or_raise(feature, crs)
        feature = collection.validate_feature_input_or_raise(request, feature)
        item_properties = feature.properties.model_dump() or {}
        for field, value in item_properties.items():
            if value is not None and field in collection.foreign_key_fields:
                foreign_key = collection.opts.get_field(field)
                item_properties[field] = get_related_object_or_raise(request, foreign_key, value, collections)
        if (geom_field := collection.geometry_field) and feature.geometry:
            item_properties[geom_field] = geometry_to_save(feature.geometry, crs)
        item = collection.model(**item_properties)
        if not collection.has_add_permission(request, item):
            raise AuthorizationError()
        validate_new_key_or_raise(collection, item)
        collection.save_model(request, item, False)
        location = request.build_absolute_uri(f"items/{item.pk}")
        item = collection.query(request, DEFAULT_CRS).filter(pk=item.pk).first()
        if item is None:
            # saved out of the rows the collection serves, such as out of the area of the user: Part 4 lets the
            # response leave the feature out
            response = HttpResponse(status=201)
        else:
            # in JSON-FG for a curve, which ninja would take for GeoJSON
            response = geojson_response(collection.model_to_feature(request, item), DEFAULT_CRS)
            response.status_code = 201
        response["Location"] = location
        return response

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
        response={200: GenericFeature, 204: None},
    )
    def replace_item(
        request: HttpRequest,
        collection_id: str,
        item_id: str,
        feature: GenericFeatureInput,
        crs: CRS = Header(DEFAULT_CRS, alias="Content-Crs"),
    ):
        collection = get_collection_by_id(collection_id, request)
        validate_crs_or_raise(collection, crs, "Content-Crs")
        take_jsonfg_members_or_raise(feature, crs)
        item = get_item_or_404(collection, request, item_id)
        if not collection.has_change_permission(request, item):
            raise AuthorizationError()
        feature = collection.validate_feature_input_or_raise(request, feature)
        for field, value in feature.properties.model_dump().items():
            if field in primary_keys(collection):
                continue
            if value is not None and field in collection.foreign_key_fields:
                foreign_key = collection.opts.get_field(field)
                # written back as it was read, a key is kept: its row may have left those the user is served since
                if value == getattr(item, foreign_key.attname):
                    continue
                value = get_related_object_or_raise(request, foreign_key, value, collections)
            setattr(item, field, value)
        if geom_field := collection.geometry_field:
            setattr(item, geom_field, geometry_to_save(feature.geometry, crs))
        collection.save_model(request, item, True)
        item = collection.query(request, DEFAULT_CRS).filter(pk=item_id).first()
        if item is None:
            # the change took it out of the rows the collection serves
            return HttpResponse(status=204)
        return geojson_response(collection.model_to_feature(request, item), DEFAULT_CRS)

    @router.patch(
        "/{collection_id}/items/{item_id}",
        operation_id="update_collection_item",
        response={200: GenericFeature, 204: None},
    )
    def update_item(
        request: HttpRequest,
        collection_id: str,
        item_id: str,
        feature: GenericFeaturePatch,
        crs: CRS = Header(DEFAULT_CRS, alias="Content-Crs"),
    ):
        collection = get_collection_by_id(collection_id, request)
        validate_crs_or_raise(collection, crs, "Content-Crs")
        take_jsonfg_members_or_raise(feature, crs)
        item = get_item_or_404(collection, request, item_id)
        if not collection.has_change_permission(request, item):
            raise AuthorizationError()
        feature = collection.validate_feature_patch_or_raise(request, feature)
        if feature.properties is not None:
            for field, value in feature.properties.model_dump(exclude_unset=True).items():
                if field in primary_keys(collection):
                    continue
                if value is not None and field in collection.foreign_key_fields:
                    foreign_key = collection.opts.get_field(field)
                    # written back as it was read, a key is kept: its row may have left those the user is served since
                    if value == getattr(item, foreign_key.attname):
                        continue
                    value = get_related_object_or_raise(request, foreign_key, value, collections)
                setattr(item, field, value)
        if (geom_field := collection.geometry_field) and "geometry" in feature.model_fields_set:
            setattr(item, geom_field, geometry_to_save(feature.geometry, crs))
        collection.save_model(request, item, True)
        item = collection.query(request, DEFAULT_CRS).filter(pk=item_id).first()
        if item is None:
            # the change took it out of the rows the collection serves
            return HttpResponse(status=204)
        return geojson_response(collection.model_to_feature(request, item), DEFAULT_CRS)

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
