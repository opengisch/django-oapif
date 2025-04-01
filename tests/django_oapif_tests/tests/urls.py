from django.contrib import admin
from django.urls import include, path
from ninja import NinjaAPI

from django_oapif.ninja_ogc import register_all_ogc_routes

ninja_api = NinjaAPI()

# Register all OGC routes from the global registry
register_all_ogc_routes(ninja_api)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("ninja/", ninja_api.urls),
    path("__debug__/", include("debug_toolbar.urls")),
]
