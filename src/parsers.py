from rest_framework.parsers import JSONParser

# OGCAPIF uses these content-types, not sure how they differs from
# regular application/json...


class GeojsonParser(JSONParser):
    media_type = "application/geo+json"


class JSONMergePatchParser(JSONParser):
    media_type = "application/merge-patch+json"
