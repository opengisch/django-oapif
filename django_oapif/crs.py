import re

# taken from https://github.com/geopython/pygeoapi/blob/953b6fa74d2ce292d8f566c4f4d3bcb4161d6e95/pygeoapi/util.py#L90

CRS_AUTHORITY = ["EPSG", "OGC"]
CRS_URI_PATTERN = re.compile(
    rf"^http://www.opengis\.net/def/crs/" rf"(?P<auth>{'|'.join(CRS_AUTHORITY)})/" rf"[\d|\.]+?/(?P<code>\w+?)$"
)


def get_srid_from_uri(uri: str) -> int:
    if (result := CRS_URI_PATTERN.match(uri)):
        auth, code = result.groups()
        if auth == "OGC" and code in ("CRS84", "CRS84h"):
            return 4979
        elif auth == "EPSG" and code.isnumeric():
            return int(code)
        else:
            msg = f"CRS could not be identified from URI (Authority: {auth}, Code: {code})."
            raise RuntimeError(msg)
    else:
        msg = (
            f"CRS could not be identified from URI {uri!r}. CRS URIs must follow the format "
            "'http://www.opengis.net/def/crs/{authority}/{version}/{code}' "
            "(see https://docs.opengeospatial.org/is/18-058r1/18-058r1.html#crs-overview)."  # noqa
        )
        raise AttributeError(msg)
