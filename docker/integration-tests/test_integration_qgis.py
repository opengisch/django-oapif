import requests
from qgis.core import (
    QgsDataSourceUri,
    QgsFeature,
    QgsProject,
    QgsVectorDataProvider,
    QgsVectorLayer,
    edit,
)
from qgis.testing import start_app, unittest

start_app()

ROOT_URL = "http://django:8000/oapif/"
COLLECTIONS_URL = "http://django:8000/oapif/collections"
POINTS_URL = "http://django:8000/oapif/collections/tests.point_2056_10fields"


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
        points_response = requests.get(POINTS_URL)

        self.assertTrue(root_response.status_code == 200)
        self.assertTrue(collections_response.status_code == 200)
        self.assertTrue(points_response.status_code == 200)

    def test_collection_exists(self):
        res = requests.get(COLLECTIONS_URL).json()
        self.assertTrue(
            "tests.point_2056_10fields"
            in [collection["id"] for collection in res["collections"]]
        )

    def test_many_points(self):
        points = requests.get(POINTS_URL).json()
        self.assertTrue(len(points) > 1)

    def test_load_layer(self):
        uri = QgsDataSourceUri()
        uri.setParam("service", "wfs")
        uri.setParam("typename", "tests_points")
        uri.setParam("url", ROOT_URL)
        layer = QgsVectorLayer(uri.uri(), "point", "OAPIF")
        self.assertTrue(layer.isValid())

        layer = self.project.addMapLayer(layer)
        self.assertIsNotNone(layer)

        f = None
        for f in layer.getFeatures("name='1-1'"):
            pass
        self.assertIsInstance(f, QgsFeature)

        self.assertFalse(
            bool(
                layer.dataProvider().capabilities()
                & QgsVectorDataProvider.Capability.AddFeatures
            )
        )

    def test_load_with_basic_auth(self):
        uri = QgsDataSourceUri()
        uri.setParam("service", "wfs")
        uri.setParam("typename", "tests_points")
        uri.setParam("url", ROOT_URL)
        uri.setPassword(self.password)
        uri.setUsername(self.user)

        layer = QgsVectorLayer(uri.uri(), "point", "OAPIF")
        self.assertTrue(layer.isValid())
        layer = self.project.addMapLayer(layer)
        self.assertIsNotNone(layer)

        self.assertTrue(
            bool(
                layer.dataProvider().capabilities()
                & QgsVectorDataProvider.Capability.AddFeatures
            )
        )

        f = None
        for f in layer.getFeatures("name='1-1'"):
            pass
        self.assertIsInstance(f, QgsFeature)

        f["field_1"] = "xyz"
        with edit(layer):
            layer.updateFeature(f)

        f = None
        for f in layer.getFeatures("field_1='xyz'"):
            pass
        self.assertIsInstance(f, QgsFeature)
