import json
from importlib.metadata import version
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.cache import patch_vary_headers

from django_oapif.utils import replace_query_param

HTML_MEDIA_TYPE = "text/html"
VERSION = version("django-oapif")


def html_response(request: HttpRequest, template: str, context: dict[str, Any], *, title: str) -> HttpResponse:
    """
    A page of the HTML encoding, for a browser. Its link to the JSON asks for it with `f=json`, as a browser
    would get the page again otherwise.
    """
    response = render(
        request,
        f"django_oapif/{template}",
        {
            "api_title": title,
            "root_url": reverse(f"{request.resolver_match.namespace}:api-root"),
            "json_url": replace_query_param(request, f="json"),
            "version": VERSION,
            **context,
        },
    )
    # the same URL serves the JSON too: a cache must not hand one to a request for the other
    patch_vary_headers(response, ["Accept"])
    return response


def as_text(value: Any) -> str:
    """A property value as a page shows it: strings as they are, and the other values as in the JSON."""
    if value is None:
        return ""
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def schema_type(schema: dict) -> str:
    """The type of a property of a JSON schema, its format when it has one, and the types of a union."""
    types = [member for member in schema.get("anyOf", [schema]) if member.get("type") != "null"]
    return " | ".join(member.get("format") or member.get("type") or "any" for member in types)
