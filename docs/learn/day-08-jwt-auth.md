# Day 8 — JWT login

## Today in one minute

- The API now has a **login**: send your email and password, get back two **tokens**.
- The React app will send the token with every request to prove who it is.
- **`/api/v1/auth/me/`** answers "who am I?", but only if you send a valid token.
- Not logged in now correctly answers **401** (yesterday it was 403).

---

## The big picture

> **Think of it like a gym.**
> You show your ID once at the front desk (**login** with email and password).
> They give you a **day pass** (the **access token**, valid 10 minutes) and a **membership card** (the **refresh token**, valid 7 days).
> You show the day pass at every door. When it runs out, you show the membership card to get a new day pass, without your ID again.

```
1. POST /api/v1/auth/login/   {"email": "...", "password": "..."}
                              ◀── {"access": "eyJ...", "refresh": "eyJ..."}

2. GET  /api/v1/auth/me/      Authorization: Bearer eyJ...(access)
                              ◀── {"id": 1, "email": "arup@gmail.com", "role": "admin", ...}
```

---

## Part 1 — The package

We added `djangorestframework-simplejwt` to [requirements.txt](../../backend/requirements.txt), then rebuilt (same as Day 7):

```bash
docker compose build web
docker compose up -d
```

`PyJWT` was installed too, automatically: SimpleJWT needs it, and pip installs what a package needs.

---

## Part 2 — The settings

In [settings.py](../../backend/config/settings.py):

| Setting | In plain words |
|---|---|
| Access token: **10 minutes** | The day pass. It's sent with every request, so if it leaks, it stops working soon. |
| Refresh token: **7 days** | The membership card. You stay logged in for a week. |
| **Rotation** | Every time you use the card, you get a **new** card |
| **Blacklist** | The old card goes on a "cancelled cards" list, so it can't be used again |
| **JWT first** | Logged out now gets **401** instead of 403 (see Day 7, Part 5) |
| Session login only in development | After logging in at `/admin/`, you can still click around the browsable API on your laptop |

The blacklist needs database tables, so we ran:

```bash
docker compose exec web python manage.py migrate
```

It applied 12 migrations. The package has existed since 2017, and its migrations are its history. A new database replays them all in order.

---

## Part 3 — What's inside a token?

A token looks like random letters, but it has **3 parts** separated by dots:

```
eyJhbGci...  .  eyJ0b2tlbl90eXBl...  .  xYz123...
   header          payload (data)        signature
```

The middle part decodes to:

```json
{"token_type": "access", "exp": 1792778475, "user_id": "1", "jti": "7c5c..."}
```

| Part | What it is | Can anyone read it? |
|---|---|---|
| Header | How it was signed | Yes |
| Payload | Who you are (`user_id`) and when it expires (`exp`) | **Yes!** |
| Signature | A stamp made with our `SECRET_KEY` | It can't be **faked** without the key |

> **Think of it like an ID card in a clear plastic sleeve with an official stamp.** Anyone can read it. But change your name, and the stamp no longer matches.

⚠️ **Rule:** never put secrets in a token (passwords, phone numbers). Anyone who has it can read it.
⚠️ **And:** keep `SECRET_KEY` secret. With it, anyone could make valid tokens.

---

## Part 4 — The login endpoint

**Address:** `POST /api/v1/auth/login/`

SimpleJWT already has a login view (`TokenObtainPairView`), so we only gave it an address. It knows to ask for **email** because our User says `USERNAME_FIELD = "email"` (Day 5).

| You send | You get |
|---|---|
| Correct email and password | ✅ `200` with `access` and `refresh` |
| `ARUP@Gmail.com` (capitals) | ✅ `200`, thanks to Day 5's lowercasing |
| Wrong password | ❌ `401` `no_active_account` |
| No password | ❌ `400` `validation_error`, `fields: {"password": [...]}` |

💡 The wrong-password message doesn't say whether the email or the password was wrong. That's on purpose: it stops strangers from checking which emails have accounts.

### How the addresses are organised

```
config/urls.py:         path('api/v1/auth/', include('accounts.api.urls'))
accounts/api/urls.py:   path("login/", ...)   path("me/", ...)
                        ─────────────────────────────────────────
Final address:          /api/v1/auth/login/    /api/v1/auth/me/
```

`include()` means each app keeps its own list of addresses, and the main `urls.py` has just one line per app.
It must sit **above** the Day 7 catch-all line.

---

## Part 5 — "Who am I?" and your first serializer

**Address:** `GET /api/v1/auth/me/` (needs a token)

**What's a serializer?** A **translator** from a Python object to JSON:

