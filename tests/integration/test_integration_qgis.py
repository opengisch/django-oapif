import requests
from osgeo import gdal
from qgis.core import (
    Qgis,
    QgsDataSourceUri,
    QgsEditError,
    QgsFeature,
    QgsPoint,
    QgsProject,
    QgsVectorDataProvider,
    QgsVectorLayer,
    QgsWkbTypes,
    edit,
)
from qgis.testing import start_app, unittest

start_app()

# GDAL reads the curves of JSON-FG since its 3.12
GDAL_READS_CURVES = int(gdal.VersionInfo()) >= 3120000

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

    def load_curves(self, url: str = ROOT_URL, **params) -> QgsVectorLayer:
        uri = QgsDataSourceUri()
        uri.setParam("service", "wfs")
        uri.setParam("typename", "tests.curvepolygon_2056")
        uri.setParam("url", url)
        for name, value in params.items():
            uri.setParam(name, value)
        layer = QgsVectorLayer(uri.uri(), "curves", "OAPIF")
        self.assertTrue(layer.isValid())
        return layer

    def assert_in_the_storage_crs(self, layer: QgsVectorLayer, feature: QgsFeature):
        # the area of the test data, in EPSG:2056
        self.assertEqual(layer.crs().authid(), "EPSG:2056")
        box = feature.geometry().boundingBox()
        self.assertGreaterEqual(box.xMinimum(), 2508500)
        self.assertLess(box.xMaximum(), 2512000)
        self.assertGreaterEqual(box.yMinimum(), 1152000)
        self.assertLess(box.yMaximum(), 1156000)

    def test_curves_are_not_linearized_unasked(self):
        layer = self.load_curves()

        features = list(layer.getFeatures())
        self.assertTrue(features)
        if GDAL_READS_CURVES:
            self.assertEqual(layer.wkbType(), QgsWkbTypes.CurvePolygon)
        else:
            # rather than a geometry that is not theirs
            self.assertTrue(all(feature.geometry().isNull() for feature in features))

    def test_curves_are_linearized_with_the_plus_profile(self):
        # QGIS 3 asks for it with the query of the URL, which it copies to every request
        layer = self.load_curves(f"{ROOT_URL}?profile=jsonfg-plus")

        feature = next(layer.getFeatures())
        geometry = feature.geometry().constGet()
        # GDAL reads "place" first, when it knows curves
        self.assertEqual(geometry.hasCurvedSegments(), GDAL_READS_CURVES)
        if not GDAL_READS_CURVES:
            # the rounded corner, linearized
            self.assertGreater(geometry.exteriorRing().numPoints(), 7)
        # which GDAL reprojects from CRS84, as JSON-FG gives it to GeoJSON readers
        self.assert_in_the_storage_crs(layer, feature)

    @unittest.skipUnless(Qgis.QGIS_VERSION_INT >= 40200, "QGIS tells JSON-FG from GeoJSON by the link since 4.2")
    def test_jsonfg_is_read_through_its_link(self):
        # in pages QGIS reads from the headers
        uri = QgsDataSourceUri()
        uri.setParam("service", "wfs")
        uri.setParam("typename", "tests.point_2056_10fields")
        uri.setParam("url", ROOT_URL)
        uri.setParam("outputformat", "application/fg+json")
        uri.setParam("pageSize", "100")
        layer = QgsVectorLayer(uri.uri(), "point", "OAPIF")
        self.assertTrue(layer.isValid())

        features = list(layer.getFeatures())
        self.assertEqual(len(features), requests.get(f"{POINTS_URL}/items").json()["numberMatched"])
        self.assertEqual(layer.crs().authid(), "EPSG:2056")
        # in "place", in the storage CRS
        point = features[0].geometry().asPoint()
        self.assertGreaterEqual(point.x(), 2508500)
        self.assertGreaterEqual(point.y(), 1152000)

    @unittest.skipUnless(
        Qgis.QGIS_VERSION_INT >= 40200 and GDAL_READS_CURVES, "needs QGIS 4.2, and GDAL 3.12 for the curves of JSON-FG"
    )
    def test_curves_are_read_in_jsonfg(self):
        layer = self.load_curves(outputformat="application/fg+json")

        self.assertEqual(layer.wkbType(), QgsWkbTypes.CurvePolygon)
        feature = next(layer.getFeatures())
        self.assertTrue(feature.geometry().constGet().hasCurvedSegments())
        self.assert_in_the_storage_crs(layer, feature)
