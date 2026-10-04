import datetime
import decimal
import json
import logging
import re
import uuid
from html.parser import HTMLParser
from typing import Annotated
from unittest import skipIf, skipUnless
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.gis.db.models import Extent
from django.contrib.gis.db.models.functions import Transform
from django.core.management import call_command
from django.db import connection
from django.db.models import FloatField, Func, Max, Min
from django.test import RequestFactory
from django.test.testcases import TestCase
from django.test.utils import CaptureQueriesContext
from django_oapif import jsonfg
from django_oapif.collections import writes_curves
from django_oapif.crs import CRS, CRS84_SRID
from django_oapif.geojson import CircularString, Coordinate2D
from django_oapif.handler import ARROW_AVAILABLE, AnonReadOnlyCollection, json_schema_pattern
from django_oapif_tests.tests.oapif import oapif
from django_oapif_tests.tests.models import (
    Arc_2056_10fields,
    Geometry_2056,
    GeometryZ_2056,
    LayerWithDate,
    LayerWithFile,
    LayerWithForeignKey,
    LayerWithOrdering,
    LayerWithVariousTypes,
    NoGeom_10fields,
    Point_2056_10fields,
    Point_2056_Empty,
)
from ninja import Schema
from ninja.errors import ValidationError as NinjaValidationError
from ninja.responses import NinjaJSONEncoder
from pydantic import AfterValidator
from pydantic import ValidationError as PydanticValidationError

try:  # Arrow is an optional extra, and its tests are skipped without it
    import pyarrow as pa
    from geoarrow.pyarrow import WkbType
    from geoarrow.types.crs import StringCrs
except ImportError:
    pass

requires_arrow = skipUnless(ARROW_AVAILABLE, "needs the arrow extra")

logger = logging.getLogger(__name__)

collections_url = "/oapif/collections"

crs_2056 = "http://www.opengis.net/def/crs/EPSG/0/2056"
crs84 = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
crs_base = "http://www.opengis.net/def/crs"

headers = {"Content-Crs": crs_2056}


def extent(queryset, geometry) -> tuple[float, float, float, float]:
    """The extent of the geometries, at the full precision of their coordinates, which Extent rounds to 15 digits."""
    aggregates = {
        name: aggregate(Func(geometry, function=f"ST_{name}", output_field=FloatField()))
        for name, aggregate in (("XMin", Min), ("YMin", Min), ("XMax", Max), ("YMax", Max))
    }
    return tuple(queryset.aggregate(**aggregates).values())


def geometry_of(feature: dict) -> dict | None:
    """The geometry of a feature, which JSON-FG gives in "place" when GeoJSON cannot carry it."""
    return feature["place"] if feature.get("place") is not None else feature["geometry"]


class TestBasicAuth(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("populate_data", "-s 100")
        call_command("populate_users")

        cls.demo_viewer = User.objects.get(username="demo_viewer")
        cls.demo_editor = User.objects.get(username="demo_editor")

    def tearDown(self):
        self.client.logout()

    def test_get_as_viewer(self):
        collections_from_anonymous = self.client.get(collections_url, content_type="application/json").json()
        self.client.force_login(user=self.demo_viewer)
        collection_response = self.client.get(collections_url, content_type="application/json")

        self.assertEqual(collection_response.status_code, 200)
        self.assertEqual(len(collection_response.json()), len(collections_from_anonymous))

    def test_anonymous_items_options(self):
        # Anonymous user
        self.maxDiff = None
        expected = {"GET", "OPTIONS"}
        url = f"{collections_url}/tests.point_2056_10fields/items"
        response = self.client.options(url)

        allowed_headers = {s.strip() for s in response.headers["Allow"].split(",")}
        self.assertEqual(allowed_headers, expected)

    def test_editor_items_options(self):
        # Authenticated user with editing permissions
        expected = {"POST", "GET", "OPTIONS"}
        self.client.force_login(user=self.demo_editor)
        layer = "tests.point_2056_10fields"
        url = f"{collections_url}/{layer}/items"
        response = self.client.options(url)

        allowed_headers = {s.strip() for s in response.headers["Allow"].split(",")}
        self.assertEqual(allowed_headers, expected)

    def test_post_geometry_less_layer(self):
        self.client.force_login(user=self.demo_editor)
        data = {
            "type": "Feature",
            "geometry": None,
            "properties": {"field_str_0": "test123456"},
        }

        url = f"{collections_url}/tests.nogeom_10fields/items"
        post_to_items = self.client.post(url, data, headers=headers, content_type="application/json")
        self.assertIn(post_to_items.status_code, (200, 201), (url, data, post_to_items))

    def test_line_must_have_the_dimension_of_its_collection(self):
        # LineString used to take any dimension, and the insert then failed in the database with a 500
        self.client.force_login(user=self.demo_editor)
        line_2d = [[2508500.0, 1152000.0], [2508600.0, 1152100.0]]
        line_3d = [[2508500.0, 1152000.0, 1.0], [2508600.0, 1152100.0, 2.0]]
        for collection, coordinates, status in (
            ("tests.line_2056_10fields", line_2d, 201),
            ("tests.line_2056_10fields", line_3d, 422),
            ("tests.geometryz_2056", line_3d, 201),
            ("tests.geometryz_2056", line_2d, 422),
        ):
            with self.subTest(collection=collection, dimension=len(coordinates[0])):
                data = {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coordinates},
                    "properties": {},
                }
                url = f"{collections_url}/{collection}/items"
                response = self.client.post(url, data, headers=headers, content_type="application/json")
                self.assertEqual(response.status_code, status)

    def test_put_and_patch_change_the_feature_of_the_url(self):
        # the payload used to set the primary key: a PUT without it inserted a copy under a fresh key, and one
        # carrying another feature's key overwrote that feature
        self.client.force_login(user=self.demo_editor)
        url = f"{collections_url}/tests.point_2056_10fields/items"
        target = Point_2056_10fields.objects.create(geom="SRID=2056;POINT(2600000 1200000)", field_str_0="target")
        other = Point_2056_10fields.objects.create(geom="SRID=2056;POINT(2600100 1200100)", field_str_0="other")
        count = Point_2056_10fields.objects.count()
        for method, key in ((self.client.put, None), (self.client.put, other.pk), (self.client.patch, other.pk)):
            with self.subTest(method=method.__name__, key=key):
                properties = {"field_str_0": "changed"} | ({"id": str(key)} if key else {})
                geometry = {"type": "Point", "coordinates": [2600500.0, 1200500.0]}
                feature = {"type": "Feature", "geometry": geometry, "properties": properties}

                response = method(f"{url}/{target.pk}", feature, headers=headers, content_type="application/json")

                self.assertEqual(response.status_code, 200)
                self.assertEqual(Point_2056_10fields.objects.count(), count)
                target.refresh_from_db()
                other.refresh_from_db()
                self.assertEqual((target.field_str_0, target.geom.coords), ("changed", (2600500.0, 1200500.0)))
                self.assertEqual(other.field_str_0, "other")

    def test_post_refuses_the_id_of_an_existing_feature(self):
        # a POST with the id of a feature was saved over it when the key has no default, as an AutoField, even over
        # one its collection hides, and failed with a 500 when the key has one
        self.client.force_login(user=self.demo_editor)
        shown = LayerWithOrdering.objects.create(name="shown")
        hidden = LayerWithOrdering.objects.create(name="hidden")
        no_geom = NoGeom_10fields.objects.create()
        collection = oapif.collections["tests.layerwithordering"]
        get_queryset = collection.get_queryset

        def served(request):
            return get_queryset(request).exclude(pk=hidden.pk)

        with patch.object(collection, "get_queryset", served):
            for collection_id, properties in (
                ("tests.layerwithordering", {"id": shown.pk, "name": "changed"}),
                ("tests.layerwithordering", {"id": hidden.pk, "name": "changed"}),
                ("tests.nogeom_10fields", {"id": str(no_geom.pk), "field_str_0": "changed"}),
            ):
                with self.subTest(collection=collection_id, id=properties["id"]):
                    url = f"{collections_url}/{collection_id}/items"
                    feature = {"type": "Feature", "geometry": None, "properties": properties}

                    response = self.client.post(url, feature, headers=headers, content_type="application/json")

                    self.assertEqual(response.status_code, 409)
        self.assertEqual(sorted(LayerWithOrdering.objects.values_list("name", flat=True)), ["hidden", "shown"])
        # a fresh id is still the one of the feature created
        fresh = str(uuid.uuid4())
        feature = {"type": "Feature", "geometry": None, "properties": {"id": fresh}}
        url = f"{collections_url}/tests.nogeom_10fields/items"
        response = self.client.post(url, feature, headers=headers, content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["id"], fresh)
        # a user who may not add is refused first, and does not learn from a 409 that the id exists
        self.client.force_login(user=self.demo_viewer)
        feature = {"type": "Feature", "geometry": None, "properties": {"id": shown.pk, "name": "changed"}}
        url = f"{collections_url}/tests.layerwithordering/items"
        response = self.client.post(url, feature, headers=headers, content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_post_refuses_the_id_of_an_existing_parent_row(self):
        # a collection leaving the link to the parent out of writes still takes the key of the parent row, which was
        # not checked: one without a default was saved over that row, and a UUID, as here, failed with a 500
        self.client.force_login(user=self.demo_editor)
        point = Point_2056_10fields.objects.create(geom="SRID=2056;POINT(2600000 1200000)")
        collection = oapif.collections["tests.point_2056_empty"]
        url = f"{collections_url}/tests.point_2056_empty/items"
        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [2600500.0, 1200500.0]},
            "properties": {"id": str(point.pk)},
        }

        with patch.object(collection, "readonly_fields", ("point_2056_10fields_ptr",)):
            response = self.client.post(url, feature, headers=headers, content_type="application/json")

        self.assertEqual(response.status_code, 409)

    def test_unknown_property_is_rejected_after_a_read(self):
        self.client.force_login(user=self.demo_editor)
        url = f"{collections_url}/tests.point_2056_10fields/items"
        self.assertEqual(self.client.get(url).status_code, 200)
        data = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [2508500.0, 1152000.0]},
            "properties": {"field_str_0": "test123456", "not_a_field": 1},
        }

        post_to_items = self.client.post(url, data, headers=headers, content_type="application/json")
        self.assertEqual(post_to_items.status_code, 422)

    def test_returned_id(self):
        self.client.force_login(user=self.demo_editor)
        data = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [2508500.0, 1152000.0],
            },
            "properties": {"field_str_0": "test123456"},
        }

        url = f"{collections_url}/tests.point_2056_10fields/items"
        post_to_items = self.client.post(url, data, headers=headers, content_type="application/json")
        self.assertIn(post_to_items.status_code, (200, 201), (url, data, post_to_items))
        fid = post_to_items.json()["id"]
        self.assertTrue(re.match(r"^[0-9a-f\-]{36}$", fid))

    def test_delete(self):
        self.client.force_login(user=self.demo_editor)
        data = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [2508500.0, 1152000.0],
            },
            "properties": {"field_str_0": "test123456"},
        }

        url = f"{collections_url}/tests.point_2056_10fields/items"
        post_to_items = self.client.post(url, data, headers=headers, content_type="application/json")
        self.assertIn(post_to_items.status_code, (200, 201), (url, data, post_to_items))
        fid = post_to_items.json()["id"]
        delete_from_items = self.client.delete(f"{url}/{fid}")
        self.assertIn(delete_from_items.status_code, (200, 204), f"{url}/{fid}")

    def test_post_model_with_foreignkey(self):
        self.client.force_login(user=self.demo_editor)
        first_point = Point_2056_10fields.objects.first()
        assert first_point is not None
        data = {
            "type": "Feature",
            "geometry": None,
            "properties": {"point": str(first_point.pk)},
        }

        url = f"{collections_url}/tests.layerwithforeignkey/items"
        post_to_items = self.client.post(url, data, headers=headers, content_type="application/json")
        self.assertEqual(post_to_items.status_code, 201, (url, data, post_to_items))
        response = post_to_items.json()
        expected_response = {
            "type": "Feature",
            "geometry": None,
            "id": response["id"],
            "properties": {
                "point": str(first_point.pk),
                "id": response["id"],
            },
        }
        self.assertEqual(post_to_items.json(), expected_response)

    def test_post_model_with_invalid_foreignkey(self):
        self.client.force_login(user=self.demo_editor)
        data = {
            "type": "Feature",
            "geometry": None,
            "properties": {"point": "7038f63b-1a77-4489-b5bf-f09586aeb5a4"},
        }
        url = f"{collections_url}/tests.layerwithforeignkey/items"
        post_to_items = self.client.post(url, data, headers=headers, content_type="application/json")
        self.assertEqual(post_to_items.status_code, 422, (url, data, post_to_items))
        expected_error = {
            "detail": [
                {
                    "loc": ["body", "feature", "properties", "point"],
                    "msg": "Foreign key not found",
                    "type": "value_error",
                }
            ]
        }
        self.assertEqual(post_to_items.json(), expected_error)

    def test_file_field(self):
        obj = LayerWithFile.objects.create(file="foo/bar.txt")
        obj.refresh_from_db()
        url = f"{collections_url}/tests.layerwithfile/items/{obj.id}"
        response = self.client.get(url, headers=headers, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "id": str(obj.id),
                "type": "Feature",
                "geometry": None,
                "properties": {
                    "file": "/media/foo/bar.txt",
                    "id": str(obj.id),
                },
            },
        )

    def test_date_field(self):
        today = datetime.date.today()
        now = datetime.datetime.now(datetime.UTC)
        obj = LayerWithDate.objects.create(date=today, time=now)
        obj.refresh_from_db()
        feature = {
            "id": str(obj.id),
            "type": "Feature",
            "geometry": None,
            "properties": {
                "date": str(today),
                # to the millisecond, as Django writes them, where pydantic would go to the microsecond
                "time": now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "id": str(obj.id),
            },
        }
        url = f"{collections_url}/tests.layerwithdate/items"

        item = self.client.get(f"{url}/{obj.id}", headers=headers, content_type="application/json")
        items = self.client.get(url, headers=headers, content_type="application/json")

        self.assertEqual(item.status_code, 200)
        self.assertEqual(item.json(), feature)
        self.assertEqual(items.status_code, 200)
        self.assertIn(feature, items.json()["features"])


