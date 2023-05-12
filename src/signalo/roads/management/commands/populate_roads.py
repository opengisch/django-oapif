from os import path

from django.core.management.base import BaseCommand

from ...models import Road


class Command(BaseCommand):
    help = "Initialize db with testdata, roads"

    def handle(self, *args, **kwargs):
        roads_csv = path.relpath("./signalo/roads/data/roads.csv")
        with open(roads_csv, "r") as fh:
            next(fh)
            roads = []
            for line in fh:
                geom, _ = line.rsplit(",", 1)
                geom = geom.strip('""')
                roads.append(Road(geom=geom))

        Road.objects.bulk_create(roads)
        print(f"🛣️ Added roads!")
