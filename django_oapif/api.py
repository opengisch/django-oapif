# ninja_ogc/routers.py

from django.contrib.gis.db.models.functions import AsGeoJSON
from django.contrib.gis.geos import Polygon
from django.db import models
from django.db.models.functions import Cast
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from geojson_pydantic import Feature, FeatureCollection
from ninja import NinjaAPI, Query, Router

# Global registries to store collection metadata and routers
OGC_COLLECTIONS_REGISTRY = []
OGC_ROUTERS_REGISTRY = {}


def register_oapif_viewset(
    *,
    key: str | None = None,
    title: str,
    description: str,
    geometry_field: str = "geom",
    properties_fields: list[str] = [],
):
    """
    Decorator to apply to a Django model (with a geometry field)
    to generate a generic Ninja router with OGC API – Features endpoints.

    :param key: Unique identifier of the collection (e.g., "parcels")
    :param title: Collection title
    :param description: Collection description
    :param geometry_field: Name of the geometry field (default: "geom")
    :param properties_fields: List of model fields to include in the GeoJSON properties.
                              By default, no fields will be included.
    """


    def decorator(model_class: models.Model):
        router = Router()
        collection_id = key or model_class._meta.label_lower

        @router.get("", response=dict)
        def get_collection(request: HttpRequest):
            return {
                "id": collection_id,
                "title": title,
                "description": description,
                "links": [
                    {
                        "href": request.build_absolute_uri(f"{collection_id}"),
                        "rel": "self",
                        "type": "application/json"
                    },
                    {
                        "href": request.build_absolute_uri(f"{collection_id}/items"),
                        "rel": "items",
                        "type": "application/geo+json"
                    }
                ],
            }

        @router.get("/items")
        def get_items(request, limit: int | None = None, bbox: str = Query(None, description="BBOX in the format: minx,miny,maxx,maxy")):
            qs = model_class.objects.only("id", *properties_fields)
            if geometry_field:
                qs = qs.annotate(geometry=Cast(AsGeoJSON(geometry_field, False, False), models.JSONField()))
            if limit is not None:
                qs = qs[:limit]
            if bbox:
                try:
                    minx, miny, maxx, maxy = map(float, bbox.split(","))
                    bbox_geom = Polygon.from_bbox((minx, miny, maxx, maxy))
                    qs = qs.filter(**{f"{geometry_field}__intersects": bbox_geom})
                except ValueError:
                    return router.create_response(
                        request, {"error": "Invalid bbox parameter. Expected format: minx,miny,maxx,maxy"}, status=400
                    )
            return FeatureCollection(
                type="FeatureCollection",
                features=[
                    Feature(
                        id=str(obj.id),
                        type="Feature",
                        geometry=None if not geometry_field else obj.geometry,
                        properties={field: getattr(obj, field) for field in properties_fields}
                    )
                    for obj in qs
                ],
            )

        @router.get("/items/{item_id}")
        def get_item(request, item_id: str):
            qs = model_class.objects.only(properties_fields)
            if geometry_field:
                qs = qs.annotate(geometry=Cast(AsGeoJSON(geometry_field, False, False), models.JSONField()))
            obj = get_object_or_404(qs, pk=item_id)
            return Feature(
                id=str(obj.id),
                type="Feature",
                geometry=None if not geometry_field else obj.geometry,
                properties={field: getattr(obj, field) for field in properties_fields}
            )

        # Register the collection metadata in the global registry
        collection_info = {
            "id": collection_id,
            "title": title,
            "description": description,
        }
        OGC_COLLECTIONS_REGISTRY.append(collection_info)
        OGC_ROUTERS_REGISTRY[collection_id] = router

        return model_class

    return decorator


# Global router for listing all collections
collections_router = Router()

@collections_router.get("")
def list_all_collections(request: HttpRequest):
    return {
        "links": [
            {
                "href": request.build_absolute_uri("collections"),
                "rel": "self",
                "type": "application/json",
                "title": "this document",
            },
        ],
        "collections": [
            {
                **collection,
                "links": [
                    {
                        "href": request.build_absolute_uri(f"collections/{collection['id']}"),
                        "rel": "self",
                        "type": "application/json"
                    },
                    {
                        "href": request.build_absolute_uri(f"collections/{collection['id']}/items"),
                        "rel": "items",
                        "type": "application/geo+json"
                    }
                ],
            }
            for collection in OGC_COLLECTIONS_REGISTRY
        ],
    }



def register_all_ogc_routes(api: NinjaAPI):
    """
    Register all OGC routers from the global registry on the provided Ninja API.
    """
    # Register the global collections endpoint at /collections
    api.add_router("collections", collections_router)
    for collection_id, collection_router in OGC_ROUTERS_REGISTRY.items():
        api.add_router(f"collections/{collection_id}", collection_router)


    @api.get("/conformance")
    def conformance(request: HttpRequest):
        return {
            "conformsTo": [
                "http://www.opengis.net/spec/ogcapi-common-2/1.0/conf/collections",
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/core",
                "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
                "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
                "http://www.opengis.net/spec/ogcapi-features-1/1.0/req/oas30",
                # "http://www.opengis.net/spec/ogcapi-features-4/1.0/conf/create-replace-delete",
                # "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/html",
                # "http://www.opengis.net/spec/ogcapi-features-2/1.0/conf/crs",
            ]
        }

    @api.get("")
    def root(request: HttpRequest):
        return {
            "title": "self.title",
            "description": "self.description",
            "links": [
                {
                    "href": request.build_absolute_uri(""),
                    "rel": "self",
                    "type": "application/json",
                    "title": "this document",
                },
                {
                    "href": request.build_absolute_uri("openapi.json"),
                    "rel": "service-desc",
                    "type": "application/vnd.oai.openapi+json;version=3.0",
                    "title": "the API definition",
                },
                {
                    "href": request.build_absolute_uri("conformance"),
                    "rel": "conformance",
                    "type": "application/json",
                    "title": "OGC API conformance classes implemented by this server",
                },
                {
                    "href": request.build_absolute_uri("collections"),
                    "rel": "data",
                    "type": "application/json",
                    "title": "Information about the feature collections",
                },
            ],
        }
