# Day 11 — Redis cache & login throttling

## Today in one minute

- Django's **cache** now lives in **Redis DB 1**. DB 0 is kept for Celery's job queue (Slice 4).
- **Login is throttled**: 5 tries a minute per IP. The 6th try gets **429 Too Many Requests**, a `Retry-After` header and our usual error shape.
- The throttle **broke our tests**: login counts stayed in Redis from one test to the next. An `autouse` fixture now gives every test its own empty cache.
- **11 tests pass**, the same on every run, and the tests never touch the dev Redis.
- Phase 1 (backend foundation, Days 1–11) is done 🎉

---

## The big picture

Without a limit, a script can try thousands of passwords a minute against `/login/` (**brute force**). A throttle counts the tries and says "wait" after too many.

> **Think of it like an ATM.**
> Get the PIN wrong too many times and the machine keeps your card for a while. A real person rarely needs more than 5 tries; a script trying 100,000 passwords would now need about 20,000 minutes (two weeks).

To count, DRF needs somewhere to keep "this IP tried at 10:00:01, 10:00:07, …". That somewhere is Django's **cache**, and we put the cache in **Redis** so every web process shares the same count.

```
POST /api/v1/auth/login/   (from IP 172.20.0.1)
        │
        ├─ ScopedRateThrottle: this view's throttle_scope is "login" → rate "5/min"
        ├─ cache key: throttle_login_172.20.0.1   (stored in Redis DB 1)
        ├─ read the list of this IP's request times from the last 60 seconds
        │      ├─ 5 or more?  → 429 + Retry-After   (the view never runs)
        │      └─ fewer?      → add "now" to the list, save it (TTL 60 s) → run the view
        ▼
   LoginView checks the password (401 or 200)
```

---

## Part 1 — The cache in Redis DB 1

### What a cache is

A cache keeps the answer to a question for a while, so you don't have to look it up again.

> **Think of it like a sticky note on your desk.** Instead of walking to the filing cabinet (Postgres) every time, you write the answer on a note. Each note has an expiry time, then it's thrown away.

Django gives one simple API for it, whatever the storage behind it:

```python
from django.core.cache import cache

cache.set("hello", "from django", timeout=60)   # keep for 60 seconds
cache.get("hello")                              # "from django" (or None after 60 s)
```

### Redis DB numbers

One Redis server has **16 separate "databases"** (numbered 0–15). The number at the end of the URL picks one: `redis://redis:6379/1` is DB 1.

| DB | Used by | Why separate |
|---|---|---|
| 0 | Health check now; **Celery** later (Slice 4) | It will hold queued jobs, like "send this email" |
| 1 | **Django cache** (and so throttle counts) | A cache can be wiped at any time: `cache.clear()` runs `FLUSHDB` |

If both shared DB 0, clearing the cache would also delete every waiting background job.

### The settings

Your `.env` (never committed) and [.env.example](../../.env.example) got one line:

```
REDIS_CACHE_URL=redis://redis:6379/1
```

[settings.py](../../backend/config/settings.py):

```python
# Redis DB 0: health check now, Celery later (Slice 4).
REDIS_URL = os.environ["REDIS_URL"]

# Cache (Day 11): Redis DB 1, so clearing the cache never touches Celery's queue in DB 0.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ["REDIS_CACHE_URL"],
    }
}
```

| Piece | Why |
|---|---|
| `CACHES["default"]` | What `from django.core.cache import cache` gives you. DRF's throttles use it too |
| `RedisCache` | Built into Django since 4.0; it uses the `redis` package we added on Day 7. No `django-redis` needed |
| `os.environ[...]`, not `.get()` | If the variable is missing, Django refuses to start with a clear error instead of quietly using the wrong place |
| Why not keep the default? | With no `CACHES`, Django uses **LocMemCache**: each process's own memory. With 4 web processes in production, each would count separately, so an attacker would get 4 × 5 tries |

🐳 `.env` is read when a container is **created**. After changing it, `docker compose restart web` keeps the old values; `docker compose up -d web` notices the change and recreates the container. No rebuild needed, because no package changed.

### 🧪 Try it yourself

```bash
docker compose exec web python manage.py shell -c "
from django.core.cache import cache
cache.set('hello', 'from django', timeout=60)
print(cache.get('hello'))
"
docker compose exec redis redis-cli -n 1 KEYS '*'          # :1:hello
docker compose exec redis redis-cli -n 1 TTL ':1:hello'    # seconds left, counting down from 60
docker compose exec redis redis-cli -n 0 KEYS '*'          # empty: DB 0 untouched
```

`-n 1` tells `redis-cli` which database to open.

💡 Why `:1:hello` and not `hello`? Django stores every key as `KEY_PREFIX:VERSION:key`. Our prefix is empty and the version is 1. A prefix only matters when several projects share one Redis database, and ours has its own.

---

