# Day 9 — Auth for a browser app

## Today in one minute

- Login still gives the **access token** in the response body, but the **refresh token** now goes into a **cookie** that JavaScript can't read.
- New **`/api/v1/auth/refresh/`**: the browser sends the cookie and gets a new access token (and a new cookie).
- New **`/api/v1/auth/logout/`**: cancels the refresh token and deletes the cookie.
- The refresh token **never** appears in a response body any more.

---

## The big picture

Yesterday's login gave the browser two tokens in the body. The React app would need somewhere to keep them. Where?

| Where | Problem |
|---|---|
| `localStorage` | Any JavaScript on the page can read it. One XSS bug (someone else's script running on our page) and the 7-day refresh token is stolen. |
| An **`HttpOnly` cookie** | The browser keeps it and sends it by itself, but **JavaScript can't read it**. An XSS bug can't steal it. |

> **Think of it like a bank locker.**
> The access token is the **cinema ticket in your pocket**: valid 10 minutes, not a big loss if dropped.
> The refresh token is the **locker key**: the bank (the browser) keeps it for you. You (JavaScript) never hold it. When you go to the counter (`/api/v1/auth/`), the bank shows the key for you.

```
1. POST /api/v1/auth/login/     {"email": "...", "password": "..."}
                                ◀── body:   {"access": "eyJ..."}
                                ◀── header: Set-Cookie: refresh_token=eyJ...; HttpOnly; Path=/api/v1/auth/; SameSite=Lax

2. GET  /api/v1/leads/          Authorization: Bearer eyJ...(access)      ← cookie NOT sent here

3. (10 minutes later, access expired)
   POST /api/v1/auth/refresh/   Cookie: refresh_token=eyJ...              ← browser adds it by itself
                                ◀── body:   {"access": "eyJ...new"}
                                ◀── header: Set-Cookie: refresh_token=eyJ...new; ...

4. POST /api/v1/auth/logout/    Cookie: refresh_token=eyJ...
                                ◀── 204, Set-Cookie: refresh_token=""; Max-Age=0
```

The access token lives only in React's memory (a variable). After a page reload it's gone, so React calls `/refresh/` once on start to get a fresh one.

---

## Part 1 — The cookie settings

In [settings.py](../../backend/config/settings.py), under `SIMPLE_JWT`:

```python
REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE = {  # passed straight to response.set_cookie()
    "max_age": int(SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
    "path": "/api/v1/auth/",
    "httponly": True,
    "secure": not DEBUG,
    "samesite": "Lax",
}
```

| Flag | In plain words | Why |
|---|---|---|
| `max_age` | The cookie lives 604800 seconds (7 days) | Same as the refresh token, so they expire together |
| `path` | The browser sends it **only** to `/api/v1/auth/...` | It doesn't travel with every leads or deals request, so fewer chances to leak |
| `httponly` | `document.cookie` can't see it | The main idea of today: XSS can't steal it |
| `secure` | Sent only over HTTPS | On in production. Off on our laptop, because `localhost` is plain `http` |
| `samesite` | `Lax`: another website's POST won't carry the cookie | Stops CSRF: an evil site can't make your browser call `/refresh/` or `/logout/` |

💡 The dict's keys have the same names as `set_cookie()`'s arguments, so the view just writes `**settings.REFRESH_COOKIE`.

---

## Part 2 — The views

All in [accounts/api/views.py](../../backend/accounts/api/views.py). SimpleJWT's views already check passwords, make tokens and answer 401 for bad tokens. We **inherit** them and only add the cookie part.

### The helper

```python
def _move_refresh_to_cookie(response):
    refresh = response.data.pop("refresh", None)
    if refresh:
        response.set_cookie(settings.REFRESH_COOKIE_NAME, refresh, **settings.REFRESH_COOKIE)
```

`pop()` removes `refresh` from the body and gives it back, then `set_cookie()` adds the `Set-Cookie` header.
It works because a DRF `Response` isn't turned into JSON until **after** the view returns, so `response.data` is still a normal dict.

### `LoginView`

```python
class LoginView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        _move_refresh_to_cookie(response)
        return response
```

`super().post()` runs SimpleJWT's login. On a wrong password it **raises** an error, so the next line never runs: no cookie on a failed login.

### `RefreshView`

```python
class RefreshView(TokenRefreshView):
    def get_serializer(self, *args, **kwargs):
        kwargs["data"] = {"refresh": self.request.COOKIES[settings.REFRESH_COOKIE_NAME]}
        return super().get_serializer(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        if settings.REFRESH_COOKIE_NAME not in request.COOKIES:
            raise NotAuthenticated("No refresh cookie. Log in again.")
        ...
```

- SimpleJWT's `post()` calls `self.get_serializer(data=request.data)`, so it reads the token from the **body**. Overriding `get_serializer` swaps the body for the **cookie**. All of SimpleJWT's checks (signature, expiry, blacklist) still run.
- `HttpOnly` hides the cookie from JavaScript, **not** from the server: Django reads it from `request.COOKIES`.
- No cookie → a clear **401** instead of SimpleJWT's confusing 400 "field may not be blank". For React, 401 means "show the login page".
- **Rotation** (Day 8 settings): every refresh returns a **new** refresh token and blacklists the old one, and the helper puts the new one in the cookie.

> **Think of it like a hotel key card** that the front desk re-codes every time you ask for a new one. Your old card stops opening the door.

### `LogoutView`

```python
class LogoutView(APIView):
    authentication_classes = []  # an expired access token must not block logout
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if token:
            try:
                RefreshToken(token).blacklist()
            except TokenError:
                pass
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(settings.REFRESH_COOKIE_NAME, path=..., samesite=...)
        return response
```

| Line | Why |
|---|---|
| `authentication_classes = []` + `AllowAny` | The project default needs an access token (Day 7). After 30 minutes the access token has expired, and logout would answer 401: the user **couldn't log out**. The cookie is enough. |
| `.blacklist()` | Writes the token into the blacklist table. A copied cookie now fails at `/refresh/`. |
| `except TokenError: pass` | Already expired or blacklisted means nothing is left to cancel |
| Always `204` | Logout never fails. Calling it twice gives the same result (**idempotent**), so the Logout button never shows an error. |
| `delete_cookie(..., path=...)` | The **same `path`** as when it was set, or the browser treats it as a different cookie and keeps the old one |

💡 HTTP has no "delete cookie" command. The server sends the cookie again with an empty value and an expiry in **1970**; the browser sees it's long expired and throws it away.

---

## Part 3 — The URLs

[accounts/api/urls.py](../../backend/accounts/api/urls.py):

```python
path("login/", views.LoginView.as_view(), name="login"),
path("refresh/", views.RefreshView.as_view(), name="refresh"),
path("logout/", views.LogoutView.as_view(), name="logout"),
path("me/", views.me, name="me"),
```

`.as_view()` turns a class-based view into the function Django's URLs expect. `me` is already a function (`@api_view`), so it doesn't need it.
All four live under `/api/v1/auth/`, the cookie's `path`, so all four receive the cookie, and no other API does.

---

## Part 4 — Testing with curl

A browser stores and sends cookies by itself. curl needs to be told:

| Flag | Meaning |
|---|---|
| `-i` | Show the response headers too (to see `Set-Cookie`) |
| `-c jar.txt` | **Save** cookies the server sends into `jar.txt` |
| `-b jar.txt` | **Send** the cookies in `jar.txt` |

### 🧪 Try it yourself

```bash
# 1. Login: body has only "access"; look for the Set-Cookie header
curl -i -c jar.txt -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"arup@gmail.com","password":"12345678"}'

# 2. Keep a copy of this cookie, then refresh (the jar gets the new cookie)
cp jar.txt old.txt
curl -i -b jar.txt -c jar.txt -X POST http://localhost:8000/api/v1/auth/refresh/

# 3. The OLD cookie is blacklisted now → 401
curl -i -b old.txt -X POST http://localhost:8000/api/v1/auth/refresh/

# 4. Logout → 204, and the cookie is deleted
curl -i -b jar.txt -c jar.txt -X POST http://localhost:8000/api/v1/auth/logout/

# 5. No cookie at all → 401 "No refresh cookie"
curl -i -X POST http://localhost:8000/api/v1/auth/refresh/

rm jar.txt old.txt
```

### What we got

| # | Test | Answer |
|---|---|---|
| 1 | Login | ✅ `200`, body `{"access": ...}`, cookie `HttpOnly; Max-Age=604800; Path=/api/v1/auth/; SameSite=Lax` |
| 2 | Refresh with the cookie | ✅ `200`, new access token, **new** cookie |
| 3 | Refresh with the old cookie | ✅ `401` `token_not_valid` "Token is blacklisted" |
| 4 | Logout | ✅ `204`, `Set-Cookie: refresh_token=""; Max-Age=0` |
| 5 | Refresh with the cookie from before logout | ✅ `401` "Token is blacklisted" |
| 6 | Refresh with no cookie | ✅ `401` `not_authenticated` "No refresh cookie. Log in again." |
| + | Logout again, already logged out | ✅ `204` |

All errors came back in the Day 7 error shape `{"error": {"code", "message"}}`.

---

## Problems we hit

None today: every test passed on the first run. Two traps we avoided on purpose:

| Trap | What would have happened |
|---|---|
| Logout requiring an access token | Users with an expired access token couldn't log out |
| `delete_cookie()` without the `path` | The browser would keep the cookie, so "logged out" users would still be logged in after a refresh |

---

## New words

| Word | Meaning |
|---|---|
| **Cookie** | A small value the server asks the browser to keep and send back automatically |
| **`Set-Cookie`** | The response header that creates (or deletes) a cookie |
| **`HttpOnly`** | JavaScript can't read the cookie; only the server sees it |
| **`Secure`** | The cookie is only sent over HTTPS |
| **`SameSite=Lax`** | Another website's POST doesn't carry the cookie |
| **`path`** | The cookie is only sent to URLs starting with this |
| **XSS** | Cross-site scripting: someone else's JavaScript running on our page |
| **CSRF** | Cross-site request forgery: another site making your browser send a request to ours |
| **`super()`** | "Run the parent class's version of this method" |
| **Override** | Writing a method with the same name in a subclass to change what it does |
| **Idempotent** | Doing it twice gives the same result as doing it once |

---

## Files changed today

| File | What changed |
|---|---|
| [config/settings.py](../../backend/config/settings.py) | `REFRESH_COOKIE_NAME` and `REFRESH_COOKIE` |
| [accounts/api/views.py](../../backend/accounts/api/views.py) | `LoginView`, `RefreshView`, `LogoutView` (new) |
| [accounts/api/urls.py](../../backend/accounts/api/urls.py) | `login/` uses our view; `refresh/` and `logout/` (new) |

---

## Check yourself

<details>
<summary>1. Why not keep the refresh token in <code>localStorage</code>?</summary>

Any JavaScript on the page can read `localStorage`. One XSS bug and a 7-day token is stolen. An `HttpOnly` cookie can't be read by JavaScript at all.
</details>

<details>
<summary>2. The cookie is <code>HttpOnly</code>. How does the server still read it?</summary>

`HttpOnly` only hides it from JavaScript. The browser still sends it with requests, and Django reads it from `request.COOKIES`.
</details>

<details>
<summary>3. What would go wrong if the cookie's <code>path</code> were <code>/</code>?</summary>

The refresh token would travel with every request to the site (leads, deals, static files), giving it many more chances to leak through logs or bugs. It's only needed by the auth endpoints.
</details>

<details>
<summary>4. Why does <code>LogoutView</code> set <code>authentication_classes = []</code>?</summary>

With the default (access token required), a user whose 10-minute access token had expired would get 401 and couldn't log out. Logout only needs the cookie.
</details>

<details>
<summary>5. After a refresh, why does the old refresh cookie stop working?</summary>

Rotation plus blacklisting (Day 8 settings): each refresh gives a new refresh token and puts the old one on the blacklist.
</details>
