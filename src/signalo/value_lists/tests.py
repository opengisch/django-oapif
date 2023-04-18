import os
from json import load
from typing import Dict, List, Set, Union

from django.core.management import call_command
from django.test import TestCase


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


class TestOfficialSigns(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        path_to_official_signs = os.path.relpath(
            "signalo/value_lists/data/official-signs.json"
        )
        cls.path_to_images = os.path.abspath("/media_volume/official_signs")
        with open(path_to_official_signs, "r") as fh:
            cls.official_signs = load(fh)
        cls.unique_official_names = get_unique_file_names(cls.official_signs)

    def setUp(self):
        call_command("populate_vl")
        self.assertTrue(os.listdir(self.path_to_images))

    def tearDown(self):
        for file in os.listdir(self.path_to_images):
            path_to_file = os.path.join(self.path_to_images, file)
            os.remove(path_to_file)
        self.assertTrue(not os.listdir(self.path_to_images))

    def test_official_names(self):
        self.assertEqual(len(self.unique_official_names), 340)

    def test_exact_files(self):
        self.assertEqual(
            self.unique_official_names, set(os.listdir(self.path_to_images))
        )
