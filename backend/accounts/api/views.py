from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import MeSerializer


def _move_refresh_to_cookie(response):
    """Take the refresh token out of the JSON body and put it in the HttpOnly cookie."""
    refresh = response.data.pop("refresh", None)
    if refresh:
        response.set_cookie(settings.REFRESH_COOKIE_NAME, refresh, **settings.REFRESH_COOKIE)


class LoginView(TokenObtainPairView):
    """Email + password in. Access token in the body, refresh token in a cookie."""

    throttle_scope = "login"  # 5 tries a minute per IP (settings.DEFAULT_THROTTLE_RATES)

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        _move_refresh_to_cookie(response)
        return response


class RefreshView(TokenRefreshView):
    """Refresh cookie in. New access token in the body, rotated refresh token in the cookie."""

    def get_serializer(self, *args, **kwargs):
        # simplejwt reads {"refresh": ...} from the body; we hand it the cookie instead.
        kwargs["data"] = {"refresh": self.request.COOKIES[settings.REFRESH_COOKIE_NAME]}
        return super().get_serializer(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        if settings.REFRESH_COOKIE_NAME not in request.COOKIES:
            raise NotAuthenticated("No refresh cookie. Log in again.")
        response = super().post(request, *args, **kwargs)
        _move_refresh_to_cookie(response)
        return response


class LogoutView(APIView):
    """Blacklist the refresh token and delete the cookie. Safe to call when already logged out."""

    authentication_classes = []  # an expired access token must not block logout
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if token:
            try:
                RefreshToken(token).blacklist()
            except TokenError:
                pass  # already expired or blacklisted: nothing left to revoke
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(
            settings.REFRESH_COOKIE_NAME,
            path=settings.REFRESH_COOKIE["path"],
            samesite=settings.REFRESH_COOKIE["samesite"],
        )
        return response


@api_view(["GET"])
def me(request):
    """Who am I? Needs a valid access token (the project default, IsAuthenticated)."""
    return Response(MeSerializer(request.user).data)
