import unittest
from urllib.parse import quote_plus, urlencode

import requests

test_client_url = "http://localhost:8081/teamengine/rest/suites/ogcapi-features-1.0/run"
api_url = "http://localhost:8000/oapif/"


class ConformanceTest(unittest.TestCase):
    def test_endpoint(self):
        params = {"iut": api_url}
        encoded_params = urlencode(params, quote_via=quote_plus)
        url = f"{test_client_url}?{encoded_params}"
        headers = {"Accept": "application/xml"}
        print(f"Validating: {api_url} with {url}")
        response = requests.get(url, headers=headers)
        print(f"{response.text}")


if __name__ == "__main__":
    unittest.main()