## Part 2 — The login throttle

[settings.py](../../backend/config/settings.py), inside `REST_FRAMEWORK`:

```python
    # Throttling (Day 11): a view opts in with `throttle_scope`; counts live in the cache (Redis DB 1).
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "login": "5/min",
    },
```

[accounts/api/views.py](../../backend/accounts/api/views.py):

```python
class LoginView(TokenObtainPairView):
    throttle_scope = "login"  # 5 tries a minute per IP (settings.DEFAULT_THROTTLE_RATES)
```

| Piece | In plain words |
|---|---|
| `ScopedRateThrottle` on every view | It only limits views that set `throttle_scope`. All other views are untouched |
| `"login": "5/min"` | Scope name → rate. Periods can be `s`, `min`, `hour`, `day` |
| `throttle_scope = "login"` | "Count me under the `login` rate" |
| Who is counted? | The user isn't logged in yet, so DRF counts by **IP address**. On logged-in views it counts by user id |

Why set the class globally instead of only on `LoginView`? Password reset and the public web-to-lead form (Day 301) will need limits too. Each will need just one line, `throttle_scope = "..."`, and every rate stays in one place in settings.

### Trade-offs to know

| Question | Our answer | Why |
|---|---|---|
| Does a correct login count too? | Yes, every try counts | Simple, and no human logs in 5 times a minute |
| 20 people in one office share one public IP | They share the 5 tries | Fine for small teams. Per-account lockout comes later (8.4, Day 236) |
| ⚠️ Behind nginx or a load balancer | Every request seems to come from the proxy's IP, so **everyone shares one bucket** | In production (Day 105+) we set DRF's `NUM_PROXIES`, so it reads the real IP from `X-Forwarded-For` |

### 🧪 Try it yourself

```bash
for i in 1 2 3 4 5 6; do
  curl -s -o /dev/null -w "try $i: %{http_code}\n" -X POST http://localhost:8000/api/v1/auth/login/ \
    -H "Content-Type: application/json" -d '{"email":"arup@gmail.com","password":"wrong"}'
done

# The full 7th answer: status, Retry-After and the body
curl -i -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" -d '{"email":"arup@gmail.com","password":"wrong"}'

docker compose exec redis redis-cli -n 1 KEYS '*throttle*'
```

### What we got

| Try | Answer |
|---|---|
| 1–5 | `401`: wrong password |
| 6 | **`429 Too Many Requests`**, `Retry-After: 59` |
| Body | `{"error":{"code":"throttled","message":"Request was throttled. Expected available in 59 seconds."}}`, the Day 7 error shape with no extra work |
| Redis DB 1 | `:1:throttle_login_172.20.0.1`, TTL 60 |

🐳 Why `172.20.0.1` and not `127.0.0.1`? curl talks to the laptop's port 8000, Docker forwards it into the container, and Django sees the request coming from the **Docker network's gateway**.

💡 Locked yourself out while testing? Wait a minute, or delete the key: `docker compose exec redis redis-cli -n 1 DEL ':1:throttle_login_172.20.0.1'`. The Django admin login (`/admin/`) isn't a DRF view, so it was never throttled.

---

## Part 3 — The throttle broke our tests

Right after adding the throttle, `pytest` went red, and **differently on each run**: 1 failure, then 3, then more.

```
E       assert 429 == 200
E       KeyError: 'refresh_token'
```

And Redis had a key nobody expected: `:1:throttle_login_127.0.0.1`. That was **the tests'** IP.

| Storage | After each test |
|---|---|
| Postgres (`test_crm`) | ✅ Rolled back by pytest-django (Day 10) |
| Cache (Redis) | ❌ **Nothing cleaned it.** Not even a test database: it was our dev Redis DB 1 |

`test_auth.py` logs in about 8 times, all from `127.0.0.1`. The 6th login was throttled. The count also **survived into the next run**, so each run broke earlier. This is the classic **test pollution** bug: tests depending on state left behind by other tests. Day 10 said tests must never depend on each other; here we saw it happen.

### The fix: an `autouse` fixture

[conftest.py](../../backend/conftest.py):

```python
@pytest.fixture(autouse=True)
def isolated_cache(settings):
    """Every test gets an empty in-memory cache: throttle counts never leak between tests or into dev Redis."""
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    cache.clear()
```

| Piece | Why |
|---|---|
| `autouse=True` | Runs before **every** test, even ones that don't ask for it. Day 10's fixtures were "ask and you get it"; this one is "everyone gets it" |
| `settings` | pytest-django's fixture. A change made through it lasts **only for this test** and is undone afterwards |
| `LocMemCache` | Memory inside the test process. Fast, and it never touches Redis |
| `cache.clear()` | A hidden trap: every `LocMemCache` with the same name shares one global store, so switching the backend alone doesn't empty it. Clearing makes each test start from zero |

