from django.http import HttpRequest
from ninja import Router

from django_oapif.collections import OAPIFLink, accepts_html, html_link
from django_oapif.html import HTML_MEDIA_TYPE, html_response
from django_oapif.schema import OAPIFRoot
from django_oapif.utils import replace_query_param


def create_root_router(*, title: str, description: str, docs_url: str | None):
    router = Router()

    @router.get("", operation_id="get_root")
    def root(request: HttpRequest):
        links = [
            OAPIFLink(
                href=request.build_absolute_uri(""),
                rel="self",
                type="application/json",
                title="This document",
            ),
            html_link(replace_query_param(request, f="html"), "This document as HTML"),
            OAPIFLink(
                href=request.build_absolute_uri("openapi.json"),
                rel="service-desc",
                type="application/vnd.oai.openapi+json;version=3.0",
                title="The API definition",
            ),
        ]
        if docs_url:
            links.append(
                OAPIFLink(
                    href=request.build_absolute_uri(docs_url.lstrip("/")),
                    rel="service-doc",
                    type=HTML_MEDIA_TYPE,
                    title="The API documentation",
                )
            )
        links += [
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
        ]
        response = OAPIFRoot(title=title, description=description, links=links)
        if accepts_html(request):
            return html_response(request, "landing.html", {"root": response}, title=title)
        return response

    return router
