from django.contrib import admin
from django.urls import include, path

from .oapif import oapif

urlpatterns = [
    path("admin/", admin.site.urls),
    path("oapif/", oapif.urls),
    path("__debug__/", include("debug_toolbar.urls")),
]
