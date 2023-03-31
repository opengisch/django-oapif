from django.contrib import admin

from .models import DifferentSrid, HighlyPaginated, VariousGeom

admin.site.register(VariousGeom)
admin.site.register(HighlyPaginated)
admin.site.register(DifferentSrid)
