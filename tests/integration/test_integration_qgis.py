import requests
from qgis.core import (
    QgsDataSourceUri,
    QgsEditError,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsNetworkAccessManager,
    QgsPoint,
    QgsProject,
    QgsVectorDataProvider,
    QgsVectorLayer,
    QgsWkbTypes,
    edit,
)
from qgis.PyQt.QtCore import QCoreApplication
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

        self.assertEqual(root_response.status_code, 200)
        self.assertEqual(collections_response.status_code, 200)
        self.assertEqual(points_response.status_code, 200)

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

        for f in layer.getFeatures("field_str_0 is not null"):
            self.assertIsInstance(f, QgsFeature)

        self.assertFalse(bool(layer.dataProvider().capabilities() & QgsVectorDataProvider.Capability.AddFeatures))

    def test_load_and_edit_with_basic_auth(self):
        uri = QgsDataSourceUri()
        uri.setParam("service", "wfs")
        uri.setParam("typename", "tests.point_2056_10fields")
        uri.setParam("url", ROOT_URL)
        uri.setUsername("admin")
        uri.setPassword("123")

        layer = QgsVectorLayer(uri.uri(), "point", "OAPIF")
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
        geom = QgsPoint(2345678.0, 1234567.0)
        f.setGeometry(geom.clone())
        with edit(layer):
            layer.addFeature(f)
        f = next(layer.getFeatures("field_str_0='Super Green'"))
        self.assertIsInstance(f, QgsFeature)
        self.assertEqual(geom.asWkt(), f.geometry().asWkt())

    def test_load_and_edit_with_missing_field(self):
        uri = QgsDataSourceUri()
        uri.setParam("service", "wfs")
        uri.setParam("typename", "tests.mandatoryfield")
        uri.setParam("url", ROOT_URL)
        uri.setUsername("admin")
        uri.setPassword("123")

        layer = QgsVectorLayer(uri.uri(), "point", "OAPIF")
        self.assertTrue(layer.isValid())
        layer = self.project.addMapLayer(layer)
        self.assertIsNotNone(layer)

        self.assertTrue(bool(layer.dataProvider().capabilities() & QgsVectorDataProvider.Capability.AddFeatures))

        f = QgsFeature()
        f.setFields(layer.fields())
        f.setGeometry(QgsPoint(2345678.0, 1234567.0))
        f["text_mandatory_field"] = None

        with self.assertRaises(QgsEditError) as ctx:
            with edit(layer):
                layer.addFeature(f)

        self.assertEqual(
            str(ctx.exception),
            """[\'ERROR: 1 feature(s) not added.\', \'\\n  Provider errors:\', \'    Feature creation failed: Create Feature request failed: Error transferring http://django:8000/oapif/collections/tests.mandatoryfield/items - server replied: Unprocessable Entity\\n    Server response: {"detail": [{"type": "string_type", "loc": ["body", "feature", "properties", "text_mandatory_field"], "msg": "Input should be a valid string", "input": null, "url": "https://errors.pydantic.dev/2.13/v/string_type"}]}\']""",
        )

        f = next(layer.getFeatures())
        self.assertIsInstance(f, QgsFeature)

    def test_load_layer_with_point_type(self):
        uri = QgsDataSourceUri()
        uri.setParam("service", "wfs")
        uri.setParam("typename", "tests.point_2056_10fields")
        uri.setParam("url", ROOT_URL)
        layer = QgsVectorLayer(uri.uri(), "point", "OAPIF")
        self.assertTrue(layer.isValid())
        layer = self.project.addMapLayer(layer)
        self.assertIsNotNone(layer)
        self.assertEqual(layer.geometryType(), QgsWkbTypes.PointGeometry)

    def test_load_layer_with_linestring_type(self):
        uri = QgsDataSourceUri()
        uri.setParam("service", "wfs")
        uri.setParam("typename", "tests.line_2056_10fields")
        uri.setParam("url", ROOT_URL)
        layer = QgsVectorLayer(uri.uri(), "line", "OAPIF")
        self.assertTrue(layer.isValid())
        layer = self.project.addMapLayer(layer)
        self.assertIsNotNone(layer)
        self.assertEqual(layer.geometryType(), QgsWkbTypes.LineGeometry)

    def test_load_layer_with_multipolygon_type(self):
        uri = QgsDataSourceUri()
        uri.setParam("service", "wfs")
        uri.setParam("typename", "tests.polygon_2056")
        uri.setParam("url", ROOT_URL)
        layer = QgsVectorLayer(uri.uri(), "polygon", "OAPIF")
        self.assertTrue(layer.isValid())
        layer = self.project.addMapLayer(layer)
        self.assertIsNotNone(layer)
        self.assertEqual(layer.geometryType(), QgsWkbTypes.PolygonGeometry)

    def test_load_empty_layer_with_point_type(self):
        uri = QgsDataSourceUri()
        uri.setParam("service", "wfs")
        uri.setParam("typename", "tests.point_2056_empty")
        uri.setParam("url", ROOT_URL)
        layer = QgsVectorLayer(uri.uri(), "point", "OAPIF")
        self.assertTrue(layer.isValid())
        layer = self.project.addMapLayer(layer)
        self.assertIsNotNone(layer)
        self.assertEqual(layer.featureCount(), 0)
        self.assertEqual(layer.geometryType(), QgsWkbTypes.PointGeometry)

    def test_layer_filters_are_applied_by_the_server(self):
        # with the filtering classes of Part 3, QGIS sends the filter of a layer to the server instead of
        # filtering every feature itself: the features it gets back have to be the ones it would have picked
        requested = []

        def record(reply):
            requested.append(reply.request().url().toString())

        # the main thread instance relays the replies of every thread, unlike the requests about to be created
        manager = QgsNetworkAccessManager.instance()
        manager.finished.connect(record)
        self.addCleanup(manager.finished.disconnect, record)

        uri = QgsDataSourceUri()
        uri.setParam("service", "wfs")
        uri.setParam("typename", "tests.point_2056_10fields")
        uri.setParam("url", ROOT_URL)
        for expression in (
            '"field_int" >= 500',
            """"field_int" >= 500 AND "field_str_0" LIKE 'a%'""",
            """"field_str_0" ILIKE 'A%'""",
            'NOT ("field_int" < 500)',
            '"field_int" IN (1, 2, 3) OR "field_int" BETWEEN 100 AND 110',
            '"field_str_1" IS NULL',
            # in the CRS of the layer, which QGIS sends as the filter-crs
            "intersects_bbox($geometry, geom_from_wkt('POLYGON((2508500 1152000, 2510000 1152000, "
            "2510000 1153500, 2508500 1153500, 2508500 1152000))'))",
        ):
            with self.subTest(expression=expression):
                layer = QgsVectorLayer(uri.uri(), "point", "OAPIF")
                self.assertTrue(layer.isValid())
                picked = QgsExpression(expression)
                context = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
                expected = set()
                for feature in layer.getFeatures():
                    context.setFeature(feature)
                    if picked.evaluate(context):
                        expected.add(feature["id"])

                requested.clear()
                self.assertTrue(layer.setSubsetString(expression))
                filtered = {feature["id"] for feature in layer.getFeatures()}
                QCoreApplication.processEvents()

                self.assertEqual(filtered, expected)
                self.assertTrue(any("filter=" in url for url in requested), requested)
