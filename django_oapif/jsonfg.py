"""Minimal JSON-FG geometry dict <-> WKB conversions: reads ISO and EWKB, writes ISO. Stdlib only."""

from math import sqrt
from struct import pack, unpack_from

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
    # GeoJSON has no polyhedral types, so they are served as their closest equivalent, the way GDAL does
    15: ("MultiPolygon", "geoms"),  # PolyhedralSurface, a collection of Polygons
    16: ("MultiPolygon", "geoms"),  # TIN, a collection of Triangles
    17: ("Polygon", "rings"),  # Triangle, laid out exactly like a Polygon
}
# GeoJSON puts homogeneous multi-parts under "coordinates", curves under "geometries"
_FLATTEN = {"MultiPoint", "MultiLineString", "MultiPolygon"}
# JSON-FG allows 5 arcs in a CircularString: a longer one is served as the CompoundCurve of its arcs,
# 5 at a time, which draws the very same curve
_MAX_ARC_POINTS = 11
# below this, PostGIS takes the ends of an arc for the same point, and its points for aligned ones
_EPSILON_SQLMM = 1e-8


def _coords(buf, off, n, dim, e, bounds=None):
    vals = unpack_from(f"{e}{n * dim}d", buf, off)
    if bounds is not None and n:
        xs, ys = vals[0::dim], vals[1::dim]
        bounds.append((min(xs), min(ys), max(xs), max(ys)))
    return [list(vals[i : i + dim]) for i in range(0, len(vals), dim)], off + 8 * n * dim


def _side(x1, y1, x2, y2, x, y):
    """Which side of the line from 1 to 2 the point is on: -1, 0 on it, or 1."""
    side = (x - x1) * (y2 - y1) - (x2 - x1) * (y - y1)
    return (side > 0) - (side < 0)


def _arc_box(x1, y1, x2, y2, x3, y3):
    """
    The box of the arc from 1 through 2 to 3, computed as PostGIS does, so that it comes out the same: its
    circle reaches beyond the ends on the side of the chord where the middle point is.
    """
    if abs(x1 - x3) < _EPSILON_SQLMM and abs(y1 - y3) < _EPSILON_SQLMM:
        # a full circle, whose middle point is the opposite of its ends
        cx, cy = x1 + (x2 - x1) / 2.0, y1 + (y2 - y1) / 2.0
    else:
        dx21, dy21, dx31, dy31 = x2 - x1, y2 - y1, x3 - x1, y3 - y1
        h21, h31 = dx21**2 + dy21**2, dx31**2 + dy31**2
        d = 2 * (dx21 * dy31 - dx31 * dy21)
        if abs(d) < _EPSILON_SQLMM:
            # aligned points, a straight segment
            return min(x1, x3), min(y1, y3), max(x1, x3), max(y1, y3)
        cx = x1 + (h21 * dy31 - h31 * dy21) / d
        cy = y1 - (h21 * dx31 - h31 * dx21) / d
    r = sqrt((cx - x1) ** 2 + (cy - y1) ** 2)
    if x1 == x3 and y1 == y3:
        return cx - r, cy - r, cx + r, cy + r
    xmin, ymin, xmax, ymax = min(x1, x3), min(y1, y3), max(x1, x3), max(y1, y3)
    middle = _side(x1, y1, x3, y3, x2, y2)
    if _side(x1, y1, x3, y3, cx - r, cy) == middle:
        xmin = cx - r
    if _side(x1, y1, x3, y3, cx, cy - r) == middle:
        ymin = cy - r
    if _side(x1, y1, x3, y3, cx + r, cy) == middle:
        xmax = cx + r
    if _side(x1, y1, x3, y3, cx, cy + r) == middle:
        ymax = cy + r
    return xmin, ymin, xmax, ymax


