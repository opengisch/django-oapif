from typing import Any

from django.conf import settings
from django.contrib.auth import authenticate
from django.http import HttpRequest
from ninja.security import APIKeyCookie, HttpBasicAuth


class BasicAuth(HttpBasicAuth):
    def authenticate(self, request: HttpRequest, username: str, password: str) -> Any | None:
        if user := authenticate(request, username=username, password=password):
            request.user = user
        return request.user


class DjangoAuth(APIKeyCookie):
    param_name: str = settings.SESSION_COOKIE_NAME

    def authenticate(self, request: HttpRequest, key: str | None) -> Any | None:
        return request.user
