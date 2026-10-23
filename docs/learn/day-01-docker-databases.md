# Day 1 — Docker: Postgres & Redis containers

## What we built

Postgres (the database) and Redis (a fast in-memory store, used later for cache and Celery) running in Docker — no installing them on the laptop.

**Files:** [docker-compose.yml](../../docker-compose.yml) · [.env.example](../../.env.example) · [.gitignore](../../.gitignore)

---

## The 5 Docker ideas you need

| Idea | Simple meaning | Real-life comparison |
|------|----------------|----------------------|
| **Image** | A ready-made package: a program + everything it needs (`postgres:17-alpine`) | A recipe |
| **Container** | A running copy of an image. Throwaway: delete it, start a new one | The cooked dish |
| **Volume** | A storage folder Docker keeps **outside** the container, so data survives | The fridge — food stays after you wash the plate |
| **Port mapping** | `"5433:5432"` = your laptop's port 5433 → container's port 5432 | A door from the outside into the room |
| **Compose** | One YAML file that describes all containers and starts them together | The full menu for the day |

**The key sentence:** a *container* is temporary, a *volume* is permanent. That's why the database files live in the `postgres_data` volume.

---

## Reading docker-compose.yml (the `db` part)

```yaml
db:
  image: postgres:17-alpine          # which image to run ("alpine" = small Linux)
  environment:
    POSTGRES_DB: ${DB_NAME}          # ${...} = read the value from .env
  volumes:
    - postgres_data:/var/lib/postgresql/data   # where Postgres keeps its files → the volume
  ports:
    - "5433:5432"                    # 5433 on your laptop, because your local Postgres uses 5432
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
```

- **healthcheck** — Docker runs `pg_isready` every 5 seconds. Status becomes `healthy` only when Postgres actually accepts connections (starting ≠ ready).
- **`$$`** — means "don't fill this in now"; the variable is read *inside* the container when the check runs.
- **Redis has no `ports`** — only other containers use it, over Docker's private network. (Your laptop's own Redis already uses 6379.)

---

## Secrets: `.env` vs `.env.example`

| File | Contains | In git? |
|------|----------|---------|
| `.env` | Real passwords and the secret key | ❌ Never (listed in `.gitignore`) |
| `.env.example` | Same keys, fake values | ✅ Yes — shows others which settings exist |

If a password ever reaches git, consider it leaked — git history keeps it forever.

---

## Commands

| Command | What it does |
|---------|--------------|
| `docker compose up -d` | Start all services in the background (`-d` = detached) |
| `docker compose ps` | List containers and their status (`healthy`?) |
| `docker compose logs db` | Show a service's output — first place to look when something fails |
| `docker compose exec db psql -U crm_user -d crm_db` | Open a Postgres prompt inside the running `db` container |
| `docker compose exec redis redis-cli ping` | Should answer `PONG` |
| `docker compose down` | Stop and delete containers — **volumes stay** |
| `docker compose down -v` | Same, **and delete volumes** → all data gone ⚠️ |

**The volume experiment:** create a table → `down` → `up` → table still there. `down -v` → `up` → table gone. This proves where data really lives.

---

## Check yourself

<details>
<summary>1. You run <code>docker compose down</code>. Is your data gone?</summary>

No. `down` deletes containers, not volumes. Only `down -v` deletes the volume.
</details>

<details>
<summary>2. Why is the port <code>5433:5432</code> and not <code>5432:5432</code>?</summary>

Your laptop already runs its own Postgres on 5432. Two programs can't listen on the same port, so the container is reached through 5433 from outside. Inside Docker's network it's still 5432.
</details>

<details>
<summary>3. Why does Redis have no <code>ports</code> section?</summary>

Only other containers (Django, later Celery) talk to it, and they use Docker's internal network. Publishing a port is only needed for access from your laptop.
</details>
