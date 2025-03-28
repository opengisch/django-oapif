import requests
from qgis.core import (
    QgsDataSourceUri,
    QgsFeature,
    QgsGeometry,
    QgsPoint,
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
        self.assertTrue("tests.point_2056_10fields" in [collection["id"] for collection in res["collections"]])

    def test_many_points(self):
        points = requests.get(POINTS_URL).json()
        self.assertTrue(len(points) > 1)

    def test_load_layer(self):
        uri = QgsDataSourceUri()
        uri.setParam("service", "wfs")
        uri.setParam("typename", "tests.point_2056_10fields")
        uri.setParam("url", ROOT_URL)
        layer = QgsVectorLayer(uri.uri(), "point", "OAPIF")
        self.assertTrue(layer.isValid())

        layer = self.project.addMapLayer(layer)
        self.assertIsNotNone(layer)

        f = None
        for f in layer.getFeatures("field_str_0 is not null"):
            pass
        self.assertIsInstance(f, QgsFeature)

        self.assertFalse(bool(layer.dataProvider().capabilities() & QgsVectorDataProvider.Capability.AddFeatures))

    def test_load_and_edit_with_basic_auth(self):
        for layer in ("tests.point_2056_10fields_local_geom", "tests.point_2056_10fields"):
            uri = QgsDataSourceUri()
            uri.setParam("service", "wfs")
            uri.setParam("typename", layer)
            uri.setParam("url", ROOT_URL)
            uri.setPassword(self.password)
            uri.setUsername(self.user)

            layer = QgsVectorLayer(uri.uri(), layer, "OAPIF")
            self.assertTrue(layer.isValid())
            layer = self.project.addMapLayer(layer)
            self.assertIsNotNone(layer)

            self.assertTrue(bool(layer.dataProvider().capabilities() & QgsVectorDataProvider.Capability.AddFeatures))

            f = next(layer.getFeatures())
            self.assertIsInstance(f, QgsFeature)

            # f["field_str_0"] = "xyz"
            # with edit(layer):
            #    layer.updateFeature(f)

            # f = next(layer.getFeatures("field_str_0='xyz'"))
            # self.assertIsInstance(f, QgsFeature)

            # create with geometry
            f = QgsFeature()
            f.setFields(layer.fields())
            f["field_bool"] = True
            f["field_str_0"] = "Super Green"
            geom = QgsGeometry.fromPoint(QgsPoint(2345678.0, 1234567.0))
            f.setGeometry(geom)
            with edit(layer):
                layer.addFeature(f)
            f = next(layer.getFeatures("field_str_0='Super Green'"))
            self.assertIsInstance(f, QgsFeature)
            self.assertEqual(geom.asWkt(), f.geometry().asWkt())

    def test_non_null_default(self):
        layer = "tests.non_null_field_with_default"
        uri = QgsDataSourceUri()
        uri.setParam("service", "wfs")
        uri.setParam("typename", layer)
        uri.setParam("url", ROOT_URL)
        uri.setPassword(self.password)
        uri.setUsername(self.user)

        layer = QgsVectorLayer(uri.uri(), layer, "OAPIF")
        self.assertTrue(layer.isValid())
        layer = self.project.addMapLayer(layer)
        self.assertIsNotNone(layer)

        self.assertTrue(bool(layer.dataProvider().capabilities() & QgsVectorDataProvider.Capability.AddFeatures))

        f = QgsFeature(layer.fields())
        self.assertIsNone(f["field_non_null_with_default"])
        with edit(layer):
            layer.addFeature(f)
        f = next(layer.getFeatures())
        self.assertIsInstance(f, QgsFeature)
        self.assertEqual(f["field_non_null_with_default"], 8)
