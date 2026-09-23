import datetime
import logging
import re
import uuid

import pyarrow as pa
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection
from django.test.testcases import TestCase
from django_oapif import jsonfg
from django_oapif.crs import CRS
from django_oapif.geojson import CircularString, Coordinate2D
from django_oapif.handler import AnonReadOnlyCollection
from django_oapif_tests.tests.oapif import oapif
from django_oapif_tests.tests.models import (
    Arc_2056_10fields,
    GeometryZ_2056,
    LayerWithDate,
    LayerWithFile,
    LayerWithOrdering,
    Point_2056_10fields,
    Point_2056_Empty,
)
from geoarrow.pyarrow import WkbType
from pydantic import ValidationError as PydanticValidationError
from geoarrow.types.crs import StringCrs

logger = logging.getLogger(__name__)

collections_url = "/oapif/collections"

crs_2056 = "http://www.opengis.net/def/crs/EPSG/0/2056"
crs84 = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
crs_base = "http://www.opengis.net/def/crs"

headers = {"Content-Crs": crs_2056}


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
        now = datetime.datetime.now()
        obj = LayerWithDate.objects.create(date=today, time=now)
        obj.refresh_from_db()
        url = f"{collections_url}/tests.layerwithdate/items/{obj.id}"
        response = self.client.get(url, headers=headers, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "id": str(obj.id),
                "type": "Feature",
                "geometry": None,
                "properties": {
                    "date": str(today),
                    "time": now.isoformat(timespec="milliseconds") + "Z",
                    "id": str(obj.id),
                },
            },
        )


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
                "id": {"title": "Id", "format": "uuid", "type": "string"},
                "field_int": {"title": "Field Int", "type": "integer"},
                "field_bool": {"default": True, "title": "Field Bool", "type": "boolean"},
                "field_str_0": {"title": "Field 0", "maxLength": 255, "type": "string"},
                "field_str_1": {"title": "Field 1", "maxLength": 255, "type": "string"},
                "field_str_2": {"title": "Field 2", "maxLength": 255, "type": "string"},
                "field_str_3": {"title": "Field 3", "maxLength": 255, "type": "string"},
                "field_str_4": {"title": "Field 4", "maxLength": 255, "type": "string"},
                "field_str_5": {"title": "Field 5", "maxLength": 255, "type": "string"},
                "field_str_6": {"title": "Field 6", "maxLength": 255, "type": "string"},
                "field_str_7": {"title": "Field 7", "maxLength": 255, "type": "string"},
                "field_str_8": {"title": "Field 8", "maxLength": 255, "type": "string"},
                "field_str_9": {"title": "Field 9", "maxLength": 255, "type": "string"},
                "geom": {"title": "geometry", "x-ogc-role": "primary-geometry", "format": "geometry-point"},
            },
            "title": "tests.Point_2056_10fields",
            "type": "object",
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "http://testserver/oapif/collections/tests.point_2056_10fields/schema",
        }

        schema_response = self.client.get(url, headers=headers, content_type="application/json")
        self.assertEqual(schema_response.status_code, 200)
        self.assertEqual(schema_response.json(), expected_schema)

    def test_properties_schema_keeps_its_extra_behaviour(self):
        # ninja caches schemas by name and fields but not by config: the output schema, built first by
        # a read, used to be handed to writes too, which then silently dropped unknown properties
        collection = oapif.collections["tests.point_2056_10fields"]
        fields = ("field_str_9", "field_str_8")  # built nowhere else, so nothing is cached for it yet

        ignoring = collection.get_properties_schema(fields, extra="ignore")
        forbidding = collection.get_properties_schema(fields)

        self.assertEqual(ignoring.model_config["extra"], "ignore")
        self.assertEqual(forbidding.model_config["extra"], "forbid")

    def test_schema_subset_recognition(self):
        self.maxDiff = None
        url = f"{collections_url}/tests.point_2056_10fields_subset/schema"

        expected_schema = {
            "additionalProperties": False,
            "properties": {
                "field_int": {"title": "Field Int", "type": "integer"},
                "field_str_0": {"title": "Field 0", "maxLength": 255, "type": "string"},
                "geom": {"title": "geometry", "x-ogc-role": "primary-geometry", "format": "geometry-point"},
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
                "id": {"format": "uuid", "title": "Id", "type": "string"},
                "text_mandatory_field": {"maxLength": 255, "title": "Mandatory Field", "type": "string"},
                "geom": {"title": "geometry", "x-ogc-role": "primary-geometry", "format": "geometry-point"},
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
            {"title": "geometry", "x-ogc-role": "primary-geometry", "format": "geometry-point"},
        )

    def test_schema_geometry_type_linestring(self):
        url = f"{collections_url}/tests.line_2056_10fields/schema"
        schema_response = self.client.get(url, headers=headers, content_type="application/json")

        self.assertEqual(schema_response.status_code, 200)
        self.assertEqual(
            schema_response.json()["properties"]["geom"],
            {"title": "geometry", "x-ogc-role": "primary-geometry", "format": "geometry-linestring"},
        )

    def test_schema_geometry_type_polygon(self):
        url = f"{collections_url}/tests.polygon_2056/schema"
        schema_response = self.client.get(url, headers=headers, content_type="application/json")

        self.assertEqual(schema_response.status_code, 200)
        self.assertEqual(
            schema_response.json()["properties"]["geom"],
            {"title": "geometry", "x-ogc-role": "primary-geometry", "format": "geometry-multipolygon"},
        )

    def test_schema_geometry_type_any(self):
        url = f"{collections_url}/tests.geometry_2056/schema"
        schema_response = self.client.get(url, headers=headers, content_type="application/json")

        self.assertEqual(schema_response.status_code, 200)
        self.assertEqual(
            schema_response.json()["properties"]["geom"],
            {"title": "geometry", "x-ogc-role": "primary-geometry", "format": "geometry-any"},
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
                response = self.client.get(
                    f"{collections_url}/{collection}/items?limit=1",
                    headers={"Accept": "application/geo+json"},
                )

                self.assertEqual(response.status_code, 200)
                feature = response.json()["features"][0]
                if geometry_type:
                    self.assertEqual(feature["geometry"]["type"], geometry_type)
                else:
                    self.assertEqual(feature["geometry"], None)

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

    def test_arrow_reports_the_total_and_the_page_links(self):
        # an Arrow stream cannot carry them in the payload, so they go to the headers
        url = f"{collections_url}/tests.point_2056_10fields/items?limit=1&offset=1"
        arrow = self.client.get(url, headers={"Accept": "application/vnd.apache.arrow.stream"})
        geojson = self.client.get(url, headers={"Accept": "application/geo+json"}).json()

        self.assertEqual(arrow.status_code, 200)
        self.assertEqual(arrow.headers["OGC-NumberMatched"], str(geojson["numberMatched"]))
        self.assertEqual({link["rel"] for link in geojson["links"]}, {"self", "prev", "next"})
        for link in geojson["links"]:
            self.assertIn(f'<{link["href"]}>; rel="{link["rel"]}"', arrow.headers["Link"])

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
                    f"{collections_url}/tests.geometryz_2056/items/{self.ids[name]}?crs={crs_2056}",
                    headers={"Accept": "application/geo+json"},
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["geometry"], expected)

    def test_items_keep_z(self):
        response = self.client.get(
            f"{collections_url}/tests.geometryz_2056/items?crs={crs_2056}",
            headers={"Accept": "application/geo+json"},
        )

        self.assertEqual(response.status_code, 200)
        features = {feature["id"]: feature["geometry"] for feature in response.json()["features"]}
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


class TestCrs(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("populate_data", "-s 100")

    def test_uri_keeps_the_requested_authority(self):
        # EPSG:4326 is lat/lon and CRS84 is lon/lat, so the two must not be conflated
        self.assertEqual(CRS("OGC", 4326).uri(), crs84)
        self.assertEqual(CRS("EPSG", 4326).uri(), "http://www.opengis.net/def/crs/EPSG/0/4326")
        self.assertEqual(CRS("EPSG", 2056).uri(), crs_2056)

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

    def test_unadvertised_bbox_crs_is_rejected(self):
        url = f"{collections_url}/tests.point_2056_10fields/items?bbox=0,0,1,1&bbox-crs={crs_base}/EPSG/0/3857"

        self.assertEqual(self.client.get(url).status_code, 400)

    def test_geometry_less_collection_ignores_crs(self):
        collection_response = self.client.get(f"{collections_url}/tests.nogeom_10fields")

        self.assertEqual(collection_response.status_code, 200)
        self.assertIsNone(collection_response.json().get("crs"))
        items = self.client.get(f"{collections_url}/tests.nogeom_10fields/items?limit=1&crs={crs_base}/EPSG/0/3857")
        self.assertEqual(items.status_code, 200)


class TestCircularString(TestCase):
    """A CircularString is a sequence of arcs, so any odd number of at least 3 points is valid."""

    POINT_COUNTS = (3, 5, 13, 27)

    @staticmethod
    def arc_wkt(point_count: int) -> str:
        points = ", ".join(f"{2508500 + i * 10} {1152000 + (i % 2) * 10}" for i in range(point_count))
        return f"CIRCULARSTRING({points})"

    @classmethod
    def setUpTestData(cls):
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
                response = self.client.get(f"{collections_url}/tests.arc_2056_10fields/items/{self.ids[count]}")

                self.assertEqual(response.status_code, 200)
                geometry = response.json()["geometry"]
                self.assertEqual(geometry["type"], "CircularString")
                self.assertEqual(len(geometry["coordinates"]), count)

    def test_arc_item_options(self):
        response = self.client.options(f"{collections_url}/tests.arc_2056_10fields/items/{self.ids[3]}")

        self.assertEqual(response.status_code, 200)

    def test_arc_can_be_deleted(self):
        # fetching an item to act on used to load the geometry through GEOS, which has no curve support
        self.client.force_login(User.objects.create_superuser(username="arc_admin", email=None, password="123"))
        url = f"{collections_url}/tests.arc_2056_10fields/items/{self.ids[3]}"

        self.assertEqual(self.client.delete(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 404)

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
