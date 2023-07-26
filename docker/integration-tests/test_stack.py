import requests
from qgis.core import QgsDataSourceUri, QgsFeature, QgsProject, QgsVectorLayer
from qgis.testing import start_app, unittest

start_app()

ROOT_URL = "http://django:8000/oapif/"
COLLECTIONS_URL = "http://django:8000/oapif/collections"
POLES_URL = "http://django:8000/oapif/collections/signalo_core.pole"


class TestStack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = QgsProject.instance()
        cls.user = "admin"
        cls.password = "123"

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

        self.project.addMapLayer(layer)
        self.assertTrue(len(self.project.mapLayers().values()) > 0)

    def test_load_with_basic_auth(self):
        uri = QgsDataSourceUri()
        uri.setParam("service", "wfs")
        uri.setParam("typename", "signalo_core.pole")
        uri.setParam("url", ROOT_URL)
        uri.setPassword(self.password)
        uri.setUsername(self.user)

        layer = QgsVectorLayer(uri.uri(), "pole", "OAPIF")
        self.assertTrue(layer.isValid())
        layer = self.project.addMapLayer(layer)
        self.assertIsNotNone(layer)

        f = None
        for f in layer.getFeatures("name='1-1'"):
            pass
        self.assertIsInstance(f, QgsFeature)
