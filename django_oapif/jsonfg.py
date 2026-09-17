"""Minimal ISO WKB -> JSON-FG geometry dict reader. Stdlib only."""

from struct import unpack_from

# base type code -> (JSON-FG name, structure)
#   "pts"  : count + flat coordinate run
#   "rings": count of rings, each a count + coordinate run
#   "geoms": count of fully-headered child geometries
_TYPES = {
    1: ("Point", "pt"),
    2: ("LineString", "pts"),
    3: ("Polygon", "rings"),
    4: ("MultiPoint", "geoms"),
    5: ("MultiLineString", "geoms"),
    6: ("MultiPolygon", "geoms"),
    7: ("GeometryCollection", "geoms"),
    8: ("CircularString", "pts"),
    9: ("CompoundCurve", "geoms"),
    10: ("CurvePolygon", "geoms"),
    11: ("MultiCurve", "geoms"),
    12: ("MultiSurface", "geoms"),
}
# GeoJSON puts homogeneous multi-parts under "coordinates", curves under "geometries"
_FLATTEN = {"MultiPoint", "MultiLineString", "MultiPolygon"}


def _coords(buf, off, n, dim, e):
    vals = unpack_from(f"{e}{n * dim}d", buf, off)
    return [list(vals[i : i + dim]) for i in range(0, len(vals), dim)], off + 8 * n * dim


def _geom(buf, off):
    e = "<" if buf[off] == 1 else ">"
    (code,) = unpack_from(e + "I", buf, off + 1)
    off += 5
    if code & 0x20000000:  # EWKB SRID flag: skip the srid, keep the base type
        off += 4
        code &= ~0xE0000000
    name, kind = _TYPES[code % 1000]
    dim = (2, 3, 3, 4)[code // 1000]  # ISO: +1000 Z, +2000 M, +3000 ZM

    if kind == "pt":
        pts, off = _coords(buf, off, 1, dim, e)
        empty = all(v != v for v in pts[0])  # POINT EMPTY is encoded as NaNs
        return {"type": name, "coordinates": [] if empty else pts[0]}, off

    (n,) = unpack_from(e + "I", buf, off)
    off += 4

    if kind == "pts":
        pts, off = _coords(buf, off, n, dim, e)
        return {"type": name, "coordinates": pts}, off

    if kind == "rings":
        rings = []
        for _ in range(n):
            (m,) = unpack_from(e + "I", buf, off)
            off += 4
            pts, off = _coords(buf, off, m, dim, e)
            rings.append(pts)
        return {"type": name, "coordinates": rings}, off

    parts = []
    for _ in range(n):
        part, off = _geom(buf, off)
        parts.append(part)
    if name in _FLATTEN:
        return {"type": name, "coordinates": [p["coordinates"] for p in parts]}, off
    return {"type": name, "geometries": parts}, off


def loads(wkb):
    """Parse one ISO (or EWKB) geometry into a JSON-FG geometry dict."""
    return _geom(wkb, 0)[0]
