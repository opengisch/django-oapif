import unittest
from urllib.parse import quote_plus, urlencode

import requests


class ConformanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app_service = "django:8000"
        conformance_service = "conformance_suite"
        cls.api_url = f"http://{app_service}/oapif/"
        cls.test_client_url = f"http://{conformance_service}/teamengine/rest/suites/ogcapi-features-1.0/run"

    def test_api_endpoint(self):
        print(f"Trying to access: {self.api_url}")
        response = requests.get(self.api_url)
        condition = response.status_code == 200

        if not condition:
            print(response.status_code)
        self.assertTrue(condition)

    def test_api_endpoint_conformance(self):
        params = {"iut": self.api_url}
        encoded_params = urlencode(params, quote_via=quote_plus)
        url = f"{self.test_client_url}?{encoded_params}"
        headers = {"Accept": "application/xml"}

        print(f"Validating: {self.api_url} with {url}")
        response = requests.get(url, headers=headers)

        condition = response.status_code == 200
        self.assertTrue(condition)


if __name__ == "__main__":
    unittest.main()
