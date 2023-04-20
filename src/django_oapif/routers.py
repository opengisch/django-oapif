from django.conf import settings
from django.urls import path
from rest_framework import routers
from rest_framework.schemas import SchemaGenerator, get_schema_view
from rest_framework.schemas.views import SchemaView
from rest_framework.urlpatterns import format_suffix_patterns

from .views import CollectionsView, ConformanceView, RootView


class OAPIFRouter(routers.SimpleRouter):
    """Router to explose a OAPIF Endpoint.

    This works just like a regular DRF router, where you need
    to register your viewsets using `router.register(...)`.

    It will take care of creating the standard OAPIF routes according
    to https://app.swaggerhub.com/apis/cportele/ogcapi-features-1-example2/1.0.0#/Capabilities/getCollections
    """

    include_format_suffixes = True
    # default_schema_renderers = None
    APISchemaView = SchemaView
    SchemaGenerator = SchemaGenerator

    oapif_title = getattr(settings, "OAPIF_TITLE", "Django OGC Api Services Endpoint")
    oapif_description = getattr(settings, "OAPIF_DESCRIPTION", "No description")

    # This is the list of routes that get generated for viewsets.
    # It is adapted from routers.SimpleRouter but adapts URLs to the specs, and adds the describe URL
    # NOTE : we don't support routes created with @action(...), if needed copy implementation from SimpleRouter.routes here
    routes = [
        # List route.
        routers.Route(
            url=r"^collections/{prefix}/items{trailing_slash}$",
            mapping={
                "get": "list",
                "post": "create",
            },
            name="{basename}-list",
            detail=False,
            initkwargs={"suffix": "List"},
        ),
        # Detail route.
        routers.Route(
            url=r"^collections/{prefix}/items/{lookup}{trailing_slash}$",
            mapping={
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            },
            name="{basename}-detail",
            detail=True,
            initkwargs={"suffix": "Instance"},
        ),
        # Describe route.
        routers.Route(
            url=r"^collections/{prefix}{trailing_slash}$",
            mapping={
                "get": "describe",
            },
            name="{basename}-describe",
            detail=False,
            initkwargs={"suffix": "List"},
        ),
    ]

    def __init__(self):
        super().__init__(trailing_slash=False)

    @property
    def urlpatterns(self):
        """Alias for self.urls, so that we can provide this instance directly to get_schema_view()"""
        return self.urls

    def get_urls(self):
        """Return all OAPIF routes"""

        root_view = RootView.as_view(
            title=self.oapif_title,
            description=self.oapif_description,
        )
        conformance_view = ConformanceView.as_view()
        collections_view = CollectionsView.as_view(registry=self.registry)
        schema_view = get_schema_view(
            title=self.oapif_title,
            description=self.oapif_description,
            version="1.0.0",
            urlconf=self,
        )

        urls = [
            path("", root_view, name="capabilities"),
            path("conformance", conformance_view, name="conformance"),
            path("collections", collections_view, name="collections"),
            path("api", schema_view, name="service-desc"),
            *super().get_urls(),
        ]

        if self.include_format_suffixes:
            urls = format_suffix_patterns(urls)
        return urls
