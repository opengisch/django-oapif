from rest_framework.test import APITestCase

from .models import (
    TestPermissionAllowAny,
    TestPermissionDefaultPermissionsSettings,
    TestPermissionIsAdminUserModel,
)

app_collections_url = "/oapif/collections"
app_models_url = f"{app_collections_url}/signalo_edge_cases"


def make_request(client, crud_type: str, url: str) -> int:
    if crud_type == "create":
        client_method = getattr(client, "put")
        resp = client_method(url, data={})
    elif crud_type == "list":
        client_method = getattr(client, "get")
        resp = client_method(url)
    elif crud_type == "read":
        client_method = getattr(client, "get")
        resp = client_method(url)
    elif crud_type == "update":
        client_method = getattr(client, "patch")
        resp = client_method(url, data={})
    elif crud_type == "destroy":
        client_method = getattr(client, "delete")
        resp = client_method(url)
    else:
        raise ValueError(f"Not supported CRUD type: {crud_type}")
    return resp.status_code


models_results = {
    f"{app_models_url}.{TestPermissionAllowAny.__name__.lower()}": {
        "create": 200,
        "list": 200,
        "read": 200,
        "update": 200,
        "destroy": 200,
    },
    f"{app_models_url}.{TestPermissionDefaultPermissionsSettings.__name__.lower()}": {
        "create": 200,
        "list": 200,
        "read": 200,
        "update": 200,
        "destroy": 200,
    },
    f"{app_models_url}.{TestPermissionIsAdminUserModel.__name__.lower()}": {
        "create": 401,
        "list": 401,
        "read": 401,
        "update": 401,
        "destroy": 401,
    },
}
# test_roles = "anonyme, pas d'autorisation spécifique, autorisations spécifiques au modèle, autorisation readonly, toutes les autorisations, admin"
collections_to_filter = {"/oapif/collections": {"signalo_edge_cases.isadminusermodel"}}


class TestViewsets(APITestCase):

    # TODO: Créer des objets test

    def test_model_viewsets(self):
        failed = []

        for url, crud_results in models_results.items():
            for crud_name, expected_results in crud_results.items():
                response_code = make_request(self.client, crud_name, url)
                if response_code != expected_results:
                    failed.append(
                        f"{crud_name}: {url} (expected any of: {expected_results})"
                    )

        print(failed)
        self.assertTrue(not failed)

    def test_filteredout_collections_viewsets(self):
        failed = []

        for url, to_filter_out in collections_to_filter.items():
            results = self.client.get(
                url, headers={"Content-Type": "application/json"}
            ).json()
            collection_ids = {collection["id"] for collection in results["collections"]}

            if collection_ids.intersection(to_filter_out):
                failed.append(f"{url} unable to filter out: {to_filter_out}")

            print(failed)
            self.assertTrue(not failed)
