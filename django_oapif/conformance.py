from django.http import HttpRequest
from ninja import Router

from django_oapif.collections import accepts_html
from django_oapif.html import html_response
from django_oapif.schema import OAPIFConformance


def create_conformance_router(*, title: str):
    router = Router()

    @router.get("", response=OAPIFConformance, operation_id="get_conformance")
    def conformance(request: HttpRequest):
        response = OAPIFConformance(
            conformsTo=[
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/core",
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/json",
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/landing-page",
                "http://www.opengis.net/spec/ogcapi-common-2/1.0/conf/collections",
                "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
                "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
                # django-ninja serves OpenAPI 3.1, which only the 1.1 draft of Features Part 1 has a class for:
                # Common Part 1 and Features Part 1 1.0 know OpenAPI 3.0 alone
                # (see docs/content/contributing/conformance.md)
                "http://www.opengis.net/spec/ogcapi-features-1/1.1/conf/oas31",
                "http://www.opengis.net/spec/ogcapi-features-2/1.0/conf/crs",
                # QGIS only sends a layer filter to the server with the filter classes of Part 3 and basic-cql2,
                # and each of the CQL2 classes below lets it send more of the filter
                "http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/queryables",
                "http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/filter",
                "http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/features-filter",
                "http://www.opengis.net/spec/cql2/1.0/conf/cql2-text",
                "http://www.opengis.net/spec/cql2/1.0/conf/basic-cql2",
                "http://www.opengis.net/spec/cql2/1.0/conf/advanced-comparison-operators",
                "http://www.opengis.net/spec/cql2/1.0/conf/case-insensitive-comparison",
                "http://www.opengis.net/spec/cql2/1.0/conf/basic-spatial-functions",
                "http://www.opengis.net/spec/ogcapi-features-4/1.0/conf/create-replace-delete",
                "http://www.opengis.net/spec/ogcapi-features-4/1.0/conf/update",
                "http://www.opengis.net/spec/ogcapi-features-4/1.0/conf/features",
                "http://www.opengis.net/spec/ogcapi-features-5/1.0/conf/core-roles-features",
                "http://www.opengis.net/spec/ogcapi-features-5/1.0/conf/feature-references",
                "http://www.opengis.net/spec/ogcapi-features-5/1.0/conf/returnables-and-receivables",
                "http://www.opengis.net/spec/ogcapi-features-5/1.0/conf/schemas",
                # the profile query parameter, which Part 5 now specifies under the name of Common Part 3, as
                # ldproxy declares it
                "http://www.opengis.net/spec/ogcapi-common-3/1.0/conf/profile-parameter",
                # JSON-FG, which serves the curves in "place", in the GeoJSON profile that parameter asks for
                "http://www.opengis.net/spec/json-fg-1/1.0/conf/core",
                "http://www.opengis.net/spec/json-fg-1/1.0/conf/circular-arcs",
                "http://www.opengis.net/spec/json-fg-1/1.0/conf/profiles",
                "http://www.opengis.net/spec/json-fg-1/1.0/conf/api",
            ]
        )
        if accepts_html(request):
            return html_response(request, "conformance.html", {"conformance": response}, title=title)
        return response

    return router
