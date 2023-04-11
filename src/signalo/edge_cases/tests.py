from enum import Enum
from typing import Any, Tuple

from django.test import Client
from rest_framework.test import APITestCase

from .models import (
    TestPermissionAllowAny,
    TestPermissionDefaultPermissionsSettings,
    TestPermissionIsAdminUserModel,
)


class Crud(str, Enum):
    create = "create"
    list = "list"
    read = "read"
    update = "update"
    destroy = "destroy"


app_collections_url = "/oapif/collections"
app_models_url = f"{app_collections_url}/signalo_edge_cases"


def make_request(client: Client, crud_type: Crud, url: str) -> Tuple[str, int, Any]:
    headers = {"Content-Type": "application/json"}
    items = f"{url}/items"
    write_params = {"geom": "Point(1300000 600000)"}
    read_params = {"geom": "Point(2600000 1200000)"}

    if crud_type == Crud.create:
        resp = client.put(url, params=write_params, headers=headers)
        return (url, resp.status_code, None)

    if crud_type == Crud.list:
        collections_or_items = url if url == app_collections_url else items
        resp = client.get(collections_or_items, params=read_params, headers=headers)
        return (collections_or_items, resp.status_code, resp.json())

    if crud_type == Crud.read:
        resp = client.get(items, params=read_params, headers=headers)
        return (items, resp.status_code, resp.json())

    if crud_type == Crud.update:
        resp = client.patch(items, params=write_params, headers=headers)
        return (items, resp.status_code, None)

    if crud_type == Crud.destroy:
        resp = client.delete(items, params=write_params, headers=headers)
        return (items, resp.status_code, None)

    raise ValueError(f"Not supported CRUD type: {crud_type}")


urls_default_role_against_model_results = {
    f"{app_models_url}.{TestPermissionAllowAny.__name__.lower()}": {
        Crud.create: 200,
        Crud.list: 200,
        Crud.read: 200,
        Crud.update: 200,
        Crud.destroy: 200,
    },
    f"{app_models_url}.{TestPermissionDefaultPermissionsSettings.__name__.lower()}": {
        Crud.create: 403,
        Crud.list: 200,
        Crud.read: 200,
        Crud.update: 403,
        Crud.destroy: 403,
    },
    f"{app_models_url}.{TestPermissionIsAdminUserModel.__name__.lower()}": {
        Crud.create: 403,
        Crud.list: 403,
        Crud.read: 403,
        Crud.update: 403,
        Crud.destroy: 403,
    },
    f"{app_collections_url}": {"list": 200},
}


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


# test_roles = "anonyme, pas d'autorisation spécifique, autorisations spécifiques au modèle, autorisation readonly, toutes les autorisations, admin"
