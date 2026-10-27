# Learning Log

2–3 lines a day: what I built and what I learned.

## Day 1 — Docker database containers
- Postgres and Redis run in Compose with healthchecks and named volumes.
- A container is throwaway; a volume keeps the data after `down` (only `down -v` deletes it).

## Day 2 — Django in a container
- Dockerfile with a non-root user; `requirements.txt` copied first so the pip layer stays cached.
- Settings read secrets from `.env` through `os.environ`, so nothing secret goes into git.

## Day 3 — Domain map
- `docs/domain.md`: 11 entities, their fields, the relationships and an ER diagram.
- Money is `DecimalField`, never float. `null` is a database rule and `blank` is a form rule; optional text uses `blank=True` only.
- `on_delete`: PROTECT for owners and stages, SET_NULL when the child still makes sense alone, CASCADE for history and notes.

## Day 4 — Design decisions (ADRs)
- Five ADRs in `docs/decisions/`: custom fields in JSON, tags as M2M, soft delete, explicit FKs for activities, API conventions.
- An ADR records the options, the decision and *why*, so later I don't have to re-argue the same choice.

## Day 5 — Custom User with email login
- `accounts.User` extends `AbstractUser`: email login, required first name, a `role` (static for now, dynamic in Phase 7.5).
- `AUTH_USER_MODEL` had to be set before the first `migrate`, because `django_admin_log` and others get FKs to the user table.
- `set_password()` stores a hash; emails are stored lowercase so login ignores capitals.

## Day 6 — Shared base models & code conventions
- `core` app: abstract `TimeStampedModel`, `AuditModel` and `SoftDeleteModel` (`objects` hides archived rows, `all_objects` sees all). Abstract = no table, so no migration.
- `save(update_fields=...)` must list `updated_at`, or `auto_now` doesn't run.
- `docs/architecture.md`: every write goes through a service. Signals are hidden, skipped by `bulk_create()`/`update()`, and don't know the user.

## Day 7 — DRF setup, health check & error shape
- New packages live in the image, so `requirements.txt` changes need `docker compose build` + `up -d`, not `restart`.
- DRF defaults: login required unless `AllowAny`, 25 per page, browsable API only in `DEBUG`. `/api/health/` answers 200 or 503.
- A custom exception handler gives every error `{"error": {code, message, fields}}`; the frontend checks `code`, since session auth answers 403 where JWT answers 401.

## Day 8 — JWT login
- `/api/v1/auth/login/` gives an access token (10 min) and a refresh token (7 days, rotated and blacklisted); `/api/v1/auth/me/` needs the access token, and without one it's 401.
- A JWT's payload is readable by anyone; only the signature (made with `SECRET_KEY`) stops it being changed. Never put secrets in it.
- Testing junk, changed and expired tokens found a crash in the Day 7 error handler (dict-shaped errors). Test the bad cases too.

## Day 9 — Auth for a browser app
- Login now returns only `access` in the body; the refresh token goes in an `HttpOnly`, `SameSite=Lax` cookie limited to `/api/v1/auth/`, so XSS can't read it.
- `/refresh/` reads the cookie (override `get_serializer` on SimpleJWT's view) and rotates it; `/logout/` blacklists it and deletes the cookie with the same `path`, needs no access token, and always answers 204.
- Tested with curl `-c`/`-b` cookie jars: old and logged-out cookies get 401 "Token is blacklisted".

## Day 10 — Test setup + auth tests
- pytest + pytest-django; `pytest.ini` points at `config.settings`, `--reuse-db` keeps `test_crm` between runs. Each test runs in a rolled-back transaction, never on the real `crm` DB.
- `conftest.py` fixtures: `make_user(role=...)` (a factory, unique emails), `api_client` (anonymous, remembers cookies), `auth_client(user)` (a new client with a real JWT, not `force_authenticate`).
- 10 tests lock in Days 5, 8 and 9 (login, case-insensitive email, `/me`, cookie refresh + rotation, logout blacklist): `docker compose exec web pytest` → 10 passed in ~3 s.