class TestSchema(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("populate_users")
        cls.demo_viewer = User.objects.get(username="demo_viewer")
        cls.demo_editor = User.objects.get(username="demo_editor")

    def tearDown(self):
        self.client.logout()

    def test_schema_and_fields_recognition(self):
        url = f"{collections_url}/tests.point_2056_10fields/schema"

        expected_schema = {
            "additionalProperties": False,
            "properties": {
                "id": {"title": "Id", "format": "uuid", "type": "string", "x-ogc-role": "id", "x-ogc-propertySeq": 1},
                "field_int": {
                    "title": "Field Int",
                    "type": "integer",
                    "minimum": -2147483648,
                    "maximum": 2147483647,
                    "x-ogc-propertySeq": 3,
                },
                "field_bool": {"default": True, "title": "Field Bool", "type": "boolean", "x-ogc-propertySeq": 2},
                "field_str_0": {"title": "Field 0", "maxLength": 255, "type": "string", "x-ogc-propertySeq": 4},
                "field_str_1": {"title": "Field 1", "maxLength": 255, "type": "string", "x-ogc-propertySeq": 5},
                "field_str_2": {"title": "Field 2", "maxLength": 255, "type": "string", "x-ogc-propertySeq": 6},
                "field_str_3": {"title": "Field 3", "maxLength": 255, "type": "string", "x-ogc-propertySeq": 7},
                "field_str_4": {"title": "Field 4", "maxLength": 255, "type": "string", "x-ogc-propertySeq": 8},
                "field_str_5": {"title": "Field 5", "maxLength": 255, "type": "string", "x-ogc-propertySeq": 9},
                "field_str_6": {"title": "Field 6", "maxLength": 255, "type": "string", "x-ogc-propertySeq": 10},
                "field_str_7": {"title": "Field 7", "maxLength": 255, "type": "string", "x-ogc-propertySeq": 11},
                "field_str_8": {"title": "Field 8", "maxLength": 255, "type": "string", "x-ogc-propertySeq": 12},
                "field_str_9": {"title": "Field 9", "maxLength": 255, "type": "string", "x-ogc-propertySeq": 13},
                "geom": {
                    "title": "geometry",
                    "x-ogc-role": "primary-geometry",
                    "format": "geometry-point",
                    "x-ogc-propertySeq": 14,
                },
            },
            "title": "tests.Point_2056_10fields",
            "type": "object",
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "http://testserver/oapif/collections/tests.point_2056_10fields/schema",
        }

        schema_response = self.client.get(url, headers=headers, content_type="application/json")
        self.assertEqual(schema_response.status_code, 200)
        self.assertEqual(schema_response.headers["Content-Type"], "application/schema+json")
        self.assertEqual(schema_response.json(), expected_schema)

    def test_collection_links_its_schema(self):
        collection = self.client.get(f"{collections_url}/tests.point_2056_10fields").json()

        self.assertIn(
            {
                "rel": "http://www.opengis.net/def/rel/ogc/1.0/schema",
                "title": "Collection schema",
                "type": "application/schema+json",
                "href": "http://testserver/oapif/collections/tests.point_2056_10fields/schema",
            },
            collection["links"],
        )

    def test_every_property_has_a_type(self):
        # Part 5 requires one of every property but the geometry, and QGIS makes no field of a property without
        for collection_id, collection in oapif.collections.items():
            schema = collection.get_json_schema(RequestFactory().get("/"))
            for name, prop in schema["properties"].items():
                if name != collection.geometry_field:
                    with self.subTest(collection=collection_id, property=name):
                        self.assertIsInstance(prop.get("type"), str)

    def test_schema_decimal_is_a_string(self):
        # a decimal is served as a string, while it is written as a number or a string
        url = f"{collections_url}/tests.layerwithvarioustypes/schema"
        amount = self.client.get(url).json()["properties"]["amount"]

        self.assertEqual(amount["type"], "string")
        self.assertNotIn("anyOf", amount)

    def test_schema_read_only_fields(self):
        # QGIS makes their fields read-only, which a write would otherwise carry and have rejected
        url = f"{collections_url}/tests.layerwithfile/schema"
        properties = self.client.get(url).json()["properties"]

        self.assertIs(properties["file"]["readOnly"], True)
        # a POST takes the primary key
        self.assertNotIn("readOnly", properties["id"])

    def test_schema_leaves_out_excluded_fields(self):
        class Excluding(AnonReadOnlyCollection):
            exclude = ("field_str_9",)

        schema = Excluding(Point_2056_10fields).get_json_schema(RequestFactory().get("/"))

        self.assertNotIn("field_str_9", schema["properties"])
        self.assertIn("field_str_8", schema["properties"])

    def test_schema_id_has_no_query(self):
        # Part 5 wants the URI of the schema, without the query parameters of the request, the queryables' too
        for resource in ("schema", "queryables"):
            url = f"{collections_url}/tests.point_2056_10fields/{resource}"
            with self.subTest(url=url):
                response = self.client.get(f"{url}?f=json")

                self.assertEqual(response.json()["$id"], f"http://testserver{url}")

    def test_schema_choices_are_an_enum(self):
        url = f"{collections_url}/tests.layerwithconstraints/schema"
        properties = self.client.get(url).json()["properties"]

        self.assertEqual(properties["kind"]["enum"], ["house", "shed"])
        self.assertEqual(properties["level"]["enum"], [1, 2])
        self.assertNotIn("enum", properties["score"])

    def test_schema_numeric_bounds(self):
        url = f"{collections_url}/tests.layerwithconstraints/schema"
        properties = self.client.get(url).json()["properties"]

        # the strictest of the validators and of the range of the column
        self.assertEqual((properties["score"]["minimum"], properties["score"]["maximum"]), (0, 10))
        self.assertEqual((properties["level"]["minimum"], properties["level"]["maximum"]), (-2147483648, 2147483647))
        self.assertNotIn("minimum", properties["kind"])

    def test_schema_string_constraints(self):
        url = f"{collections_url}/tests.layerwithconstraints/schema"
        properties = self.client.get(url).json()["properties"]

        self.assertEqual(properties["code"]["minLength"], 2)
        self.assertEqual(properties["code"]["maxLength"], 5)
        self.assertEqual(properties["code"]["pattern"], "^[A-Z]+$")
        # ninja leaves out the length of URLs, and their validator ignores case, which a pattern cannot say
        self.assertEqual(properties["website"]["maxLength"], 200)
        self.assertNotIn("pattern", properties["website"])

    def test_schema_patterns_are_anchored_as_in_json_schema(self):
        self.assertEqual(json_schema_pattern(r"^[-a-zA-Z0-9_]+\Z"), "^[-a-zA-Z0-9_]+$")
        # an escaped backslash followed by a letter is no anchor
        self.assertEqual(json_schema_pattern(r"\A\\Z\\\Z"), r"^\\Z\\$")

    def test_schema_formats(self):
        def properties(collection):
            return self.client.get(f"{collections_url}/{collection}/schema").json()["properties"]

        constraints = properties("tests.layerwithconstraints")
        self.assertEqual(constraints["website"]["format"], "uri")
        self.assertEqual(constraints["email"]["format"], "email")
        self.assertEqual(constraints["address"]["format"], "ipv4")
        # files are served as the path their storage gives
        self.assertEqual(properties("tests.layerwithfile")["file"]["format"], "uri-reference")
        # an address of either version has no format in JSON Schema
        self.assertNotIn("format", properties("tests.layerwithvarioustypes")["ip"])

    def test_schema_references(self):
        url = f"{collections_url}/tests.layerwithforeignkey/schema"
        point = self.client.get(url).json()["properties"]["point"]

        # the model of the key has two collections
        self.assertEqual(point["x-ogc-role"], "reference")
        self.assertEqual(point["x-ogc-collectionId"], ["tests.point_2056_10fields", "tests.point_2056_10fields_subset"])

    def test_schema_references_only_viewable_collections(self):
        url = f"{collections_url}/tests.layerwithforeignkey/schema"
        subset = oapif.collections["tests.point_2056_10fields_subset"]
        with patch.object(subset, "has_view_permission", return_value=False):
            point = self.client.get(url).json()["properties"]["point"]

        self.assertEqual(point["x-ogc-collectionId"], "tests.point_2056_10fields")

    def test_schema_primary_key_is_the_id(self):
        # the key to the parent of a multi-table inheritance is the primary key, not a reference
        properties = self.client.get(f"{collections_url}/tests.point_2056_empty/schema").json()["properties"]

        self.assertEqual(properties["point_2056_10fields_ptr"]["x-ogc-role"], "id")
        self.assertNotIn("x-ogc-role", properties["id"])

    def test_properties_schema_keeps_its_extra_behaviour(self):
        # ninja caches schemas by name and fields but not by config: the output schema, built first by
        # a read, used to be handed to writes too, which then silently dropped unknown properties
        collection = oapif.collections["tests.point_2056_10fields"]
        fields = ("field_str_9", "field_str_8")  # built nowhere else, so nothing is cached for it yet

        ignoring = collection.get_properties_schema(fields, extra="ignore")
        forbidding = collection.get_properties_schema(fields)

        self.assertEqual(ignoring.model_config["extra"], "ignore")
        self.assertEqual(forbidding.model_config["extra"], "forbid")

    def test_validation_errors_serialize(self):
        # a validator raising a ValueError leaves the exception in the error context, which made the 422 a 500
        def refuse(value):
            raise ValueError("refused")

        class Refusing(Schema):
            name: Annotated[str, AfterValidator(refuse)]

        collection = oapif.collections["tests.point_2056_10fields"]
        with self.assertRaises(NinjaValidationError) as raised:
            collection.validate_feature_or_raise(RequestFactory().get("/"), Refusing, {"name": "x"})

        self.assertIn('"refused"', json.dumps(raised.exception.errors, cls=NinjaJSONEncoder))

    def test_schema_subset_recognition(self):
        self.maxDiff = None
        url = f"{collections_url}/tests.point_2056_10fields_subset/schema"

        expected_schema = {
            "additionalProperties": False,
            "properties": {
                "field_int": {
                    "title": "Field Int",
                    "type": "integer",
                    "minimum": -2147483648,
                    "maximum": 2147483647,
                    "x-ogc-propertySeq": 1,
                },
                "field_str_0": {"title": "Field 0", "maxLength": 255, "type": "string", "x-ogc-propertySeq": 2},
                "geom": {
                    "title": "geometry",
                    "x-ogc-role": "primary-geometry",
                    "format": "geometry-point",
                    "x-ogc-propertySeq": 3,
                },
            },
            "title": "tests.Point_2056_10fields",
            "type": "object",
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "http://testserver/oapif/collections/tests.point_2056_10fields_subset/schema",
        }

        schema_response = self.client.get(url, headers=headers, content_type="application/json")
        self.assertEqual(schema_response.status_code, 200)
        self.assertEqual(schema_response.json(), expected_schema)

    def test_schema_mandatory_field(self):
        url = f"{collections_url}/tests.mandatoryfield/schema"

        expected_schema = {
            "additionalProperties": False,
            "properties": {
                "id": {"format": "uuid", "title": "Id", "type": "string", "x-ogc-role": "id", "x-ogc-propertySeq": 1},
                "text_mandatory_field": {
                    "maxLength": 255,
                    "title": "Mandatory Field",
                    "type": "string",
                    "x-ogc-propertySeq": 2,
                },
                "geom": {
                    "title": "geometry",
                    "x-ogc-role": "primary-geometry",
                    "format": "geometry-point",
                    "x-ogc-propertySeq": 3,
                },
            },
            "required": ["text_mandatory_field"],
            "title": "tests.MandatoryField",
            "type": "object",
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "http://testserver/oapif/collections/tests.mandatoryfield/schema",
        }

        schema_response = self.client.get(url, headers=headers, content_type="application/json")
        self.assertEqual(schema_response.status_code, 200)
        self.assertEqual(schema_response.json(), expected_schema)

    def test_schema_geometry_type_point(self):
        url = f"{collections_url}/tests.point_2056_10fields/schema"
        schema_response = self.client.get(url, headers=headers, content_type="application/json")

        self.assertEqual(schema_response.status_code, 200)
        self.assertEqual(
            schema_response.json()["properties"]["geom"],
            {
                "title": "geometry",
                "x-ogc-role": "primary-geometry",
                "format": "geometry-point",
                "x-ogc-propertySeq": 14,
            },
        )

    def test_schema_geometry_type_linestring(self):
        url = f"{collections_url}/tests.line_2056_10fields/schema"
        schema_response = self.client.get(url, headers=headers, content_type="application/json")

        self.assertEqual(schema_response.status_code, 200)
        self.assertEqual(
            schema_response.json()["properties"]["geom"],
            {
                "title": "geometry",
                "x-ogc-role": "primary-geometry",
                "format": "geometry-linestring",
                "x-ogc-propertySeq": 14,
            },
        )

    def test_schema_geometry_type_polygon(self):
        url = f"{collections_url}/tests.polygon_2056/schema"
        schema_response = self.client.get(url, headers=headers, content_type="application/json")

        self.assertEqual(schema_response.status_code, 200)
        self.assertEqual(
            schema_response.json()["properties"]["geom"],
            {
                "title": "geometry",
                "x-ogc-role": "primary-geometry",
                "format": "geometry-multipolygon",
                "x-ogc-propertySeq": 3,
            },
        )

    def test_schema_geometry_type_any(self):
        url = f"{collections_url}/tests.geometry_2056/schema"
        schema_response = self.client.get(url, headers=headers, content_type="application/json")

        self.assertEqual(schema_response.status_code, 200)
        self.assertEqual(
            schema_response.json()["properties"]["geom"],
            {"title": "geometry", "x-ogc-role": "primary-geometry", "format": "geometry-any", "x-ogc-propertySeq": 2},
        )


class TestOutputFormat(TestCase):
    COLLECTIONS = {
        "tests.nogeom_10fields": None,
        "tests.point_2056_10fields": "Point",
        "tests.line_2056_10fields": "LineString",
        "tests.arc_2056_10fields": "CircularString",
    }

    @classmethod
    def setUpTestData(cls):
        call_command("populate_data", "-s 100")
        call_command("populate_users")

    def test_geojson_geometry_types(self):
        for collection, geometry_type in self.COLLECTIONS.items():
            with self.subTest(collection=collection):
                # which GeoJSON has not, in JSON-FG
                params = {"profile": "jsonfg"} if geometry_type == "CircularString" else {}
                response = self.client.get(
                    f"{collections_url}/{collection}/items?limit=1",
                    params,
                    headers={"Accept": "application/geo+json"},
                )

                self.assertEqual(response.status_code, 200)
                feature = response.json()["features"][0]
                if geometry_type:
                    self.assertEqual(geometry_of(feature)["type"], geometry_type)
                else:
                    self.assertEqual(feature["geometry"], None)

    @patch("django_oapif.collections.ARROW_AVAILABLE", False)
    def test_arrow_without_the_extra_is_not_acceptable(self):
        url = f"{collections_url}/tests.point_2056_10fields/items"
        for item_url in (url, f"{url}/{Point_2056_10fields.objects.first().pk}"):
            with self.subTest(url=item_url):
                response = self.client.get(item_url, headers={"Accept": "application/vnd.apache.arrow.stream"})

                self.assertEqual(response.status_code, 406)
                geojson = self.client.get(item_url, headers={"Accept": "application/geo+json"})
                self.assertEqual(geojson.status_code, 200)

    @requires_arrow
    def test_arrow_empty_page(self):
        # an empty page used to come back as a table without a single column
        for collection in ("tests.point_2056_10fields", "tests.nogeom_10fields"):
            with self.subTest(collection=collection):
                url = f"{collections_url}/{collection}/items?limit=1"
                arrow_headers = {"Accept": "application/vnd.apache.arrow.stream"}
                populated = self.client.get(url, headers=arrow_headers)
                empty = self.client.get(f"{url}&offset=1000000", headers=arrow_headers)

                self.assertEqual(populated.status_code, 200)
                self.assertEqual(empty.status_code, 200)
                populated_table = pa.ipc.open_stream(populated.content).read_all()
                empty_table = pa.ipc.open_stream(empty.content).read_all()
                self.assertEqual(populated_table.num_rows, 1)
                self.assertEqual(empty_table.num_rows, 0)
                self.assertEqual(empty_table.schema.names, populated_table.schema.names)

    @requires_arrow
    def test_arrow_empty_collection(self):
        response = self.client.get(
            f"{collections_url}/tests.point_2056_empty/items",
            headers={"Accept": "application/vnd.apache.arrow.stream"},
        )

        self.assertEqual(response.status_code, 200)
        table = pa.ipc.open_stream(response.content).read_all()
        self.assertEqual(table.num_rows, 0)
        self.assertIn("geometry", table.schema.names)
        self.assertIsInstance(table.schema.field("geometry").type, WkbType)

    @requires_arrow
    def test_arrow_pages_share_one_schema(self):
        # a column that is all null on one page used to be null-typed, and stop concatenating
        Point_2056_Empty.objects.create(geom="POINT(2508500 1152000)", field_int=1)
        Point_2056_Empty.objects.create(geom="POINT(2508600 1152100)", field_int=None)
        pages = []
        for offset in (0, 1):
            response = self.client.get(
                f"{collections_url}/tests.point_2056_empty/items?limit=1&offset={offset}",
                headers={"Accept": "application/vnd.apache.arrow.stream"},
            )

            self.assertEqual(response.status_code, 200)
            pages.append(pa.ipc.open_stream(response.content).read_all())

        self.assertEqual(pages[0].schema, pages[1].schema)
        self.assertEqual(pa.concat_tables(pages).num_rows, 2)

    @requires_arrow
    def test_arrow_columns_keep_the_declared_order(self):
        # the order of a set changes from one process to the next, so pages served by different
        # workers used to come back with their columns shuffled, and no longer concatenated
        expected = {
            "tests.point_2056_10fields": [
                "id",
                "field_bool",
                "field_int",
                *(f"field_str_{i}" for i in range(10)),
                "geometry",
            ],
            "tests.point_2056_10fields_subset": ["field_int", "field_str_0", "geometry"],
        }
        for collection, columns in expected.items():
            with self.subTest(collection=collection):
                response = self.client.get(
                    f"{collections_url}/{collection}/items?limit=1",
                    headers={"Accept": "application/vnd.apache.arrow.stream"},
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(pa.ipc.open_stream(response.content).schema.names, columns)

    @requires_arrow
    def test_arrow_writes_the_other_types_as_the_geojson(self):
        # their column types used to be inferred from the values: an IP address could not be encoded, nor a
        # JSON field of objects and lists, failing the whole page, and pages could differ in their schema
        LayerWithVariousTypes.objects.create(
            data={"kind": 1, "tags": ["a"]},
            ip="192.168.0.1",
            amount=decimal.Decimal("1.50"),
            delay=datetime.timedelta(hours=2),
        )
        LayerWithVariousTypes.objects.create(data=["x", {"kind": "é"}], ip="::1")
        LayerWithVariousTypes.objects.create(amount=decimal.Decimal("-3"), delay=datetime.timedelta(0))
        url = f"{collections_url}/tests.layerwithvarioustypes/items"
        arrow_headers = {"Accept": "application/vnd.apache.arrow.stream"}

        response = self.client.get(url, headers=arrow_headers)

        self.assertEqual(response.status_code, 200)
        table = pa.ipc.open_stream(response.content).read_all()
        # the canonical extension of JSON text, whether this pyarrow knows it or not
        data_type = table.schema.field("data").type
        self.assertEqual(getattr(data_type, "storage_type", data_type), pa.string())
        self.assertIn(b"arrow.json", response.content)
        for name in ("ip", "amount", "delay"):
            self.assertEqual(table.schema.field(name).type, pa.string())
        geojson = self.client.get(url, headers={"Accept": "application/geo+json"}).json()
        expected = {feature["id"]: feature["properties"] for feature in geojson["features"]}
        for row in table.to_pylist():
            with self.subTest(id=row["id"]):
                properties = expected[row["id"]]
                self.assertEqual(None if row["data"] is None else json.loads(row["data"]), properties["data"])
                for name in ("ip", "amount", "delay"):
                    self.assertEqual(row[name], properties[name])

        pages = [
            pa.ipc.open_stream(self.client.get(f"{url}?limit=1&offset={offset}", headers=arrow_headers).content)
            for offset in range(3)
        ]
        self.assertEqual(len({page.schema for page in pages}), 1)

    @requires_arrow
    def test_arrow_reports_the_total_and_the_page_links(self):
        # an Arrow stream cannot carry them in the payload, so they go to the headers
        url = f"{collections_url}/tests.point_2056_10fields/items?limit=1&offset=1"
        arrow = self.client.get(url, headers={"Accept": "application/vnd.apache.arrow.stream"})
        geojson = self.client.get(url, headers={"Accept": "application/geo+json"}).json()

        self.assertEqual(arrow.status_code, 200)
        self.assertEqual(arrow.headers["OGC-NumberMatched"], str(geojson["numberMatched"]))
        self.assertEqual({link["rel"] for link in geojson["links"]}, {"self", "alternate", "prev", "next"})
        for link in geojson["links"]:
            self.assertIn(f'<{link["href"]}>; rel="{link["rel"]}"', arrow.headers["Link"])

    def test_encodings_vary_on_accept(self):
        # the same URL serves both encodings, which a cache has to tell apart
        url = f"{collections_url}/tests.point_2056_10fields/items"
        accepts = ["application/geo+json", *(["application/vnd.apache.arrow.stream"] if ARROW_AVAILABLE else [])]
        for item_url in (url, f"{url}/{Point_2056_10fields.objects.first().pk}"):
            for accept in accepts:
                with self.subTest(url=item_url, accept=accept):
                    response = self.client.get(item_url, headers={"Accept": accept})

                    self.assertEqual(response.status_code, 200)
                    self.assertIn("Accept", [value.strip() for value in response.headers["Vary"].split(",")])

    def test_collection_links_its_items_in_each_encoding(self):
        response = self.client.get(f"{collections_url}/tests.point_2056_10fields")

        self.assertEqual(response.status_code, 200)
        # but for the profile of JSON-FG
        items = [link for link in response.json()["links"] if link["rel"] == "items" and "profile" not in link]
        encodings = {"application/geo+json", *({"application/vnd.apache.arrow.stream"} if ARROW_AVAILABLE else ())}
        self.assertEqual({link["type"] for link in items}, encodings)
        # a single URL, negotiated with the Accept header
        self.assertEqual(len({link["href"] for link in items}), 1)

    def test_geojson_bbox_is_the_extent_of_the_page(self):
        for crs_uri, geometry in ((None, Transform("geom", 4326)), (crs_2056, "geom")):
            with self.subTest(crs=crs_uri or crs84):
                url = f"{collections_url}/tests.point_2056_10fields/items?limit=10&offset=20"
                if crs_uri:
                    url += f"&crs={crs_uri}"
                with CaptureQueriesContext(connection) as queries:
                    response = self.client.get(url, headers={"Accept": "application/geo+json"})

                self.assertEqual(response.status_code, 200)
                page = Point_2056_10fields.objects.order_by("pk")[20:30]
                self.assertEqual(tuple(response.json()["bbox"]), extent(page, geometry))
                # the boxes come along with the features, instead of from a query of their own, or from
                # reprojecting the geometries again
                self.assertFalse(any("ST_Extent" in query["sql"] for query in queries.captured_queries))
                transforms = sum(query["sql"].count("ST_Transform") for query in queries.captured_queries)
                self.assertEqual(transforms, 0 if crs_uri else 1)

    def test_featurecollection_is_complete_on_its_own(self):
        # it used to come back with numberMatched=0 and no bbox, for the endpoint to fill in
        collection = oapif.collections["tests.point_2056_10fields"]
        request = RequestFactory().get("/")
        crs = CRS("OGC", 4326)

        feature_collection = collection.queryset_to_featurecollection(request, collection.query(request, crs)[:5])

        self.assertEqual(feature_collection.numberReturned, 5)
        self.assertEqual(feature_collection.numberMatched, 5)
        self.assertIsNotNone(feature_collection.bbox)

    @requires_arrow
    def test_arrow_crs_matches_coordinates(self):
        # the column crs must describe the coordinates that are in it, not the storage srid
        for crs_uri, expected_crs in ((None, "OGC:CRS84"), (crs_2056, "EPSG:2056")):
            with self.subTest(crs=expected_crs):
                url = f"{collections_url}/tests.point_2056_10fields/items?limit=1"
                if crs_uri:
                    url += f"&crs={crs_uri}"
                arrow = self.client.get(url, headers={"Accept": "application/vnd.apache.arrow.stream"})
                geojson = self.client.get(url, headers={"Accept": "application/geo+json"})

                self.assertEqual(arrow.status_code, 200)
                self.assertEqual(geojson.status_code, 200)
                table = pa.ipc.open_stream(arrow.content).read_all()
                self.assertEqual(table.schema.field("geometry").type.crs, StringCrs(expected_crs))
                self.assertEqual(
                    jsonfg.loads(table["geometry"][0].as_py()),
                    geojson.json()["features"][0]["geometry"],
                )

    @requires_arrow
    def test_arrow_geometry_types(self):
        for collection, geometry_type in self.COLLECTIONS.items():
            with self.subTest(collection=collection):
                response = self.client.get(
                    f"{collections_url}/{collection}/items?limit=1",
                    headers={"Accept": "application/vnd.apache.arrow.stream"},
                )

                self.assertEqual(response.status_code, 200)
                table = pa.ipc.open_stream(response.content).read_all()
                if geometry_type is not None:
                    self.assertIn("geometry", table.schema.names)
                    geometry_field = table.schema.field("geometry")
                    self.assertIsNotNone(geometry_field)
                    self.assertIsInstance(geometry_field.type, WkbType)
                    self.assertEqual(geometry_field.type.crs, StringCrs("OGC:CRS84"))
                    self.assertEqual(geometry_field.type.extension_name, "geoarrow.wkb")
                    self.assertEqual(table.num_rows, 1)
                else:
                    self.assertNotIn("geometry", table.schema.names)


class TableText(HTMLParser):
    """The text of the cells of the tables of a page, row by row, the parts of a cell separated by a space."""

    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self.cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.rows.append([])
        elif tag in ("th", "td"):
            self.cell = []

    def handle_endtag(self, tag):
        if tag in ("th", "td"):
            self.rows[-1].append(" ".join(" ".join(self.cell).split()))
            self.cell = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def properties_table(page: str) -> dict[str, dict[str, str]]:
    """The table of the properties of a schema page, by property and by column."""
    parser = TableText()
    parser.feed(page)
    header, *rows = parser.rows
    return {row[0]: dict(zip(header, row)) for row in rows}


class TestHtml(TestCase):
    # what browsers send
    BROWSER = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
    HTML = "text/html; charset=utf-8"

    @classmethod
    def setUpTestData(cls):
        call_command("populate_data", "-s 10")
        call_command("populate_users")

    def urls(self) -> list[str]:
        point = Point_2056_10fields.objects.first().pk
        return [
            "/oapif/",
            "/oapif/conformance",
            collections_url,
            f"{collections_url}/tests.point_2056_10fields",
            f"{collections_url}/tests.point_2056_10fields/schema",
            f"{collections_url}/tests.point_2056_10fields/queryables",
            f"{collections_url}/tests.point_2056_10fields/items",
            f"{collections_url}/tests.point_2056_10fields/items/{point}",
            f"{collections_url}/tests.nogeom_10fields/items",
            f"{collections_url}/tests.arc_2056_10fields/items",
            f"{collections_url}/tests.point_2056_empty/items",
        ]

    def assertVariesOnAccept(self, response):
        self.assertIn("Accept", [value.strip() for value in response.headers["Vary"].split(",")])

    def test_browsers_get_the_pages(self):
        for url in self.urls():
            with self.subTest(url=url):
                response = self.client.get(url, headers=self.BROWSER)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], self.HTML)
                self.assertVariesOnAccept(response)

    def test_other_clients_get_the_json(self):
        # the JSON stays the default, for a client that accepts any type or does not say, but for the curves,
        # which GeoJSON refuses
        for url in [url for url in self.urls() if "arc_2056" not in url]:
            for headers in ({}, {"Accept": "*/*"}, {"Accept": "application/json"}):
                with self.subTest(url=url, headers=headers):
                    response = self.client.get(url, headers=headers)

                    self.assertEqual(response.status_code, 200)
                    self.assertRegex(response["Content-Type"], r"^application/((geo|schema)\+)?json")
                    self.assertVariesOnAccept(response)

    def test_f_chooses_over_the_accept_header(self):
        url = f"{collections_url}/tests.point_2056_10fields/items"

        self.assertEqual(self.client.get(url, {"f": "html"})["Content-Type"], self.HTML)
        self.assertEqual(
            self.client.get(url, {"f": "json"}, headers=self.BROWSER)["Content-Type"], "application/geo+json"
        )
        arrow = {"Accept": "application/vnd.apache.arrow.stream"}
        self.assertEqual(self.client.get(url, {"f": "html"}, headers=arrow)["Content-Type"], self.HTML)

    def test_json_links_the_page(self):
        collection_url = f"{collections_url}/tests.point_2056_10fields"
        # the conformance declaration and the schemas have no links
        for url in ("/oapif/", collections_url, collection_url, f"{collection_url}/items"):
            with self.subTest(url=url):
                links = self.client.get(url).json()["links"]

                [alternate] = [link for link in links if link["rel"] == "alternate"]
                self.assertEqual(alternate["type"], "text/html")
                self.assertEqual(self.client.get(alternate["href"])["Content-Type"], self.HTML)

    def page(self, url: str) -> str:
        return self.client.get(url, headers=self.BROWSER).content.decode()

    def test_schema_page_shows_the_constraints(self):
        rows = properties_table(self.page(f"{collections_url}/tests.layerwithconstraints/schema"))

        self.assertEqual(rows["id"]["Role"], "id")
        self.assertEqual(rows["kind"]["Default"], '"house"')
        self.assertEqual(rows["kind"]["Constraints"], 'maxLength 10 enum ["house", "shed"]')
        self.assertEqual(rows["score"]["Constraints"], "minimum 0 maximum 10")
        self.assertEqual(rows["code"]["Constraints"], "maxLength 5 minLength 2 pattern ^[A-Z]+$")
        self.assertEqual(rows["website"]["Type"], "string (uri)")
        self.assertEqual(rows["address"]["Type"], "string (ipv4)")

    def test_schema_page_shows_the_read_only_properties(self):
        rows = properties_table(self.page(f"{collections_url}/tests.layerwithfile/schema"))

        self.assertEqual((rows["file"]["Required"], rows["file"]["Read-only"]), ("yes", "yes"))
        self.assertEqual(rows["id"]["Read-only"], "")

    def test_schema_page_links_the_referenced_collections(self):
        page = self.page(f"{collections_url}/tests.layerwithforeignkey/schema")

        role = properties_table(page)["point"]["Role"]
        self.assertEqual(role, "reference tests.point_2056_10fields tests.point_2056_10fields_subset")
        self.assertIn(f'href="{collections_url}/tests.point_2056_10fields"', page)

    def test_schema_page_leaves_out_no_keyword(self):
        # a keyword the page has no column for, such as one a collection adds, is listed with the constraints
        collection = oapif.collections["tests.layerwithconstraints"]
        get_json_schema = collection.get_json_schema

        def with_unit(request):
            schema = get_json_schema(request)
            schema["properties"]["score"] |= {"description": "Out of ten", "x-ogc-unit": "point"}
            return schema

        with patch.object(collection, "get_json_schema", with_unit):
            rows = properties_table(self.page(f"{collections_url}/tests.layerwithconstraints/schema"))

        self.assertEqual(rows["score"]["Title"], "Score Out of ten")
        self.assertEqual(rows["score"]["Constraints"], "minimum 0 maximum 10 x-ogc-unit point")

    def test_queryables_page_links_the_geometry_schema(self):
        page = self.page(f"{collections_url}/tests.point_2056_10fields/queryables")

        self.assertEqual(properties_table(page)["geom"]["Role"], "primary-geometry")
        self.assertIn('href="https://geojson.org/schema/Point.json"', page)

    def test_landing_page_links_the_api_documentation(self):
        links = self.client.get("/oapif/").json()["links"]

        [doc] = [link for link in links if link["rel"] == "service-doc"]
        self.assertEqual(self.client.get(doc["href"]).status_code, 200)

    def test_items_page_shows_the_features(self):
        url = f"{collections_url}/tests.point_2056_10fields/items?limit=3&offset=3"
        geojson = self.client.get(url).json()

        page = self.client.get(url, headers=self.BROWSER).content.decode()

        for feature in geojson["features"]:
            self.assertIn(
                f'href="http://testserver{collections_url}/tests.point_2056_10fields/items/{feature["id"]}"', page
            )
        for link in geojson["links"]:
            if link["rel"] in ("prev", "next"):
                self.assertIn(f'href="{link["href"].replace("&", "&amp;")}"', page)
        self.assertIn("oapifMap(", page)

    def test_map_is_drawn_in_crs84_only(self):
        url = f"{collections_url}/tests.point_2056_10fields/items"

        page = self.client.get(url, {"crs": crs_2056}, headers=self.BROWSER)

        self.assertEqual(page.status_code, 200)
        self.assertNotIn("oapifMap(", page.content.decode())

    def test_pages_escape_the_properties(self):
        point = Point_2056_10fields.objects.first()
        point.field_str_0 = "<script>alert(1)</script>"
        point.save()
        urls = [
            f"{collections_url}/tests.point_2056_10fields/items",
            f"{collections_url}/tests.point_2056_10fields/items/{point.pk}",
        ]
        for url in urls:
            with self.subTest(url=url):
                page = self.client.get(url, {"limit": 1000}, headers=self.BROWSER).content.decode()

                self.assertNotIn("<script>alert(1)", page)
                self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)

    def test_pages_keep_the_permissions(self):
        url = f"{collections_url}/tests.secretlayer"
        for path in (url, f"{url}/items"):
            with self.subTest(path=path):
                page = self.client.get(path, headers=self.BROWSER)

                self.assertEqual(page.status_code, self.client.get(path).status_code)
                self.assertNotEqual(page.status_code, 200)
        self.assertNotIn("tests.secretlayer", self.client.get(collections_url, headers=self.BROWSER).content.decode())


