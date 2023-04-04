import unittest

from rest_framework.test import RequestsClient


class TestViewsets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = RequestsClient()

    def test_model_level_permissions_collections(self):
        response = self.client.get("http://testserver/oapif/collections/")
        self.assertIn(response.status_code, [403, 404])

    def test_model_level_permissions_pole(self):
        response = self.client.get(
            "http://testserver/oapif/collections/signalo_core.pole"
        )
        self.assertIn(response.status_code, [403, 404])

    def test_model_level_permissions_sign(self):
        response = self.client.get(
            "http://testserver/oapif/collections/signalo_core.sign"
        )
        self.assertIn(response.status_code, [403, 404])
