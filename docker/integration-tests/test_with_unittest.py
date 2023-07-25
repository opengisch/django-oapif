from qgis.core import QgsDataSourceUri, QgsProject, QgsVectorLayer
from qgis.testing import start_app, unittest
import requests

start_app()

ROOT_URL = "http://django:8000/oapif/"
COLLECTIONS_URL = "http://django:8000/oapif/collections"
POLES_URL = "http://django:8000/oapif/collections/signalo_core.pole"


class TestStack(unittest.TestCase):
    def test_endpoint_ok(self):
        root_response = requests.get(ROOT_URL)
        collections_response = requests.get(COLLECTIONS_URL)
        poles_response = requests.get(POLES_URL)

        self.assertTrue(root_response.status_code == 200)
        self.assertTrue(collections_response.status_code == 200)
        self.assertTrue(poles_response.status_code == 200)

    def test_collection_exists(self):
        res = requests.get(COLLECTIONS_URL).json()
        self.assertTrue(
            "signalo_core.pole"
            in [collection["id"] for collection in res["collections"]]
        )

    def test_many_poles(self):
        poles = requests.get(POLES_URL).json()
        self.assertTrue(len(poles) > 1)

    def test_load_layer(self):
        uri = QgsDataSourceUri()
        uri.setParam("service", "wfs")
        uri.setParam("typename", "signalo_core.pole")
        uri.setParam("url", ROOT_URL)
        layer = QgsVectorLayer(uri.uri(), "pole", "OAPIF")
        self.assertTrue(layer.isValid())

        project = QgsProject.instance()
        project.addMapLayer(layer)
        self.assertTrue(len(project.mapLayers().values()) > 0)
