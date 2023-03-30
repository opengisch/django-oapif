from django_oapif.urls import oapif_router

from . import views

oapif_router.register(r"various_geoms", views.VariousGeomViewset, "various_geom")
oapif_router.register(
    r"highly_paginateds", views.HighlyPaginatedViewset, "highly_paginated"
)


urlpatterns = []
