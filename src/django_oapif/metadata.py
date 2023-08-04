from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions, metadata
from rest_framework.request import clone_request


class OAPIFMetadata(metadata.SimpleMetadata):
    def determine_actions(self, request, view) -> dict:
        actions = {}
        for method in set(view.allowed_methods):
            view.request = clone_request(request, method)
            try:
                # Test global permissions
                if hasattr(view, "check_permissions"):
                    view.check_permissions(view.request)
                # Test object permissions
                if hasattr(view, "get_object") and method in {"PUT", "PATCH", "DELETE"}:
                    view.get_object()
            except (exceptions.APIException, PermissionDenied, Http404):
                pass
            else:
                serializer = view.get_serializer()
                actions[method] = self.get_serializer_info(serializer)
            finally:
                view.request = request

        return actions
