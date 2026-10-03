# CRM — Docker Guide (Install, Setup, Daily Run)

Everything in this project runs in Docker containers: PostgreSQL and Redis (from Day 1), Django (Day 2), the React dev server (Day 12), Celery (Day 68) and Mailpit (Day 69). Apart from Docker and Git, nothing needs to be installed on your machine. Day numbers refer to [CRM-TASK-PLAN.md](CRM-TASK-PLAN.md).

**How to use this guide**

| Part | When |
|---|---|
| [1 · Docker concepts](#part-1--docker-concepts-youll-use) | Read before Day 1, come back when a word is unclear |
| [2 · Install Docker](#part-2--install-docker-ubuntu-2404) | Once per computer |
| [3 · Project setup](#part-3--project-setup) | Day 1–2 (their tasks in detail), and later whenever a new service is added |
| [4 · Daily run](#part-4--daily-run) | Every day |
| [5 · Database & Redis](#part-5--database--redis) | Backups, resets, looking at data |
| [6 · Troubleshooting](#part-6--troubleshooting) | When something breaks |
| [7 · Shortcuts](#part-7--optional-shortcuts-with-make) | Optional, once the long commands feel familiar |
| [8 · Production preview](#part-8--production-preview) | Before Phase 5 (Day 105) |
| [9 · Disk cleanup](#part-9--disk-cleanup) | When disk space runs low |

---

## Part 1 — Docker concepts you'll use

| Concept | What it is | In this project |
|---|---|---|
| **Image** | A read-only template (OS files + Python + your packages), built from a Dockerfile | `crm-backend:dev` (built from `backend/Dockerfile`); `postgres:17-alpine` and `redis:7-alpine` (downloaded) |
| **Container** | A running instance of an image. You can delete and recreate it at any time. | `web`, `db`, `redis`; later `worker`, `beat`, `frontend` |
| **Dockerfile** | A step-by-step recipe for building an image. Each step becomes a cached **layer**. | `backend/Dockerfile`, `frontend/Dockerfile` |
| **Docker Compose** | One YAML file that describes all the containers and how they connect | `docker-compose.yml` |
| **Bind mount** | A folder on your machine that appears inside a container. An edit on either side shows up on both. | `./backend` → `/app`, so runserver reloads when you save a file |
| **Named volume** | Storage managed by Docker that survives when containers are deleted | `postgres_data` (your database), `redis_data` |
| **Network** | Compose puts every service on one private network, and each service name works as a hostname | Django connects to the host `db`, not `localhost` |
| **Port mapping** | `"HOST:CONTAINER"` makes a container's port reachable from your machine | `"8000:8000"` → http://localhost:8000 |

> **Rule to remember:** containers are disposable; volumes are not. Deleting a container loses nothing important. Deleting the `postgres_data` volume deletes your database.

### What runs where (development)

```
 browser ── localhost:5173 ──► frontend (Vite)   (Day 12+)
                                  │ /api
                                  ▼
 browser ── localhost:8000 ──► web (Django)
                                  │
                   ┌──────────────┴──────────────┐
                   ▼                             ▼
              db (Postgres)                    redis
                   ▲                           ▲   │
                   │                 beat ─────┘   │
                   │                               ▼
                   └──────────────────────────── worker
```

- All of these containers share one private Docker network, and each one reaches the others by service name (`db`, `redis`, `web`).
- `beat` puts scheduled tasks into Redis, and `worker` takes them out and reads/writes Postgres (both from Day 68).
- Bind mounts: `./backend` → `/app` (web, worker, beat) and `./frontend` → `/app` (frontend).
- Named volumes: `postgres_data`, `redis_data`, `frontend_node_modules`.

| Service | Image | Port on your machine | From |
|---|---|---|---|
| `db` | `postgres:17-alpine` | 5433 (for GUI tools like DBeaver) | Day 1 |
| `redis` | `redis:7-alpine` | not published (only containers use it) | Day 1 |
| `web` | `crm-backend:dev` | 8000 | Day 2 |
| `frontend` | built from `frontend/Dockerfile` | 5173 | Day 12 |
| `worker` | `crm-backend:dev` (same image) | – | Day 68 |
| `beat` | `crm-backend:dev` (same image) | – | Day 68 |
| `mailpit` | `axllent/mailpit` | 8025 (web UI for reading sent emails) | Day 69 |

---

## Part 2 — Install Docker (Ubuntu 24.04)

> **This computer already has Docker 29.1 and Compose 2.40** (from Ubuntu's packages). Skip 2.1 and go through 2.2–2.6.

### 2.1 Install

**Option A: Ubuntu's packages** (what this computer uses; the simplest)

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
```

**Option B: Docker's official repository** (newest versions). Follow https://docs.docker.com/engine/install/ubuntu/. It installs `docker-ce` and `docker-compose-plugin`.

Pick one option; don't mix them on the same machine.

### 2.2 Post-install

```bash
sudo systemctl enable --now docker   # start Docker now and on every boot
sudo usermod -aG docker $USER        # let your user run docker without sudo
```

Then **log out and log back in** (or restart) so the group change applies.

> Members of the `docker` group effectively have root access to the machine. That's fine on your own development computer; don't do it on a shared server.

### 2.3 Verify

```bash
docker --version
docker compose version     # "docker compose" with a space is Compose v2; the old "docker-compose" is v1
docker run --rm hello-world
```

**Done when:** `hello-world` prints "Hello from Docker!" without `sudo`.

### 2.4 Check for port conflicts

This machine also has PostgreSQL and Redis installed directly. If they're running, they occupy ports 5432 and 6379. That's why the compose file below publishes Postgres on **5433** and doesn't publish Redis at all.

To see what's using a port:

```bash
sudo ss -ltnp | grep -E ':(5432|5433|6379|8000|5173)\b'
```

If you won't use the locally installed ones any more, you can switch them off: `sudo systemctl disable --now postgresql redis-server`.

### 2.5 ⚠️ Project location

The project is inside `/var/www/html/`, which is Apache's default web folder. If Apache is running (`systemctl is-active apache2` prints `active`), anyone on your network may be able to download files from this folder, **including `.env` with your passwords**. Either move the project to your home folder (for example `~/projects/crm-python`) or stop Apache if you don't need it: `sudo systemctl disable --now apache2`.

### 2.6 Find your user id

```bash
id -u   # usually 1000
id -g   # usually 1000
```

These go into `.env` as `HOST_UID` / `HOST_GID`. The containers then run as a user with your id, so files they create (for example from `startproject`) belong to you, not to `root`.

---

## Part 3 — Project setup

Files you'll create on Day 1–2:

```
crm-python/
├── .env                 real values, never committed
├── .env.example         same keys with fake values, committed
├── .gitignore
├── docker-compose.yml   all services for development
└── backend/
    ├── Dockerfile
    ├── .dockerignore
    └── requirements.txt
```

### 3.1 `.env`: one file for every setting

`.env.example` (committed to git):

```ini
# --- Django ---
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# --- PostgreSQL: used by the db container AND by Django ---
DB_NAME=crm_db
DB_USER=crm_user
DB_PASSWORD=change-me
DB_HOST=db            # the compose service name, not localhost
DB_PORT=5432          # the port inside the Docker network (5433 is only for your machine)

# --- Redis ---
REDIS_URL=redis://redis:6379/0

# --- Your user id (Part 2.6), so files created in containers belong to you ---
HOST_UID=1000
HOST_GID=1000
```

Create your real `.env` and a secret key:

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # paste the output as DJANGO_SECRET_KEY
```

Also set a real `DB_PASSWORD` in `.env`.

`.gitignore` must contain `.env` (plus `__pycache__/`, `*.pyc`, `media/`, `node_modules/`).

**How a value travels:** `.env` → Compose (`env_file: .env`) → the container's environment → `os.environ` in `settings.py`. Django reads environment variables; it never opens `.env` itself. Compose also uses `.env` to fill in `${DB_NAME}`-style placeholders inside `docker-compose.yml`.

### 3.2 `backend/requirements.txt`

```
Django>=5.2,<5.3
psycopg[binary]>=3.2,<4
```

Version ranges keep every build the same until you choose to upgrade. `Django 5.2` is the LTS release (supported until April 2028).

### 3.3 `backend/Dockerfile`

```dockerfile
FROM python:3.12-slim

# No .pyc files; print logs immediately instead of buffering them
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# A normal (non-root) user with the same id as you
ARG UID=1000
ARG GID=1000
RUN groupadd --gid ${GID} app && useradd --uid ${UID} --gid ${GID} --create-home app

WORKDIR /app

# Dependencies first: this layer is reused from cache until requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . .
USER app

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

| Line | Why |
|---|---|
| `FROM python:3.12-slim` | Start from the official Python image. `slim` leaves out tools you don't need, so the image is smaller. |
| `PYTHONUNBUFFERED=1` | Without it, `print()` and log output can be delayed and `docker compose logs` looks empty |
| `ARG UID` + `useradd` | Running as a normal user is safer, and files created in the bind mount are owned by you |
| `COPY requirements.txt` **before** `COPY . .` | **Layer caching.** If only your code changed, Docker reuses the cached `pip install` layer, so a rebuild takes seconds instead of minutes. |
| `--no-cache-dir` | Keeps pip's download cache out of the image (smaller image) |
| `0.0.0.0:8000` | Listen on every network interface inside the container. `127.0.0.1` would only accept connections from inside the container itself, so your browser couldn't reach it. |

### 3.4 `backend/.dockerignore`

```
.venv/
__pycache__/
*.pyc
.env
media/
```

Everything in `backend/` is sent to Docker when you build (the **build context**). This file keeps junk and secrets out of it, so builds are faster and secrets never end up inside an image.

### 3.5 `docker-compose.yml`

On Day 1, write only the `db` and `redis` services and the `volumes:` section. Add `web` on Day 2.

```yaml
services:
  db:
    image: postgres:17-alpine
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5433:5432"   # your machine's 5433 → the container's 5432
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  web:
    build:
      context: ./backend
      args:
        UID: ${HOST_UID:-1000}
        GID: ${HOST_GID:-1000}
    image: crm-backend:dev
    env_file: .env
    volumes:
      - ./backend:/app   # live code: save a file → runserver reloads
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

volumes:
  postgres_data:
  redis_data:
```

| Part | Why |
|---|---|
| `image:` vs `build:` | `db` and `redis` use ready-made images from Docker Hub. `web` is built from your Dockerfile and tagged `crm-backend:dev`. |
| Pinned versions (`postgres:17`, `redis:7`) | `latest` can jump a major version one day and break your data directory. Upgrade on purpose. |
| `${DB_NAME}` | Filled in from `.env` when Compose reads the file |
| `$${POSTGRES_USER}` | `$$` means "don't fill this in now". The variable is read inside the container when the healthcheck runs. |
| `POSTGRES_*` variables | The Postgres image creates this database and user **only on the first start, when the volume is empty**. Changing them later does nothing (see Part 6). |
| `healthcheck` + `condition: service_healthy` | `web` waits until Postgres actually accepts connections, not just until its container has started |
| No `ports` on `redis` | Only other containers need Redis, and they reach it over the Docker network. Not publishing it avoids a clash with the local Redis on 6379. |
| `volumes:` at the bottom | Declares the named volumes. Docker creates them the first time and keeps them until you delete them. |

### 3.6 Create the Django project inside the container

```bash
docker compose build web
docker compose run --rm web django-admin startproject config .
```

- `build` creates the `crm-backend:dev` image. The first build downloads the Python image, so it's slow; later builds use the cache.
- `run --rm` starts a one-off container, runs one command in it, then deletes the container. The generated files land in `./backend` on your machine because of the bind mount.

### 3.7 Read settings from the environment

In `backend/config/settings.py`, replace the hard-coded values:

```python
import os

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.environ["DB_HOST"],
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}
```

`os.environ["X"]` raises an error straight away if `X` is missing. That's what you want for secrets: a clear crash at startup, instead of silently running with a wrong value. `.get()` with a default is only for settings that have a safe default.

### 3.8 Start everything

```bash
docker compose up -d
docker compose ps
docker compose exec web python manage.py check --database default
```

- `up -d` starts every service in the background (`-d` = detached).
- `ps` should show `db` and `redis` as **healthy** and `web` as **running**.
- `check --database default` confirms Django can reach Postgres.

Open http://localhost:8000 and you should see Django's welcome page.

> ⚠️ **Don't run `migrate` yet.** The custom user model comes first (Day 5).

Commit:

```bash
git status              # .env must NOT be in the list
git add -A
git commit -m "Day 2: Django project running in Docker"
```

### 3.9 Services added later

**Day 68: Celery worker and beat.** They use the same image and settings as `web`, so move the shared part into a YAML anchor (`x-backend`) instead of copying it three times:

```yaml
x-backend: &backend
  build:
    context: ./backend
    args:
      UID: ${HOST_UID:-1000}
      GID: ${HOST_GID:-1000}
  image: crm-backend:dev
  env_file: .env
  volumes:
    - ./backend:/app
  depends_on:
    db:
      condition: service_healthy
    redis:
      condition: service_healthy

services:
  # db and redis stay as they are

  web:
    <<: *backend
    ports:
      - "8000:8000"

  worker:
    <<: *backend
    command: celery -A config worker -l info

  beat:
    <<: *backend
    command: celery -A config beat -l info
```

One image, three containers, three different commands. The worker can never run different code from the web server, which the roadmap calls out as a real source of bugs.

**Day 12: React dev server.** Create the Vite project with a throwaway Node container, so Node isn't needed on your machine:

```bash
docker run --rm -it -u $(id -u):$(id -g) -e npm_config_cache=/tmp/.npm \
  -v "$PWD":/work -w /work node:24-alpine \
  npm create vite@latest frontend -- --template react
```

`frontend/Dockerfile` (the `dev` stage now; a `prod` stage is added on Day 109):

```dockerfile
FROM node:24-alpine AS dev
WORKDIR /app
RUN chown node:node /app
USER node
COPY --chown=node:node package*.json ./
RUN npm ci
COPY --chown=node:node . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

Add to `docker-compose.yml`:

```yaml
  frontend:
    build:
      context: ./frontend
      target: dev
    volumes:
      - ./frontend:/app
      - frontend_node_modules:/app/node_modules   # keep the container's own node_modules
    ports:
      - "5173:5173"
    depends_on:
      - web

volumes:
  # ...existing volumes
  frontend_node_modules:
```

In `frontend/vite.config.js`, the `/api` proxy target is **`http://web:8000`**, not `localhost:8000`. The proxy runs inside the frontend container, where `localhost` is the frontend container itself.

---

## Part 4 — Daily run

### 4.1 Start

```bash
cd /var/www/html/crm-python
docker compose up -d
docker compose ps
```

| URL | What | From |
|---|---|---|
| http://localhost:8000/admin/ | Django admin | Day 5 |
| http://localhost:5173 | React app | Day 12 |
| http://localhost:8000/api/docs/ | Swagger UI | Day 27 |
| http://localhost:8025 | Mailpit (emails sent in development) | Day 69 |

### 4.2 Watch logs

```bash
docker compose logs -f web           # follow one service (Ctrl+C stops watching, not the service)
docker compose logs -f web worker    # several services at once
docker compose logs --tail=50 db     # the last 50 lines
```

### 4.3 Run commands inside containers

**Rule:** every `python manage.py ...` runs **inside** the `web` container, because that's where Python, Django and your packages are installed.

| Task | Command |
|---|---|
| Create migrations | `docker compose exec web python manage.py makemigrations` |
| Apply migrations | `docker compose exec web python manage.py migrate` |
| Admin user | `docker compose exec web python manage.py createsuperuser` |
| Django shell | `docker compose exec web python manage.py shell` |
| New app | `docker compose exec web python manage.py startapp deals` |
| Seed demo data | `docker compose exec web python manage.py seed_demo_data` |
| Backend tests | `docker compose exec web pytest` (one app: `pytest deals`; by name: `pytest -k move_stage`) |
| A terminal inside the container | `docker compose exec web bash` (leave with `exit`) |
| Frontend tests (Day 23+) | `docker compose exec frontend npm test` |

- `exec` runs the command inside the **already running** container.
- `run --rm` starts a **fresh one-off** container. Use it when `web` isn't running, for example when your code has an error that stops runserver from starting.

### 4.4 When something changes

| You changed… | Do this | Why |
|---|---|---|
| Python code | nothing | Bind mount + runserver reloads automatically |
| Celery task code | `docker compose restart worker beat` | Celery doesn't reload on its own |
| A model | `makemigrations`, then `migrate` (in `web`) | |
| `requirements.txt` | `docker compose build`, then `docker compose up -d` | Packages are installed into the image at **build** time, not at start |
| A `Dockerfile` | `docker compose build`, then `docker compose up -d` | Same reason |
| `docker-compose.yml` | `docker compose up -d` | Compose recreates only the services whose config changed |
| `.env` | `docker compose up -d` | Environment variables are read when a container is **created**; `restart` is not enough |
| Frontend packages | `docker compose exec frontend npm install <package>` | Updates `package.json` (bind mount) and `node_modules` (volume) |
| New computer / fresh clone | Part 2, then `cp .env.example .env` (fill it in), `docker compose up -d --build`, `migrate`, `seed_demo_data` | |

Adding a Python package, for example DRF:

```bash
# 1. add a line to backend/requirements.txt:  djangorestframework>=3.16,<3.17
docker compose build
docker compose up -d
```

### 4.5 End of day

```bash
docker compose exec web pytest
git status                        # .env must not appear
git add -A && git commit -m "Day N: <what you did>"
docker compose stop
```

Then write 2–3 lines in `docs/learning-log.md`.

| Command | Containers | Data (volumes) | Use it when |
|---|---|---|---|
| `docker compose stop` | stopped, kept | kept | End of the day |
| `docker compose down` | deleted | kept | You want a clean restart |
| `docker compose down -v` | deleted | **deleted** | You want an empty database (Part 5.3) |

---

## Part 5 — Database & Redis

### 5.1 Look at the database

```bash
docker compose exec db psql -U crm_user -d crm_db
```

Inside psql: `\dt` lists tables, `\d deals_deal` describes a table, `\q` quits.

From a GUI tool on your machine (DBeaver, pgAdmin): host `localhost`, port **5433**, plus the database, user and password from `.env`.

### 5.2 Look at Redis

```bash
docker compose exec redis redis-cli
```

Try `PING`, `KEYS *` (fine in development, never on a big production server) and `INFO memory`.

### 5.3 Start over with an empty database

```bash
docker compose down -v            # deletes the Postgres AND Redis volumes
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_demo_data
```

To delete only the database and keep Redis, run `docker compose down`, then `docker volume ls` to find the volume name (it starts with the project folder name, e.g. `crm-python_postgres_data`), then `docker volume rm <name>`.

### 5.4 Backup and restore

```bash
mkdir -p ~/backups

# backup
docker compose exec -T db pg_dump -U crm_user -Fc crm_db > ~/backups/crm_$(date +%F).dump

# restore
docker compose exec -T db pg_restore -U crm_user -d crm_db --clean --if-exists < ~/backups/crm_2026-10-01.dump
```

`-T` turns off the terminal emulation that Compose normally adds. Without it, binary data piped through `>` or `<` gets corrupted. Keep backups outside the project folder so they never end up in git.

---

## Part 6 — Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `permission denied while trying to connect to the Docker daemon socket` | Your user isn't in the `docker` group yet | Part 2.2, then log out and back in |
| `port is already allocated` or `address already in use` | Another program uses that port on your machine | Change the left side of `ports:` (e.g. `"8001:8000"`) or stop that program (Part 2.4) |
| `web` exits or keeps restarting | A Python error | `docker compose logs web` |
| `could not translate host name "db"` | You ran `python manage.py` on your machine instead of in the container | Use `docker compose exec web python manage.py ...` |
| `connection refused` to `localhost:5432` from Django | `DB_HOST=localhost` in `.env` | `DB_HOST=db`. Inside a container, `localhost` is the container itself. |
| `password authentication failed` after changing `DB_PASSWORD` | Postgres only reads `POSTGRES_*` when its volume is empty | Put the old password back, or change it in psql (`ALTER USER crm_user WITH PASSWORD '...';`), or start over (5.3, deletes data) |
| `ModuleNotFoundError` right after adding a package | The image wasn't rebuilt | `docker compose build && docker compose up -d` |
| Files created by a container belong to `root`, and VS Code can't save them | The container ran as root, or `HOST_UID` is wrong | Fix `HOST_UID`/`HOST_GID`, rebuild, then fix existing files: `sudo chown -R $USER:$USER backend frontend` |
| Changed `.env` but nothing changed | `restart` doesn't re-read environment variables | `docker compose up -d` |
| Celery still runs old code | Celery doesn't reload on its own | `docker compose restart worker beat` |
| A scheduled task never runs | `beat` isn't running (the worker runs tasks, beat schedules them) | `docker compose ps`, then `docker compose logs beat` |
| React page doesn't load on :5173 | Vite is listening only on the container's `localhost` | `--host 0.0.0.0` (already in the Dockerfile's `CMD`) |
| Vite `/api` proxy error `ECONNREFUSED` | The proxy target is `localhost:8000` | Use `http://web:8000` in `vite.config.js` |
| VS Code: "Import 'django' could not be resolved" | Packages are inside the image, not on your machine | Install the **Dev Containers** extension, then use "Attach to Running Container" on `web` |
| Disk is full | Old images and build cache | Part 9 |

---

## Part 7 — Optional shortcuts with `make`

Once you know the long commands, a `Makefile` in the repo root saves typing. (`sudo apt install make` if it's missing.)

```make
# make up | make logs | make m c=migrate | make m c="startapp deals" | make test
up:    ; docker compose up -d
down:  ; docker compose down
stop:  ; docker compose stop
ps:    ; docker compose ps
logs:  ; docker compose logs -f
build: ; docker compose build
m:     ; docker compose exec web python manage.py $(c)
shell: ; docker compose exec web python manage.py shell
test:  ; docker compose exec web pytest
psql:  ; docker compose exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

.PHONY: up down stop ps logs build m shell test psql
```

Learn the full commands first. The shortcuts only help once you know what they hide.

---

## Part 8 — Production preview

Production uses the same images with a second compose file, `docker-compose.prod.yml`, built in Phase 5 (Day 105–109).

| | Development (`docker-compose.yml`) | Production (`docker-compose.prod.yml`) |
|---|---|---|
| Django server | `runserver` (auto-reload, debug pages) | `gunicorn` (several worker processes) |
| Code | Bind mount from your folder | Copied into the image at build time |
| `DEBUG` | `True` | `False` |
| React | Vite dev server | `npm run build` → static files served by nginx |
| In front of Django | Nothing | `nginx`: TLS, static files, `/api` → gunicorn, everything else → React |
| Postgres / Redis ports | Postgres on 5433 for your tools | Not published at all |
| Crash handling | You restart it | `restart: unless-stopped` |

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

---

## Part 9 — Disk cleanup

Images and build cache pile up over months.

```bash
docker system df         # what uses space
docker image prune       # remove dangling (untagged) images
docker builder prune     # remove the build cache
```

> ⚠️ `docker system prune -a --volumes` also deletes volumes, which means your database. Don't use it unless you really want to lose all data.
