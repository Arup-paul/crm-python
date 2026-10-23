# Architecture: where code goes

The rules every backend app follows. When you're unsure where a piece of code belongs, check here first.
The *why* behind a rule matters more than the rule. If a new case doesn't fit, write an ADR.

## Apps

| App | Owns |
|-----|------|
| `core` | Shared base models, managers, permissions, the error handler. Depends on no other app. |
| `accounts` | The custom `User`, auth API, users admin API |
| `crm_core` | Company, Contact, Tag |
| `deals` | PipelineStage, Deal, stage history, LostReason |
| `activities` | Activity, Task, Celery tasks |
| `reports` | Read-only aggregations; never writes |

Apps may import from `core`. `core` imports from nobody, and it uses `settings.AUTH_USER_MODEL` instead of importing `User`.

## Inside an app

```
crm_core/
├── models.py        tables, fields, constraints, QuerySet classes (reads)
├── services.py      every write: create / update / archive / restore / business actions
├── admin.py         Django admin (a developer tool)
├── api/
│   ├── serializers.py   shape and validation of JSON in and out
│   ├── views.py         ViewSets: permissions, pick the queryset, call services
│   └── urls.py          routes under /api/v1/
├── migrations/
└── tests/
    ├── test_models.py
    ├── test_services.py
    └── test_api.py
```

## The layers

```
Write:  HTTP request → view → serializer (is the JSON valid?) → service (business rules, writes) → model → Postgres
Read:   HTTP request → view → Model.objects.visible_to(user).<more QuerySet methods> → serializer → JSON
```

| Layer | Does | Never does |
|-------|------|------------|
| **Model** | Fields, constraints, `__str__`, small methods that change **only its own row** (`archive()`, `restore()`) | Touch other models, know the request, send emails |
| **QuerySet methods** | Reusable, chainable **reads**: `visible_to(user)`, `open()`, `with_deal_totals()` | Write anything |
| **Service** | **Every write**: checks business rules, sets `created_by` / `updated_by`, wraps several writes in a transaction, triggers side effects (emails, Celery tasks) | Know about HTTP, requests or JSON |
| **Serializer** | Checks the shape of the input, turns model instances into JSON | Save to the database with business rules, set `owner` / `created_by` from client data |
| **View** | Authentication, permissions, chooses the queryset, calls a service, returns the response | Contain business rules |

## Rule 1: every write goes through a service

```python
# crm_core/services.py (built on Day 26)
@transaction.atomic
def create_contact(*, user, **data):
    contact = Contact(**data, created_by=user, updated_by=user)
    contact.full_clean()
    contact.save()
    return contact
```

The view only calls it: `create_contact(user=request.user, **serializer.validated_data)`.

Why:

- **One place per action.** "What happens when a deal is won?" One function answers that, so you never hunt through views, models and signals.
- **Many callers, same rules.** The API, the Django admin, Celery jobs, the `seed_demo_data` command and tests all call the same service. Nobody can skip a rule by taking another path.
- **Transactions.** Winning a deal writes the deal, a stage history row and an activity. `@transaction.atomic` saves all of them or none.
- **Server-set fields.** The service gets `user` from the request, never from the JSON, so the client can't fake `created_by` or `owner`.
- **Easy to test.** Call the function and check the database, with no HTTP involved.

**Service conventions:**

- Name them as a verb plus a noun: `create_contact`, `archive_company`, `move_deal_stage`.
- Use keyword-only arguments (the `*`), so calls read clearly: `move_deal_stage(deal=d, stage=s, user=u)`.
- The acting user is always passed in explicitly.
- Return the changed instance.
- When a rule is broken, raise Django's `ValidationError`. The API's exception handler (Day 7) turns it into the ADR 005 error shape.

## Rule 2: no signals for our own business logic

A signal (`post_save` etc.) runs code "somewhere else" whenever a model is saved. We don't use them for our own rules:

| Problem | Example |
|---------|---------|
| **Hidden** | Reading `create_deal()` doesn't show that a `post_save` handler in another file also sends an email |
| **Skipped by bulk operations** | `bulk_create()` and `QuerySet.update()` never send `post_save`, so the rule silently doesn't run |
| **No context** | A signal doesn't know who made the change or why, because there's no `request.user` |
| **Hard to test and order** | Several handlers on one signal run in an order you don't control |

Signals are fine only for wiring Django or a third-party library where no other hook exists. Events between apps go through an outbox table (a later ADR), not through signals.

## Rule 3: "fat models" only for the row itself

A model method may change **its own fields** (`archive()` sets three fields on itself). As soon as the logic involves another model, the acting user's permissions, a transaction across rows, or a side effect, it belongs in a service.

## Rule 4: reads live on QuerySets

```python
Contact.objects.visible_to(user).filter(company=c).with_open_deal_count()
```

- QuerySet methods chain together and are reused by the API, reports and tests.
- Every list a user can see starts with `visible_to(user)`: reps see their own rows, managers see their team's, admins see everything.
- Use `select_related` / `prefetch_related` in the queryset the view uses, and lock query counts in tests (Day 28).

## Base models (`core/models.py`)

| Class | Gives | Use for |
|-------|-------|---------|
| `TimeStampedModel` | `created_at`, `updated_at` | Every table |
| `AuditModel` | `created_by`, `updated_by` | Tables people edit |
| `SoftDeleteModel` | `is_active`, `archived_at`, `archived_by`, `archive()`, `restore()`, `objects` / `all_objects`; includes `TimeStampedModel` | Every domain model (ADR 003) |

A normal domain model: `class Company(SoftDeleteModel, AuditModel)`. `User` uses none of these (see `docs/domain.md`).

**Soft-delete gotchas:**

- `objects` hides archived rows, so **restore** and the **Django admin** use `all_objects`.
- Django's form unique check uses the default manager (`objects`), so it can't see archived rows. Unique validators in serializers must use `Model.all_objects`, or Postgres raises an `IntegrityError`.
- `save(update_fields=[...])` must list `"updated_at"`, or `auto_now` doesn't run.
- `QuerySet.update()` skips `save()`, so `updated_at` and `updated_by` must be set by hand.

## Serializers

- List fields explicitly. Never use `fields = "__all__"`: a new model field would be exposed automatically.
- `owner`, `created_by`, `updated_by` and the archive fields are read-only. The server sets them.
- Read and write shapes can differ: `company` is returned as `{id, name}` but accepted as an id.
