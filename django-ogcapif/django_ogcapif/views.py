from django.urls import NoReverseMatch
from rest_framework import exceptions, permissions, routers, views
from rest_framework.response import Response
from rest_framework.reverse import reverse


class RootView(views.APIView):
    """OAPIF index view.

    This is currently more or less static
    """

    title = None
    description = None
    permission_classes = (permissions.AllowAny,)

    def get(self, request, *args, **kwargs):
        return Response(
            {
                "title": self.title,
                "description": self.description,
                "links": [
                    {
                        "href": request.build_absolute_uri(""),
                        "rel": "self",
                        "type": "application/json",
                        "title": "this document",
                    },
                    {
                        "href": request.build_absolute_uri("api"),
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
        )


class ConformanceView(views.APIView):
    """Conformance view as defined by OGCAPI's specifications."""

    permission_classes = (permissions.AllowAny,)

    def get(self, request, *args, **kwargs):
        return Response(
            {
                "conformsTo": [
                    # copied from pygeoapi, commented out what we don't support
                    "http://www.opengis.net/spec/ogcapi-features-4/1.0/conf/create-replace-delete",
                    # "http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/json",
                    # "http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/oas30",
                    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
                    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/oas30",
                    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/html",
                    # "http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/core",
                    "http://www.opengis.net/spec/ogcapi-common-2/1.0/conf/collections",
                    # "http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/core",
                    # "http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/ogc-process-description",
                    "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/core",
                    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
                    # additionnal
                    "http://www.opengis.net/spec/ogcapi-features-2/1.0/req/crs",
                ]
            }
        )


class CollectionsView(routers.APIRootView):
    """Collections index view.

    This is extends DRF's APIRootView as it works in the same way, but just
    adds some more elements.
    """

    schema = None  # exclude from schema
    registry = None
    permission_classes = (permissions.AllowAny,)

    def get(self, request, *args, **kwargs):
        collections = []
        namespace = request.resolver_match.namespace
        for prefix, Viewset, basename in self.registry:
            url_name = f"{basename}-list"
            if namespace:
                url_name = namespace + ":" + url_name
            try:
                url = reverse(
                    url_name,
                    args=args,
                    kwargs=kwargs,
                    request=request,
                    format=kwargs.get("format", None),
                )
            except NoReverseMatch:
                # Don't bail out if eg. no list routes exist, only detail routes.
                continue

            # Instantiating the viewset
            viewset = Viewset(request=request)

            # Returning only viewsets that match the request's permissions
            try:
                viewset.check_permissions(request)
                collections.append(viewset._describe(request, base_url=f"collections/"))
            except (
                exceptions.NotAuthenticated,
                exceptions.AuthenticationFailed,
                exceptions.PermissionDenied,
            ):
                continue

        return Response(
            {
                "links": [
                    {
                        "href": request.build_absolute_uri(""),
                        "rel": "self",
                        "type": "application/json",
                        "title": "this document",
                    },
                ],
                "collections": collections,
            }
        )