class TestGeometry3D(TestCase):
    """Z ordinates must survive the WKB -> JSON-FG round trip, whatever the geometry type."""

    # WKT to store -> geometry expected back, unprojected, in EPSG:2056
    GEOMETRIES = {
        "point": (
            "POINT Z (2508500 1152000 555)",
            {"type": "Point", "coordinates": [2508500.0, 1152000.0, 555.0]},
        ),
        "linestring": (
            "LINESTRING Z (2508500 1152000 1, 2508600 1152100 2)",
            {"type": "LineString", "coordinates": [[2508500.0, 1152000.0, 1.0], [2508600.0, 1152100.0, 2.0]]},
        ),
        "polygon": (
            "POLYGON Z ((2508500 1152000 1, 2508600 1152000 2, 2508600 1152100 3, 2508500 1152000 1))",
            {
                "type": "Polygon",
                "coordinates": [
                    [
                        [2508500.0, 1152000.0, 1.0],
                        [2508600.0, 1152000.0, 2.0],
                        [2508600.0, 1152100.0, 3.0],
                        [2508500.0, 1152000.0, 1.0],
                    ]
                ],
            },
        ),
        "multipoint": (
            "MULTIPOINT Z ((2508500 1152000 1), (2508600 1152100 2))",
            {"type": "MultiPoint", "coordinates": [[2508500.0, 1152000.0, 1.0], [2508600.0, 1152100.0, 2.0]]},
        ),
        "multilinestring": (
            "MULTILINESTRING Z ((2508500 1152000 1, 2508600 1152100 2))",
            {
                "type": "MultiLineString",
                "coordinates": [[[2508500.0, 1152000.0, 1.0], [2508600.0, 1152100.0, 2.0]]],
            },
        ),
        "multipolygon": (
            "MULTIPOLYGON Z (((2508500 1152000 1, 2508600 1152000 2, 2508600 1152100 3, 2508500 1152000 1)))",
            {
                "type": "MultiPolygon",
                "coordinates": [
                    [
                        [
                            [2508500.0, 1152000.0, 1.0],
                            [2508600.0, 1152000.0, 2.0],
                            [2508600.0, 1152100.0, 3.0],
                            [2508500.0, 1152000.0, 1.0],
                        ]
                    ]
                ],
            },
        ),
        "geometrycollection": (
            "GEOMETRYCOLLECTION Z (POINT Z (2508500 1152000 1), LINESTRING Z (2508500 1152000 1, 2508600 1152100 2))",
            {
                "type": "GeometryCollection",
                "geometries": [
                    {"type": "Point", "coordinates": [2508500.0, 1152000.0, 1.0]},
                    {
                        "type": "LineString",
                        "coordinates": [[2508500.0, 1152000.0, 1.0], [2508600.0, 1152100.0, 2.0]],
                    },
                ],
            },
        ),
        # GeoJSON has no polyhedral types, so they come back as their closest equivalent
        "triangle": (
            "TRIANGLE Z ((2508500 1152000 1, 2508600 1152000 2, 2508600 1152100 3, 2508500 1152000 1))",
            {
                "type": "Polygon",
                "coordinates": [
                    [
                        [2508500.0, 1152000.0, 1.0],
                        [2508600.0, 1152000.0, 2.0],
                        [2508600.0, 1152100.0, 3.0],
                        [2508500.0, 1152000.0, 1.0],
                    ]
                ],
            },
        ),
        "tin": (
            "TIN Z (((2508500 1152000 1, 2508600 1152000 2, 2508600 1152100 3, 2508500 1152000 1)))",
            {
                "type": "MultiPolygon",
                "coordinates": [
                    [
                        [
                            [2508500.0, 1152000.0, 1.0],
                            [2508600.0, 1152000.0, 2.0],
                            [2508600.0, 1152100.0, 3.0],
                            [2508500.0, 1152000.0, 1.0],
                        ]
                    ]
                ],
            },
        ),
        "polyhedralsurface": (
            "POLYHEDRALSURFACE Z (((2508500 1152000 1, 2508600 1152000 1, 2508600 1152100 1, "
            "2508500 1152100 1, 2508500 1152000 1)))",
            {
                "type": "MultiPolygon",
                "coordinates": [
                    [
                        [
                            [2508500.0, 1152000.0, 1.0],
                            [2508600.0, 1152000.0, 1.0],
                            [2508600.0, 1152100.0, 1.0],
                            [2508500.0, 1152100.0, 1.0],
                            [2508500.0, 1152000.0, 1.0],
                        ]
                    ]
                ],
            },
        ),
        "circularstring": (
            "CIRCULARSTRING Z (2508500 1152000 1, 2508550 1152050 2, 2508600 1152000 3)",
            {
                "type": "CircularString",
                "coordinates": [
                    [2508500.0, 1152000.0, 1.0],
                    [2508550.0, 1152050.0, 2.0],
                    [2508600.0, 1152000.0, 3.0],
                ],
            },
        ),
    }

    @classmethod
    def setUpTestData(cls):
        # The GEOS version used by geodjango does not support curves, so insert the WKT as is
        table_name = connection.ops.quote_name(GeometryZ_2056._meta.db_table)
        cls.ids = {name: uuid.uuid4() for name in cls.GEOMETRIES}
        with connection.cursor() as cursor:
            cursor.executemany(
                f"INSERT INTO {table_name} (id, geom) VALUES (%s, ST_GeomFromEWKT(%s))",
                [(cls.ids[name], f"SRID=2056;{wkt}") for name, (wkt, _) in cls.GEOMETRIES.items()],
            )

    def test_item_keeps_z(self):
        for name, (_, expected) in self.GEOMETRIES.items():
            with self.subTest(geometry=name):
                response = self.client.get(
                    f"{collections_url}/tests.geometryz_2056/items/{self.ids[name]}?crs={crs_2056}&profile=jsonfg",
                    headers={"Accept": "application/geo+json"},
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(geometry_of(response.json()), expected)

    def test_items_keep_z(self):
        response = self.client.get(
            f"{collections_url}/tests.geometryz_2056/items?crs={crs_2056}&profile=jsonfg",
            headers={"Accept": "application/geo+json"},
        )

        self.assertEqual(response.status_code, 200)
        features = {feature["id"]: geometry_of(feature) for feature in response.json()["features"]}
        expected = {str(self.ids[name]): geometry for name, (_, geometry) in self.GEOMETRIES.items()}
        self.assertEqual(features, expected)

    def test_wkb_reader_accepts_iso_and_ewkb(self):
        # query() asks for ISO WKB, but the reader must cope with the EWKB a bytea cast returns too
        for name, (wkt, expected) in self.GEOMETRIES.items():
            for flavour in ("ST_AsBinary", "ST_AsEWKB"):
                with self.subTest(geometry=name, flavour=flavour):
                    with connection.cursor() as cursor:
                        cursor.execute(f"SELECT {flavour}(ST_GeomFromEWKT(%s))", [f"SRID=2056;{wkt}"])
                        wkb = bytes(cursor.fetchone()[0])

                    self.assertEqual(jsonfg.loads(wkb), expected)

    def test_item_reprojected_keeps_z(self):
        # Transform() must not drop the Z ordinate either
        response = self.client.get(
            f"{collections_url}/tests.geometryz_2056/items/{self.ids['point']}",
            headers={"Accept": "application/geo+json"},
        )

        self.assertEqual(response.status_code, 200)
        coordinates = response.json()["geometry"]["coordinates"]
        self.assertEqual(len(coordinates), 3)
        self.assertAlmostEqual(coordinates[2], 555.0, places=3)


class TestBounds(TestCase):
    """The bbox of a page is the union of the boxes the WKB reader gathers: they have to be the PostGIS ones."""

    WKTS = (
        "POINT (2600000 1200000)",
        "POINT EMPTY",
        "LINESTRING (0 0, 3 -1, 2 5)",
        "POLYGON ((0 0, 4 0, 4 3, 0 0), (1 0.5, 3 0.5, 3 2, 1 0.5))",
        "POLYGON Z ((0 0 5, 4 0 6, 4 3 7, 0 0 5))",
        "MULTIPOINT ((0 0), (5 -1))",
        "MULTIPOLYGON (((0 0, 1 0, 1 1, 0 0)), ((10 10, 11 10, 11 12, 10 10)))",
        "GEOMETRYCOLLECTION (POINT (-3 7), LINESTRING (0 0, 1 1))",
        # an arc that reaches beyond its points, a full circle, and aligned points
        "CIRCULARSTRING (0.5 0.8660254037844386, -1 0, 0.5 -0.8660254037844386)",
        "CIRCULARSTRING (0 0, 2 0, 0 0)",
        "CIRCULARSTRING (0 0, 1 1, 2 2)",
        "COMPOUNDCURVE (CIRCULARSTRING (0 0, 1 1, 2 0), (2 0, 3 -1))",
        "CURVEPOLYGON (CIRCULARSTRING (0 0, 4 0, 0 0), (1 -1, 3 -1, 3 1, 1 -1))",
        "MULTICURVE (CIRCULARSTRING (0 0, 1 1, 2 0), (5 5, 6 7))",
        "MULTISURFACE (CURVEPOLYGON (CIRCULARSTRING (0 0, 4 0, 0 0)), ((10 10, 11 10, 11 12, 10 10)))",
    )

    def test_bounds_are_the_postgis_box(self):
        for wkt in self.WKTS:
            with self.subTest(wkt=wkt):
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT ST_AsBinary(g), ST_XMin(b), ST_YMin(b), ST_XMax(b), ST_YMax(b)"
                        " FROM ST_GeomFromText(%s) AS g, Box2D(g) AS b",
                        [wkt],
                    )
                    wkb, *box = cursor.fetchone()
                bounds = []
                jsonfg.loads(bytes(wkb), bounds)

                if box[0] is None:
                    self.assertEqual(bounds, [])
                else:
                    xmins, ymins, xmaxs, ymaxs = zip(*bounds)
                    self.assertEqual((min(xmins), min(ymins), max(xmaxs), max(ymaxs)), tuple(box))


