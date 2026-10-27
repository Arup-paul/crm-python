# Day 10 — Test setup + auth tests

## Today in one minute

- We installed **pytest** and **pytest-django**, and `docker compose exec web pytest` now runs our tests inside the container.
- **`pytest.ini`** tells pytest which Django settings to load.
- **`conftest.py`** holds three shared **fixtures**: `make_user`, `api_client`, `auth_client`.
- **10 tests** now check everything we built and tested by hand with curl on Days 8 and 9: login, `/me`, refresh through the cookie, rotation, logout.
- Result: **10 passed in 3.3 s**. From now on, one command tells us whether we broke auth.

---

## The big picture

On Days 8 and 9 we tested auth **by hand**: seven curl commands, reading every header. That works once. It doesn't work after every change for the next 800 days.

| By hand (curl) | Automatic (pytest) |
|---|---|
| ~5 minutes, and you have to remember every step | ~3 seconds, the same steps every time |
| You check the output with your eyes | `assert` checks it, and a mistake turns the test red |
| You test what you remember to test | Every old test runs again on every change |

> **Think of it like a smoke alarm.**
> You don't stand in the kitchen sniffing the air all day. You install an alarm once, and it shouts the moment something burns.
> A test is an alarm for one behaviour: "the refresh token must never be in the body". If anyone breaks that rule later, even by accident months from now, the test shouts.

How a run works:

```
docker compose exec web pytest
        │
        ├─ reads pytest.ini           → "this is Django, settings = config.settings"
        ├─ reads conftest.py          → fixtures: make_user, api_client, auth_client
        ├─ creates the database test_crm (or reuses it) and runs migrations
        ├─ finds files named test_*.py → accounts/tests/test_auth.py
        └─ runs each test_ function:
               start a transaction → run the test → ROLL BACK
               (so the next test starts with an empty database again)
```

---

## Part 1 — Installing pytest

[requirements.txt](../../backend/requirements.txt) got two lines:

```
pytest>=9.1,<9.2
pytest-django>=4.14,<4.15
```

| Package | In plain words |
|---|---|
| `pytest` | The test runner. It finds functions named `test_...` and runs them. A check is just `assert a == b`. |
| `pytest-django` | Teaches pytest about Django: loads the settings, creates a separate **test database**, and gives ready-made fixtures like `db`. |

A new package lives **in the image**, so (as on Day 7) it needs a rebuild, not a restart:

```bash
docker compose build web
docker compose up -d web
docker compose exec web pytest --version   # pytest 9.1.1
```

💡 Why not Django's built-in `TestCase`? It works too, but pytest's **fixtures** let us write "give me a logged-in client" once and reuse it everywhere. In DRF projects, pytest is the usual choice.

---

## Part 2 — `pytest.ini`

[backend/pytest.ini](../../backend/pytest.ini):

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = test_*.py
addopts = --reuse-db
```

| Line | In plain words | Why |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | Load `backend/config/settings.py` | `manage.py` does this for `runserver`. pytest doesn't go through `manage.py`, so we tell it here |
| `python_files` | Only files named `test_*.py` hold tests | One naming rule: see the name, know it's a test |
| `addopts = --reuse-db` | Add this flag to every run | Keep `test_crm` between runs instead of rebuilding it and re-running every migration each time |

### The test database

pytest-django **never touches our real database** (`crm`). It makes a second one, `test_crm`, and runs every test inside a **transaction** that's rolled back at the end.

> **Think of it like a whiteboard.** Each test writes on it, and when the test ends the board is wiped. A user made in one test doesn't exist in the next one.

| Situation | Command |
|---|---|
| Normal run | `pytest` (reuses `test_crm`, applies any new migrations) |
| Something feels stale or strange | `pytest --create-db` (builds `test_crm` from scratch) |

🐳 Creating a database needs the `CREATEDB` permission. The Postgres image makes `POSTGRES_USER` a superuser, so our `DB_USER` already has it.

We also added `.pytest_cache/` to [.gitignore](../../.gitignore). pytest stores "which tests failed last time" there, and because of the bind mount the folder appears on our laptop too.

### 🧪 Try it yourself

```bash
docker compose exec web pytest
```

Before any test existed, this printed `django: version: 5.2.18, settings: config.settings (from ini)` and `collected 0 items`, with **exit code 5**. That code means "no tests found", not an error. Exit code 0 means everything passed, and 1 means something failed.

---

## Part 3 — Fixtures in `conftest.py`

### What a fixture is

A fixture is something a test **needs ready before it starts**: a user, a client, a logged-in client.
You ask for it by **writing its name as a parameter**, and pytest builds it and passes it in:

```python
def test_something(make_user, api_client):   # pytest sees the names and supplies both
    ...
