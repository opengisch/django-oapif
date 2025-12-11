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
        return True

    def has_add_permission(self, _request: HttpRequest, _obj: M | None = None) -> bool:
        return True

    def has_change_permission(self, _request: HttpRequest, _obj: M | None = None) -> bool:
        return True

    def has_delete_permission(self, _request: HttpRequest, _obj: M | None = None) -> bool:
        return True


class AllowAnyHandler(QueryHandler):
    pass


class AuthenticatedHandler[M: Model](QueryHandler):
    """Allows access only to authenticated users."""

    def has_view_permission(self, request: HttpRequest, _obj: M | None = None) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_add_permission(self, request: HttpRequest, _obj: M | None = None) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_change_permission(self, request: HttpRequest, _obj: M | None = None) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_delete_permission(self, request: HttpRequest, _obj: M | None = None) -> bool:
        return bool(request.user and request.user.is_authenticated)


class AuthenticatedOrReadOnlyHandler[M: Model](AuthenticatedHandler):
    """Allows access only to authenticated users."""

    def has_view_permission(self, _request: HttpRequest, _obj: M | None = None) -> bool:
        return True


class DjangoModelPermissionsHandler[M: Model](QueryHandler):
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


class DjangoModelPermissionsOrAnonReadOnly[M: Model](DjangoModelPermissionsHandler):
    def has_view_permission(self, _request: HttpRequest, _obj: M | None = None) -> bool:
        return True
