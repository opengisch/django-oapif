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