```

> **Think of it like a cook's prep station.** Before cooking, the onions are cut and the spices are measured. The test (the cooking) only does the interesting part.

`conftest.py` is a **special file name**. Fixtures in it are available to every test in that folder and below, **with no import**. Ours is at `backend/conftest.py`, so every app gets them.

### `make_user`: a factory

```python
@pytest.fixture
def make_user(db):
    numbers = count(1)

    def _make_user(role=User.Role.REP, **fields):
        n = next(numbers)
        fields.setdefault("email", f"user{n}@example.com")
        fields.setdefault("first_name", f"User{n}")
        return User.objects.create_user(password=PASSWORD, role=role, **fields)

    return _make_user
```

| Piece | Why |
|---|---|
| `db` parameter | pytest-django's own fixture: "this test may use the database". Without it, touching the database raises *"Database access not allowed"*, so it's always clear which tests use the database |
| Returns a **function**, not a user | One test may need an admin and two reps. The fixture hands over a user **maker** ("factory") |
| `count(1)` + `next()` | 1, 2, 3…, so the emails `user1@`, `user2@` never clash with Day 5's `unique=True` |
| `setdefault` | A test can pass its own email: `make_user(email="rahim@example.com")` |
| `create_user()` | Day 5's manager **hashes** the password. `User(password=...)` would store plain text, and login would never work |

```python
admin = make_user(role=User.Role.ADMIN)
rep = make_user()                         # role defaults to rep
```

### `api_client`

```python
@pytest.fixture
def api_client():
    return APIClient()