class TestCrs(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("populate_users")
        call_command("populate_data", "-s 100")

    def test_uri_keeps_the_requested_authority(self):
        # EPSG:4326 is lat/lon and CRS84 is lon/lat, so the two must not be conflated
        self.assertEqual(CRS("OGC", 4326).uri(), crs84)
        self.assertEqual(CRS("EPSG", 4326).uri(), "http://www.opengis.net/def/crs/EPSG/0/4326")
        self.assertEqual(CRS("EPSG", 2056).uri(), crs_2056)

    def test_extent_takes_no_reprojection_of_every_geometry(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(f"{collections_url}/tests.point_2056_10fields")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(any("ST_Extent(ST_Transform(" in query["sql"] for query in queries.captured_queries))

    def test_extent_covers_the_bulge_of_its_reprojected_edges(self):
        # the top edge of a box across Switzerland bulges north by over a kilometre once reprojected, so a
        # point in the middle of it would lie outside an extent made of the reprojected corners alone
        for x, y in ((2485000, 1075000), (2834000, 1296000), (2659500, 1296000)):
            Point_2056_Empty.objects.create(geom=f"SRID=2056;POINT({x} {y})")

        response = self.client.get(f"{collections_url}/tests.point_2056_empty")

        self.assertEqual(response.status_code, 200)
        xmin, ymin, xmax, ymax = response.json()["extent"]["spatial"]["bbox"][0]
        exact = Point_2056_Empty.objects.aggregate(extent=Extent(Transform("geom", 4326)))["extent"]
        self.assertLessEqual(xmin, exact[0])
        self.assertLessEqual(ymin, exact[1])
        self.assertGreaterEqual(xmax, exact[2])
        self.assertGreaterEqual(ymax, exact[3])

    def test_extent_covers_only_the_rows_the_collection_serves(self):
        # a collection filtering its rows, such as one serving each user their own, used to give the extent of
        # every row of its model
        url = f"{collections_url}/tests.point_2056_empty"
        for x, y in ((2600000, 1200000), (2601000, 1201000)):
            Point_2056_Empty.objects.create(geom=f"SRID=2056;POINT({x} {y})", field_str_0="served")
        served_extent = self.client.get(url).json()["extent"]
        Point_2056_Empty.objects.create(geom="SRID=2056;POINT(2700000 1100000)", field_str_0="filtered out")
        collection = oapif.collections["tests.point_2056_empty"]
        get_queryset = collection.get_queryset

        def served(request):
            return get_queryset(request).filter(field_str_0="served")

        with patch.object(collection, "get_queryset", served):
            response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["extent"], served_extent)

    def test_crs84_extent_covers_only_the_rows_the_collection_serves(self):
        # a collection stored in CRS84, Django's default srid, takes the extent of its rows as it is: here, those of
        # EPSG:2056, which no model of the tests is stored in
        url = f"{collections_url}/tests.point_2056_empty"
        for x, y in ((2600000, 1200000), (2601000, 1201000)):
            Point_2056_Empty.objects.create(geom=f"SRID=2056;POINT({x} {y})", field_str_0="served")
        Point_2056_Empty.objects.create(geom="SRID=2056;POINT(2700000 1100000)", field_str_0="filtered out")
        collection = oapif.collections["tests.point_2056_empty"]
        get_queryset = collection.get_queryset

        def served(request):
            return get_queryset(request).filter(field_str_0="served")

        with patch.object(collection, "srid", CRS84_SRID), patch.object(collection, "get_queryset", served):
            response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["extent"]["spatial"]["bbox"], [[2600000, 1200000, 2601000, 1201000]])

    def test_extent_covers_features_on_one_northing_or_easting(self):
        # points on one northing or one easting have an extent of no height or no width, which PostGIS casts to a
        # line: it has no perimeter to densify it by, and the collection answered 500. A line along one northing
        # still bulges north in its middle once reprojected. The extent of a single point is cast to a point, which
        # ST_Segmentize returns as it is, even with a step of 0
        for points in (
            ((2485000, 1296000), (2834000, 1296000), (2659500, 1296000)),
            ((2834000, 1075000), (2834000, 1296000)),
            ((2600000, 1200000),),
        ):
            with self.subTest(points=points):
                Point_2056_Empty.objects.all().delete()
                for x, y in points:
                    Point_2056_Empty.objects.create(geom=f"SRID=2056;POINT({x} {y})")

                response = self.client.get(f"{collections_url}/tests.point_2056_empty")

                self.assertEqual(response.status_code, 200)
                xmin, ymin, xmax, ymax = response.json()["extent"]["spatial"]["bbox"][0]
                exact = Point_2056_Empty.objects.aggregate(extent=Extent(Transform("geom", 4326)))["extent"]
                self.assertLessEqual(xmin, exact[0])
                self.assertLessEqual(ymin, exact[1])
                self.assertGreaterEqual(xmax, exact[2])
                self.assertGreaterEqual(ymax, exact[3])

    def test_advertised_crs_are_accepted(self):
        collection_response = self.client.get(f"{collections_url}/tests.point_2056_10fields")

        self.assertEqual(collection_response.status_code, 200)
        advertised = collection_response.json()["crs"]
        self.assertEqual(advertised, [crs84, crs_2056])
        self.assertEqual(collection_response.json()["storageCrs"], crs_2056)
        for crs in advertised:
            with self.subTest(crs=crs):
                url = f"{collections_url}/tests.point_2056_10fields/items?limit=1&crs={crs}"
                items_response = self.client.get(url)

                self.assertEqual(items_response.status_code, 200)
                self.assertEqual(items_response.headers["Content-Crs"], f"<{crs}>")

    def test_unadvertised_crs_is_rejected(self):
        # EPSG:4326 is not the same as CRS84 and the collection does not offer it
        for crs in (f"{crs_base}/EPSG/0/4326", f"{crs_base}/EPSG/0/3857"):
            with self.subTest(crs=crs):
                items = self.client.get(f"{collections_url}/tests.point_2056_10fields/items?crs={crs}")
                self.assertEqual(items.status_code, 400)

                item_id = self.client.get(f"{collections_url}/tests.point_2056_10fields/items?limit=1").json()[
                    "features"
                ][0]["id"]
                item = self.client.get(f"{collections_url}/tests.point_2056_10fields/items/{item_id}?crs={crs}")
                self.assertEqual(item.status_code, 400)

    def test_writes_take_only_an_advertised_content_crs(self):
        # coordinates are always read as x/y: a client sending EPSG:4326 latitude first would have its
        # features stored with swapped coordinates, so a CRS the collection does not offer is refused
        self.client.force_login(User.objects.get(username="demo_editor"))
        url = f"{collections_url}/tests.point_2056_10fields/items"
        item_url = f"{url}/{Point_2056_10fields.objects.first().pk}"
        for crs, coordinates, status in (
            (crs84, [7.44, 46.95], 201),
            (crs_2056, [2600000.0, 1200000.0], 201),
            (f"{crs_base}/EPSG/0/4326", [46.95, 7.44], 400),
            (f"{crs_base}/EPSG/0/3857", [828000.0, 5933000.0], 400),
        ):
            with self.subTest(crs=crs):
                feature = {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": coordinates},
                    "properties": {},
                }
                crs_header = {"Content-Crs": crs}
                post = self.client.post(url, feature, content_type="application/json", headers=crs_header)
                self.assertEqual(post.status_code, status)
                if status == 400:
                    for method in (self.client.put, self.client.patch):
                        response = method(item_url, feature, content_type="application/json", headers=crs_header)
                        self.assertEqual(response.status_code, 400)

    def test_content_crs_of_a_response_is_taken_by_writes(self):
        # the header has the URI in angle brackets: a client that sent it back as it came used to be refused
        self.client.force_login(User.objects.get(username="demo_editor"))
        url = f"{collections_url}/tests.point_2056_10fields/items"
        content_crs = self.client.get(f"{url}?limit=1&crs={crs_2056}").headers["Content-Crs"]
        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [2600000.0, 1200000.0]},
            "properties": {},
        }

        post = self.client.post(url, feature, content_type="application/json", headers={"Content-Crs": content_crs})

        self.assertEqual(content_crs, f"<{crs_2056}>")
        self.assertEqual(post.status_code, 201)
        # and read in the CRS it names
        self.assertEqual(Point_2056_10fields.objects.get(pk=post.json()["id"]).geom.coords, (2600000.0, 1200000.0))

    def test_unadvertised_bbox_crs_is_rejected(self):
        url = f"{collections_url}/tests.point_2056_10fields/items?bbox=0,0,1,1&bbox-crs={crs_base}/EPSG/0/3857"

        self.assertEqual(self.client.get(url).status_code, 400)

    def test_geometry_less_collection_ignores_crs(self):
        collection_response = self.client.get(f"{collections_url}/tests.nogeom_10fields")

        self.assertEqual(collection_response.status_code, 200)
        self.assertIsNone(collection_response.json().get("crs"))
        items = self.client.get(f"{collections_url}/tests.nogeom_10fields/items?limit=1&crs={crs_base}/EPSG/0/3857")
        self.assertEqual(items.status_code, 200)

    def test_collection_leaves_out_the_members_it_has_no_value_for(self):
        # they used to be null, which OGC API - Features does not allow
        listed = {collection["id"]: collection for collection in self.client.get(collections_url).json()["collections"]}
        for collection_id, members in (
            ("tests.point_2056_10fields", {"crs", "storageCrs", "extent"}),
            ("tests.point_2056_empty", {"crs", "storageCrs"}),
            ("tests.nogeom_10fields", set()),
        ):
            with self.subTest(collection=collection_id):
                response = self.client.get(f"{collections_url}/{collection_id}")

                self.assertEqual(response.status_code, 200)
                for collection in (response.json(), listed[collection_id]):
                    self.assertEqual([name for name, value in collection.items() if value is None], [])
                    self.assertEqual(collection.keys() & {"description", "crs", "storageCrs", "extent"}, members)


