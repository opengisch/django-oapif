from typing import Dict

from django.db import models
from ninja import NinjaAPI

from django_oapif.collections import OAPIFCollectionEntry, create_collections_router
from django_oapif.conformance import create_conformance_router
from django_oapif.root import create_root_router


class OAPIF:

    def __init__(self):
        self.api = NinjaAPI()
        self.collections: Dict[str, OAPIFCollectionEntry] = {}
        self.api.add_router("", create_root_router())
        self.api.add_router("conformance", create_conformance_router())
        self.api.add_router("collections", create_collections_router(self.collections))

    def register(
            self,
            model_class: models.Model,
            /,
            id: str | None = None,
            title: str | None = None,
            description: str | None = None,
            geometry_field: str = "geom",
            properties_fields: list[str] = [],
    ):
        collection_id = id or model_class._meta.label_lower
        self.collections[collection_id] = OAPIFCollectionEntry(
            model_class=model_class,
            id=collection_id,
            title=title,
            description=description,
            geometry_field=geometry_field,
            properties_fields=properties_fields,
        )

    @property
    def urls(self):
        return self.api.urls
