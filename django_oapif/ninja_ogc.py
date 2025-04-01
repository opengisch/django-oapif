# ninja_ogc/routers.py
from typing import Any, Optional

from django.contrib.gis.db.models.functions import AsGeoJSON
from django.contrib.gis.geos import Polygon
from django.shortcuts import get_object_or_404
from ninja import Query, Router, Schema

# Global registries to store collection metadata and routers
OGC_COLLECTIONS_REGISTRY = []
OGC_ROUTERS_REGISTRY = {}


# Pydantic schemas for GeoJSON-compliant responses
class FeatureSchema(Schema):
    type: str = "Feature"
    id: int
    geometry: dict[str, Any]
    properties: dict[str, Any]


class FeatureCollectionSchema(Schema):
    type: str = "FeatureCollection"
    features: list[FeatureSchema]


def ogc_features(
    *,
    collection_id: str,
    title: str,
    description: str,
    geometry_field: str = "geom",
    properties_fields: Optional[list[str]] = None,
):
    """
    Decorator to apply to a Django model (with a geometry field)
    to generate a generic Ninja router with OGC API – Features endpoints.

    :param collection_id: Unique identifier of the collection (e.g., "parcels")
    :param title: Collection title
    :param description: Collection description
    :param geometry_field: Name of the geometry field (default: "geom")
    :param properties_fields: List of model fields to include in the GeoJSON properties.
                              If None, no fields will be included.
    """

    def decorator(model_class):
        router = Router()

        @router.get("/", response=dict)
        def get_collection(request):
            return {
                "id": collection_id,
                "title": title,
                "description": description,
                "links": [
                    {"href": f"/collections/{collection_id}/items", "rel": "items", "type": "application/geo+json"}
                ],
            }

        @router.get("/items", response=FeatureCollectionSchema)
        def get_items(request, bbox: str = Query(None, description="BBOX in the format: minx,miny,maxx,maxy")):
            qs = model_class.objects.all()
            if bbox:
                try:
                    minx, miny, maxx, maxy = map(float, bbox.split(","))
                    bbox_geom = Polygon.from_bbox((minx, miny, maxx, maxy))
                    qs = qs.filter(**{f"{geometry_field}__intersects": bbox_geom})
                except ValueError:
                    return router.create_response(
                        request, {"error": "Invalid bbox parameter. Expected format: minx,miny,maxx,maxy"}, status=400
                    )
            qs = qs.annotate(geometry=AsGeoJSON(geometry_field))
            features = []
            for obj in qs:
                properties = {}
                if properties_fields:
                    for field in properties_fields:
                        properties[field] = getattr(obj, field)
                feature = {"type": "Feature", "id": obj.id, "geometry": obj.geometry, "properties": properties}
                features.append(feature)
            return {"type": "FeatureCollection", "features": features}

        @router.get("/items/{item_id}", response=FeatureSchema)
        def get_item(request, item_id: int):
            obj = get_object_or_404(model_class.objects.annotate(geometry=AsGeoJSON(geometry_field)), pk=item_id)
            properties = {}
            if properties_fields:
                for field in properties_fields:
                    properties[field] = getattr(obj, field)
            return {"type": "Feature", "id": obj.id, "geometry": obj.geometry, "properties": properties}

        # Register the collection metadata in the global registry
        collection_info = {
            "id": collection_id,
            "title": title,
            "description": description,
            "links": [{"href": f"/collections/{collection_id}/items", "rel": "items", "type": "application/geo+json"}],
        }
        OGC_COLLECTIONS_REGISTRY.append(collection_info)
        OGC_ROUTERS_REGISTRY[collection_id] = router

        return model_class

    return decorator


# Global router for listing all collections
global_ogc_router = Router()


@global_ogc_router.get("/", response=list)
def list_all_collections(request):
    return OGC_COLLECTIONS_REGISTRY


def register_all_ogc_routes(api):
    """
    Register all OGC routers from the global registry on the provided Ninja API.
    """
    for collection_id, router in OGC_ROUTERS_REGISTRY.items():
        api.add_router(f"/collections/{collection_id}", router)
    # Also register the global collections endpoint at /collections
    api.add_router("/collections", global_ogc_router)
