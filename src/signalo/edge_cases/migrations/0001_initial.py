# Generated by Django 4.1.7 on 2023-03-30 21:43

import uuid

import django.contrib.gis.db.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="VariousGeom",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "geom",
                    django.contrib.gis.db.models.fields.GeometryField(
                        srid=2056, verbose_name="Geometry"
                    ),
                ),
            ],
        ),
    ]