from django.urls import path
from django_oapif.urls import oapif_router
from signalo_app.views import PoleViewset, SignViewset

from . import views

oapif_router.register(r"signs", SignViewset, "sign")
oapif_router.register(r"poles", PoleViewset, "pole")

urlpatterns = [
    path("", views.index, name="index"),
]
