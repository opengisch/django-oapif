import copy
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from django.http import HttpRequest
from ninja import Schema
from pydantic import create_model
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined


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


class PatchSchema[T: Schema]:
    """Make all fields in a schema optional by settings their default to None"""

    def __class_getitem__(cls, model: type[T]) -> type[T]:
        def make_field_optional(field: FieldInfo) -> tuple[Any, FieldInfo]:
            new = copy.deepcopy(field)
            if field.default is PydanticUndefined and field.default_factory is None:
                new.default = None
            return new.annotation, new

        return create_model(
            f"Partial{model.__name__}",
            __base__=model,
            __module__=model.__module__,
            **{field_name: make_field_optional(field_info) for field_name, field_info in model.model_fields.items()},  # type: ignore
        )  # type: ignore
