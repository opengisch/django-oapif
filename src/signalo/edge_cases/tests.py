from typing import Any, Tuple
from django.test import Client
from rest_framework.test import APITestCase

from .models import (
    TestPermissionAllowAny,
    TestPermissionDefaultPermissionsSettings,
    TestPermissionIsAdminUserModel,
)

app_collections_url = "/oapif/collections"
app_models_url = f"{app_collections_url}/signalo_edge_cases"


def make_request(client: Client, crud_type: str, url: str) -> Tuple[str, int, Any]:
    headers = {"Content-Type": "application/json"}
    items = f"{url}/items"
    item = f"{items}/1"

    if crud_type == "create":
        data = {"id": 2, "geom": f"Point(2600000 1200000)"}
        resp = client.put(url, data=data, headers=headers)
        return (url, resp.status_code, None)

    if crud_type == "list":
        collections_or_items = url if url == app_collections_url else items
        resp = client.get(collections_or_items, headers=headers)
        return (collections_or_items, resp.status_code, resp.json())

    if crud_type == "read":
        resp = client.get(item, headers=headers)
        return (item, resp.status_code, resp.json())

    if crud_type == "update":
        data = {"geom": f"Point(1300000 600000)"}
        resp = client.patch(item, data=data, headers=headers)
        return (item, resp.status_code, None)

    if crud_type == "destroy":
        resp = client.delete(item, headers=headers)
        return (item, resp.status_code, None)

    raise ValueError(f"Not supported CRUD type: {crud_type}")


urls_default_role_against_model_results = {
    f"{app_models_url}.{TestPermissionAllowAny.__name__.lower()}": {
        "create": 200,
        "list": 200,
        "read": 200,
        "update": 200,
        "destroy": 200,
    },
    f"{app_models_url}.{TestPermissionDefaultPermissionsSettings.__name__.lower()}": {
        "create": 403,
        "list": 200,
        "read": 200,
        "update": 403,
        "destroy": 403,
    },
    f"{app_models_url}.{TestPermissionIsAdminUserModel.__name__.lower()}": {
        "create": 403,
        "list": 403,
        "read": 403,
        "update": 403,
        "destroy": 403,
    },
    f"{app_collections_url}": {"list": 200},
}
# test_roles = "anonyme, pas d'autorisation spécifique, autorisations spécifiques au modèle, autorisation readonly, toutes les autorisations, admin"


class TestViewsets(APITestCase):
    def test_default_role_against_viewsets(self):
        run = 0
        failed = []
        to_filter_out = (
            f"{app_models_url}.{TestPermissionIsAdminUserModel.__name__.lower()}"
        )

        for model_url, crud_results in urls_default_role_against_model_results.items():

            for crud_name, expected_status_code in crud_results.items():
                url, response_code, results = make_request(
                    self.client, crud_name, model_url
                )

                if response_code != expected_status_code:
                    failed.append(
                        f"{crud_name}: {url} (got {response_code}, expected {expected_status_code})"
                    )

                if model_url == app_collections_url:
                    collection_ids = {
                        collection["id"] for collection in results["collections"]
                    }

                    if collection_ids.intersection(to_filter_out):
                        failed.append(f"{url} unable to filter out: {to_filter_out}")

                run += 1

        if failed:
            print(f" => Failed {len(failed)}/{run}")
            print("\n".join(failed))

        self.assertTrue(not failed)
