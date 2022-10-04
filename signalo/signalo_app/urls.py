from django_wfs3.urls import wfs3_router
from django.urls import path, include
from signalo_app.views import SignViewset, PoleViewset
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("wfs3/", include(wfs3_router.urls)),  # Django-rest urls
]


wfs3_router.register(r"signs", SignViewset, "sign")
wfs3_router.register(r"poles", PoleViewset, "pole")
