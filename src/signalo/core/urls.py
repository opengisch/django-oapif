from django.urls import path

from django_oapif.urls import oapif_router

from . import views
from .views import PoleViewset, SignViewset

oapif_router.register(r"signs", SignViewset, "sign")
oapif_router.register(r"poles", PoleViewset, "pole")

urlpatterns = [
    path("", views.index, name="index"),
]
