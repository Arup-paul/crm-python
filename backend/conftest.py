"""Fixtures shared by every app's tests. pytest finds this file by name; no import needed."""

from itertools import count

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User

PASSWORD = "test-pass-123"


@pytest.fixture(autouse=True)
def isolated_cache(settings):
    """Every test gets an empty in-memory cache: throttle counts never leak between tests or into dev Redis."""
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    cache.clear()


@pytest.fixture
def make_user(db):
    """make_user(role=..., **fields) → a saved User with password PASSWORD. Emails are unique per call."""
    numbers = count(1)

    def _make_user(role=User.Role.REP, **fields):
        n = next(numbers)
        fields.setdefault("email", f"user{n}@example.com")
        fields.setdefault("first_name", f"User{n}")
        return User.objects.create_user(password=PASSWORD, role=role, **fields)

    return _make_user


@pytest.fixture
def api_client():
    """An anonymous client: no token, no cookies."""
    return APIClient()


@pytest.fixture
def auth_client():
    """auth_client(user) → a new client that sends a real access token for that user."""

    def _auth_client(user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
        return client

    return _auth_client
