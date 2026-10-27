"""Auth API: login, refresh via the HttpOnly cookie, /me, logout (Days 8–9)."""

from django.conf import settings

from conftest import PASSWORD

LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/refresh/"
LOGOUT_URL = "/api/v1/auth/logout/"
ME_URL = "/api/v1/auth/me/"
COOKIE = settings.REFRESH_COOKIE_NAME


def login(client, user, password=PASSWORD):
    return client.post(LOGIN_URL, {"email": user.email, "password": password}, format="json")


# --- login ---


def test_login_returns_access_token_and_sets_refresh_cookie(api_client, make_user):
    response = login(api_client, make_user())

    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" not in response.data  # Day 9: never in the body
    cookie = response.cookies[COOKIE]
    assert cookie["httponly"]
    assert cookie["path"] == "/api/v1/auth/"
    assert cookie["samesite"] == "Lax"


def test_login_with_wrong_password_fails(api_client, make_user):
    response = login(api_client, make_user(), password="wrong-password")

    assert response.status_code == 401
    assert response.data["error"]["code"] == "no_active_account"
    assert COOKIE not in response.cookies


def test_login_email_is_case_insensitive(api_client, make_user):
    make_user(email="rahim@example.com")

    response = api_client.post(LOGIN_URL, {"email": "Rahim@Example.COM", "password": PASSWORD}, format="json")

    assert response.status_code == 200


# --- /me ---


def test_me_needs_an_access_token(api_client):
    response = api_client.get(ME_URL)

    assert response.status_code == 401
    assert response.data["error"]["code"] == "not_authenticated"


def test_me_returns_the_logged_in_user(auth_client, make_user):
    user = make_user(role="manager")

    response = auth_client(user).get(ME_URL)

    assert response.status_code == 200
    assert response.data["email"] == user.email
    assert response.data["role"] == "manager"


# --- refresh ---


def test_refresh_uses_the_cookie_and_rotates_it(api_client, make_user):
    login(api_client, make_user())  # the client keeps the cookie, like a browser
    old_refresh = api_client.cookies[COOKIE].value

    response = api_client.post(REFRESH_URL)

    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" not in response.data
    assert response.cookies[COOKIE].value != old_refresh


def test_refresh_without_a_cookie_fails(api_client):
    response = api_client.post(REFRESH_URL)

    assert response.status_code == 401
    assert response.data["error"]["code"] == "not_authenticated"


def test_old_refresh_token_is_rejected_after_rotation(api_client, make_user):
    login(api_client, make_user())
    old_refresh = api_client.cookies[COOKIE].value
    api_client.post(REFRESH_URL)  # rotates: old token goes on the blacklist

    api_client.cookies[COOKIE] = old_refresh  # an attacker replaying a stolen old token
    response = api_client.post(REFRESH_URL)

    assert response.status_code == 401
    assert response.data["error"]["code"] == "token_not_valid"


# --- logout ---


def test_logout_blacklists_the_token_and_clears_the_cookie(api_client, make_user):
    login(api_client, make_user())
    refresh = api_client.cookies[COOKIE].value

    response = api_client.post(LOGOUT_URL)

    assert response.status_code == 204
    assert response.cookies[COOKIE].value == ""  # Set-Cookie with an empty value and max-age=0
    api_client.cookies[COOKIE] = refresh  # try to use the token after logout
    assert api_client.post(REFRESH_URL).status_code == 401


def test_logout_without_a_cookie_still_succeeds(api_client):
    assert api_client.post(LOGOUT_URL).status_code == 204


# --- throttling (Day 11) ---


def test_login_is_throttled_after_5_tries_a_minute(api_client, make_user):
    user = make_user()
    for _ in range(5):
        assert login(api_client, user, password="wrong-password").status_code == 401

    response = login(api_client, user)  # even the right password is refused now

    assert response.status_code == 429
    assert response.data["error"]["code"] == "throttled"
    assert "Retry-After" in response.headers
