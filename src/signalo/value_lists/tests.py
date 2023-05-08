import os
import shutil
from json import load
from typing import Dict, List, Set, Union

from django.core.management import call_command
from rest_framework.test import APITestCase


def get_unique_file_names(rows: Union[List[Dict], List[str]]) -> Set[str]:
    language_keys = {"img_de", "img_fr", "img_it", "img_ro"}
    names = set()
    for row in rows:
        if isinstance(row, Dict):
            for k, v in row.items():
                if k in language_keys:
                    names.add(v)
        elif isinstance(row, str):
            names.add(row)
    return names


class TestOfficialSigns(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        path_to_official_signs = os.path.relpath(
            "signalo/value_lists/data/official-signs.json"
        )
        cls.path_to_signs_images = os.path.abspath("/media_volume/official_signs")

        with open(path_to_official_signs, "r") as fh:
            cls.official_signs = load(fh)
        cls.unique_official_names = get_unique_file_names(cls.official_signs)

    def setUp(self):
        if os.path.exists(self.path_to_signs_images):
            shutil.rmtree(self.path_to_signs_images)

        call_command("populate_vl")
        self.assertTrue(os.listdir(self.path_to_signs_images))

    def tearDown(self):
        for file in os.listdir(self.path_to_signs_images):
            path_to_file = os.path.join(self.path_to_signs_images, file)
            os.remove(path_to_file)
        self.assertTrue(not os.listdir(self.path_to_signs_images))

    def test_official_names(self):
        self.assertEqual(len(self.unique_official_names), 340)

    def test_exact_files(self):
        self.assertEqual(
            self.unique_official_names, set(os.listdir(self.path_to_signs_images))
        )

    def test_official_signs_collection(self):
        response = self.client.get("/oapif/collections/signalo_vl.officialsigntype")
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.json()), 0)

    def test_official_signs_items(self):
        response = self.client.get(
            "/oapif/collections/signalo_vl.officialsigntype/items"
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        expected = {"type": "FeatureCollection", "features": []}

        for k, v in result.items():
            if k in expected:
                if isinstance(v, str):
                    self.assertEqual(v, expected[k])
                elif isinstance(v, List):
                    self.assertTrue(isinstance(expected[k], List))
                    self.assertGreater(len(v), 0)

    def test_dotty_dashy_url_patterns(self):
        collection_url = "/oapif/collections/signalo_vl.officialsigntype/items"
        ids = ["0.2-r", "1.06"]
        urls = [f"{collection_url}/{id}" for id in ids]
        condition = all(
            self.client.get(url, format="json").json()["id"] == id
            for (url, id) in zip(urls, ids)
        )
        self.assertTrue(condition)
