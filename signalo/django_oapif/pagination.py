from rest_framework import pagination
from rest_framework.response import Response


class CustomPagination(pagination.LimitOffsetPagination):
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
                **data,
            }
        )
