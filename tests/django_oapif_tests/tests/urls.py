from django.contrib import admin
from django.urls import include, path
from django_oapif.urls import oapif_router

urlpatterns = [
    path("admin/", admin.site.urls),
    path("oapif/", include(oapif_router.urls)),  # Django-rest urls
    path("__debug__/", include("debug_toolbar.urls")),  # Debug toolbar
]
