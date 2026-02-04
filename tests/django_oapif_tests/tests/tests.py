import logging
import re

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test.testcases import TestCase

logger = logging.getLogger(__name__)

collections_url = "/oapif/collections"

headers = {"Content-Crs": "http://www.opengis.net/def/crs/EPSG/0/2056"}


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
