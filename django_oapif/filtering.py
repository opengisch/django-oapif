"""
CQL2 filters of OGC API - Features Part 3, as QGIS sends them for the subset string of a layer.

cql2-rs parses them to the JSON encoding of CQL2, which is translated here to Django lookups: the names of a filter
are only taken among the queryables, never handed to the ORM as they are, which would reach the fields of related
models, and the negations do not match the null values, which neither CQL2 nor QGIS do.
"""

import re
import struct
from dataclasses import dataclass
from datetime import date, datetime
from functools import reduce
from operator import and_, or_

import cql2
from django.contrib.gis.db.models import GeometryField
from django.contrib.gis.geos import GEOSException, GEOSGeometry, Polygon
from django.db.models import F, Field, Q

from django_oapif import jsonfg
from django_oapif.crs import CRS84_SRID


class FilterError(ValueError):
    """A filter that cannot be applied, for a reason the client can fix."""


# the lookups of the comparisons, <> being the negation of =
COMPARISONS = {"=": "exact", "<>": "exact", "<": "lt", "<=": "lte", ">": "gt", ">=": "gte"}
SPATIAL = {
    "s_intersects": "intersects",
    "s_disjoint": "disjoint",
    "s_contains": "contains",
    "s_within": "within",
    "s_touches": "touches",
    "s_crosses": "crosses",
    "s_overlaps": "overlaps",
    "s_equals": "equals",
}
ARITHMETIC = {"+", "-", "*", "/", "%", "^", "div"}
# the lookups that differ once their operands are swapped, for a literal on the left
MIRRORED = {"lt": "gt", "lte": "gte", "gt": "lt", "gte": "lte", "contains": "within", "within": "contains"}
# a bool is an int, and a datetime a date
LITERALS = (str, int, float, date)
# the numbers of cql2-rs are floats, which hold the integers exactly up to 2^53
MAX_INTEGER = 2**53

# cql2-rs recurses into each parenthesis and each NOT or minus sign in a row, and overflows its stack, which kills the
# process, from about 2000 levels: the ones of QGIS take one per condition
MAX_NESTING = 256
TOKENS = re.compile(r"'(?:[^']|'')*'|\"[^\"]*\"|\s+|[()-]|\bNOT\b|[^\s()'\"-]+|.", re.IGNORECASE)


def nesting(text: str) -> int:
    """How deep a filter nests, counting its parentheses and its runs of NOT and minus signs, out of the strings."""
    deepest = depth = run = 0
    for token in TOKENS.findall(text):
        if token == "(":
            depth += 1
        elif token == ")":
            depth = max(depth - 1, 0)
        elif token == "-" or token.upper() == "NOT":
            run += 1
        elif not token.isspace():
            run = 0
        deepest = max(deepest, depth + run)
    return deepest


def parse(text: str):
    """The JSON encoding of a CQL2 text filter."""
    if nesting(text) > MAX_NESTING:
        raise FilterError(f"The filter is nested deeper than {MAX_NESTING} levels")
    try:
        return cql2.parse_text(text).to_json()
    except cql2.ParseError as e:
        # pest gives the position on its first line and what it expected there on its last one
        lines = str(e).strip().splitlines()
        raise FilterError(f"{lines[-1].strip().removeprefix('= ')} at {lines[0].strip().removeprefix('--> ')}") from e


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


