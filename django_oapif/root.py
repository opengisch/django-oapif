from django.http import HttpRequest
from ninja import Router

from django_oapif.collections import OAPIFLink
from django_oapif.schema import OAPIFRoot


def create_root_router():
    router = Router()

    @router.get("")
    def root(request: HttpRequest):
        return OAPIFRoot(
            title="self.title",
            description="self.description",
            links=[
                OAPIFLink(
                    href=request.build_absolute_uri(""),
                    rel="self",
                    type="application/json",
                    title="this document",
                ),
                OAPIFLink(
                    href=request.build_absolute_uri("openapi.json"),
                    rel="service-desc",
                    type="application/vnd.oai.openapi+json;version=3.0",
                    title="the API definition",
                ),
                OAPIFLink(
                    href=request.build_absolute_uri("conformance"),
                    rel="conformance",
                    type="application/json",
                    title="OGC API conformance classes implemented by this server",
                ),
                OAPIFLink(
                    href=request.build_absolute_uri("collections"),
                    rel="data",
                    type="application/json",
                    title="Information about the feature collections",
                ),
            ],
        )

    return router
