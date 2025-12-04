from django.contrib.auth import get_permission_codename
from django.db import models


class QueryHandler:
    def __init__(self, model: models.Model):
        self.model = model
        self.opts = model._meta

    def get_queryset(self, request):
        return self.model._default_manager.get_queryset()

    def save_model(self, request, obj, change: bool):
        """
        Given a model instance save it to the database.
        """
        obj.save()

    def delete_model(self, request, obj):
        """
        Given a model instance delete it from the database.
        """
        obj.delete()

    def has_view_permission(self, request, obj=None):
        return True

    def has_add_permission(self, request, obj=None):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return True


class AllowAnyHandler(QueryHandler):
    pass


class AuthenticatedHandler(QueryHandler):
    """
    Allows access only to authenticated users.
    """

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_authenticated)

    def has_add_permission(self, request, obj=None):
        return bool(request.user and request.user.is_authenticated)

    def has_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_authenticated)

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_authenticated)


class AuthenticatedOrReadOnlyHandler(AuthenticatedHandler):
    """
    Allows access only to authenticated users.
    """

    def has_view_permission(self, request, obj=None):
        return True


class DjangoModelPermissionsHandler(QueryHandler):
    def has_view_permission(self, request, obj=None):
        codename = get_permission_codename("view", self.opts)
        return request.user.has_perm(f"{self.opts.app_label}.{codename}")

    def has_add_permission(self, request, obj=None):
        codename = get_permission_codename("add", self.opts)
        return request.user.has_perm(f"{self.opts.app_label}.{codename}")

    def has_change_permission(self, request, obj=None):
        codename = get_permission_codename("change", self.opts)
        return request.user.has_perm(f"{self.opts.app_label}.{codename}")

    def has_delete_permission(self, request, obj=None):
        codename = get_permission_codename("delete", self.opts)
        return request.user.has_perm(f"{self.opts.app_label}.{codename}")


class DjangoModelPermissionsOrAnonReadOnly(DjangoModelPermissionsHandler):
    def has_view_permission(self, request, obj=None):
        return True
