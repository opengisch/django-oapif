from django.contrib import admin

from .models import HighlyPaginated, VariousGeom

admin.site.register(VariousGeom)
admin.site.register(HighlyPaginated)
