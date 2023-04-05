# Generated by Django 4.1.7 on 2023-04-05 20:45

import uuid

import django.contrib.gis.db.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("signalo_edge_cases", "0003_differentsrid"),
    ]

    operations = [
        migrations.CreateModel(
            name="AllowAnyModel",
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
                    django.contrib.gis.db.models.fields.PointField(
                        srid=2154, verbose_name="Geometry"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="IsAdminUserModel",
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
                    django.contrib.gis.db.models.fields.PointField(
                        srid=2154, verbose_name="Geometry"
                    ),
                ),
            ],
        ),
    ]
