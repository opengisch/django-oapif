from os import path

from django.core.management.base import BaseCommand

from ...models import Road


class Command(BaseCommand):
    help = "Initialize db with testdata, roads"

    def handle(self, *args, **kwargs):
        roads_csv = path.relpath("./signalo/roads/data/roads.csv")
        roads = []
        with open(roads_csv, "r") as fh:
            next(fh)
            for line in fh:
                geom, _ = line.split(",", 1)
                road = Road(geom=bytes(geom, encoding="utf-8"))
                roads.append(road)
        Road.objects.bulk_create(roads)
        print(f"🛣️ Added roads!")
