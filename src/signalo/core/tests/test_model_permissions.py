import unittest

from rest_framework.test import RequestsClient


class TestViewsets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = RequestsClient()

    def test_pole(self):
        response = self.client.patch(
            "http://testserver/oapif/collections/signalo_core.pole/1", data={}
        )
        self.assertIn(response.status_code, [403, 404])

    def test_sign(self):
        response = self.client.get(
            "http://testserver/oapif/collections/signalo_core.sign/1", data={}
        )
        self.assertIn(response.status_code, [403, 404])
