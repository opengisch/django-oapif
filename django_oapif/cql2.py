"""
CQL2 filters of OGC API - Features Part 3, as QGIS sends them for the subset string of a layer.

pygeofilter parses them, but they are not translated with its Django backend: it hands a name it does not know to
the ORM as it is, relations included, reads a BBOX in the CRS of the geometries, knows no CASEI, and its negations
match the null values, which neither CQL2 nor QGIS do.
"""

import os
import re
import struct
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import cache, reduce
from operator import and_, or_

from django.contrib.gis.db.models import GeometryField
from django.contrib.gis.geos import GEOSException, GEOSGeometry, Polygon
from django.db.models import F, Field, Q
from lark import Lark, v_args
from lark.exceptions import LarkError
from pygeofilter import ast, values
from pygeofilter.parsers.cql2_text import parser as cql2_text

from django_oapif import jsonfg
from django_oapif.crs import CRS84_SRID
from django_oapif.handler import reprojected


class FilterError(ValueError):
    """A filter that cannot be applied, for a reason the client can fix."""


# the lookups of the comparisons, <> being the negation of =
COMPARISONS = {
    ast.Equal: "exact",
    ast.NotEqual: "exact",
    ast.LessThan: "lt",
    ast.LessEqual: "lte",
    ast.GreaterThan: "gt",
    ast.GreaterEqual: "gte",
}
SPATIAL = {
    ast.GeometryIntersects: "intersects",
    ast.GeometryDisjoint: "disjoint",
    ast.GeometryContains: "contains",
    ast.GeometryWithin: "within",
    ast.GeometryTouches: "touches",
    ast.GeometryCrosses: "crosses",
    ast.GeometryOverlaps: "overlaps",
    ast.GeometryEquals: "equals",
}
# the lookups that differ once their operands are swapped, for a literal on the left
MIRRORED = {"lt": "gt", "lte": "gte", "gt": "lt", "gte": "lte", "contains": "within", "within": "contains"}
# a bool is an int, and a datetime a date
LITERALS = (str, int, float, date)


# cql2.lark, this transformer and parser() go once a release of pygeofilter has its pull requests #170, #171 and
# #172, for the parser of pygeofilter
class Transformer(cql2_text.CQLTransformer):
    """The one of pygeofilter, with the fixes of its pull requests that cql2.lark takes."""

    def SINGLE_QUOTED(self, token):
        # CQL2 escapes a quote as '' or \', and the other backslashes are left for LIKE, where they escape the next
        # character
        return re.sub(r"''|\\(.)", lambda m: "'" if m[0] == "''" or m[1] == "'" else m[0], token[1:-1], flags=re.DOTALL)

    @v_args(inline=True)
    def bbox(self, *coordinates):
        # minx, miny, maxx, maxy, or in 3D minx, miny, minz, maxx, maxy, maxz, whose elevations are dropped
        half = len(coordinates) // 2
        return values.Envelope(coordinates[0], coordinates[half], coordinates[1], coordinates[half + 1])


@cache
def parser() -> Lark:
    # the grammars it imports are the ones of pygeofilter
    parsers = os.path.dirname(os.path.dirname(cql2_text.__file__))
    with open(os.path.join(os.path.dirname(__file__), "cql2.lark")) as file:
        grammar = file.read()
    return Lark(grammar, parser="lalr", maybe_placeholders=False, transformer=Transformer(), import_paths=[parsers])


def parse(text: str):
    try:
        return parser().parse(text)
    except LarkError as e:
        raise FilterError(str(e).splitlines()[0]) from e


def like_regex(pattern: str) -> str:
    """
    The regular expression of a LIKE pattern: % stands for any characters, _ for one, and a backslash makes the
    next character an ordinary one. The other characters are escaped, which all of them can be with a backslash.
    """
    parts = ["^"]
    characters = iter(pattern)
    for character in characters:
        if character == "%":
            parts.append(".*")
        elif character == "_":
            parts.append(".")
        else:
            if character == "\\":
                character = next(characters, "\\")
            parts.append(character if character.isalnum() else f"\\{character}")
    parts.append("$")
    return "".join(parts)


@dataclass(frozen=True)
class Property:
    name: str
    field: Field


@dataclass(frozen=True)
class CaseInsensitive:
    """The CASEI of a property or of a string."""

    value: Property | str


