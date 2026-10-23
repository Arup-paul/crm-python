# Day 5 — Custom User with email login

## What we built

An `accounts` app with our own `User`: logs in with **email**, has a **role** (admin / manager / rep), and works in the Django admin. Then the project's **first `migrate`**.

**Files:**

| File | Job |
|------|-----|
| [accounts/models.py](../../backend/accounts/models.py) | The User table |
| [accounts/managers.py](../../backend/accounts/managers.py) | How users are created and found at login |
| [accounts/admin.py](../../backend/accounts/admin.py) | The User pages in `/admin/` |
| [config/settings.py](../../backend/config/settings.py) | `'accounts'` in `INSTALLED_APPS` + `AUTH_USER_MODEL` |
| [accounts/migrations/0001_initial.py](../../backend/accounts/migrations/0001_initial.py) | Generated: creates the table |

---

## Why a custom User — and why *before* the first migrate

Django's built-in User logs in with a `username`. We want email + role.

The first `migrate` creates tables like `django_admin_log` that have a **foreign key to the user table**. We checked in Postgres:

```
django_admin_log.user_id  →  accounts_user     ✅ our table
```

If the first migrate had run with Django's User, every FK would point at `auth_user`. Switching later = rewriting every FK and moving all user data by hand. Django has no tool for it. **Set `AUTH_USER_MODEL` once, before the first migrate, and never change it.**

---

## models.py — the important parts

```python
class User(AbstractUser):            # inherit ALL of Django's user fields
    class Role(models.TextChoices):  # fixed list: stored value, label
        ADMIN = "admin", "Admin"
        REP = "rep", "Sales rep"

    username = None                                  # remove the username column
    email = models.EmailField(unique=True)           # login field must be unique
    first_name = models.CharField(max_length=150)    # no blank=True → required
    role = models.CharField(choices=Role.choices, default=Role.REP)  # least privilege

    USERNAME_FIELD = "email"          # what login uses
    REQUIRED_FIELDS = ["first_name"]  # extra questions in createsuperuser
    objects = UserManager()           # our manager (Django's expects a username)
```

| Concept | Meaning |
|---------|---------|
| `AbstractUser` | A full user *template*. "Abstract" = no table of its own; we inherit its fields. |
| `TextChoices` | Write `User.Role.REP` in code. A typo crashes now instead of saving bad data. |
| `__str__` | How a user is shown as text (admin, shell). Without it: `User object (1)`. |
| `save()` override | Lowercases the email on **every** save (admin, shell, API) — one rule, one place. Must call `super().save()` or nothing is saved. |

---

## managers.py — creating users safely

`User.objects` is the **manager**: every query starts there.

| Method | Does |
|--------|------|
| `_create_user()` | Shared helper: check email, normalize it, **hash the password**, save |
| `create_user()` | Normal user: `is_staff=False`, `is_superuser=False` |
| `create_superuser()` | `is_staff=True`, `is_superuser=True`, `role="admin"` |
| `get_by_natural_key()` | Called at login: finds the user by lowercased email |

**The most important line:** `user.set_password(password)` — stores a **hash** like `pbkdf2_sha256$1000000$...`, never the real password. Never write `user.password = "abc"`.

**Two different "admins"** — easy to mix up:

| Field | Meaning |
|-------|---------|
| `is_staff` / `is_superuser` | Can use Django's `/admin/` — a **developer** tool |
| `role = "admin"` | Admin **inside our CRM** (React app, later) |

**Why `"admin"` as a plain string in the manager?** `models.py` imports `managers.py`. If `managers.py` imported `User` back, the two files would import each other → circular import error.

---

## admin.py — fixing Django's UserAdmin

Django's `UserAdmin` is great (password forms, permissions) but expects `username` everywhere. We inherit it and redefine:

- `ordering = ["email"]` — the base sorts by `username` → would crash
- `fieldsets` — layout of the **edit** page (we added a "CRM" section for `role`)
- `add_fieldsets` — layout of the **add user** page, with `password1` / `password2`

---

## Reading the migration

`makemigrations` compares models with existing migrations and **writes a Python file**. `migrate` runs it against the database.

- `dependencies = [('auth', '0012_...')]` — run Django's auth migrations first (we link to `Group` and `Permission`).
- Fields come from two places: inherited (`password`, `is_staff`, `last_login`…) and ours (`email`, `first_name`, `role`).
- No `username` line → `username = None` worked.
- Migration files go into git: every server builds the same table from them.

In Postgres, `last_name` is `NOT NULL` even though it's optional — empty is stored as `""` (Day 3 rule).

---

## Commands

| Command | What it does |
|---------|--------------|
| `docker compose run --rm web python manage.py startapp accounts` | Create the app folder |
| `docker compose run --rm web python manage.py check` | Find mistakes without touching the database |
| `docker compose run --rm web python manage.py makemigrations accounts` | Write the migration file |
| `docker compose run --rm web python manage.py migrate` | Create the tables |
| `docker compose run --rm web python manage.py createsuperuser` | Create an admin login (asks for a password) |
| `docker compose up -d --force-recreate web` | Throw away the `web` container and make a fresh one |

---

## Problems we hit

| Problem | Cause | Fix |
|---------|-------|-----|
| `failed to bind host port 8000: address already in use` | A PHP server from another project used port 8000 | Stop the PHP server while working here |
| `failed to resolve host 'db'` + no ports on `web` | The failed start left a broken `web` container with no network | `docker compose up -d --force-recreate web` |
| `12345678` rejected as a password | Django's validators (too common, all numeric) | Fine to bypass for **local dev only**, via `set_password()` in the shell |

**Lesson:** when a container behaves strangely, check `docker compose ps` — look at **CREATED** and **PORTS**. An old container from a failed start is a common cause.

---

## Check yourself

<details>
<summary>1. Why must <code>AUTH_USER_MODEL</code> be set before the first migrate?</summary>

The first migrate creates FKs (e.g. `django_admin_log.user_id`) pointing at the user table. Once they point at `auth_user`, switching to a custom User means rewriting every FK and moving data by hand.
</details>

<details>
<summary>2. Why is <code>if not email: raise</code> needed when the email column is NOT NULL?</summary>

The database accepts an empty string `""` — it isn't NULL. Only the Python check stops an empty email.
</details>

<details>
<summary>3. A user types <code>Arup@Gmail.com</code> at login. How does it still work?</summary>

`save()` stored the email lowercase, and `get_by_natural_key()` lowercases what the user typed before looking it up.
</details>

<details>
<summary>4. What's the difference between <code>is_staff</code> and <code>role="admin"</code>?</summary>

`is_staff` = can open Django's `/admin/` (developer tool). `role="admin"` = admin inside the CRM app.
</details>
