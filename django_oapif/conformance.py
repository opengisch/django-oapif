from django.http import HttpRequest
from ninja import Router

from django_oapif.schema import OAPIFConformance


def create_conformance_router():
    router = Router()

    @router.get("", response=OAPIFConformance, operation_id="get_conformance")
    def conformance(request: HttpRequest):
        return OAPIFConformance(
            conformsTo=[
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/core",
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/json",
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/landing-page",
                "http://www.opengis.net/spec/ogcapi-common-2/1.0/conf/collections",
                "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
                "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
                # django-ninja serves OpenAPI 3.1, which only the 1.1 draft of Features Part 1 has a class for:
                # Common Part 1 and Features Part 1 1.0 know OpenAPI 3.0 alone (see docs/content/tests.md)
                "http://www.opengis.net/spec/ogcapi-features-1/1.1/conf/oas31",
                "http://www.opengis.net/spec/ogcapi-features-2/1.0/conf/crs",
                "http://www.opengis.net/spec/ogcapi-features-4/1.0/conf/create-replace-delete",
                "http://www.opengis.net/spec/ogcapi-features-4/1.0/conf/update",
                "http://www.opengis.net/spec/ogcapi-features-4/1.0/conf/features",
                "http://www.opengis.net/spec/ogcapi-features-5/1.0/conf/core-roles-features",
                "http://www.opengis.net/spec/ogcapi-features-5/1.0/conf/schemas",
            ]
        )

    return router