```

DRF's `APIClient` is a pretend browser. It sends requests **straight into Django** without a real server or network, so it's fast. Like a browser, it **remembers cookies**: after a login, the refresh cookie is sent with later requests by itself (what `curl -c`/`-b` did on Day 9).

### `auth_client(user)`

```python
@pytest.fixture
def auth_client():
    def _auth_client(user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
        return client

    return _auth_client
```

Two decisions:

| Decision | Why |
|---|---|
| A **real** JWT (`AccessToken.for_user`), not `force_authenticate()` | `force_authenticate()` skips authentication completely. A real token goes through the same JWT check as React's requests, so a broken JWT setup breaks the tests too. No call to `/login/`, so it's still fast |
| A **new** `APIClient()` every time | If it changed the `api_client` fixture instead, a test using both would have its "anonymous" client logged in too, and would test the wrong thing |

`client.credentials(...)` adds that header to **every** request the client makes.

---

## Part 4 — The tests

[accounts/tests/test_auth.py](../../backend/accounts/tests/test_auth.py). First, the folder:

```
backend/accounts/
├── tests.py          ← deleted (startapp's empty file)
└── tests/
    ├── __init__.py   ← empty; makes the folder a Python package
    └── test_auth.py
```

A folder because more test files are coming (`test_services.py`, `test_permissions.py`…). Python can't have `tests.py` **and** `tests/` side by side: both would be imported as `accounts.tests`.

### The shape of a test: Arrange → Act → Assert

```python
def test_login_returns_access_token_and_sets_refresh_cookie(api_client, make_user):
    response = login(api_client, make_user())          # arrange + act

    assert response.status_code == 200                 # assert
    assert "access" in response.data
    assert "refresh" not in response.data  # Day 9: never in the body
    cookie = response.cookies[COOKIE]
    assert cookie["httponly"]
    assert cookie["path"] == "/api/v1/auth/"
    assert cookie["samesite"] == "Lax"
```

A blank line separates the parts. The test name says the behaviour in plain words, so a red test tells you what broke before you open the file.

💡 The URLs are written as plain strings (`"/api/v1/auth/login/"`), not `reverse("accounts:login")`. React will call these **exact** URLs, so if someone changes one, a red test is what we want.

### What the 10 tests protect

| Test | Protects | From |
|---|---|---|
| `login_returns_access_token_and_sets_refresh_cookie` | Refresh only in an `HttpOnly`, `Lax` cookie on `/api/v1/auth/` | Day 9 |
| `login_with_wrong_password_fails` | 401, error code `no_active_account`, no cookie | Days 7–8 |
| `login_email_is_case_insensitive` | `Rahim@Example.COM` logs in as `rahim@example.com` | Day 5 |
| `me_needs_an_access_token` | No token → 401 `not_authenticated` | Day 8 |
| `me_returns_the_logged_in_user` | A real JWT works; `/me` returns email and role | Day 8 |
| `refresh_uses_the_cookie_and_rotates_it` | Refresh reads the cookie, sends a **new** cookie, nothing in the body | Day 9 |
| `refresh_without_a_cookie_fails` | 401, not SimpleJWT's confusing 400 | Day 9 |
| `old_refresh_token_is_rejected_after_rotation` | A stolen old token is useless → 401 `token_not_valid` | Days 8–9 |
| `logout_blacklists_the_token_and_clears_the_cookie` | 204, cookie emptied, the token no longer refreshes | Day 9 |
| `logout_without_a_cookie_still_succeeds` | Logout never fails (idempotent) | Day 9 |

### Replaying an old cookie

```python
api_client.cookies[COOKIE] = old_refresh  # an attacker replaying a stolen old token
response = api_client.post(REFRESH_URL)
```

`api_client.cookies` is a dict-like jar. Putting an old value back is how we pretend to be someone who copied the cookie earlier.

💡 We prove "blacklisted" by **behaviour** (the token no longer refreshes), not by looking inside the blacklist table. If the implementation changes later, the test still holds.

⚠️ The test client sends every cookie to every URL; it ignores `path`. So we check the cookie's `path` **attribute** in the login test. A real browser does respect it.

### 🧪 Try it yourself

```bash
docker compose exec web pytest -v              # every test's name and PASSED/FAILED
docker compose exec web pytest -k logout       # only tests with "logout" in the name
docker compose exec web pytest --lf            # only the tests that failed last time
docker compose exec web pytest --create-db     # rebuild test_crm from scratch
```

**Break it on purpose.** A test that can never fail is useless, so check that ours can:

1. In [views.py](../../backend/accounts/api/views.py), change `response.data.pop("refresh", None)` to `response.data.get("refresh")`. The refresh token now stays in the body.
2. Run `pytest`. The login and refresh tests turn red, each pointing at the line `assert "refresh" not in response.data`.
3. Change it back and confirm everything is green again.

### What we got

```
collected 10 items
...
============================== 10 passed in 3.29s ==============================
```

The order wasn't the file's order: pytest-django runs database tests first and the database-free ones (`me_needs_an_access_token`, `refresh_without_a_cookie_fails`, `logout_without_a_cookie_still_succeeds`) last. Tests must **never** depend on running in a certain order.

---

## Problems we hit

None today: all 10 passed on the first run. Things to know:

| Thing | What it means |
|---|---|
| `exit code: 5` with no tests | "No tests collected". Not an error |
| VS Code: "Package `Django` is not installed" | VS Code checks the laptop's Python. Our packages are in the Docker image. Ignore it |
| `tests.py` and `tests/` together | Python can't have both; we deleted the empty `tests.py` |

---

## New words

| Word | Meaning |
|---|---|
| **pytest** | The test runner: finds `test_` functions and runs them |
| **Fixture** | Something a test needs ready before it runs, requested by parameter name |
| **Factory fixture** | A fixture that returns a function for making things (`make_user(...)`) instead of one thing |
| **`conftest.py`** | A special file whose fixtures every test below it can use without importing |
| **Test database** | A separate database (`test_crm`) only tests use; the real data is never touched |
| **Rollback** | Undoing everything a transaction did; each test's changes are thrown away |
| **`assert`** | "This must be true". If it isn't, the test fails and shows the values |
| **Arrange / Act / Assert** | Set up, do the one thing, check the result |
| **`APIClient`** | DRF's pretend browser for tests; remembers cookies |
| **Regression** | Something that used to work and breaks after a change. Tests catch regressions |

---

## Files changed today

| File | What changed |
|---|---|
| [requirements.txt](../../backend/requirements.txt) | + `pytest`, `pytest-django` |
| [pytest.ini](../../backend/pytest.ini) | New: settings module, file pattern, `--reuse-db` |
| [conftest.py](../../backend/conftest.py) | New: `make_user`, `api_client`, `auth_client` |
| `accounts/tests.py` | Deleted (empty) |
| [accounts/tests/test_auth.py](../../backend/accounts/tests/test_auth.py) | New: 10 auth tests |
| [.gitignore](../../.gitignore) | + `.pytest_cache/` |

---

## Check yourself

<details>
<summary>1. Why do the tests never touch our real users in the <code>crm</code> database?</summary>

pytest-django creates a separate `test_crm` database, and each test runs in a transaction that's rolled back at the end.
</details>

<details>
<summary>2. What does the <code>db</code> parameter in <code>make_user(db)</code> do?</summary>

It's pytest-django's fixture that allows database access. Without it, any database query in the test raises "Database access not allowed".
</details>

<details>
<summary>3. Why does <code>make_user</code> return a function instead of a user?</summary>

So one test can make as many users as it needs, with different roles or emails. It's a factory.
</details>

<details>
<summary>4. Why does <code>auth_client</code> use a real JWT instead of <code>force_authenticate()</code>?</summary>

`force_authenticate()` skips authentication, so a broken JWT setup would go unnoticed. A real token goes through the same check as React's requests.
</details>

<details>
<summary>5. Why does pytest run the database-free tests last, and why must that not matter?</summary>

pytest-django orders database tests first. Each test must set up everything it needs itself, so it passes in any order or on its own (`pytest -k name`).
</details>
