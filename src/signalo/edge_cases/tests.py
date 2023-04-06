from rest_framework.test import APITestCase

test_status_codes = {
    "/oapif/collections/signalo_edge_cases.allowanymodel": {"get": [200], "put": [200]},
    "/oapif/collections/signalo_edge_cases.djangomodelpermissionsmodel": {
        "get": [200],
        "put": [403, 405],
    },
    "/oapif/collections/signalo_edge_cases.isadminusermodel": {
        "get": [403, 405],
        "put": [403, 405],
    },
}

test_filtered_out = {"/oapif/collections": {"signalo_edge_cases.isadminusermodel"}}


class TestViewsets(APITestCase):
    def test_model_viewsets(self):
        failed = []

        for url, method_results in test_status_codes.items():
            for method_name, expected_results in method_results.items():
                client_method = getattr(self.client, method_name)
                target = f"{url}, {method_name}"

                if method_name == "get":
                    result = client_method(url).status_code

                if method_name == "put":
                    result = client_method(url, data={}).status_code

                if result not in expected_results:
                    failed.append(
                        f"{target}: {result} (expected any of: {expected_results})"
                    )

        print(failed)
        self.assertTrue(not failed)

    def test_filteredout_collections_viewsets(self):
        headers = {"Content-Type": "application/json"}
        for url, filtered_out in test_filtered_out.items():
            results = self.client.get(url, headers=headers).json()
            collection_ids = {collection["id"] for collection in results["collections"]}
            self.assertTrue(not collection_ids.intersection(filtered_out))