> **Think of it like Day 10's whiteboard, now for the cache.** pytest-django wipes the database board by itself. The cache board we wipe ourselves.

**But then are we testing Redis?** No, and that's on purpose. The test checks the throttle's **rule** (5 tries, then 429). We saw with `redis-cli` that the counts land in Redis. Tests that truly need Redis (like `/api/health/`) can be written separately later.

### The new test

[accounts/tests/test_auth.py](../../backend/accounts/tests/test_auth.py):

```python
def test_login_is_throttled_after_5_tries_a_minute(api_client, make_user):
    user = make_user()
    for _ in range(5):
        assert login(api_client, user, password="wrong-password").status_code == 401

    response = login(api_client, user)  # even the right password is refused now

    assert response.status_code == 429
    assert response.data["error"]["code"] == "throttled"
    assert "Retry-After" in response.headers
```

The 6th try uses the **right** password and still gets 429. That proves the throttle runs **before** the password check, so an attacker can't learn that try 6 would have worked.

### What we got

```
run 1: 11 passed in 3.72s
run 2: 11 passed in 3.75s
run 3: 11 passed in 3.74s
--- Redis DB 1 keys after tests:
(empty)
```

Same result every run, and Redis untouched.

---

## Problems we hit

| Problem | Cause | Fix |
|---|---|---|
| Tests failing, more each run (`429 == 200`, `KeyError: 'refresh_token'`) | Throttle counts lived in the shared Redis cache, outside the test database's rollback | `isolated_cache` autouse fixture: an empty in-memory cache per test |
| (Avoided) `restart` would have missed the new `REDIS_CACHE_URL` | `env_file` is read when the container is created | `docker compose up -d web` |

---

## New words

| Word | Meaning |
|---|---|
| **Cache** | A fast, temporary store of answers, each with an expiry |
| **TTL** | Time to live: seconds left before Redis deletes a key by itself |
| **Redis DB number** | One of Redis's 16 separate key spaces (0–15), picked by the number at the end of the URL |
| **`FLUSHDB`** | The Redis command that deletes every key in the current database; `cache.clear()` uses it |
| **Throttling / rate limiting** | Allowing only so many requests per period |
| **Brute force** | Guessing a password by trying huge numbers of them |
| **429 Too Many Requests** | The HTTP status for "slow down" |
| **`Retry-After`** | Response header: how many seconds to wait before trying again |
| **Scope** | A name (`"login"`) that links a view to a rate in settings |
| **`autouse` fixture** | A fixture that runs for every test without being asked for |
| **Test pollution** | One test's leftovers changing another test's result |
| **Flaky test** | A test that passes or fails depending on things outside it, such as order or leftover data |

---

## Files changed today

| File | What changed |
|---|---|
| [.env.example](../../.env.example) and your `.env` | + `REDIS_CACHE_URL=redis://redis:6379/1` |
| [config/settings.py](../../backend/config/settings.py) | `CACHES` → Redis DB 1; `DEFAULT_THROTTLE_CLASSES` and `DEFAULT_THROTTLE_RATES` |
| [accounts/api/views.py](../../backend/accounts/api/views.py) | `LoginView.throttle_scope = "login"` |
| [conftest.py](../../backend/conftest.py) | + `isolated_cache` autouse fixture |
| [accounts/tests/test_auth.py](../../backend/accounts/tests/test_auth.py) | + `test_login_is_throttled_after_5_tries_a_minute` |

---

## Check yourself

<details>
<summary>1. Why does the cache use Redis DB 1 instead of DB 0?</summary>

DB 0 will hold Celery's queued jobs. `cache.clear()` wipes the whole database it uses, so a shared database would also delete waiting jobs.
</details>

<details>
<summary>2. Why store throttle counts in Redis instead of Django's default in-memory cache?</summary>

Each web process has its own memory. With several processes, each would count separately and an attacker would get 5 tries per process. Redis is one shared place for all of them.
</details>

<details>
<summary>3. After adding <code>REDIS_CACHE_URL</code> to <code>.env</code>, why <code>up -d</code> and not <code>restart</code>?</summary>

`env_file` is read when the container is created. `restart` reuses the old container with the old values; `up -d` sees the change and recreates it.
</details>

<details>
<summary>4. Why did the tests fail differently on each run before the fix?</summary>

The throttle counts lived in Redis, which pytest-django doesn't roll back. Counts from earlier tests, and even from earlier runs, were still there, so the 429 came sooner each time.
</details>

<details>
<summary>5. In the throttle test, why is the 6th try made with the right password?</summary>

To prove the throttle runs before the password check: even a correct password is refused, so an attacker learns nothing from the 6th try.
</details>

<details>
<summary>6. What would go wrong in production behind nginx without <code>NUM_PROXIES</code>?</summary>

Every request would seem to come from nginx's IP, so all users would share one 5-a-minute bucket, and one person's typos could lock everyone out.
</details>
