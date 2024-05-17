import re

from pyproj import CRS

# taken from https://github.com/geopython/pygeoapi/blob/953b6fa74d2ce292d8f566c4f4d3bcb4161d6e95/pygeoapi/util.py#L90


CRS_AUTHORITY = [
    "AUTO",
    "EPSG",
    "OGC",
]
CRS_URI_PATTERN = re.compile(
    rf"^http://www.opengis\.net/def/crs/" rf"(?P<auth>{'|'.join(CRS_AUTHORITY)})/" rf"[\d|\.]+?/(?P<code>\w+?)$"
)


def get_crs_from_uri(uri: str) -> CRS:
    """
    Get a `pyproj.CRS` instance from a CRS URI.
    Author: @MTachon

    :param uri: Uniform resource identifier of the coordinate
        reference system.
    :type uri: str

    :raises `CRSError`: Error raised if no CRS could be identified from the
        URI.

    :returns: `pyproj.CRS` instance matching the input URI.
    :rtype: `pyproj.CRS`
    """

    try:
        crs = CRS.from_authority(*CRS_URI_PATTERN.search(uri).groups())
    except RuntimeError:
        msg = (
            f"CRS could not be identified from URI {uri!r} "
            f"(Authority: {CRS_URI_PATTERN.search(uri).group('auth')!r}, "
            f"Code: {CRS_URI_PATTERN.search(uri).group('code')!r})."
        )
        raise RuntimeError(msg)
    except AttributeError:
        msg = (
            f"CRS could not be identified from URI {uri!r}. CRS URIs must "
            "follow the format "
            "'http://www.opengis.net/def/crs/{authority}/{version}/{code}' "
            "(see https://docs.opengeospatial.org/is/18-058r1/18-058r1.html#crs-overview)."  # noqa
        )
        raise AttributeError(msg)
    else:
        return crs