def _geom(buf, off, bounds=None):
    e = "<" if buf[off] == 1 else ">"
    (code,) = unpack_from(e + "I", buf, off + 1)
    off += 5
    if code & 0x20000000:  # EWKB SRID flag: only the outermost geometry carries it
        off += 4
    # EWKB flags Z/M in the high bits, ISO adds 1000/2000/3000 to the base code.
    # A geometry uses one convention or the other, so the two never contribute at once.
    dim = 2 + bool(code & 0x80000000) + bool(code & 0x40000000)
    code &= ~0xE0000000
    try:
        dim += (0, 1, 1, 2)[code // 1000]
        name, kind = _TYPES[code % 1000]
    except (IndexError, KeyError):
        raise ValueError(f"unsupported WKB geometry type {code}") from None

    if kind == "pt":
        pts, off = _coords(buf, off, 1, dim, e)
        empty = all(v != v for v in pts[0])  # POINT EMPTY is encoded as NaNs
        if bounds is not None and not empty:
            x, y = pts[0][:2]
            bounds.append((x, y, x, y))
        return {"type": name, "coordinates": [] if empty else pts[0]}, off

    (n,) = unpack_from(e + "I", buf, off)
    off += 4

    if kind == "pts":
        arcs = name == "CircularString"
        pts, off = _coords(buf, off, n, dim, e, None if arcs else bounds)
        if arcs and bounds is not None:
            bounds.extend(_arc_box(*pts[i][:2], *pts[i + 1][:2], *pts[i + 2][:2]) for i in range(0, n - 2, 2))
        if arcs and n > _MAX_ARC_POINTS:
            # each part starts on the last point of the previous one
            step = _MAX_ARC_POINTS - 1
            parts = [{"type": name, "coordinates": pts[i : i + _MAX_ARC_POINTS]} for i in range(0, n - 1, step)]
            return {"type": "CompoundCurve", "geometries": parts}, off
        return {"type": name, "coordinates": pts}, off

    if kind == "rings":
        rings = []
        for _ in range(n):
            (m,) = unpack_from(e + "I", buf, off)
            off += 4
            pts, off = _coords(buf, off, m, dim, e, bounds)
            rings.append(pts)
        return {"type": name, "coordinates": rings}, off

    parts = []
    for _ in range(n):
        part, off = _geom(buf, off, bounds)
        parts.append(part)
    if name == "CompoundCurve":
        # a CompoundCurve cannot hold another, so the parts of a long CircularString join its own
        parts = [member for part in parts for member in part.get("geometries", [part])]
    if name in _FLATTEN:
        return {"type": name, "coordinates": [p["coordinates"] for p in parts]}, off
    return {"type": name, "geometries": parts}, off


def loads(wkb, bounds: list | None = None):
    """
    Parse one ISO (or EWKB) geometry into a JSON-FG geometry dict. Given a list, adds to it the boxes
    (xmin, ymin, xmax, ymax) of its parts, whose union is the box PostGIS computes for it, arcs included.
    """
    return _geom(wkb, 0, bounds)[0]


# base type code of each JSON-FG type, for writing: the polyhedral ones are read as (Multi)Polygons
_CODES = {name: code for code, (name, _) in _TYPES.items() if code <= 12}


def _dimension(geometry):
    # the number of ordinates of its first position: all its positions have the same
    pending = [geometry]
    while pending:
        part = pending.pop()
        if "geometries" in part:
            pending.extend(part["geometries"])
            continue
        coordinates = part["coordinates"]
        while coordinates and isinstance(coordinates[0], (list, tuple)):
            coordinates = coordinates[0]
        if coordinates:
            return len(coordinates)
    return 2


def _positions(out, positions, dim):
    out += pack(f"<I{len(positions) * dim}d", len(positions), *(v for position in positions for v in position))


def _write(out, geometry, dim):
    name = geometry["type"]
    code = _CODES[name]
    kind = _TYPES[code][1]
    out += pack("<BI", 1, code + (dim - 2) * 1000)
    if kind == "pt":
        # POINT EMPTY is encoded as NaNs
        out += pack(f"<{dim}d", *(geometry["coordinates"] or [float("nan")] * dim))
    elif kind == "pts":
        _positions(out, geometry["coordinates"], dim)
    elif kind == "rings":
        out += pack("<I", len(geometry["coordinates"]))
        for ring in geometry["coordinates"]:
            _positions(out, ring, dim)
    else:
        if name in _FLATTEN:
            member = name.removeprefix("Multi")
            members = [{"type": member, "coordinates": coordinates} for coordinates in geometry["coordinates"]]
        else:
            members = geometry["geometries"]
        out += pack("<I", len(members))
        for part in members:
            _write(out, part, dim)


def dumps(geometry):
    """Write a JSON-FG geometry dict as ISO WKB."""
    out = bytearray()
    _write(out, geometry, _dimension(geometry))
    return bytes(out)
