from django.contrib.auth import get_permission_codename
from django.db.models import Model, QuerySet
from django.http import HttpRequest


class QueryHandler[M: Model]:
    def __init__(self, model: type[M]) -> None:
        self.model = model
        self.opts = model._meta

    def get_queryset(self, _request: HttpRequest) -> QuerySet[M]:
        return self.model._default_manager.get_queryset()

    def save_model(self, _request: HttpRequest, obj: M, _change: bool) -> None:
        """Given a model instance save it to the database."""
        obj.save()

    def delete_model(self, _request: HttpRequest, obj: M) -> tuple[int, dict[str, int]]:
        """Given a model instance delete it from the database."""
        return obj.delete()

    def has_view_permission(self, _request: HttpRequest, _obj: M | None = None) -> bool:
        """Returns True if the given request has permission to view objects in the collection,
        or a given object if defined.
        """
        return True

    def has_add_permission(self, _request: HttpRequest, _obj: M | None = None) -> bool:
        """Returns True if the given request has permission to create objects in the collection,
        or a given object if defined.
        """
        return True

    def has_change_permission(self, _request: HttpRequest, _obj: M | None = None) -> bool:
        """Returns True if the given request has permission to change objects in the collection,
        or a given object if defined.
        """
        return True

    def has_delete_permission(self, _request: HttpRequest, _obj: M | None = None) -> bool:
        """Returns True if the given request has permission to delete objects in the collection,
        or a given object if defined.
        """
        return True


class AllowAny(QueryHandler):
    """Allows full access to everyone."""

    pass


class IsAuthenticated[M: Model](QueryHandler):
    """Allows full access to authenticated users only."""

    def has_view_permission(self, request: HttpRequest, _obj: M | None = None) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_add_permission(self, request: HttpRequest, _obj: M | None = None) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_change_permission(self, request: HttpRequest, _obj: M | None = None) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_delete_permission(self, request: HttpRequest, _obj: M | None = None) -> bool:
        return bool(request.user and request.user.is_authenticated)


class IsAuthenticatedOrReadOnly[M: Model](IsAuthenticated):
    """Allows full access to authenticated users only, but allows readonly access to everyone."""

    def has_view_permission(self, _request: HttpRequest, _obj: M | None = None) -> bool:
        return True


class DjangoModelPermissions[M: Model](QueryHandler):
    """Reuses all Django permissions for a given model."""

    def has_view_permission(self, request: HttpRequest, _obj: M | None = None) -> bool:
        codename = get_permission_codename("view", self.opts)
        return request.user.has_perm(f"{self.opts.app_label}.{codename}")

    def has_add_permission(self, request: HttpRequest, _obj: M | None = None) -> bool:
        codename = get_permission_codename("add", self.opts)
        return request.user.has_perm(f"{self.opts.app_label}.{codename}")

    def has_change_permission(self, request: HttpRequest, _obj: M | None = None) -> bool:
        codename = get_permission_codename("change", self.opts)
        return request.user.has_perm(f"{self.opts.app_label}.{codename}")

    def has_delete_permission(self, request: HttpRequest, _obj: M | None = None) -> bool:
        codename = get_permission_codename("delete", self.opts)
        return request.user.has_perm(f"{self.opts.app_label}.{codename}")


class DjangoModelPermissionsOrAnonReadOnly[M: Model](DjangoModelPermissions):
    """Reuses all Django permissions for a given model, but allows readonly access to everyone."""

    def has_view_permission(self, _request: HttpRequest, _obj: M | None = None) -> bool:
        return True
