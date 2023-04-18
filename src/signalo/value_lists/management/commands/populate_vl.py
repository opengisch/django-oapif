import argparse
import json
import os

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.utils import IntegrityError

from ...models import OfficialSignType


class Command(BaseCommand):
    help = "Populate value lists"

    def add_arguments(self, parser):
        parser.add_argument("--clean", action=argparse.BooleanOptionalAction)
        parser.set_defaults(clean=False)

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clean"]:
            print("cleaning all types of signs")
            OfficialSignType.objects.all().delete()

        path_to_images = os.path.abspath(os.path.dirname(__file__))
        langs = {"img_de", "img_fr", "img_it", "img_ro"}
        saved_files = set()
        signs = []

        with open(f"{path_to_images}/../../data/official-signs.json") as csvfile:
            data = json.load(csvfile)

            for row in data:
                sign_instance = OfficialSignType(**row)
                sign_instance.img_fr = f"official_signs/{sign_instance.img_fr}"
                sign_instance.img_it = f"official_signs/{sign_instance.img_it}"
                sign_instance.img_ro = f"official_signs/{sign_instance.img_ro}"
                signs.append(sign_instance)

                lang_path = {k: v for k, v in row.items() if k in langs}
                for lang, path_to_img in lang_path.items():
                    if path_to_img not in saved_files:
                        with open(
                            f"{path_to_images}/../../data/images/official/original/{row[lang]}"
                        ) as fi:
                            data = fi.read()
                            getattr(sign_instance, lang).save(
                                row[lang], ContentFile(data)
                            )
                            saved_files.add(path_to_img)

        try:
            OfficialSignType.objects.bulk_create(signs, ignore_conflicts=True)
        except IntegrityError as e:
            print("you might need to clean the list of type of signs")
            raise IntegrityError(e)

        print(f"🚦 Added value lists for signs!")
