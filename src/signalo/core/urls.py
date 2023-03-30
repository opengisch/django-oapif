from django.urls import path

from django_oapif.urls import oapif_router

from . import views

oapif_router.register(r"signs", views.SignViewset, "sign")
oapif_router.register(r"poles", views.PoleViewset, "pole")
oapif_router.register(r"poles_highperf", views.PoleHighPerfViewset, "poles_highperf")

urlpatterns = [
    path("", views.index, name="index"),
]
