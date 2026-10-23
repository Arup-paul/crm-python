import logging

from django.conf import settings
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.serializers import as_serializer_error
from rest_framework.settings import api_settings
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    """Turn every API error into the ADR 005 shape: {"error": {"code", "message", "fields"?}}."""
    # Convert Django's exceptions to DRF's, so the code below only deals with one kind.
    if isinstance(exc, DjangoValidationError):  # raised by services
        exc = exceptions.ValidationError(as_serializer_error(exc))
    elif isinstance(exc, Http404):  # raised by get_object_or_404()
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = drf_exception_handler(exc, context)  # status code and headers

    if response is None:
        # Not an expected API error: a bug. In development, show Django's traceback page.
        if settings.DEBUG:
            return None
        logger.exception("Unhandled API error", exc_info=exc)
        return Response(
            {"error": {"code": "server_error", "message": "Something went wrong."}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, exceptions.ValidationError):
        fields = response.data
        if isinstance(fields, list):  # raise ValidationError("...") with no field name
            fields = {api_settings.NON_FIELD_ERRORS_KEY: fields}
        response.data = {
            "error": {"code": "validation_error", "message": "Some fields are invalid.", "fields": fields}
        }
    else:
        response.data = {"error": {"code": exc.detail.code, "message": str(exc.detail)}}
    return response
