from rest_framework.test import APITestCase


class TestViewsets(APITestCase):
    def test_allowanymodel(self):
        response = self.client.get(
            "/oapif/collections/signalo_edge_cases.allowanymodel"
        )
        self.assertIs(response.status_code, 200)

    def test_isadminusermodel(self):
        response = self.client.put(
            "/oapif/collections/signalo_edge_cases.isadminusermodel", data={}
        )
        self.assertIn(response.status_code, [403, 405])
