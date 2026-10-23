import redis
from django.conf import settings
from django.db import DatabaseError, connection
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def health(request):
    """Public check for monitoring: 200 if Postgres and Redis both answer, 503 if not."""
    checks = {"db": _check_db(), "redis": _check_redis()}
    healthy = all(result == "ok" for result in checks.values())
    return Response(checks, status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(["GET", "POST", "PUT", "PATCH", "DELETE"])
@authentication_classes([])
@permission_classes([AllowAny])
def api_not_found(request, *args, **kwargs):
    """The last API route: unknown /api/ URLs get a JSON 404, not Django's HTML page."""
    raise NotFound()


def _check_db():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return "ok"
    except DatabaseError:
        return "error"


def _check_redis():
    try:
        with redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1) as client:
            client.ping()
        return "ok"
    except redis.RedisError:
        return "error"
