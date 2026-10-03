# CRM Project — Daily Breakdown (Part A + Part B)

**Source:** [CRM-PROJECT-ROADMAP.md](CRM-PROJECT-ROADMAP.md) — this file only expands Part A (A1–A6) and Part B (B1–B6) into day-by-day tasks. Everything else (Architecture Plan, Full Feature Set #1–24, sequencing) is unchanged — go back to the source file for that.

**How to use this:** Each week below assumes ~5 working days. Treat day boundaries as a guide, not a hard wall — if Day 2's task bleeds into Day 3, that's fine; don't start a new week until the prior week's mini-project/deliverable is actually done and reviewed (per the roadmap's working agreement).

---

## Part A — Backend: CRM Domain (Django + DRF)

### A1 — Domain Modeling

- **Day 1 — Prototype without Django:** Sketch `Contact`, `Company`, `Deal`, `PipelineStage`, `Activity`, `Task` as plain dataclasses/Pydantic models first. No ORM yet — just get the fields and relationships right on paper/code.
- **Day 2 — Custom fields decision:** Write out the `JSONField` vs EAV-table tradeoff for custom fields as a short doc/comment. Pick one and justify it in writing (this decision affects A1 forward and #8 later).
- **Day 3 — Django models:** Convert the Day 1 prototypes into real Django models in a new `crm_core` app. Add tagging (contacts/deals) and the soft-delete pattern (`is_active` flag) with a first-pass audit trail hook.
- **Day 4 — Migrations, admin, seed data:** Write migrations, register models in Django admin, and build a seed-data management command (`python manage.py seed_demo_data` or similar) producing enough fake data to work with in later weeks.
- **Day 5 — Docker from day one:** Stand up `docker-compose.yml` with at minimum `web`, `postgres`, `redis`. Confirm `docker compose up` gives a working dev environment. Deliverable check: `crm_core` app with migrations, admin-registered models, seed command, and Docker Compose all working together.

### A2 — Pipeline & Deals Logic

- **Day 1 — PipelineStage model:** Build `PipelineStage` as an ordered, admin-configurable model (not a hardcoded enum). Seed a default stage set (e.g. New → Qualified → Proposal → Won/Lost).
- **Day 2 — Stage transition logging:** Add `DealStageHistory` and make stage transitions append-only/immutable — never overwrite prior history.
- **Day 3 — Concurrency-safe move_stage():** Write `deals.services.move_stage()` using `select_for_update()` + `atomic()` so two reps can't corrupt the same deal's stage simultaneously. Write a test that actually exercises the race condition.
- **Day 4 — Custom managers/querysets:** Implement `Deal.objects.open()`, `.won()`, `.lost()`, `.stale(days=N)`.
- **Day 5 — Win/loss + value history:** Add win/loss reason tracking and deal-value history (appended, not overwritten, same pattern as stage history). Deliverable check: `deals` app with custom managers and a tested `move_stage()` service method.

### A3 — Activities, Reminders & Celery

- **Day 1 — Activity model design:** Design `Activity` (calls/emails/notes/meetings) via `activity_type` + `related_object`. Decide generic FK vs explicit FKs and write down why.
- **Day 2 — Task model + relations:** Build the `Task` model tied to Activities/Deals/Contacts as needed.
- **Day 3 — Celery setup:** Wire Celery into the Docker Compose stack (worker + beat containers), confirm a trivial task round-trips through Redis.
- **Day 4 — Scheduled jobs:** Implement Celery Beat jobs for overdue-task alerts and "no activity in N days" nudges.
- **Day 5 — Retry-safe sending + tests:** Apply the core roadmap's retry-decorator pattern to notification sending. Write `pytest` tests with a mocked broker. Deliverable check: `activities` app + working Celery task(s), tested.

### A4 — Reporting & Aggregation

- **Day 1 — Pipeline value by stage:** Build the first aggregation endpoint using `annotate`/`aggregate`/`F()` — zero N+1 from the start.
- **Day 2 — Conversion rate + rep leaderboard:** Add the remaining 2–3 aggregation endpoints.
- **Day 3 — Lock in query counts:** Add `assertNumQueries` tests for every report endpoint so future changes can't silently reintroduce N+1.
- **Day 4 — Deliberately break it, then fix it:** Introduce an N+1 on purpose in one endpoint, confirm it via `django-debug-toolbar`/query logging, then fix it and confirm the test catches the regression.
- **Day 5 — Cleanup + review:** Polish serializer output, review all 3–4 endpoints together. Deliverable check: `reports` app with query-count-locked tests.

### A5 — DRF API Layer

- **Day 1 — Serializers:** Build `ModelSerializer`s including at least one nested writable serializer (e.g. create a `Deal` with an initial `Activity` in one payload).
- **Day 2 — ViewSets & routing:** Wire up `ViewSet` + `DefaultRouter`, add `SerializerMethodField`s for computed fields (days-in-stage, etc.).
- **Day 3 — Auth + minimal object-level permissions:** Add JWT auth (`simplejwt`) and the minimal version of object-level permissions (rep sees only assigned contacts/deals unless manager role). Note in comments that the full admin-configurable system arrives later as `access_control` (#24).
- **Day 4 — Filtering, pagination, docs:** Add `django-filter` for list filtering/search/ordering, cursor pagination on activity timelines, and wire up `drf-spectacular` for Swagger docs.
- **Day 5 — API test suite:** Build the `factory_boy`-backed pytest-django suite using `APIClient` covering the endpoints built this week. Deliverable check: full REST API surface, Swagger UI live, tests passing.

### A6 — Productionization

- **Day 1 — Env-based settings:** Move settings to `.env` via `django-environ` (or the hand-rolled loader per the package-philosophy table).
- **Day 2 — Seed data + install docs (draft):** Finalize the demo-data seed command, start drafting install docs.
- **Day 3 — Structured error handling:** Add a custom DRF exception handler producing consistent structured error responses.
- **Day 4 — Security pass:** Audit every writable serializer for `fields = '__all__'` (mass-assignment risk), confirm `DEBUG=False` checklist, audit secrets/env handling.
- **Day 5 — Final review:** Walk the whole backend end-to-end as if handing it to a frontend dev or shipping API-only. Deliverable check: installable, documented backend.

---

## Part B — Frontend: React + TypeScript Dashboard

### B1 — TypeScript Foundations for React Devs

- **Day 1 — interface vs type, structural typing:** Work through both, connect to the Python `Protocol` comparison from the core roadmap.
- **Day 2 — Generics:** Build a generic `useFetch<T>` hook and a generic `<Table<T>>` component skeleton.
- **Day 3 — Discriminated unions:** Rewrite a loading/error/success state (that you'd normally model with booleans) as a discriminated union.
- **Day 4 — unknown vs any, narrowing:** Practice type guards and narrowing on a small piece of real or sample data.
- **Day 5 — Mini-project:** Convert a small existing JS/React component you've written before into strict-mode TS, using a discriminated union for its loading/error/success state instead of multiple booleans.

### B2 — Typing the API Layer

- **Day 1 — Generate/hand-write types:** Point `openapi-typescript` (or hand-write) at the `drf-spectacular` schema from A5, producing types matching the DRF serializers.
- **Day 2 — Typed API client:** Build a fetch/axios wrapper with generic request/response typing.
- **Day 3 — React Query setup:** Wire up TanStack Query with typed query keys.
- **Day 4 — Typed mutations:** Add typed mutations (create/update deal) on top of the Day 3 setup.
- **Day 5 — Mini-project:** A typed `useDeals()` / `useCreateDeal()` hook pair backed by React Query, with zero `any` in the request/response path, verified against the live DRF API.

### B3 — Forms & Validation

- **Day 1 — Zod schema:** Write a `zod` schema for the "New Deal" form, infer the TS type via `z.infer`.
- **Day 2 — react-hook-form wiring:** Wire the schema into `react-hook-form`, get validation errors rendering.
- **Day 3 — Nested writable form:** Extend the form to submit deal + initial activity in one payload, matching A5's nested serializer.
- **Day 4 — Error/edge case handling:** Handle server-side validation errors surfaced back into the form.
- **Day 5 — Mini-project polish:** Finish and review the "New Deal" form end-to-end against the live API.

### B4 — Pipeline Board & State

- **Day 1 — Static board layout:** Build the Kanban-style pipeline view (columns per `PipelineStage`, no drag yet), backed by A2's data via React Query.
- **Day 2 — Drag-and-drop:** Add drag-and-drop between stage columns (evaluate native HTML5 drag vs a small package like `@dnd-kit/core` per the package-philosophy table).
- **Day 3 — Context + useReducer state:** Add plain Context API + `useReducer` for UI state (modal open/close, active filters, selected deal) — no Zustand/Redux yet. Type actions with a discriminated union (reuse B1's pattern).
- **Day 4 — Optimistic updates:** Implement optimistic UI update on stage-drag with typed mutation rollback on failure.
- **Day 5 — Mini-project:** Drag a deal card between stage columns, optimistic UI update, rollback + typed error toast on API failure.

### B5 — Dashboard & Reporting Views

- **Day 1 — Typed chart data shapes:** Define TS types for the data feeding A4's reporting endpoints.
- **Day 2 — Generic table component:** Build a sortable/filterable table component with generics, reusable across contact/deal lists.
- **Day 3 — Pipeline-value-by-stage view:** Render this chart/view on the dashboard.
- **Day 4 — Rep leaderboard view + route splitting:** Render the leaderboard, add route-level code splitting and typed route params.
- **Day 5 — Mini-project:** A dashboard page rendering pipeline-value-by-stage and rep-leaderboard from A4's endpoints, fully typed end-to-end.

### B6 — Testing & Build

- **Day 1 — Typed component tests setup:** Wire up Vitest/React Testing Library with typed test fixtures matching B2's API types.
- **Day 2 — Write tests:** Cover the pipeline board, forms, and dashboard components built in B3–B5.
- **Day 3 — Production build config:** Set up the production build and environment config.
- **Day 4 — Deploy-ready bundle:** Produce a deploy-ready static bundle, verify it against the Docker `frontend` container from the Architecture Plan.
- **Day 5 — Final review:** Deliverable check — full CRM dashboard (contacts, deals pipeline, activities timeline, reports), typed end-to-end against the DRF API, tested, buildable.

---

## Working agreement (unchanged from source roadmap)

- No new day starts until the prior day's task is actually done — don't stack unfinished work forward "to catch up later."
- No new week starts until the prior week's mini-project is reviewed.
- Day boundaries are pacing guidance, not a hard deadline — if something takes 2 days instead of 1, that's fine; don't cut a task short just to stay on the day-count.
