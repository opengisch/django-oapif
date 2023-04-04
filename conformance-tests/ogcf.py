import unittest
from urllib.parse import quote_plus, urlencode

import requests


def is_200(res: requests.Response) -> bool:
    return res.status_code == 200


class ConformanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app_address = "django:8000"
        cls.api_url = f"http://{app_address}/oapif/"

        conformance_suite_address = "conformance_suite:8080"
        cls.conformance_suites_url = (
            f"http://{conformance_suite_address}/teamengine/rest/suites"
        )
        cls.conformance_ogc_suite_url = (
            f"{cls.conformance_suites_url}/ogcapi-features-1.0/run"
        )

    def test_endpoint_django(self):
        print(f"Trying to access: {self.api_url}")
        response = requests.get(self.api_url)
        self.assertTrue(is_200(response))

    def test_endpoint_testsuite(self):
        print(f"Trying to access: {self.conformance_suites_url}")
        response = requests.get(self.conformance_suites_url)
        print(response.text, response.status_code)
        self.assertTrue(is_200(response))

    def test_conformance_api(self):
        params = {"iut": self.api_url}
        encoded_params = urlencode(params, quote_via=quote_plus)
        url = f"{self.conformance_ogc_suite_url}?{encoded_params}"
        headers = {"Accept": "application/xml"}
        response = requests.get(url, headers=headers)
        self.assertTrue(is_200(response))


if __name__ == "__main__":
    unittest.main()
