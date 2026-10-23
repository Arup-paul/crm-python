# Day 6 — Shared base models & code conventions

## What we built

A `core` app with three **abstract base models** that every future CRM model inherits, plus `docs/architecture.md`, the rules for where code goes. No new tables today: abstract models only share fields.

**Files:**

| File | Job |
|------|-----|
| [core/models.py](../../backend/core/models.py) | `TimeStampedModel`, `AuditModel`, `ActiveManager`, `SoftDeleteModel` |
| [config/settings.py](../../backend/config/settings.py) | `'core'` added to `INSTALLED_APPS` |
| [docs/architecture.md](../architecture.md) | Where code goes: models, QuerySets, services, serializers, views |

---

## Abstract models

```python
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
```

| | Normal model | Abstract model (`abstract = True`) |
|---|---|---|
| Own table? | ✅ | ❌ |
| `Model.objects...`? | ✅ | ❌ |
| For | Storing data | Sharing fields and methods with child models |

`class Company(SoftDeleteModel, AuditModel)` gets all 8 base fields in **its own** table. `makemigrations` for `core` says "No changes detected", which is correct, because there's nothing to create.

---

## The three base models

| Class | Fields | Notes |
|-------|--------|-------|
| `TimeStampedModel` | `created_at`, `updated_at` | `auto_now_add` = set once on create; `auto_now` = set on every `save()`. Both hidden from forms. |
| `AuditModel` | `created_by`, `updated_by` | FK to `settings.AUTH_USER_MODEL`, `SET_NULL`, `related_name="+"`. Set by services, never by the client. |
| `SoftDeleteModel` | `is_active`, `archived_at`, `archived_by` + `archive()`, `restore()` | Inherits `TimeStampedModel`. Two managers: `objects` and `all_objects`. |

### Why these FK options?

| Option | Why |
|--------|-----|
| `settings.AUTH_USER_MODEL` | The string `"accounts.User"`. `core` must not import `accounts` (shared code depends on nobody; avoids circular imports). |
| `on_delete=SET_NULL` + `null=True` | If a user is really deleted, their companies stay, and "created by" becomes empty. It's history, not ownership (`owner` will be `PROTECT`). |
| `related_name="+"` | No reverse link. Two FKs to User in one model would both want `user.company_set`, a clash error. Query instead: `Company.objects.filter(created_by=user)`. |

The database column is `created_by_id` (holds the id number). `obj.created_by` = the User object, `obj.created_by_id` = just the number, with no extra query.

---

## Managers

A **manager** is where every query starts (`Company.objects`). Its `get_queryset()` returns the starting query.

```python
class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)
```

```python
objects = ActiveManager()       # first = the DEFAULT manager
all_objects = models.Manager()  # sees everything
```