```
User object  ──MeSerializer──▶  {"id": 1, "email": "arup@gmail.com", "first_name": "Arup", "role": "admin"}
```

```python
class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role"]
```

⚠️ **Always list the fields. Never write `fields = "__all__"`.**
`__all__` would send the password hash and admin flags to the browser, and any new field added later would leak automatically.

**Notice what the view does *not* have:** no "login required" line. It's locked anyway, because login-required is the default (Day 7). Only public pages need to say so.

### 🧪 Try it yourself

```bash
# 1. Log in and copy the "access" value
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"arup@gmail.com","password":"12345678"}'

# 2. Ask "who am I?" (paste the token after Bearer)
curl http://localhost:8000/api/v1/auth/me/ -H "Authorization: Bearer PASTE_ACCESS_TOKEN_HERE"

# 3. Without a token, you should get 401
curl http://localhost:8000/api/v1/auth/me/
```

Wait 10 minutes and try step 2 again: the token has expired, so you get `token_not_valid`.

---

## Part 6 — Testing the bad tokens

| Token sent | Answer |
|---|---|
| None | `401` `not_authenticated` |
| Valid | `200`, your details |
| Junk (`hello123`) | `401` `token_not_valid` |
| **Changed** (`user_id` 1 → 2) | `401` `token_not_valid`, because the stamp didn't match |
| **Expired** | `401` `token_not_valid` |

**What React will do later:**
- `token_not_valid` → the day pass probably expired, so get a new one with the membership card (Day 9) and try again
- `not_authenticated` → nobody is logged in, so show the login page

---

## Problems we hit

| What happened | Why | Fix |
|---|---|---|
| Junk, changed and expired tokens crashed with **500** | Our Day 7 error handler expected every error to be one piece of text, but SimpleJWT's "token not valid" error is a **dict** | The handler now takes the text out of a dict-shaped error, and uses the default code if there isn't one |

**Lesson:** test the **bad** cases, not just the good ones. The happy path worked on the first try; the bug was only in the error paths.

---

## New words

| Word | Meaning |
|---|---|
| **Token** | A signed digital pass that proves who you are |
| **JWT** | JSON Web Token, the standard token format (header.payload.signature) |
| **Access token** | Short-lived pass sent with every request (10 min) |
| **Refresh token** | Long-lived pass used only to get new access tokens (7 days) |
| **Rotation** | Getting a new refresh token every time you use one |
| **Blacklist** | The list of cancelled refresh tokens |
| **Signature** | A stamp made with `SECRET_KEY`; any change to the token breaks it |
| **`Bearer`** | The word before the token in the `Authorization` header: "whoever bears (carries) this token" |
| **Serializer** | Translates Python objects to JSON (and back) |
| **`include()`** | Hands part of the URL list to an app's own `urls.py` |
| **Namespace** (`app_name`) | A surname for URL names: `accounts:login` |

---

## Files changed today

| File | What changed |
|---|---|
| [requirements.txt](../../backend/requirements.txt) | `djangorestframework-simplejwt` |
| [config/settings.py](../../backend/config/settings.py) | Blacklist app, `SIMPLE_JWT`, JWT as the first login method |
| [config/urls.py](../../backend/config/urls.py) | `api/v1/auth/` → the accounts app |
| [accounts/api/urls.py](../../backend/accounts/api/urls.py) | `login/` and `me/` (new) |
| [accounts/api/serializers.py](../../backend/accounts/api/serializers.py) | `MeSerializer` (new) |
| [accounts/api/views.py](../../backend/accounts/api/views.py) | The `me` view (new) |
| [core/exceptions.py](../../backend/core/exceptions.py) | Fixed the crash on dict-shaped errors |

---

## Check yourself

<details>
<summary>1. Why is the access token short (10 minutes) but the refresh token long (7 days)?</summary>

The access token is sent with every request, so it's the one most likely to leak. If it does, it stops working soon. The refresh token is used rarely, only to get new access tokens, so you stay logged in for a week.
</details>

<details>
<summary>2. Anyone can read a token's payload. So why can't someone change <code>user_id</code> to become another user?</summary>

The signature was made from the original payload with `SECRET_KEY`. Any change breaks it, and without the key nobody can make a new valid one.
</details>

<details>
<summary>3. Why must a serializer list its fields instead of using <code>"__all__"</code>?</summary>

`__all__` sends every field, including the password hash and admin flags, and any new field would leak automatically. A list sends only what you chose.
</details>

<details>
<summary>4. The <code>me</code> view has no permission line. Why is it still locked?</summary>

The project default is `IsAuthenticated` (Day 7). Every API page needs login unless it says `AllowAny`.
</details>
