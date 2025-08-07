from typing import Any, Optional

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import models
from django.http import HttpRequest
from ninja import NinjaAPI
from ninja.security import APIKeyCookie, HttpBasicAuth

from django_oapif.collections import (
    OAPIFCollectionEntry,
    create_collection_router,
    create_collections_router,
)
from django_oapif.conformance import create_conformance_router
from django_oapif.permissions import (
    BasePermission,
    DjangoModelPermissionsOrAnonReadOnly,
)
from django_oapif.root import create_root_router


class BasicAuth(HttpBasicAuth):
    def authenticate(self, request, username, password):
        if user := authenticate(request, username=username, password=password):
            request.user = user
        return request.user


class DjangoAuth(APIKeyCookie):
    param_name: str = settings.SESSION_COOKIE_NAME

    def authenticate(self, request: HttpRequest, key: Optional[str]) -> Optional[Any]:
        return request.user


class OAPIF:
    """Ninja API."""

    def __init__(self, auth=[BasicAuth(), DjangoAuth()], **kwargs):
        self.api = NinjaAPI(auth=auth, **kwargs)
        self.collections: dict[str, OAPIFCollectionEntry] = {}
        self.api.add_router("/", create_root_router())
        self.api.add_router("/conformance", create_conformance_router())
        self.api.add_router("/collections", create_collections_router(self.collections))

    def register(
        self,
        /,
        id: str | None = None,
        title: str | None = None,
        description: str | None = None,
        geometry_field: str | None = "geom",
        properties_fields: list[str] | None = None,
        auth: type[BasePermission] = DjangoModelPermissionsOrAnonReadOnly,
    ):
        """Register a Django model in the API."""

        def decorator(model_class: models.Model):
            collection_id = id or model_class._meta.label_lower
            collection_title = id or model_class._meta.label
            self.collections[collection_id] = OAPIFCollectionEntry(
                model_class=model_class,
                id=collection_id,
                title=collection_title,
                description=description,
                geometry_field=geometry_field,
                properties_fields=properties_fields,
                auth=auth,
            )

            return model_class

        return decorator

    def _add_collections_routers(self):
        for collection_id, collection_entry in self.collections.items():
            self.api.add_router(f"/collections/{collection_id}", create_collection_router(collection_entry))

    @property
    def urls(self):
        self._add_collections_routers()
        return self.api.urls
