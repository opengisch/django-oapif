import requests
from qgis.core import QgsDataSourceUri, QgsProject, QgsVectorLayer

ROOT_URL = "http://django:8000/oapif/"
COLLECTIONS_URL = "http://django:8000/oapif/collections"
POLES_URL = "http://django:8000/oapif/collections/signalo_core.pole"


def test_endpoint_ok():
    root_response = requests.get(ROOT_URL)
    collections_response = requests.get(COLLECTIONS_URL)
    poles_response = requests.get(POLES_URL)

    assert root_response.status_code == 200
    assert collections_response.status_code == 200
    assert poles_response.status_code == 200


def test_collection_exists():
    res = requests.get(COLLECTIONS_URL).json()
    assert "signalo_core.pole" in [
        collection["id"] for collection in res["collections"]
    ]


def test_many_poles():
    poles = requests.get(POLES_URL).json()
    assert len(poles) > 1


def test_load_layer():
    uri = QgsDataSourceUri()
    uri.setParam("service", "wfs")
    uri.setParam("version", "1.1.0")
    uri.setParam("url", ROOT_URL)

    layer = QgsVectorLayer(uri.uri(), "signalo_core.pole", "WFS")
    assert layer.isValid()

    project = QgsProject.instance()
    project.addLayer(layer)
    assert len(project.mapLayers().values()) > 0
