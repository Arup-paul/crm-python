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
