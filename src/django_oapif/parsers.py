from rest_framework.parsers import JSONParser


# Not exactly sure why, but OGCAPIF uses this content-type, not sure how
# it differs from redular application/json...
class GeojsonParser(JSONParser):
    media_type = "application/geo+json"
