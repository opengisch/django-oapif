import uuid
from typing import Union

from django.contrib.gis.db import models
from django.utils.translation import gettext as _

from django_oapif.decorators import register_oapif_viewset
from django_oapif.pagination import OapifPagination
from signalo.settings import GEOMETRY_SRID


class Limit1000(OapifPagination):
    default_limit = 100


@register_oapif_viewset(custom_viewset_attrs={"pagination_class": Limit1000})
class Road(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.MultiLineStringField(srid=GEOMETRY_SRID, verbose_name=_("Geometry"))

    def get_geom(self, geometry: str = "wkb") -> Union[memoryview, str]:
        if geometry == "wkb":
            return self.geom.wkb
        return self.geom.wkt