class TestCircularString(TestCase):
    """A CircularString is a sequence of arcs, so any odd number of at least 3 points is valid."""

    POINT_COUNTS = (3, 5, 13, 27)

    @staticmethod
    def arc_wkt(point_count: int) -> str:
        points = ", ".join(f"{2508500 + i * 10} {1152000 + (i % 2) * 10}" for i in range(point_count))
        return f"CIRCULARSTRING({points})"

    @classmethod
    def setUpTestData(cls):
        call_command("populate_users")
        # The GEOS version used by geodjango does not support curves, so insert the WKT as is
        table_name = connection.ops.quote_name(Arc_2056_10fields._meta.db_table)
        cls.ids = {count: uuid.uuid4() for count in cls.POINT_COUNTS}
        with connection.cursor() as cursor:
            cursor.executemany(
                f"INSERT INTO {table_name} (id, geom) VALUES (%s, ST_GeomFromText(%s, 2056))",
                [(cls.ids[count], cls.arc_wkt(count)) for count in cls.POINT_COUNTS],
            )

    def test_arc_of_any_odd_length_is_served(self):
        for count in self.POINT_COUNTS:
            with self.subTest(points=count):
                response = self.client.get(
                    f"{collections_url}/tests.arc_2056_10fields/items/{self.ids[count]}", {"profile": "jsonfg"}
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(arc_points(response.json()["place"])), count)

    def test_long_arc_is_served_in_parts(self):
        # JSON-FG allows 11 points in a CircularString, so a longer one is the CompoundCurve of its arcs
        for count, sizes in ((5, None), (13, [11, 3]), (27, [11, 11, 7])):
            with self.subTest(points=count):
                response = self.client.get(
                    f"{collections_url}/tests.arc_2056_10fields/items/{self.ids[count]}", {"profile": "jsonfg"}
                )

                geometry = response.json()["place"]
                if sizes is None:
                    self.assertEqual(geometry["type"], "CircularString")
                else:
                    self.assertEqual(geometry["type"], "CompoundCurve")
                    self.assertEqual([len(part["coordinates"]) for part in geometry["geometries"]], sizes)

    def test_long_arc_in_a_compound_curve_is_flattened(self):
        # a CompoundCurve cannot hold another, so the parts of the arc take its place
        line = "(2508480 1152000, 2508500 1152000)"
        arc = self.arc_wkt(13).removeprefix("CIRCULARSTRING")
        with connection.cursor() as cursor:
            cursor.execute("SELECT ST_AsBinary(ST_GeomFromText(%s))", [f"COMPOUNDCURVE({line}, CIRCULARSTRING{arc})"])
            geometry = jsonfg.loads(bytes(cursor.fetchone()[0]))

        self.assertEqual(geometry["type"], "CompoundCurve")
        self.assertEqual([part["type"] for part in geometry["geometries"]], ["LineString", *["CircularString"] * 2])

    def test_disjoint_arc_parts_are_a_client_error(self):
        # parts that do not follow one another cannot be joined back into a CircularString
        self.client.force_login(User.objects.get(username="demo_editor"))
        parts = [{"type": "CircularString", "coordinates": arc(x, 1152000.0)} for x in (2508500.0, 2508600.0)]

        response = self.client.post(
            f"{collections_url}/tests.arc_2056_10fields/items",
            {"type": "Feature", "geometry": {"type": "CompoundCurve", "geometries": parts}, "properties": {}},
            headers=headers,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("last point of the previous", response.content.decode())

    def test_bbox_follows_the_arcs(self):
        # an arc can reach beyond its control points: this one goes up to 1200100, its points to 1200060
        table_name = connection.ops.quote_name(Arc_2056_10fields._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {table_name} (id, geom) VALUES (%s, ST_GeomFromText(%s, 2056))",
                [uuid.uuid4(), "CIRCULARSTRING(2600000 1200000, 2600020 1200060, 2600200 1200000)"],
            )

        for crs_uri, geometry in ((None, Transform("geom", 4326)), (crs_2056, "geom")):
            with self.subTest(crs=crs_uri or crs84):
                url = f"{collections_url}/tests.arc_2056_10fields/items?profile=jsonfg"
                response = self.client.get(f"{url}&crs={crs_uri}" if crs_uri else url)

                self.assertEqual(response.status_code, 200)
                bbox = tuple(response.json()["bbox"])
                self.assertEqual(bbox, extent(Arc_2056_10fields.objects, geometry))
                if crs_uri:
                    self.assertGreater(bbox[3], 1200099)

    def test_arc_item_options(self):
        response = self.client.options(f"{collections_url}/tests.arc_2056_10fields/items/{self.ids[3]}")

        self.assertEqual(response.status_code, 200)

    def test_arc_can_be_deleted(self):
        # fetching an item to act on used to load the geometry through GEOS, which has no curve support
        self.client.force_login(User.objects.get(username="demo_editor"))
        url = f"{collections_url}/tests.arc_2056_10fields/items/{self.ids[3]}"

        self.assertEqual(self.client.delete(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_arc_of_even_points_is_a_client_error(self):
        # the validation error used to carry a ValueError, which could not be serialized: a 500
        self.client.force_login(User.objects.get(username="demo_editor"))
        arc = {"type": "CircularString", "coordinates": [[2508500.0, 1152000.0], [2508510.0, 1152010.0]]}

        response = self.client.post(
            f"{collections_url}/tests.arc_2056_10fields/items",
            {"type": "Feature", "geometry": arc, "properties": {}},
            headers=headers,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("odd number", response.content.decode())

    def test_other_geometry_type_is_a_client_error(self):
        # a curve column validated against any geometry type, and the insert then failed in the database
        self.client.force_login(User.objects.get(username="demo_editor"))
        line = {"type": "LineString", "coordinates": [[2508500.0, 1152000.0], [2508520.0, 1152000.0]]}

        response = self.client.post(
            f"{collections_url}/tests.arc_2056_10fields/items",
            {"type": "Feature", "geometry": line, "properties": {}},
            headers=headers,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 422)

    def test_empty_arc_is_accepted(self):
        arc = CircularString[Coordinate2D](type="CircularString", coordinates=[])

        self.assertEqual(arc.coordinates, [])

    def test_arc_of_even_or_too_few_points_is_rejected(self):
        for count in (1, 2, 4, 12):
            with self.subTest(points=count):
                with self.assertRaises(PydanticValidationError):
                    CircularString[Coordinate2D](
                        type="CircularString",
                        coordinates=[(float(i), 0.0) for i in range(count)],
                    )

    def test_arc_lengths_are_published(self):
        # the validator does not show in the OpenAPI document, so the lengths of JSON-FG are listed there
        schemas = self.client.get("/oapif/openapi.json").json()["components"]["schemas"]
        lengths = schemas["CircularString_Coordinate_"]["properties"]["coordinates"]["oneOf"]

        self.assertEqual([length.get("minItems", 0) for length in lengths], [0, 3, 5, 7, 9, 11])
        self.assertEqual([length["maxItems"] for length in lengths], [0, 3, 5, 7, 9, 11])


class TestJsonFg(TestCase):
    """
    GeoJSON has no curves, which JSON-FG gives in "place", "geometry" being null: a client asks for it with the
    profile of Part 5, the jsonfg one, and a request of curves in GeoJSON is refused.
    """

    ARC = "CIRCULARSTRING(2508500 1152000, 2508510 1152010, 2508520 1152000)"
    CONFORMS_TO = [
        "http://www.opengis.net/spec/json-fg-1/1.0/conf/core",
        "http://www.opengis.net/spec/json-fg-1/1.0/conf/circular-arcs",
    ]
    JSONFG = "http://www.opengis.net/def/profile/ogc/0/jsonfg"

    @classmethod
    def setUpTestData(cls):
        call_command("populate_users")
        # inserted as they are: GEOS may not know curves
        cls.arc_id, cls.curve_id, cls.point_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        rows = {
            Arc_2056_10fields: [(cls.arc_id, cls.ARC)],
            Geometry_2056: [(cls.curve_id, cls.ARC), (cls.point_id, "POINT(2508500 1152000)")],
        }
        with connection.cursor() as cursor:
            for model, values in rows.items():
                table_name = connection.ops.quote_name(model._meta.db_table)
                cursor.executemany(
                    f"INSERT INTO {table_name} (id, geom) VALUES (%s, ST_GeomFromText(%s, 2056))",
                    [(str(pk), wkt) for pk, wkt in values],
                )
        cls.point = Point_2056_10fields.objects.create(geom="POINT(2508500 1152000)")

    def test_curves_are_in_place(self):
        response = self.client.get(f"{collections_url}/tests.arc_2056_10fields/items", {"profile": "jsonfg"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/geo+json")
        collection = response.json()
        self.assertEqual(collection["conformsTo"], self.CONFORMS_TO)
        self.assertEqual(collection["coordRefSys"], crs84)
        [feature] = collection["features"]
        self.assertIsNone(feature["geometry"])
        self.assertEqual(feature["place"]["type"], "CircularString")
        # only the root of a document declares its classes and its CRS
        self.assertFalse({"conformsTo", "coordRefSys"} & set(feature))

    def test_curves_are_in_the_crs_asked_for(self):
        url = f"{collections_url}/tests.arc_2056_10fields/items"

        response = self.client.get(url, {"crs": crs_2056, "profile": "jsonfg"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["coordRefSys"], crs_2056)
        self.assertEqual(response.json()["features"][0]["place"]["coordinates"][0], [2508500.0, 1152000.0])

    def test_feature_on_its_own_is_a_jsonfg_document(self):
        url = f"{collections_url}/tests.arc_2056_10fields/items/{self.arc_id}"

        response = self.client.get(url, {"crs": crs_2056, "profile": "jsonfg"})

        self.assertEqual(response.status_code, 200)
        feature = response.json()
        self.assertEqual(feature["conformsTo"], self.CONFORMS_TO)
        self.assertEqual(feature["coordRefSys"], crs_2056)
        self.assertIsNone(feature["geometry"])
        self.assertEqual(
            feature["place"],
            {
                "type": "CircularString",
                "coordinates": [[2508500.0, 1152000.0], [2508510.0, 1152010.0], [2508520.0, 1152000.0]],
            },
        )

    def test_jsonfg_members_come_first(self):
        # GDAL tells JSON-FG from GeoJSON by the members it finds at the start of a document, before the features
        url = f"{collections_url}/tests.arc_2056_10fields/items"
        for document_url in (url, f"{url}/{self.arc_id}"):
            with self.subTest(url=document_url):
                content = self.client.get(document_url, {"profile": "jsonfg"}).content

                self.assertRegex(content, rb'^\{"type":"Feature(Collection)?","conformsTo":\[[^]]*\],"coordRefSys":"')

    def test_geometries_of_jsonfg_follow_the_crs(self):
        # JSON-FG gives "geometry" in CRS84, and a geometry in another CRS in "place"
        url = f"{collections_url}/tests.point_2056_10fields/items/{self.point.pk}"
        for crs, member in ((crs84, "geometry"), (crs_2056, "place")):
            with self.subTest(crs=crs):
                feature = self.client.get(url, {"crs": crs, "profile": "jsonfg"}).json()

                self.assertEqual(feature["conformsTo"], self.CONFORMS_TO[:1])
                self.assertEqual(feature["coordRefSys"], crs)
                self.assertEqual(feature[member]["type"], "Point")
                self.assertIsNone(feature["place" if member == "geometry" else "geometry"])

    def test_geometries_among_curves_follow_the_crs(self):
        url = f"{collections_url}/tests.geometry_2056/items"
        for crs, in_geometry in ((crs84, {str(self.point_id)}), (crs_2056, set())):
            with self.subTest(crs=crs):
                page = self.client.get(url, {"crs": crs, "profile": "jsonfg"}).json()

                self.assertEqual(page["coordRefSys"], crs)
                features = {feature["id"]: feature for feature in page["features"]}
                self.assertEqual({pk for pk, feature in features.items() if feature["geometry"]}, in_geometry)
                self.assertEqual(
                    {pk for pk, feature in features.items() if feature["place"]}, features.keys() - in_geometry
                )

    def test_jsonfg_is_asked_for_with_the_profile(self):
        # by the query parameter of Part 5, and the parameter of the media type
        url = f"{collections_url}/tests.point_2056_10fields/items"
        for params, accept in (
            ({"profile": "jsonfg"}, "application/geo+json"),
            ({"profile": self.JSONFG}, "application/geo+json"),
            # as the OGC register writes it
            ({"profile": self.JSONFG.replace("/ogc/", "/OGC/")}, "application/geo+json"),
            ({"profile": "flatgeobuf,jsonfg"}, "application/geo+json"),
            ({}, f'application/geo+json; profile="{self.JSONFG}"'),
            # and not taken for another type than the one it goes with
            ({}, f'application/geo+json; profile="{self.JSONFG}", text/html;q=0.1'),
        ):
            for item_url in (url, f"{url}/{self.point.pk}"):
                with self.subTest(url=item_url, params=params, accept=accept):
                    response = self.client.get(item_url, params, headers={"Accept": accept})

                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response["Content-Type"], "application/geo+json")
                    self.assertEqual(response.json()["conformsTo"], self.CONFORMS_TO[:1])
                    self.assertIn("Accept", [value.strip() for value in response["Vary"].split(",")])

    def test_geojson_is_the_default(self):
        url = f"{collections_url}/tests.point_2056_10fields/items"
        for params in ({}, {"crs": crs_2056}, {"profile": "rfc7946"}, {"profile": "unknown"}):
            for item_url in (url, f"{url}/{self.point.pk}"):
                with self.subTest(url=item_url, **params):
                    document = self.client.get(item_url, params).json()

                    self.assertFalse({"conformsTo", "coordRefSys"} & set(document))
                    for feature in document.get("features", [document]):
                        self.assertNotIn("place", feature)
                        self.assertIsNotNone(feature["geometry"])

    def test_geojson_refuses_curves(self):
        # rather than give features without geometry, or with one GeoJSON has not: the answer links them in JSON-FG
        url = f"{collections_url}/tests.arc_2056_10fields/items"
        for params, accept in (
            ({}, "application/geo+json"),
            ({}, "application/json"),
            ({}, "*/*"),
            ({"profile": "rfc7946"}, "application/geo+json"),
        ):
            for item_url in (url, f"{url}/{self.arc_id}"):
                with self.subTest(url=item_url, params=params, accept=accept):
                    response = self.client.get(item_url, {**params, "crs": crs_2056}, headers={"Accept": accept})

                    self.assertEqual(response.status_code, 406)
                    self.assertIn("Accept", [value.strip() for value in response["Vary"].split(",")])
                    [jsonfg_link, linearized_link] = response.json()["links"]
                    self.assertEqual(jsonfg_link["profile"], [self.JSONFG])
                    self.assertNotIn("profile", linearized_link)
                    jsonfg = self.client.get(jsonfg_link["href"])
                    linearized = self.client.get(linearized_link["href"])
                    self.assertEqual(jsonfg.status_code, 200)
                    self.assertEqual(jsonfg.json()["conformsTo"], self.CONFORMS_TO)
                    self.assertEqual(linearized.status_code, 200)
                    self.assertNotIn("conformsTo", linearized.json())
                    # in the CRS asked for
                    self.assertEqual(jsonfg["Content-Crs"], f"<{crs_2056}>")
                    self.assertEqual(linearized["Content-Crs"], f"<{crs_2056}>")

    def test_curve_column_refuses_geojson_on_every_page(self):
        # even without a feature
        response = self.client.get(f"{collections_url}/tests.arc_2056_10fields/items", {"bbox": "0,0,1,1"})

        self.assertEqual(response.status_code, 406)

    def test_page_with_a_curve_refuses_geojson(self):
        # a geometry column of any type may hold curves: its pages are refused in GeoJSON as they have one
        url = f"{collections_url}/tests.geometry_2056/items"
        for offset in (0, 1):
            with self.subTest(offset=offset):
                page = self.client.get(url, {"limit": 1, "offset": offset})
                jsonfg = self.client.get(url, {"limit": 1, "offset": offset, "profile": "jsonfg"}).json()

                [feature] = jsonfg["features"]
                self.assertEqual(page.status_code, 406 if feature["id"] == str(self.curve_id) else 200)
        self.assertEqual(self.client.get(f"{url}/{self.curve_id}").status_code, 406)
        self.assertEqual(self.client.get(f"{url}/{self.point_id}").status_code, 200)

    @skipUnless(writes_curves(), "needs GEOS 3.13 or newer and a Django that supports curves")
    def test_curve_written_is_returned_in_jsonfg(self):
        self.client.force_login(User.objects.get(username="demo_editor"))
        curve = {"type": "CircularString", "coordinates": arc(2508500.0, 1152000.0)}

        response = self.client.post(
            f"{collections_url}/tests.arc_2056_10fields/items",
            {"type": "Feature", "geometry": curve, "properties": {}},
            headers=headers,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response["Content-Type"], "application/geo+json")
        self.assertEqual(response.json()["conformsTo"], self.CONFORMS_TO)
        self.assertIsNone(response.json()["geometry"])
        self.assertEqual(response.json()["place"]["type"], "CircularString")

    def test_pages_draw_the_curves(self):
        url = f"{collections_url}/tests.arc_2056_10fields/items"
        for page_url in (url, f"{url}/{self.arc_id}"):
            with self.subTest(url=page_url):
                page = self.client.get(page_url, {"f": "html"})

                self.assertEqual(page.status_code, 200)
                self.assertIn("oapifMap(", page.content.decode())
                self.assertIn("CircularString", page.content.decode())

    def linearized(self, pk, crs: CRS, tolerance: float | None = None) -> list:
        """The points PostGIS makes of the arcs of a row, in a CRS."""
        tolerance, tolerance_type = (32.0, 0) if tolerance is None else (tolerance, 1)
        table_name = connection.ops.quote_name(Arc_2056_10fields._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT ST_AsBinary(ST_Transform(ST_CurveToLine(geom, %s, %s, 1), %s)) FROM {table_name} WHERE id = %s",
                [tolerance, tolerance_type, crs.srid, str(pk)],
            )
            return jsonfg.loads(bytes(cursor.fetchone()[0]))["coordinates"]

    def test_curves_are_linearized_on_request(self):
        # in GeoJSON, in the CRS asked for: as PostGIS makes lines of them in the storage CRS, where the arcs are drawn
        url = f"{collections_url}/tests.arc_2056_10fields/items"
        for crs in (CRS("OGC", 4326), CRS("EPSG", 2056)):
            for item_url in (url, f"{url}/{self.arc_id}"):
                with self.subTest(url=item_url, crs=crs):
                    response = self.client.get(item_url, {"crs": crs.uri(), "linearize": "true"})

                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response["Content-Crs"], crs.uri_header())
                    document = response.json()
                    self.assertFalse({"conformsTo", "coordRefSys"} & set(document))
                    [feature] = document.get("features", [document])
                    self.assertNotIn("place", feature)
                    self.assertEqual(feature["geometry"]["type"], "LineString")
                    self.assertEqual(feature["geometry"]["coordinates"], self.linearized(self.arc_id, crs))

    def test_linearized_page_has_the_box_of_its_lines(self):
        response = self.client.get(
            f"{collections_url}/tests.arc_2056_10fields/items", {"crs": crs_2056, "linearize": "true"}
        )

        xs, ys = zip(*self.linearized(self.arc_id, CRS("EPSG", 2056)))
        self.assertEqual(tuple(response.json()["bbox"]), (min(xs), min(ys), max(xs), max(ys)))

    def test_linearization_takes_the_tolerance_of_the_collection(self):
        # in the unit of the storage CRS, the metre, instead of 32 segments a quarter of a circle
        collection = oapif.collections["tests.arc_2056_10fields"]
        url = f"{collections_url}/tests.arc_2056_10fields/items/{self.arc_id}"
        for tolerance in (0.001, 1.0):
            with self.subTest(tolerance=tolerance), patch.object(collection, "linearization_tolerance", tolerance):
                feature = self.client.get(url, {"crs": crs_2056, "linearize": "true"}).json()

                coordinates = feature["geometry"]["coordinates"]
                self.assertEqual(coordinates, self.linearized(self.arc_id, CRS("EPSG", 2056), tolerance))
                self.assertNotEqual(len(coordinates), len(self.linearized(self.arc_id, CRS("EPSG", 2056))))

    def test_arcs_shared_are_linearized_alike(self):
        # the boundary two parcels share runs one way round the one, and the other way round the other: at a
        # tolerance, PostGIS would make other segments of it the other way round
        collection = oapif.collections["tests.arc_2056_10fields"]
        table_name = connection.ops.quote_name(Arc_2056_10fields._meta.db_table)
        reversed_id = uuid.uuid4()
        with connection.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {table_name} (id, geom) VALUES (%s, ST_Reverse(ST_GeomFromText(%s, 2056)))",
                [str(reversed_id), self.ARC],
            )
        url = f"{collections_url}/tests.arc_2056_10fields/items"

        with patch.object(collection, "linearization_tolerance", 0.001):
            lines = [
                self.client.get(f"{url}/{pk}", {"crs": crs_2056, "linearize": "true"}).json()["geometry"]["coordinates"]
                for pk in (self.arc_id, reversed_id)
            ]

        self.assertEqual(lines[0], lines[1][::-1])

    def test_page_with_a_curve_is_linearized_on_request(self):
        # its other geometries as they are
        response = self.client.get(
            f"{collections_url}/tests.geometry_2056/items", {"crs": crs_2056, "linearize": "true"}
        )

        self.assertEqual(response.status_code, 200)
        geometries = {feature["id"]: feature["geometry"] for feature in response.json()["features"]}
        self.assertEqual(geometries[str(self.point_id)], {"type": "Point", "coordinates": [2508500.0, 1152000.0]})
        self.assertEqual(geometries[str(self.curve_id)]["type"], "LineString")

    def test_empty_curve_is_linearized_to_no_geometry(self):
        # PostGIS fails to linearize an empty CurvePolygon, which used to fail the whole page
        table_name = connection.ops.quote_name(Geometry_2056._meta.db_table)
        empty_id = uuid.uuid4()
        with connection.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {table_name} (id, geom) VALUES (%s, ST_GeomFromText('CURVEPOLYGON EMPTY', 2056))",
                [str(empty_id)],
            )

        response = self.client.get(f"{collections_url}/tests.geometry_2056/items", {"linearize": "true"})

        self.assertEqual(response.status_code, 200)
        [empty] = [feature for feature in response.json()["features"] if feature["id"] == str(empty_id)]
        self.assertIsNone(empty["geometry"])

    def test_linearization_leaves_the_other_columns_as_they_are(self):
        # QGIS asks for it for every layer of a connection whose URL has it
        url = f"{collections_url}/tests.point_2056_10fields/items"
        for item_url in (url, f"{url}/{self.point.pk}"):
            with self.subTest(url=item_url):
                linearized = self.client.get(item_url, {"linearize": "true"}).json()
                default = self.client.get(item_url).json()

                for feature in (linearized, default):
                    feature.pop("links", None)
                self.assertEqual(linearized, default)

    def test_jsonfg_is_not_linearized(self):
        # it has the curves as they are
        url = f"{collections_url}/tests.arc_2056_10fields/items"
        for item_url in (url, f"{url}/{self.arc_id}"):
            with self.subTest(url=item_url):
                response = self.client.get(item_url, {"profile": "jsonfg", "linearize": "true"})

                self.assertEqual(response.status_code, 400)
                self.assertIn("linearize", response.json()["detail"])

    @requires_arrow
    def test_geoarrow_has_the_curves(self):
        # its WKB carries them, whatever GeoJSON is asked for
        response = self.client.get(
            f"{collections_url}/tests.arc_2056_10fields/items",
            {"linearize": "true"},
            headers={"Accept": "application/vnd.apache.arrow.stream"},
        )

        self.assertEqual(response.status_code, 200)
        table = pa.ipc.open_stream(response.content).read_all()
        self.assertEqual(jsonfg.loads(table["geometry"][0].as_py())["type"], "CircularString")

    def profile_of(self, response) -> str:
        [profile] = re.findall(r'<([^>]*)>; rel="profile"', response.headers.get("Link", ""))
        return profile

    def test_responses_link_their_profile(self):
        # as Part 5 wants: GeoJSON, but for JSON-FG asked for, and the linearized curves are GeoJSON
        rfc7946 = "http://www.opengis.net/def/profile/ogc/0/rfc7946"
        points = f"{collections_url}/tests.point_2056_10fields/items"
        arcs = f"{collections_url}/tests.arc_2056_10fields/items"
        for url, params, profile in (
            (points, {}, rfc7946),
            (f"{points}/{self.point.pk}", {}, rfc7946),
            (points, {"profile": "jsonfg"}, self.JSONFG),
            (arcs, {"profile": "jsonfg"}, self.JSONFG),
            (f"{arcs}/{self.arc_id}", {"profile": "jsonfg"}, self.JSONFG),
            (arcs, {"linearize": "true"}, rfc7946),
        ):
            with self.subTest(url=url, **params):
                self.assertEqual(self.profile_of(self.client.get(url, params)), profile)

    def test_collection_links_its_items_in_jsonfg(self):
        # as QGIS 4.2 tells them from GeoJSON: GeoJSON links with a single profile. The link without one comes
        # last, as QGIS 4.0 takes the last link of a type
        for collection in ("tests.point_2056_10fields", "tests.arc_2056_10fields"):
            with self.subTest(collection=collection):
                links = self.client.get(f"{collections_url}/{collection}").json()["links"]

                items = [link for link in links if link["rel"] == "items" and link["type"] == "application/geo+json"]
                self.assertEqual([link.get("profile") for link in items], [[self.JSONFG], None])
                self.assertEqual(self.profile_of(self.client.get(items[0]["href"])), self.JSONFG)

    def test_collection_without_geometry_links_no_jsonfg(self):
        links = self.client.get(f"{collections_url}/tests.nogeom_10fields").json()["links"]

        self.assertFalse([link for link in links if "profile" in link])

    def test_pages_are_linked_in_the_headers(self):
        # QGIS reads the next page of JSON-FG, and the number of features, from the headers only
        url = f"{collections_url}/tests.geometry_2056/items"
        response = self.client.get(url, {"limit": 1, "profile": "jsonfg"})

        [next_link] = [link for link in response.json()["links"] if link["rel"] == "next"]
        self.assertEqual(next_link["profile"], [self.JSONFG])
        self.assertIn(
            f'<{next_link["href"]}>; rel="next"; type="application/geo+json"; profile="{self.JSONFG}"', response["Link"]
        )
        self.assertEqual(response["OGC-NumberMatched"], "2")

    def test_pages_without_a_profile_link_none(self):
        Point_2056_10fields.objects.create(geom="POINT(2508600 1152000)")

        links = self.client.get(f"{collections_url}/tests.point_2056_10fields/items", {"limit": 1}).json()["links"]

        self.assertIn("next", {link["rel"] for link in links})
        self.assertFalse([link for link in links if "profile" in link])

    def test_linearized_pages_link_linearized_pages(self):
        response = self.client.get(f"{collections_url}/tests.geometry_2056/items", {"limit": 1, "linearize": "true"})

        [next_link] = [link for link in response.json()["links"] if link["rel"] == "next"]
        self.assertIn("linearize=true", next_link["href"])

    def test_query_parameter_chooses_over_the_accept_header(self):
        response = self.client.get(
            f"{collections_url}/tests.point_2056_10fields/items",
            {"profile": "rfc7946"},
            headers={"Accept": f'application/geo+json; profile="{self.JSONFG}"'},
        )

        self.assertNotIn("conformsTo", response.json())


class TestOrdering(TestCase):
    # inserted in reverse, so ordering by pk gives exactly the opposite of the model ordering
    NAMES = ("delta", "charlie", "bravo", "alpha")

    @classmethod
    def setUpTestData(cls):
        for name in cls.NAMES:
            LayerWithOrdering.objects.create(name=name)

    def test_model_ordering_is_kept(self):
        response = self.client.get(f"{collections_url}/tests.layerwithordering/items")

        self.assertEqual(response.status_code, 200)
        names = [feature["properties"]["name"] for feature in response.json()["features"]]
        self.assertEqual(names, sorted(self.NAMES))

    def test_model_ordering_gets_the_pk_as_tie_breaker(self):
        collection = oapif.collections["tests.layerwithordering"]

        self.assertEqual(collection.get_ordering(None), ("name", "pk"))

    def test_ordering_defaults_to_the_pk(self):
        collection = oapif.collections["tests.point_2056_10fields"]

        self.assertEqual(collection.get_ordering(None), ("pk",))

    def test_collection_ordering_wins(self):
        class ReversedCollection(AnonReadOnlyCollection):
            ordering = ("-name",)

        collection = ReversedCollection(LayerWithOrdering)

        self.assertEqual(collection.get_ordering(None), ("-name",))


def ring(x, y, size=10.0):
    return [[x, y], [x + size, y], [x + size, y + size], [x, y]]


def arc(x, y, size=10.0):
    return [[x, y], [x + size, y + size], [x + 2 * size, y]]


def arc_points(geometry):
    """The points of a CircularString, joined back when it is served in parts."""
    if geometry["type"] == "CircularString":
        return geometry["coordinates"]
    parts = [part["coordinates"] for part in geometry["geometries"]]
    return parts[0] + [point for part in parts[1:] for point in part[1:]]


class TestWriteGeometries(TestCase):
    """Every geometry type goes to GEOS as WKB: GeoJSON ones everywhere, curves with GEOS 3.13 and a Django for them."""

    GEOJSON = {
        "point": {"type": "Point", "coordinates": [2508500.0, 1152000.0]},
        "multipoint": {"type": "MultiPoint", "coordinates": [[2508500.0, 1152000.0], [2508600.0, 1152100.0]]},
        "linestring": {"type": "LineString", "coordinates": [[2508500.0, 1152000.0], [2508600.0, 1152100.0]]},
        "multilinestring": {
            "type": "MultiLineString",
            "coordinates": [[[2508500.0, 1152000.0], [2508600.0, 1152100.0]]],
        },
        "polygon": {"type": "Polygon", "coordinates": [ring(2508500.0, 1152000.0)]},
        "multipolygon": {
            "type": "MultiPolygon",
            "coordinates": [[ring(2508500.0, 1152000.0)], [ring(2508600.0, 1152000.0)]],
        },
        "geometrycollection": {
            "type": "GeometryCollection",
            "geometries": [
                {"type": "Point", "coordinates": [2508500.0, 1152000.0]},
                {"type": "LineString", "coordinates": [[2508500.0, 1152000.0], [2508600.0, 1152100.0]]},
            ],
        },
    }
    CURVES = {
        "circularstring": {"type": "CircularString", "coordinates": arc(2508500.0, 1152000.0)},
        "compoundcurve": {
            "type": "CompoundCurve",
            "geometries": [
                {"type": "LineString", "coordinates": [[2508480.0, 1152000.0], [2508500.0, 1152000.0]]},
                {"type": "CircularString", "coordinates": arc(2508500.0, 1152000.0)},
            ],
        },
        "curvepolygon": {
            "type": "CurvePolygon",
            "geometries": [
                {
                    "type": "CircularString",
                    "coordinates": [
                        [2508500.0, 1152000.0],
                        [2508510.0, 1152010.0],
                        [2508520.0, 1152000.0],
                        [2508510.0, 1151990.0],
                        [2508500.0, 1152000.0],
                    ],
                }
            ],
        },
        "multicurve": {
            "type": "MultiCurve",
            "geometries": [
                {"type": "LineString", "coordinates": [[2508500.0, 1152000.0], [2508600.0, 1152100.0]]},
                {"type": "CircularString", "coordinates": arc(2508700.0, 1152000.0)},
            ],
        },
        "multisurface": {
            "type": "MultiSurface",
            "geometries": [
                {"type": "Polygon", "coordinates": [ring(2508500.0, 1152000.0)]},
                {
                    "type": "CurvePolygon",
                    "geometries": [{"type": "LineString", "coordinates": ring(2508600.0, 1152000.0)}],
                },
            ],
        },
        "geometrycollection with a curve": {
            "type": "GeometryCollection",
            "geometries": [
                {"type": "Point", "coordinates": [2508500.0, 1152000.0]},
                {"type": "CircularString", "coordinates": arc(2508500.0, 1152000.0)},
            ],
        },
    }

    @classmethod
    def setUpTestData(cls):
        call_command("populate_users")
        # an arc to replace and update, inserted as it is: GEOS may not know curves
        table_name = connection.ops.quote_name(Arc_2056_10fields._meta.db_table)
        cls.arc_id = uuid.uuid4()
        with connection.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {table_name} (id, geom) VALUES (%s, ST_GeomFromText(%s, 2056))",
                [cls.arc_id, "CIRCULARSTRING(2508500 1152000, 2508510 1152010, 2508520 1152000)"],
            )

    def setUp(self):
        self.client.force_login(User.objects.get(username="demo_editor"))

    def post(self, collection, geometry, crs=crs_2056):
        return self.client.post(
            f"{collections_url}/{collection}/items",
            {"type": "Feature", "geometry": geometry, "properties": {}},
            headers={"Content-Crs": crs},
            content_type="application/json",
        )

    def assert_round_trip(self, collection, geometries):
        for name, geometry in geometries.items():
            with self.subTest(geometry=name):
                response = self.post(collection, geometry)

                self.assertEqual(response.status_code, 201)
                item = self.client.get(
                    f"{collections_url}/{collection}/items/{response.json()['id']}",
                    {"crs": crs_2056, "profile": "jsonfg"},
                )
                self.assertEqual(geometry_of(item.json()), geometry)

    def test_geojson_geometries_round_trip(self):
        self.assert_round_trip("tests.geometry_2056", self.GEOJSON)

    def test_3d_geometry_round_trips(self):
        line = {"type": "LineString", "coordinates": [[2508500.0, 1152000.0, 1.0], [2508600.0, 1152100.0, 2.0]]}

        self.assert_round_trip("tests.geometryz_2056", {"linestring": line})

    def test_invalid_geometry_is_a_client_error(self):
        # GEOS refuses a ring that is not closed, which used to be a 500
        unclosed = {"type": "Polygon", "coordinates": [ring(2508500.0, 1152000.0)[:-1] + [[2508505.0, 1152005.0]]]}

        self.assertEqual(self.post("tests.geometry_2056", unclosed).status_code, 422)

    def jsonfg_feature(self, fallback, place, **members):
        return {
            "type": "Feature",
            "conformsTo": [
                "http://www.opengis.net/spec/json-fg-1/1.0/conf/core",
                "http://www.opengis.net/spec/json-fg-1/1.0/conf/circular-arcs",
            ],
            "coordRefSys": crs_2056,
            "geometry": fallback,
            "place": place,
            "properties": {},
            **members,
        }

    def test_place_is_the_geometry_written(self):
        # JSON-FG writes the geometries GeoJSON cannot carry in "place", "geometry" being their fallback
        url = f"{collections_url}/tests.geometry_2056/items"
        fallback = {"type": "Point", "coordinates": [2508400.0, 1152000.0]}
        post = self.client.post(
            url,
            self.jsonfg_feature(fallback, {"type": "Point", "coordinates": [2508500.0, 1152000.0]}),
            headers=headers,
            content_type="application/json",
        )

        self.assertEqual(post.status_code, 201)
        item_url = f"{url}/{post.json()['id']}"
        self.assertEqual(
            self.client.get(f"{item_url}?crs={crs_2056}").json()["geometry"]["coordinates"], [2508500.0, 1152000.0]
        )
        for method, x in ((self.client.put, 2508600.0), (self.client.patch, 2508700.0)):
            with self.subTest(method=method.__name__):
                place = {"type": "Point", "coordinates": [x, 1152000.0]}

                response = method(
                    item_url, self.jsonfg_feature(fallback, place), headers=headers, content_type="application/json"
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.client.get(f"{item_url}?crs={crs_2056}").json()["geometry"], place)

    def test_arc_in_place_is_written(self):
        # its linearized fallback used to be taken, which a column of arcs refuses
        fallback = {"type": "LineString", "coordinates": [[2508500.0, 1152000.0], [2508520.0, 1152000.0]]}
        place = {"type": "CircularString", "coordinates": arc(2508500.0, 1152000.0)}
        item_url = f"{collections_url}/tests.arc_2056_10fields/items/{self.arc_id}"
        status = 200 if writes_curves() else 501

        post = self.client.post(
            f"{collections_url}/tests.arc_2056_10fields/items",
            self.jsonfg_feature(fallback, place),
            headers=headers,
            content_type="application/json",
        )
        patch = self.client.patch(
            item_url, self.jsonfg_feature(fallback, place), headers=headers, content_type="application/json"
        )

        self.assertEqual(post.status_code, 201 if writes_curves() else 501)
        self.assertEqual(patch.status_code, status)
        if writes_curves():
            self.assertEqual(self.client.get(f"{item_url}?crs={crs_2056}&profile=jsonfg").json()["place"], place)

    def test_linearized_curve_is_refused_for_its_curve(self):
        # a GeoJSON client writes back the linearization of a curve it read, like QGIS with linearize=true
        line = {
            "type": "LineString",
            "coordinates": [[2508500.0, 1152000.0], [2508510.0, 1152007.0], [2508520.0, 1152000.0]],
        }
        url = f"{collections_url}/tests.arc_2056_10fields/items"
        item_url = f"{url}/{self.arc_id}"
        for method, method_url in ((self.client.post, url), (self.client.put, item_url), (self.client.patch, item_url)):
            with self.subTest(method=method.__name__):
                response = method(
                    method_url,
                    {"type": "Feature", "geometry": line, "properties": {}},
                    headers=headers,
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 422)
                [error] = response.json()["detail"]
                self.assertEqual(error["loc"], ["body", "feature", "geometry"])
                self.assertIn('send the curve in "place"', error["msg"])

    def test_coord_ref_sys_must_be_the_content_crs(self):
        # the coordinates are read in the Content-Crs: another coordRefSys would be ignored
        point = {"type": "Point", "coordinates": [2508500.0, 1152000.0]}

        response = self.client.post(
            f"{collections_url}/tests.geometry_2056/items",
            self.jsonfg_feature(point, point),
            headers={"Content-Crs": crs84},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("coordRefSys", response.json()["detail"])

    @skipIf(writes_curves(), "this GEOS and Django can write curves")
    def test_curves_are_not_implemented_without_support(self):
        curve = self.CURVES["circularstring"]
        feature = {"type": "Feature", "geometry": curve, "properties": {}}
        item_url = f"{collections_url}/tests.arc_2056_10fields/items/{self.arc_id}"

        self.assertEqual(self.post("tests.arc_2056_10fields", curve).status_code, 501)
        for method in (self.client.put, self.client.patch):
            response = method(item_url, feature, headers=headers, content_type="application/json")
            self.assertEqual(response.status_code, 501)

    @skipUnless(writes_curves(), "needs GEOS 3.13 or newer and a Django that supports curves")
    def test_curves_round_trip(self):
        self.assert_round_trip("tests.geometry_2056", self.CURVES)

    @skipUnless(writes_curves(), "needs GEOS 3.13 or newer and a Django that supports curves")
    def test_3d_curve_round_trips(self):
        curve = {
            "type": "CompoundCurve",
            "geometries": [
                {"type": "LineString", "coordinates": [[2508480.0, 1152000.0, 1.0], [2508500.0, 1152000.0, 2.0]]},
                {
                    "type": "CircularString",
                    "coordinates": [
                        [2508500.0, 1152000.0, 2.0],
                        [2508510.0, 1152010.0, 3.0],
                        [2508520.0, 1152000.0, 4.0],
                    ],
                },
            ],
        }

        self.assert_round_trip("tests.geometryz_2056", {"compoundcurve": curve})

    @skipUnless(writes_curves(), "needs GEOS 3.13 or newer and a Django that supports curves")
    def test_arc_is_replaced_and_updated(self):
        item_url = f"{collections_url}/tests.arc_2056_10fields/items/{self.arc_id}"
        for method, x in ((self.client.put, 2508700.0), (self.client.patch, 2508900.0)):
            with self.subTest(method=method.__name__):
                curve = {"type": "CircularString", "coordinates": arc(x, 1152000.0)}
                feature = {"type": "Feature", "geometry": curve, "properties": {}}

                response = method(item_url, feature, headers=headers, content_type="application/json")

                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.client.get(f"{item_url}?crs={crs_2056}&profile=jsonfg").json()["place"], curve)

    @skipUnless(writes_curves(), "needs GEOS 3.13 or newer and a Django that supports curves")
    def test_long_arc_round_trips_in_parts(self):
        # served as a CompoundCurve, it goes back into its column as the CircularString it was
        wkt = TestCircularString.arc_wkt(13)
        table_name = connection.ops.quote_name(Arc_2056_10fields._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {table_name} SET geom = ST_GeomFromText(%s, 2056) WHERE id = %s", [wkt, self.arc_id]
            )
        item_url = f"{collections_url}/tests.arc_2056_10fields/items/{self.arc_id}"
        served = self.client.get(f"{item_url}?crs={crs_2056}&profile=jsonfg").json()

        response = self.client.put(item_url, served, headers=headers, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(f"{item_url}?crs={crs_2056}&profile=jsonfg").json()["place"], served["place"])
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT ST_Equals(geom, ST_GeomFromText(%s, 2056)) FROM {table_name} WHERE id = %s", [wkt, self.arc_id]
            )
            self.assertTrue(cursor.fetchone()[0])

    @skipUnless(writes_curves(), "needs GEOS 3.13 or newer and a Django that supports curves")
    def test_arc_is_reprojected_on_the_way_in(self):
        curve = {"type": "CircularString", "coordinates": [[7.44, 46.95], [7.4401, 46.9501], [7.4402, 46.95]]}

        response = self.post("tests.arc_2056_10fields", curve, crs=crs84)

        self.assertEqual(response.status_code, 201)
        stored = self.client.get(
            f"{collections_url}/tests.arc_2056_10fields/items/{response.json()['id']}", {"profile": "jsonfg"}
        )
        for position, expected in zip(stored.json()["place"]["coordinates"], curve["coordinates"], strict=True):
            self.assertAlmostEqual(position[0], expected[0], places=7)
            self.assertAlmostEqual(position[1], expected[1], places=7)


class TestQueryables(TestCase):
    def test_queryables(self):
        response = self.client.get(f"{collections_url}/tests.point_2056_10fields_subset/queryables")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "application/schema+json")
        self.assertEqual(
            response.json(),
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "http://testserver/oapif/collections/tests.point_2056_10fields_subset/queryables",
                "type": "object",
                "title": "tests.Point_2056_10fields",
                "properties": {
                    "field_int": {
                        "title": "Field Int",
                        "type": "integer",
                        "minimum": -2147483648,
                        "maximum": 2147483647,
                        "x-ogc-propertySeq": 1,
                    },
                    "field_str_0": {"title": "Field 0", "maxLength": 255, "type": "string", "x-ogc-propertySeq": 2},
                    # the reference to the GeoJSON schema is how QGIS recognizes a geometry
                    "geom": {
                        "title": "geometry",
                        "x-ogc-role": "primary-geometry",
                        "format": "geometry-point",
                        "x-ogc-propertySeq": 3,
                        "$ref": "https://geojson.org/schema/Point.json",
                    },
                },
                "additionalProperties": False,
            },
        )

    def test_queryables_of_any_geometry_or_none(self):
        any_geometry = self.client.get(f"{collections_url}/tests.geometry_2056/queryables").json()
        no_geometry = self.client.get(f"{collections_url}/tests.nogeom_10fields/queryables").json()

        self.assertEqual(any_geometry["properties"]["geom"]["$ref"], "https://geojson.org/schema/Geometry.json")
        self.assertNotIn("geom", no_geometry["properties"])
        self.assertIn("field_str_0", no_geometry["properties"])

    def test_collection_links_its_queryables(self):
        collection = self.client.get(f"{collections_url}/tests.point_2056_10fields").json()

        self.assertIn(
            {
                "rel": "http://www.opengis.net/def/rel/ogc/1.0/queryables",
                "title": "Collection queryables",
                "type": "application/schema+json",
                "href": "http://testserver/oapif/collections/tests.point_2056_10fields/queryables",
            },
            collection["links"],
        )


