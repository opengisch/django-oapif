from django.http import HttpResponse
from rest_framework import pagination
from rest_framework.response import Response


class OapifPagination(pagination.LimitOffsetPagination):
    def get_paginated_response(self, data):
        if type(data) == dict:
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
                    **data,
                }
            )

        else:
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
                    {data}}}"""
            )
