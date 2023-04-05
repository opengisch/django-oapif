from rest_framework.test import APITestCase


class TestViewsets(APITestCase):
    def test_sign_read(self):
        response = self.client.get(
            "/oapif/collections/signalo_core.sign",
        )
        self.assertIs(response.status_code, 200)

    def test_pole_read(self):
        response = self.client.get(
            "/oapif/collections/signalo_core.pole"
        )
        self.assertIs(response.status_code, 200)

    def test_sign_write(self):
        response = self.client.put(
            "/oapif/collections/signalo_core.sign", data={}
        )
        self.assertIn(response.status_code, [403, 405])

    def test_pole_write(self):
        response = self.client.put(
            "/oapif/collections/signalo_core.pole", data={}
        )
        self.assertIn(response.status_code, [403, 405])

