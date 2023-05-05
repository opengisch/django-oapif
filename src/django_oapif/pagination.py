from django.http import HttpResponse
from rest_framework import pagination
from rest_framework.response import Response


class OapifPagination(pagination.LimitOffsetPagination):
    """OAPIF-compatible django rest paginator"""

    def get_paginated_response(self, data):
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
                "numberReturned": len(data["features"]),
                "numberMatched": self.count,
                **data,  # this looks to be unpacked by LimitOffsetPagination anyway
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
