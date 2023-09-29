import logging

from django.contrib.auth.models import User
from django.core.management import call_command
from rest_framework.test import APITestCase

logger = logging.getLogger(__name__)

collections_url = "/oapif/collections"


class TestBasicAuth(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("populate_data", "-s 100")
        call_command("populate_users")

        cls.demo_viewer = User.objects.get(username="demo_viewer")
        cls.demo_editor = User.objects.get(username="demo_editor")
        cls.collection_url = collections_url + "/tests.point_2056_10fields"
        cls.items_url = cls.collection_url + "/items"

    def tearDown(self):
        self.client.force_authenticate(user=None)

    def test_get_as_viewer(self):
        collections_from_anonymous = self.client.get(collections_url, format="json").json()
        self.client.force_authenticate(user=self.demo_viewer)
        collection_response = self.client.get(collections_url, format="json")

        self.assertEqual(collection_response.status_code, 200)
        self.assertEqual(len(collection_response.json()), len(collections_from_anonymous))

    def test_post_as_editor(self):
        self.client.force_authenticate(user=self.demo_editor)
        data = {"geom": "Point(1300000 600000)", "field_0": "test123"}
        post_to_items = self.client.post(self.items_url, data, format="json")
        self.assertIn(post_to_items.status_code, (200, 201))

    def test_anonymous_items_options(self):
        # Anonymous user
        expected = {"GET", "OPTIONS", "HEAD"}
        response = self.client.options(self.items_url)

        allowed_headers = set(s.strip() for s in response.headers["Allow"].split(","))
        allowed_body = set(response.json()["actions"].keys())

        self.assertEqual(allowed_body, expected)
        self.assertEqual(allowed_headers, allowed_body)

    def test_editor_items_options(self):
        # Authenticated user with editing permissions
        expected = {"POST", "GET", "OPTIONS", "HEAD"}
        self.client.force_authenticate(user=self.demo_editor)
        response = self.client.options(self.items_url)

        allowed_headers = set(s.strip() for s in response.headers["Allow"].split(","))
        allowed_body = set(response.json()["actions"].keys())

        self.assertEqual(allowed_body, expected)
        self.assertEqual(allowed_headers, allowed_body)
