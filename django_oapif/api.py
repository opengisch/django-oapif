from typing import Dict, Type

from django.db import models
from ninja import NinjaAPI

from django_oapif.collections import (
    OAPIFCollectionEntry,
    create_collection_router,
    create_collections_router,
)
from django_oapif.conformance import create_conformance_router
from django_oapif.permissions import AllowAny, BasePermission
from django_oapif.root import create_root_router


class OAPIF:

    def __init__(self):
        self.api = NinjaAPI()
        self.collections: Dict[str, OAPIFCollectionEntry] = {}
        self.api.add_router("/", create_root_router())
        self.api.add_router("/conformance", create_conformance_router())
        self.api.add_router("/collections", create_collections_router(self.collections))

    def register(
            self,
            /,
            id: str | None = None,
            title: str | None = None,
            description: str | None = None,
            geometry_field: str = "geom",
            properties_fields: list[str] | None = None,
            auth: Type[BasePermission] = AllowAny,
    ):
        def decorator(model_class: models.Model):
            collection_id = id or model_class._meta.label_lower
            self.collections[collection_id] = OAPIFCollectionEntry(
                model_class=model_class,
                id=collection_id,
                title=title,
                description=description,
                geometry_field=geometry_field,
                properties_fields=properties_fields,
                auth=auth,
            )
            
            return model_class
        
        return decorator

    def _add_collections_routers(self):
        for collection_id, collection_entry in self.collections.items():
            self.api.add_router(
                f"/collections/{collection_id}",
                create_collection_router(collection_entry)
            )

    @property
    def urls(self):
        self._add_collections_routers()
        return self.api.urls
