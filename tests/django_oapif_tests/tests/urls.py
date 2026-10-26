from django.contrib import admin
from django.urls import include, path

from .oapif import oapif

oapif_patterns, oapif_app_name, _ = oapif.urls

urlpatterns = [
    path("admin/", admin.site.urls),
    path("oapif/", oapif.urls),
    # the API again under a URL that takes an argument, as a site serving several views of its data would
    path("views/<str:view>/oapif/", include((oapif_patterns, oapif_app_name), namespace="oapif-view")),
    path("__debug__/", include("debug_toolbar.urls")),
]