def operation(node) -> tuple[str | None, list]:
    """The operator of a node and its arguments, or None for an operand."""
    if isinstance(node, dict) and "op" in node:
        return node["op"], node.get("args", [])
    return None, []


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
        op, args = operation(node)
        if op == "not":
            (sub_node,) = args
            return self.condition(sub_node, not negated)
        if op in ("and", "or"):
            conditions = [self.condition(arg, negated) for arg in args]
            return reduce(or_ if (op == "or") != negated else and_, conditions)
        if op == "isNull":
            (operand,) = args
            prop = self.property(self.operand(operand))
            return Q(**{f"{prop.name}__isnull": not negated})
        q, properties = self.predicate(op, args)
        if negated == (op == "<>"):
            return q
        # the negation of Django matches the null values, so they are left out
        not_null = [Q(**{f"{prop.name}__isnull": False}) for prop in properties if prop.field.null]
        return reduce(and_, not_null, ~q)

    def predicate(self, op: str | None, args: list) -> tuple[Q, list[Property]]:
        """The lookup of a predicate, left un-negated, and the properties it takes."""
        if (lookup := COMPARISONS.get(op)) is not None:
            lhs, rhs = args
            return self.comparison(lookup, self.operand(lhs), self.operand(rhs))
        if op == "between":
            lhs, low, high = args
            prop = self.scalar_property(self.operand(lhs))
            low, high = self.literal(self.operand(low)), self.literal(self.operand(high))
            return Q(**{f"{prop.name}__range": (low, high)}), [prop]
        if op == "like":
            lhs, pattern = args
            return self.like(self.operand(lhs), self.operand(pattern))
        if op == "in":
            lhs, items = args
            return self.in_(self.operand(lhs), [self.operand(item) for item in items])
        if (lookup := SPATIAL.get(op)) is not None:
            lhs, rhs = args
            return self.spatial(lookup, self.operand(lhs), self.operand(rhs))
        raise FilterError(f"Unsupported predicate {op}" if op else "Expected a predicate")

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
        if not isinstance(self.property(lhs).field, GeometryField):
            raise FilterError(f"'{lhs.name}' is not a geometry, which spatial functions take")
        if not isinstance(rhs, GEOSGeometry):
            raise FilterError("Spatial functions compare the geometry of the features with a geometry literal")
        return Q(**{f"{lhs.name}__{lookup}": rhs}), [lhs]

    def operand(self, node):
        if isinstance(node, dict):
            if "property" in node:
                if (field := self.fields.get(node["property"])) is None:
                    raise FilterError(f"'{node['property']}' is not a queryable")
                return Property(node["property"], field)
            if "op" in node:
                return self.function(*operation(node))
            if "bbox" in node:
                return self.bbox(node["bbox"])
            if "type" in node:
                return self.geometry(node)
            if "timestamp" in node:
                # cql2-rs gives them in UTC
                return self.temporal(datetime, node["timestamp"])
            if "date" in node:
                return self.temporal(date, node["date"])
            raise FilterError(f"Unsupported {', '.join(node)}")
        if node is None:
            raise FilterError("NULL is only compared with IS NULL")
        if isinstance(node, bool | str):
            return node
        if isinstance(node, int | float):
            return self.number(node)
        raise FilterError(f"Unsupported {type(node).__name__}")

    def function(self, op: str, args: list):
        if op == "casei":
            (argument,) = [self.operand(arg) for arg in args]
            if not isinstance(argument, (Property, str)):
                raise FilterError("CASEI takes a property or a string")
            return CaseInsensitive(argument)
        if op in ARITHMETIC:
            raise FilterError("Arithmetic is not supported")
        raise FilterError(f"Unsupported function {op}")

    def number(self, number: int | float) -> int | float:
        if abs(number) >= MAX_INTEGER:
            raise FilterError(f"{number:g} is too large to be compared exactly")
        # an integer compared with a string is written as one
        return int(number) if number.is_integer() else number

    def temporal(self, kind: type[date], value: str) -> date:
        try:
            return kind.fromisoformat(value)
        except ValueError as e:
            raise FilterError(f"Invalid {kind.__name__} '{value}'") from e

    def bbox(self, coordinates: list) -> Polygon:
        # in 3D, minx, miny, minz, maxx, maxy, maxz, whose elevations are left out
        if len(coordinates) not in (4, 6):
            raise FilterError("BBOX takes 4 or 6 numbers")
        half = len(coordinates) // 2
        box = Polygon.from_bbox((coordinates[0], coordinates[1], coordinates[half], coordinates[half + 1]))
        box.srid = self.srid
        return self.in_range(box)

    def geometry(self, geometry: dict) -> GEOSGeometry:
        try:
            return self.in_range(GEOSGeometry(memoryview(jsonfg.dumps(geometry)), srid=self.srid))
        except (GEOSException, struct.error, KeyError) as e:
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
