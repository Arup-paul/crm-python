# Day 2 — Django inside a container

## What we built

Our own Docker **image** for Django, a `web` service in Compose, and a Django project (`config`) whose settings come from `.env`.

**Files:** [backend/Dockerfile](../../backend/Dockerfile) · [backend/requirements.txt](../../backend/requirements.txt) · [backend/.dockerignore](../../backend/.dockerignore) · [backend/config/settings.py](../../backend/config/settings.py) · [docker-compose.yml](../../docker-compose.yml) (`web` part)

---

## The Dockerfile, line by line

A Dockerfile is the recipe for building an image. Each instruction makes one **layer**.

```dockerfile
FROM python:3.12-slim                 # start from an image that already has Python
ENV PYTHONDONTWRITEBYTECODE=1 \       # don't create .pyc files
    PYTHONUNBUFFERED=1                # print logs immediately (no buffering)

ARG UID=1000                          # build-time values, passed from compose
ARG GID=1000
RUN groupadd --gid ${GID} app && useradd --uid ${UID} --gid ${GID} --create-home app

WORKDIR /app                          # "cd /app" for everything below

COPY requirements.txt .               # 1) copy ONLY the package list
RUN pip install --no-cache-dir -r requirements.txt   # 2) install packages

COPY --chown=app:app . .              # 3) then copy the code
USER app                              # run as a normal user, not root

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

### Why copy `requirements.txt` before the code? (layer caching)

Docker reuses a layer from cache if nothing it depends on changed.

| You changed… | What rebuilds |
|--------------|---------------|
| Only a `.py` file | Just the last `COPY` — fast (seconds) |
| `requirements.txt` | `pip install` and everything after — slow |

If we copied all code first, *every* code change would re-run `pip install`. Order = speed.

### Why a non-root user with your UID?

- **Security:** if someone breaks into the app, they're a normal user, not root.
- **File ownership:** files Django creates (like migrations) belong to *you* on your laptop, not to `root`. That's why `UID`/`GID` come from `.env` (`HOST_UID=1000`).

### `.dockerignore`

Like `.gitignore`, but for the **build context** (the folder sent to Docker). Keeps `.env`, `__pycache__/` and `.venv/` out of the image — smaller, and no secrets baked in.

---

## The `web` service in Compose

```yaml
web:
  build:
    context: ./backend              # folder with the Dockerfile
  env_file: .env                    # every .env line becomes an environment variable
  volumes:
    - ./backend:/app                # bind mount: live code
  ports:
    - "8000:8000"
  depends_on:
    db:
      condition: service_healthy    # wait until Postgres is really ready
```

- **Bind mount** `./backend:/app` — the container sees your real folder. Save a file → `runserver` reloads. No rebuild needed for code changes.
- **Named volume vs bind mount:** a named volume (`postgres_data`) is managed by Docker; a bind mount is *your* folder shared into the container.

---

## How `.env` reaches `settings.py`

```
.env  ──(env_file)──▶  container environment  ──(os.environ)──▶  settings.py
```

```python
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]                  # [] = required: crash if missing
DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"     # .get = optional, with a default
```

- `os.environ["X"]` → crashes immediately if missing. Good for required secrets: you notice at once.
- Environment values are always **strings** — that's why `DEBUG` is compared to `"True"`.
- `DB_HOST=db` — inside Docker, containers find each other by **service name**, not `localhost`.

---

## Commands

| Command | What it does |
|---------|--------------|
| `docker compose build web` | Build the image from the Dockerfile |
| `docker compose run --rm web <cmd>` | Start a temporary `web` container, run one command, delete it |
| `docker compose run --rm web django-admin startproject config .` | Create the Django project |
| `docker compose exec web python manage.py check --database default` | Check settings and the database connection |

---

## Check yourself

<details>
<summary>1. You edit a <code>.py</code> file. Do you need to rebuild the image?</summary>

No. The bind mount shares your folder live, and `runserver` reloads. Rebuild only when `requirements.txt` or the `Dockerfile` changes.
</details>

<details>
<summary>2. Why is <code>DB_HOST=db</code> and not <code>localhost</code>?</summary>

Inside the `web` container, `localhost` means the web container itself. Postgres runs in another container, reachable by its service name `db`.
</details>

<details>
<summary>3. Why didn't we run <code>migrate</code> on Day 2?</summary>

The first `migrate` creates tables that point at the user table. We had to set our custom User (Day 5) first — see Day 5 notes.
</details>
