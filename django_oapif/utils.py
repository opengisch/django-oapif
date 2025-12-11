from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from django.http import HttpRequest


def replace_query_param(request: HttpRequest, **kwargs: Any) -> str:
    url = request.build_absolute_uri()
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    # Update or remove parameters
    for k, v in kwargs.items():
        if v is None:
            query.pop(k)
        else:
            query[k] = [str(v)]
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=new_query))
