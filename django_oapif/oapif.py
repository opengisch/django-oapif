from collections.abc import Callable, Iterable, Sequence
from importlib.metadata import version
from typing import (
    Any,
)

from django.db.models import Model
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
    create_collections_router,
)
from django_oapif.conformance import create_conformance_router
from django_oapif.handler import OapifCollection
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
        docs_url: str | None = "/docs",
        docs_decorator: Callable[[TCallable], TCallable] | None = None,
        servers: list[DictStrAny] | None = None,
        urls_namespace: str | None = None,
        auth: Sequence[Callable] | Callable | NOT_SET_TYPE | None = NOT_SET,
        throttle: BaseThrottle | list[BaseThrottle] | NOT_SET_TYPE = NOT_SET,
        renderer: BaseRenderer | None = None,
        parser: Parser | None = None,
        default_router: Router | None = None,
        openapi_extra: dict[str, Any] | None = None,
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
        self.collections: dict[str, OapifCollection] = {}
        self.api.add_router("/", create_root_router(title=title, description=description))
        self.api.add_router("/conformance", create_conformance_router())
        self.api.add_router("/collections", create_collections_router(self.collections))

    def register_collection(
        self,
        models: type[Model] | Iterable[type[Model]],
        oapif_class: type[OapifCollection] = OapifCollection,
    ) -> None:
        """Register a model to expose as an OGC API Features collection."""

        for model in models if isinstance(models, Iterable) else [models]:
            collection = oapif_class(model)
            self.collections[collection.id] = collection

    def register[T: OapifCollection](self, *models: type[Model]) -> Callable[[type[T]], type[T]]:
        """Register a model to expose as an OGC API Features collection."""

        def wrapper(oapif_class: type[T]) -> type[T]:
            for model in models:
                collection = oapif_class(model)
                self.collections[collection.id] = collection
            return oapif_class

        return wrapper

    @property
    def urls(self) -> tuple[list[URLResolver | URLPattern], str, str]:
        return self.api.urls
