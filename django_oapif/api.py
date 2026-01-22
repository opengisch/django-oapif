from collections.abc import Sequence
from importlib.metadata import version
from typing import (
    Any,
    Callable,
    Optional,
    Union,
)

from django.db import models
from django.urls import URLPattern, URLResolver
from ninja import NinjaAPI
from ninja.constants import NOT_SET, NOT_SET_TYPE
from ninja.openapi.docs import DocsBase, Swagger
from ninja.parser import Parser
from ninja.renderers import BaseRenderer
from ninja.router import Router
from ninja.throttling import BaseThrottle
from ninja.types import DictStrAny, TCallable

from django_oapif.auth import DjangoAuth
from django_oapif.collections import (
    OAPIFCollectionEntry,
    create_collection_router,
    create_collections_router,
)
from django_oapif.conformance import create_conformance_router
from django_oapif.handler import DjangoModelPermissionsOrAnonReadOnly, QueryHandler
from django_oapif.root import create_root_router


class OAPIF:
    """The OAPIF class wraps a Ninja API that will expose the OGC API Features endpoints.

    The parameters will be passed to the [NinjaApi constructor](https://django-ninja.dev/reference/api/#ninja.main.NinjaAPI).
    By default `auth` will be set to use the same authentication method as Django, but
     it may be configured differently ([see Ninja authentication documentation](https://django-ninja.dev/guides/authentication/)).
     Django OAPIF also provides a utility to use HTTP Basic Auth as an authentication method.

    Examples:
        >>> from django_oapif import OAPIF
        >>> from django_oapif.auth import BasicAuth, DjangoAuth
        >>>
        >>> api = OAPIF(auth=[BasicAuth(), DjangoAuth()])
    """

    def __init__(
        self,
        *,
        title: str = "OAPIF",
        version: str = version("django-oapif"),
        description: str = "",
        docs: DocsBase = Swagger(),
        docs_url: Optional[str] = "/docs",
        docs_decorator: Optional[Callable[[TCallable], TCallable]] = None,
        servers: Optional[list[DictStrAny]] = None,
        urls_namespace: Optional[str] = None,
        auth: Optional[Union[Sequence[Callable], Callable, NOT_SET_TYPE]] = NOT_SET,
        throttle: Union[BaseThrottle, list[BaseThrottle], NOT_SET_TYPE] = NOT_SET,
        renderer: Optional[BaseRenderer] = None,
        parser: Optional[Parser] = None,
        default_router: Optional[Router] = None,
        openapi_extra: Optional[dict[str, Any]] = None,
    ) -> None:
        self.api = NinjaAPI(
            title=title,
            version=version,
            description=description,
            docs=docs,
            docs_url=docs_url,
            docs_decorator=docs_decorator,
            servers=servers,
            urls_namespace=urls_namespace,
            auth=auth or [DjangoAuth()],
            throttle=throttle,
            renderer=renderer,
            parser=parser,
            default_router=default_router,
            openapi_extra=openapi_extra,
        )
        self.collections: dict[str, OAPIFCollectionEntry] = {}
        self.api.add_router("/", create_root_router(title=title, description=description))
        self.api.add_router("/conformance", create_conformance_router())
        self.api.add_router("/collections", create_collections_router(self.collections))

    def register(
        self,
        model_class: type[models.Model],
        /,
        id: str | None = None,
        title: str | None = None,
        description: str = "",
        geometry_field: str | None = "geom",
        properties_fields: list[str] | None = None,
        handler: type[QueryHandler] = DjangoModelPermissionsOrAnonReadOnly,
    ) -> None:
        """Register a model to expose as an OGC API Features collection.

        Args:
            id:
                The collection identifier when calling the API, eg: `https://example.com/oapif/collections/<id>/items`.
                If not defined, will be set to `model_class._meta.label_lower`.
            title:
                The collection title. If not defined, will be set to `model_class._meta.label`.
            description:
                The collection description.
            geometry_field:
                The collection geometry field. Must be set to `None` for collections without a geometry.
            properties_fields:
                The list of fields that will be exposed as feature properties. If not defined, all fields will be used.
        """
        collection_id = id or model_class._meta.label_lower
        collection_title = title or model_class._meta.label
        self.collections[collection_id] = OAPIFCollectionEntry(
            model_class=model_class,
            id=collection_id,
            title=collection_title,
            description=description,
            geometry_field=geometry_field,
            properties_fields=properties_fields,
            handler=handler(model_class),
        )

    def _add_collections_routers(self) -> None:
        for collection_id, collection_entry in self.collections.items():
            self.api.add_router(f"/collections/{collection_id}", create_collection_router(collection_entry))

    @property
    def urls(self) -> tuple[list[URLResolver | URLPattern], str, str]:
        self._add_collections_routers()
        return self.api.urls
