from django.urls import path
from django_wfs3.urls import wfs3_router
from signalo_app.views import PoleViewset, SignViewset

from . import views

wfs3_router.register(r"signs", SignViewset, "sign")
wfs3_router.register(r"poles", PoleViewset, "pole")

urlpatterns = [
    path("", views.index, name="index"),
]
