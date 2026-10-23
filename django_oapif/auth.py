from typing import Any

from django.conf import settings
from django.contrib.auth import authenticate
from django.http import HttpRequest
from ninja.security import APIKeyCookie, HttpBasicAuth


class BasicAuth(HttpBasicAuth):
    """HTTP Basic authentication, checked against the authentication backends of Django."""

    def authenticate(self, request: HttpRequest, username: str, password: str) -> Any | None:
        if user := authenticate(request, username=username, password=password):
            request.user = user
        return request.user


class DjangoAuth(APIKeyCookie):
    """The user of the Django session, or the anonymous user without one."""

    param_name: str = settings.SESSION_COOKIE_NAME

    def __call__(self, request: HttpRequest) -> Any | None:
        # The CSRF token guards the writes of a session: an anonymous request has none to forge. It was refused for
        # want of the token, even by a collection that lets anyone write.
        if not request.user.is_authenticated:
            return request.user
        return super().__call__(request)

    def authenticate(self, request: HttpRequest, key: str | None) -> Any | None:
        return request.user
