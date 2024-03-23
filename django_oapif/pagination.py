from django.http import HttpResponse
from rest_framework import pagination
from rest_framework.response import Response
from rest_framework.utils.serializer_helpers import ReturnList


class OapifPagination(pagination.LimitOffsetPagination):
    """OAPIF-compatible django_oapif_tests rest paginator"""

    default_limit = 1000

    def get_paginated_response(self, data):
        if isinstance(data, ReturnList):
            number_returned = len(data)

            extra_params = {"features": [*data]}
        else:
            number_returned = len(data["features"])
            extra_params = {**data}

        return Response(
            {
                "links": [
                    {
                        "type": "application/geo+json",
                        "rel": "next",
                        "title": "items (next)",
                        "href": self.get_next_link(),
                    },
                    {
                        "type": "application/geo+json",
                        "rel": "previous",
                        "title": "items (previous)",
                        "href": self.get_previous_link(),
                    },
                ],
                "numberReturned": number_returned,
                "numberMatched": self.count,
                **extra_params,
            }
        )

    def get_schema_operation_parameters(self, view):
        params = super().get_schema_operation_parameters(view)
        for param in params:
            if param["name"] in ("limit", "offset") and "style" not in param:
                # The OGC conformance test requires `style: form` to be specified in the OpenAPI schema,
                # even though it is the default style.
                # see https://swagger.io/docs/specification/serialization/
                param["style"] = "form"
        return params


class HighPerfPagination(pagination.LimitOffsetPagination):
    """OAPIF-compatible django_oapif_tests rest paginator, tailored for the high performance version where data is pre-concatenated json"""

    def get_paginated_response(self, data):
        # FIXME: this probably is a bug, since `data` is a string, it is not the number of features
        number_returned = len(data)
        data = f'"type": "FeatureCollection", "features": [{",".join(data)}]'

        return HttpResponse(
            f"""{{
                "links": [
                    {{
                        "type": "application/geo+json",
                        "rel": "next",
                        "title": "items (next)",
                        "href": "{self.get_next_link()}"
                    }},
                    {{
                        "type": "application/geo+json",
                        "rel": "previous",
                        "title": "items (previous)",
                        "href": "{self.get_previous_link()}"
                    }}
                ],
                "numberReturned": {number_returned},
                "numberMatched": {self.count},
                {data}}}
            """
        )