class TestFilter(TestCase):
    """CQL2 filters, in the shapes QGIS sends them: it applies none of them itself once the server takes them."""

    # label, field_int, field_str_0, field_str_1, field_bool, and the point, in Lausanne, Zurich, Geneva and Bern
    POINTS = (
        ("a", 1, "Route d'Oron", None, True, (2538000, 1152000)),
        ("b", 2, "foo_bar", "x", False, (2683000, 1248000)),
        ("c", None, "FOO%bar", None, True, (2500000, 1118000)),
        ("d", 10, None, "y", True, (2600000, 1200000)),
    )
    ZURICH = "BBOX(8.4,47.3,8.7,47.5)"
    GENEVA = "POLYGON((6 46.1,6.3 46.1,6.3 46.3,6 46.3,6 46.1))"

    @classmethod
    def setUpTestData(cls):
        for label, field_int, field_str_0, field_str_1, field_bool, (x, y) in cls.POINTS:
            Point_2056_10fields.objects.create(
                field_str_9=label,
                field_int=field_int,
                field_str_0=field_str_0,
                field_str_1=field_str_1,
                field_bool=field_bool,
                geom=f"SRID=2056;POINT({x} {y})",
            )
        LayerWithDate.objects.create(
            date=datetime.date(2023, 4, 19), time=datetime.datetime(2023, 4, 19, 12, 34, 56, tzinfo=datetime.UTC)
        )
        LayerWithDate.objects.create(
            date=datetime.date(2024, 1, 1), time=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC)
        )

    def get(self, filter_expr: str, collection: str = "tests.point_2056_10fields", **params):
        return self.client.get(f"{collections_url}/{collection}/items", {"filter": filter_expr, **params})

    def matches(self, filter_expr: str, collection: str = "tests.point_2056_10fields", label="field_str_9", **params):
        response = self.get(filter_expr, collection, **params)
        self.assertEqual(response.status_code, 200, response.content)
        return sorted(feature["properties"][label] for feature in response.json()["features"])

    def assert_matches(self, cases, **kwargs):
        for filter_expr, expected in cases:
            with self.subTest(filter=filter_expr):
                self.assertEqual(self.matches(filter_expr, **kwargs), expected)

    def test_comparisons(self):
        self.assert_matches((
            ("(field_int = 1)", ["a"]),
            ("(field_int >= 2)", ["b", "d"]),
            ("(field_int < 2)", ["a"]),
            ("(field_int <= 2)", ["a", "b"]),
            ("(field_int > 1)", ["b", "d"]),
            ("2 < field_int", ["d"]),
            ("(field_bool = FALSE)", ["b"]),
            ('"field_int" = 2', ["b"]),
            ("((field_int = 1) OR (field_int = 10))", ["a", "d"]),
            ("((field_int >= 1) AND (field_str_1 = 'x'))", ["b"]),
            # AND binds tighter than OR
            ("field_int = 1 OR field_int = 2 AND field_str_1 = 'y'", ["a"]),
            ("field_int IN (1,10)", ["a", "d"]),
            ("field_int BETWEEN 1 AND 2", ["a", "b"]),
            ("(field_int IS NULL)", ["c"]),
            ("(field_str_0 IS NOT NULL)", ["a", "b", "c"]),
            ("field_int = field_int", ["a", "b", "d"]),
        ))

    def test_quotes_are_escaped_as_in_cql2(self):
        # doubled by QGIS, and names with an apostrophe are common in Switzerland
        self.assert_matches((
            ("(field_str_0 = 'Route d''Oron')", ["a"]),
            ("field_str_0 = 'Route d\\'Oron'", ["a"]),
        ))

    def test_negations_leave_out_null_values(self):
        # a comparison with null is unknown, and so is its negation: QGIS would not match them, and Django would
        self.assert_matches((
            ("(field_int <> 1)", ["b", "d"]),
            ("(NOT ((field_int = 1)))", ["b", "d"]),
            ("NOT (field_int = 1 OR field_int = 2)", ["d"]),
            ("NOT (field_str_1 = 'x' AND field_int = 2)", ["a", "d"]),
            ("NOT (NOT (field_int = 1))", ["a"]),
            ("field_int NOT IN (1,2)", ["d"]),
            ("field_int NOT BETWEEN 1 AND 2", ["d"]),
            ("(field_str_0 NOT LIKE 'foo%')", ["a", "c"]),
            ("NOT (field_int IS NULL)", ["a", "b", "d"]),
            ("field_str_1 <> field_str_0", ["b"]),
        ))

    def test_like(self):
        self.assert_matches((
            ("(field_str_0 LIKE 'foo%')", ["b"]),
            ("field_str_0 LIKE '%bar'", ["b", "c"]),
            ("field_str_0 LIKE 'fo__bar'", ["b"]),
            ("field_str_0 LIKE 'foo\\_%'", ["b"]),
            ("field_str_0 LIKE 'FOO\\%%'", ["c"]),
            ("field_str_0 LIKE '%d''O%'", ["a"]),
            # the parts are matched in their order, and the other characters as they are
            ("field_str_0 LIKE '%bar%foo%'", []),
            ("field_str_0 LIKE 'Route d''O.on'", []),
        ))

    def test_case_insensitive_comparisons(self):
        self.assert_matches((
            ("(CASEI(field_str_0) LIKE CASEI('foo%'))", ["b", "c"]),
            ("(CASEI(field_str_0) NOT LIKE CASEI('foo%'))", ["a"]),
            ("CASEI(field_str_0) = CASEI('FOO_BAR')", ["b"]),
            ("CASEI('FOO_BAR') = CASEI(field_str_0)", ["b"]),
            ("CASEI(field_str_0) IN (CASEI('foo_bar'), CASEI('route d''oron'))", ["a", "b"]),
        ))

    def test_temporal_literals(self):
        self.assert_matches(
            (
                ("(date = DATE('2023-04-19'))", ["2023-04-19"]),
                ("(time = TIMESTAMP('2023-04-19T12:34:56.000Z'))", ["2023-04-19"]),
                ("time > TIMESTAMP('2023-06-01T00:00:00Z')", ["2024-01-01"]),
                # the timestamps of CQL2 are in UTC
                ("time < TIMESTAMP('2023-04-19T12:34:57')", ["2023-04-19"]),
            ),
            collection="tests.layerwithdate",
            label="date",
        )

    def test_spatial_functions(self):
        # the literals are in CRS84 unless the filter-crs says otherwise, whatever the CRS of the geometries
        self.assert_matches((
            (f"S_INTERSECTS(geom,{self.ZURICH})", ["b"]),
            ("S_INTERSECTS(geom,BBOX(8.4,47.3,0,8.7,47.5,1000))", ["b"]),
            (f"S_INTERSECTS(geom,{self.GENEVA})", ["c"]),
            (f"S_CONTAINS({self.GENEVA},geom)", ["c"]),
            (f"S_DISJOINT(geom,{self.ZURICH})", ["a", "c", "d"]),
            (f"NOT S_INTERSECTS(geom,{self.ZURICH})", ["a", "c", "d"]),
        ))
        self.assert_matches(
            (
                ("S_INTERSECTS(geom,POINT(2600000 1200000))", ["d"]),
                ("S_INTERSECTS(geom,BBOX(2590000,1190000,2610000,1210000))", ["d"]),
            ),
            **{"filter-crs": crs_2056},
        )

    def test_filter_and_bbox_both_apply(self):
        self.assertEqual(self.matches("field_int >= 1", bbox="8.4,47.3,8.7,47.5"), ["b"])

    def test_pages_keep_the_filter(self):
        page = self.get("field_int >= 1", limit=1).json()
        next_url = next(link["href"] for link in page["links"] if link["rel"] == "next")
        next_page = self.client.get(next_url.removeprefix("http://testserver")).json()

        self.assertEqual(page["numberMatched"], 3)
        self.assertEqual(next_page["numberMatched"], 3)
        self.assertEqual(len(next_page["features"]), 1)

    def test_foreign_key(self):
        point = Point_2056_10fields.objects.get(field_str_9="a")
        LayerWithForeignKey.objects.create(point=point)

        response = self.get(f"point = '{point.pk}'", "tests.layerwithforeignkey")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["numberMatched"], 1)

    def test_invalid_filters_are_client_errors(self):
        for filter_expr, collection, params in (
            ("field_int >", "tests.point_2056_10fields", {}),
            ("unknown = 1", "tests.point_2056_10fields", {}),
            ("field_int = 'abc'", "tests.point_2056_10fields", {}),
            ("id = 'not-a-uuid'", "tests.point_2056_10fields", {}),
            ("field_int * 2 > 3", "tests.point_2056_10fields", {}),
            ("ACCENTI(field_str_0) = 'x'", "tests.point_2056_10fields", {}),
            ("CASEI(field_str_0) > CASEI('a')", "tests.point_2056_10fields", {}),
            ("field_int = field_str_0", "tests.point_2056_10fields", {}),
            ("geom = 1", "tests.point_2056_10fields", {}),
            ("S_INTERSECTS(field_int,BBOX(0,0,1,1))", "tests.point_2056_10fields", {}),
            ("S_INTERSECTS(geom,field_int)", "tests.point_2056_10fields", {}),
            ("S_INTERSECTS(geom,BBOX(8.4,47.3,8.7))", "tests.point_2056_10fields", {}),
            ("field_int = BBOX(0,0,1,1)", "tests.point_2056_10fields", {}),
            # coordinates of another CRS, sent without a filter-crs: PostGIS would fail to reproject them
            ("S_INTERSECTS(geom,BBOX(2590000,1190000,2610000,1210000))", "tests.point_2056_10fields", {}),
            ("field_int = 1", "tests.point_2056_10fields", {"filter-crs": f"{crs_base}/EPSG/0/3857"}),
            # a field the collection does not expose, or one of a related model
            ("field_str_1 = 'x'", "tests.point_2056_10fields_subset", {}),
            ("point__field_str_0 = 'x'", "tests.layerwithforeignkey", {}),
            ("point LIKE 'a%'", "tests.layerwithforeignkey", {}),
            ("S_INTERSECTS(geom,BBOX(0,0,1,1))", "tests.nogeom_10fields", {}),
        ):
            with self.subTest(filter=filter_expr, collection=collection):
                response = self.get(filter_expr, collection, **params)

                self.assertEqual(response.status_code, 400, response.content)

    def test_only_cql2_text_is_accepted(self):
        response = self.get("field_int = 1", **{"filter-lang": "cql2-json"})

        self.assertEqual(response.status_code, 422)


