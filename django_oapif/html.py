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
    """
    The type of a property of a JSON schema with its format, a geometry having a format only, and the types of a
    union.
    """
    types = [member for member in schema.get("anyOf", [schema]) if member.get("type") != "null"]
    return " | ".join(
        f"{member['type']} ({member['format']})"
        if "type" in member and "format" in member
        else member.get("type") or member.get("format") or "any"
        for member in types
    )


# the keywords of a property that the schema pages give a column of their own, the position being the order of rows
COLUMN_KEYWORDS = {
    "title",
    "description",
    "type",
    "format",
    "anyOf",
    "$ref",
    "x-ogc-role",
    "x-ogc-collectionId",
    "readOnly",
    "default",
    "x-ogc-propertySeq",
}


def schema_properties(schema: dict) -> list[dict[str, Any]]:
    """
    The properties of a JSON schema as the schema pages show them. The keywords without a column are listed as the
    constraints of the property, whatever they are, so that a page leaves out nothing its schema says, even the
    keywords a collection adds.
    """
    required = set(schema.get("required", ()))
    properties = []
    for name, prop in schema["properties"].items():
        collections = prop.get("x-ogc-collectionId", [])
        properties.append({
            "name": name,
            "title": prop.get("title"),
            "description": prop.get("description"),
            "type": schema_type(prop),
            "ref": prop.get("$ref"),
            "role": prop.get("x-ogc-role"),
            "collections": [collections] if isinstance(collections, str) else collections,
            "required": name in required,
            "read_only": prop.get("readOnly", False),
            # written as in the JSON, where an empty string still shows
            "default": json.dumps(prop["default"], ensure_ascii=False) if "default" in prop else None,
            "constraints": [(key, as_text(value)) for key, value in prop.items() if key not in COLUMN_KEYWORDS],
        })
    return properties
