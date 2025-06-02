from django.http import HttpRequest
from ninja import Router

from django_oapif.schema import OAPIFConformance


def create_conformance_router():
    router = Router()

    @router.get("", response=OAPIFConformance)
    def conformance(request: HttpRequest):
        return OAPIFConformance(
            conformsTo=[
                "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
                "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
                "http://www.opengis.net/spec/ogcapi-features-2/1.0/conf/crs",
                "http://www.opengis.net/spec/ogcapi-features-1/1.0/req/oas30",
                "http://www.opengis.net/spec/ogcapi-features-4/1.0/req/create-replace-delete"
            ]
        )

    return router