def is_property(operand) -> bool:
    return isinstance(operand, Property) or isinstance(operand, CaseInsensitive) and isinstance(operand.value, Property)


def describe(operand) -> str:
    """An operand, as the error messages name it."""
    if isinstance(operand, Property):
        return f"the property '{operand.name}'"
    if isinstance(operand, CaseInsensitive):
        return f"CASEI({describe(operand.value)})"
    if isinstance(operand, GEOSGeometry):
        return "a geometry"
    return repr(operand)


class Translator:
    """Translates a parsed filter to Django lookups, on the given fields, its geometries being in the given SRID."""

    def __init__(self, fields: dict[str, Field], srid: int) -> None:
        self.fields = fields
        self.srid = srid

    def condition(self, node, negated: bool = False) -> Q:
        """
        The lookups of a condition. A negation is taken down to the predicates, as NOT (a AND b) is NOT a OR NOT b:
        a comparison with a null value is unknown, and so is its negation, which is then not a match either.
        """
        if isinstance(node, ast.Not):
            return self.condition(node.sub_node, not negated)
        if isinstance(node, (ast.And, ast.Or)):
            lhs, rhs = self.condition(node.lhs, negated), self.condition(node.rhs, negated)
            return lhs | rhs if isinstance(node, ast.Or) != negated else lhs & rhs
        if isinstance(node, ast.IsNull):
            prop = self.property(self.operand(node.lhs))
            return Q(**{f"{prop.name}__isnull": node.not_ == negated})
        q, properties = self.predicate(node)
        if negated == (getattr(node, "not_", False) or isinstance(node, ast.NotEqual)):
            return q
        # the negation of Django matches the null values, so they are left out
        not_null = [Q(**{f"{prop.name}__isnull": False}) for prop in properties if prop.field.null]
        return reduce(and_, not_null, ~q)

    def predicate(self, node) -> tuple[Q, list[Property]]:
        """The lookup of a predicate, left un-negated, and the properties it takes."""
        if (lookup := COMPARISONS.get(type(node))) is not None:
            return self.comparison(lookup, self.operand(node.lhs), self.operand(node.rhs))
        if isinstance(node, ast.Between):
            prop = self.scalar_property(self.operand(node.lhs))
            low, high = self.literal(self.operand(node.low)), self.literal(self.operand(node.high))
            return Q(**{f"{prop.name}__range": (low, high)}), [prop]
        if isinstance(node, ast.Like):
            return self.like(self.operand(node.lhs), self.operand(node.pattern))
        if isinstance(node, ast.In):
            return self.in_(self.operand(node.lhs), [self.operand(item) for item in node.sub_nodes])
        if (lookup := SPATIAL.get(type(node))) is not None:
            return self.spatial(lookup, self.operand(node.lhs), self.operand(node.rhs))
        raise FilterError(f"Unsupported predicate {type(node).__name__}")

    def comparison(self, lookup: str, lhs, rhs) -> tuple[Q, list[Property]]:
        if not is_property(lhs):
            lhs, rhs, lookup = rhs, lhs, MIRRORED.get(lookup, lookup)
        if isinstance(lhs, CaseInsensitive):
            if lookup != "exact" or not isinstance(rhs, CaseInsensitive):
                raise FilterError("CASEI can only be compared with = or <> to another CASEI")
            prop = self.scalar_property(lhs.value)
            return Q(**{f"{prop.name}__iexact": self.string(rhs.value)}), [prop]
        prop = self.scalar_property(lhs)
        if isinstance(rhs, Property):
            other = self.scalar_property(rhs)
            # the database would only refuse to compare other types once the query runs
            if prop.field.get_internal_type() != other.field.get_internal_type():
                raise FilterError(f"'{prop.name}' and '{other.name}' are not of the same type")
            return Q(**{f"{prop.name}__{lookup}": F(other.name)}), [prop, other]
        return Q(**{f"{prop.name}__{lookup}": self.literal(rhs)}), [prop]

    def like(self, lhs, pattern) -> tuple[Q, list[Property]]:
        nocase = isinstance(lhs, CaseInsensitive) or isinstance(pattern, CaseInsensitive)
        prop = self.scalar_property(lhs.value if isinstance(lhs, CaseInsensitive) else lhs)
        pattern = self.string(pattern.value if isinstance(pattern, CaseInsensitive) else pattern)
        return Q(**{f"{prop.name}__{'iregex' if nocase else 'regex'}": like_regex(pattern)}), [prop]

    def in_(self, lhs, items: list) -> tuple[Q, list[Property]]:
        if isinstance(lhs, CaseInsensitive):
            prop = self.scalar_property(lhs.value)
            strings = [self.string(item.value if isinstance(item, CaseInsensitive) else item) for item in items]
            return reduce(or_, (Q(**{f"{prop.name}__iexact": string}) for string in strings)), [prop]
        prop = self.scalar_property(lhs)
        return Q(**{f"{prop.name}__in": [self.literal(item) for item in items]}), [prop]

    def spatial(self, lookup: str, lhs, rhs) -> tuple[Q, list[Property]]:
        if not isinstance(lhs, Property):
            lhs, rhs, lookup = rhs, lhs, MIRRORED.get(lookup, lookup)
        if not isinstance(field := self.property(lhs).field, GeometryField):
            raise FilterError(f"'{lhs.name}' is not a geometry, which spatial functions take")
        if not isinstance(rhs, GEOSGeometry):
            raise FilterError("Spatial functions compare the geometry of the features with a geometry literal")
        return Q(**{f"{lhs.name}__{lookup}": reprojected(rhs, field.srid)}), [lhs]

    def operand(self, node):
        if isinstance(node, ast.Attribute):
            if (field := self.fields.get(node.name)) is None:
                raise FilterError(f"'{node.name}' is not a queryable")
            return Property(node.name, field)
        if isinstance(node, ast.Function):
            return self.function(node)
        if isinstance(node, values.Geometry):
            return self.geometry(node.geometry)
        if isinstance(node, values.Envelope):
            box = Polygon.from_bbox((node.x1, node.y1, node.x2, node.y2))
            box.srid = self.srid
            return self.in_range(box)
        if isinstance(node, ast.Arithmetic):
            raise FilterError("Arithmetic is not supported")
        if isinstance(node, datetime) and node.tzinfo is None:
            # the timestamps of CQL2 are in UTC
            return node.replace(tzinfo=UTC)
        if isinstance(node, LITERALS):
            return node
        raise FilterError(f"Unsupported {type(node).__name__}")

    def function(self, node: ast.Function):
        arguments = [self.operand(argument) for argument in node.arguments]
        # pygeofilter names CASEI lower
        if node.name == "lower":
            if len(arguments) != 1 or not isinstance(arguments[0], (Property, str)):
                raise FilterError("CASEI takes a property or a string")
            return CaseInsensitive(arguments[0])
        raise FilterError(f"Unsupported function {node.name}")

    def geometry(self, geometry: dict) -> GEOSGeometry:
        if "crs" in geometry:
            raise FilterError("The geometries of a filter are in its filter-crs, and take no SRID")
        try:
            return self.in_range(GEOSGeometry(memoryview(jsonfg.dumps(geometry)), srid=self.srid))
        except (GEOSException, struct.error) as e:
            raise FilterError("Invalid geometry") from e

    def in_range(self, geometry: GEOSGeometry) -> GEOSGeometry:
        xmin, ymin, xmax, ymax = geometry.extent
        # PostGIS would fail to reproject them, most likely given in another CRS without saying so
        if self.srid == CRS84_SRID and not (-180 <= xmin <= xmax <= 180 and -90 <= ymin <= ymax <= 90):
            raise FilterError("Coordinates out of the range of CRS84: the ones of another CRS need a filter-crs")
        return geometry

    def property(self, operand) -> Property:
        if not isinstance(operand, Property):
            raise FilterError(f"Expected a property, not {describe(operand)}")
        return operand

    def scalar_property(self, operand) -> Property:
        if isinstance(self.property(operand).field, GeometryField):
            raise FilterError(f"'{operand.name}' is a geometry, which only spatial functions take")
        return operand

    def literal(self, operand):
        if not isinstance(operand, LITERALS):
            raise FilterError(f"Expected a literal, not {describe(operand)}")
        return operand

    def string(self, operand) -> str:
        if not isinstance(operand, str):
            raise FilterError(f"Expected a string, not {describe(operand)}")
        return operand


def to_q(text: str, fields: dict[str, Field], srid: int) -> Q:
    """The lookups of a CQL2 text filter, on the given fields, its geometries being in the given SRID."""
    try:
        return Translator(fields, srid).condition(parse(text))
    except RecursionError as e:
        raise FilterError("The filter is nested too deeply") from e