| Code | Sees archived rows? |
|------|---------------------|
| `Company.objects.filter(...)` | ❌ (`WHERE is_active`) |
| `Company.all_objects.filter(...)` | ✅ |
| `company.contacts.all()` (reverse relation, uses the default manager) | ❌ |
| `deal.company` (forward FK, uses Django's plain base manager) | ✅ returns it anyway |

---

## archive() and restore()

```python
def archive(self, user=None):
    if not self.is_active:
        return
    self.is_active = False
    self.archived_at = timezone.now()
    self.archived_by = user
    self.save(update_fields=["is_active", "archived_at", "archived_by", "updated_at"])
```

| Detail | Why |
|--------|-----|
| `if not self.is_active: return` | **Idempotent**: archiving twice keeps the first date and person |
| `update_fields=[...]` | Writes only these columns, so it doesn't overwrite someone else's change to `name` made a second ago |
| `"updated_at"` in the list | With `update_fields`, `auto_now` only runs if the field is listed |
| `timezone.now()` | A UTC time with the timezone attached. `datetime.now()` has none, and Django warns. |
| `user=None` | Scripts and Celery jobs archive with no logged-in user |

**When is `updated_at` updated?**

| Code | Updated? |
|------|----------|
| `obj.save()` | ✅ |
| `obj.save(update_fields=["name"])` | ❌ list `"updated_at"` too |
| `Model.objects.filter(...).update(...)` | ❌ SQL directly, skips `save()` |

---

## Where code goes (docs/architecture.md)

```
view → serializer → service → model → Postgres
```

| Layer | Job |
|-------|-----|
| Model | Fields, constraints, methods that change **only its own row** |
| QuerySet methods | Chainable **reads**: `visible_to(user)`, `open()` |
| Service (`services.py`) | **Every write**: rules, `created_by` / `updated_by`, transactions, side effects |
| Serializer | Checks JSON shape, turns instances into JSON |
| View | Auth, permissions, chooses the queryset, calls a service |

### Why services, not signals

| Signal problem | Example |
|----------------|---------|
| Hidden | `deal.save()` in a view doesn't show that another file sends an email |
| Skipped | `bulk_create()` and `QuerySet.update()` never send `post_save` |
| No context | A signal doesn't know which user made the change |
| Fires too often | Editing a won deal's title fires `post_save` again, so a second email goes out |

A service like `move_deal_stage(deal=, stage=, user=)` puts the whole action in one visible function, inside one transaction, called the same way by the API, admin, Celery, seed scripts and tests.

---

## Commands

| Command | What it does |
|---------|--------------|
| `docker compose exec web python manage.py startapp core` | Create the app inside the **running** `web` container |
| `docker compose exec web python manage.py check` | Find mistakes without touching the database |
| `docker compose exec web python manage.py makemigrations core --dry-run` | Show what a migration *would* contain, without writing it |
| `docker compose exec -T web python manage.py shell < script.py` | Run a Python script in the Django shell (`-T`: input comes from a file, not the keyboard) |

`exec` = run in the already running container. `run --rm` = start a fresh temporary one, then delete it.

---

## How we tested without a real model

Company doesn't exist until Day 25, so a shell script made a temporary `Demo(SoftDeleteModel, AuditModel)` table with `connection.schema_editor().create_model()`, all inside `transaction.atomic()`, and raised an error at the end. Postgres rolled **everything** back, even the `CREATE TABLE` (MySQL can't do that).

Results: `objects.count()` = 0 and `all_objects.count()` = 1 after archive; archiving twice kept the first date; `updated_at` changed; no table was left behind.

---

## Gotchas to remember

| Gotcha | What to do |
|--------|------------|
| `objects.get(id=5)` can't find an archived row | Restore endpoints and the Django admin use `all_objects` |
| Django's form unique check uses the default manager, so it misses archived rows and Postgres then raises an `IntegrityError` (like the Day 5 email bug) | Unique validators in serializers use `Model.all_objects` |
| `save(update_fields=...)` without `"updated_at"` | Always list it |

---

## Check yourself

<details>
<summary>1. Why does <code>makemigrations core</code> say "No changes detected"?</summary>

All three base models are `abstract = True`, so they have no table of their own. Their fields appear in the tables of the models that inherit them.
</details>

<details>
<summary>2. Why is <code>created_by</code> <code>SET_NULL</code> but a company's <code>owner</code> <code>PROTECT</code>?</summary>

`created_by` is history: "unknown" is fine if that user is deleted. `owner` is who is responsible now, and a customer must never be left without an owner, so you reassign first.
</details>

<details>
<summary>3. Which manager does Django use by default, and how does it decide?</summary>

The first manager declared in the class. In `SoftDeleteModel` that's `objects = ActiveManager()`, so archived rows are hidden by default.
</details>

<details>
<summary>4. An import uses <code>bulk_create()</code> for 500 deals, and a <code>post_save</code> signal should write history rows. How many are written, and what's the fix?</summary>

Zero: `bulk_create()` doesn't send `post_save`. The fix is a service that writes the history rows itself.
</details>
