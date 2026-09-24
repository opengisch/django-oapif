"""Minimal JSON-FG geometry dict <-> WKB conversions: reads ISO and EWKB, writes ISO. Stdlib only."""

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


def _coords(buf, off, n, dim, e):
    vals = unpack_from(f"{e}{n * dim}d", buf, off)
    return [list(vals[i : i + dim]) for i in range(0, len(vals), dim)], off + 8 * n * dim


def _geom(buf, off):
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
        return {"type": name, "coordinates": [] if empty else pts[0]}, off

    (n,) = unpack_from(e + "I", buf, off)
    off += 4

    if kind == "pts":
        pts, off = _coords(buf, off, n, dim, e)
        if name == "CircularString" and n > _MAX_ARC_POINTS:
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
            pts, off = _coords(buf, off, m, dim, e)
            rings.append(pts)
        return {"type": name, "coordinates": rings}, off

    parts = []
    for _ in range(n):
        part, off = _geom(buf, off)
        parts.append(part)
    if name == "CompoundCurve":
        # a CompoundCurve cannot hold another, so the parts of a long CircularString join its own
        parts = [member for part in parts for member in part.get("geometries", [part])]
    if name in _FLATTEN:
        return {"type": name, "coordinates": [p["coordinates"] for p in parts]}, off
    return {"type": name, "geometries": parts}, off


def loads(wkb):
    """Parse one ISO (or EWKB) geometry into a JSON-FG geometry dict."""
    return _geom(wkb, 0)[0]


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
