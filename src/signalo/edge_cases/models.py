import uuid

from django.contrib.gis.db import models
from rest_framework import permissions

from django_oapif.decorators import register_oapif_viewset

from .pagination import HighlyPaginatedPagination


@register_oapif_viewset()
class SimpleGeom(models.Model):
    """Represents a very basic model, if this doesnt work, nothing will."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.PointField()


@register_oapif_viewset()
class VariousGeom(models.Model):
    """Represents a model with mixed geometries (point, lines, polygons), as this is not always well supported yet very useful."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.GeometryField()


@register_oapif_viewset()
class EmptyTableGeom(models.Model):
    """Represents a model with a well defined geometry type (point) but without any data in it. Ideally QGIS should still recognize it as a point layer."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.PointField()


@register_oapif_viewset(
    custom_viewset_attrs={"pagination_class": HighlyPaginatedPagination}
)
class HighlyPaginated(models.Model):
    """The viewset of this model has very short pages (3 items or so), so we can test the impact of pagination on components like the attribute table."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.PointField()


@register_oapif_viewset()
class DifferentSrid(models.Model):
    """This model uses a different SRID from the others, allowing to check that this is properly managed by QGIS."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.PointField(srid=2154)


@register_oapif_viewset(
    custom_viewset_attrs={"permission_classes": (permissions.AllowAny,)}
)
class TestPermissionAllowAny(models.Model):
    """This model exemplifies the most permissive permission class (AllowAny)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.PointField()


@register_oapif_viewset()
class TestPermissionDefaultPermissionsSettings(models.Model):
    """This model exemplifies the 'DefaultPermissionsSettings' class."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.PointField()


@register_oapif_viewset(
    custom_viewset_attrs={"permission_classes": (permissions.IsAdminUser,)}
)
class TestPermissionIsAdminUserModel(models.Model):
    """This model exemplifies the 'IsAdminUserModel' class."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.PointField()
