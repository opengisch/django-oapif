from django.http import HttpResponse, StreamingHttpResponse
from json_stream import streamable_dict, streamable_list
from json_stream.dump import JSONStreamEncoder
from rest_framework import pagination
from rest_framework.response import Response
from rest_framework.utils.serializer_helpers import ReturnList


class OapifPagination(pagination.LimitOffsetPagination):
    """OAPIF-compatible django rest paginator"""

    default_limit = 1000

    @streamable_dict
    def streamable_payload(self, number_returned, data):
        payload = {
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
            "features": streamable_list(data),
        }

        for k, v in payload.items():
            yield k, v

    def get_paginated_response(self, data):
        if isinstance(data, ReturnList):
            number_returned = len(data)

            if True:
                streamable_payload = self.streamable_payload(number_returned, data)
                iterator = JSONStreamEncoder().iterencode(streamable_payload)
                return StreamingHttpResponse(iterator, content_type="application/json")
            else:
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


class HighPerfPagination(pagination.LimitOffsetPagination):
    """OAPIF-compatible django rest paginator, tailored for the high performance version where data is pre-concatenated json"""

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