class TestConformance(TestCase):
    def test_openapi_class_matches_the_served_document(self):
        # django-ninja serves OpenAPI 3.1: a 3.0 class would be a false claim, and only the 1.1 draft of
        # Features Part 1 has one for 3.1
        conforms_to = self.client.get("/oapif/conformance").json()["conformsTo"]
        openapi = self.client.get("/oapif/openapi.json").json()["openapi"]

        self.assertRegex(openapi, r"^3\.1\.")
        self.assertIn("http://www.opengis.net/spec/ogcapi-features-1/1.1/conf/oas31", conforms_to)
        self.assertEqual([uri for uri in conforms_to if uri.endswith("/conf/oas30")], [])

    def test_schemas_are_declared(self):
        # QGIS only reads the schema of a collection with the schemas class, and the collections link it with
        # the returnables and receivables one
        conforms_to = self.client.get("/oapif/conformance").json()["conformsTo"]

        for uri in (
            "http://www.opengis.net/spec/ogcapi-features-5/1.0/conf/schemas",
            "http://www.opengis.net/spec/ogcapi-features-5/1.0/conf/returnables-and-receivables",
            "http://www.opengis.net/spec/ogcapi-features-5/1.0/conf/feature-references",
        ):
            self.assertIn(uri, conforms_to)

    def test_jsonfg_is_declared(self):
        conforms_to = self.client.get("/oapif/conformance").json()["conformsTo"]

        for uri in (
            "http://www.opengis.net/spec/json-fg-1/1.0/conf/core",
            "http://www.opengis.net/spec/json-fg-1/1.0/conf/circular-arcs",
            "http://www.opengis.net/spec/json-fg-1/1.0/conf/profiles",
            "http://www.opengis.net/spec/json-fg-1/1.0/conf/api",
            "http://www.opengis.net/spec/ogcapi-common-3/1.0/conf/profile-parameter",
        ):
            self.assertIn(uri, conforms_to)

    def test_filters_are_declared(self):
        # without the classes of Part 3 and basic-cql2, QGIS filters the layers itself
        conforms_to = self.client.get("/oapif/conformance").json()["conformsTo"]

        for uri in (
            "http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/queryables",
            "http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/filter",
            "http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/features-filter",
            "http://www.opengis.net/spec/cql2/1.0/conf/basic-cql2",
        ):
            self.assertIn(uri, conforms_to)

    def test_openapi_crs_defaults_are_uris(self):
        # they used to be documented as the fields of the CRS, which the interactive docs then sent
        document = self.client.get("/oapif/openapi.json").json()
        defaults = {
            (method, path, parameter["name"]): parameter["schema"]["default"]
            for path, operations in document["paths"].items()
            for method, operation in operations.items()
            for parameter in operation.get("parameters", [])
            if parameter.get("name") in ("crs", "bbox-crs", "filter-crs", "Content-Crs")
        }

        self.assertEqual(len(defaults), 7)
        self.assertEqual(defaults, dict.fromkeys(defaults, crs84))

    def test_openapi_publishes_the_limit_of_the_items(self):
        # QGIS takes the page size from this component only: without it, it pages by 100 features
        document = self.client.get("/oapif/openapi.json").json()
        parameters = document["paths"]["/oapif/collections/{collection_id}/items"]["get"]["parameters"]

        self.assertEqual(document["components"]["parameters"]["limit"]["schema"]["default"], 100)
        self.assertIn({"$ref": "#/components/parameters/limit"}, parameters)
        # and in its place: declared inline as well, the operation would have it twice
        self.assertNotIn("limit", [parameter.get("name") for parameter in parameters])

    def test_openapi_describes_the_jsonfg_members_of_writes_only(self):
        # the requests used to be described with the schema of the responses, which do not have them
        document = self.client.get("/oapif/openapi.json").json()
        items = document["paths"]["/oapif/collections/{collection_id}/items"]
        item = document["paths"]["/oapif/collections/{collection_id}/items/{item_id}"]

        def members(schema: dict) -> set[str]:
            return set(document["components"]["schemas"][schema["$ref"].rsplit("/", 1)[-1]]["properties"])

        for method, operation in (("POST", items["post"]), ("PUT", item["put"]), ("PATCH", item["patch"])):
            with self.subTest(method=method):
                body = operation["requestBody"]["content"]["application/json"]["schema"]
                response = next(iter(operation["responses"].values()))["content"]["application/json"]["schema"]

                self.assertLessEqual({"place", "coordRefSys"}, members(body))
                self.assertFalse({"place", "coordRefSys"} & members(response))
