from django.contrib import admin
from django.urls import include, path

from .ogc import ogc_api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("oapif/", ogc_api.urls),
    path("__debug__/", include("debug_toolbar.urls")),
]
