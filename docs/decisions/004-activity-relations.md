# ADR 004: Activities and tasks use explicit nullable FKs

- **Status:** Accepted
- **Date:** 2026-10-12

## Context

An activity (call, email, meeting, note) or a task can be about a contact, a company, a deal, or several of them at once: "Called Rahim (contact) about the ERP deal (deal)".

## Options

1. **Explicit FKs** — three nullable columns: `contact`, `company`, `deal`, plus a `CheckConstraint` that at least one is set.
2. **Generic FK** — Django's `content_type` + `object_id`, pointing at any model.

## Decision

Explicit nullable FKs on `Activity` and `Task`. `Activity` has a `CheckConstraint` requiring at least one target; a `Task` may have none.

## Why

- **Real foreign keys.** The database guarantees the target exists and applies `on_delete`. A generic FK is just two numbers the database can't check.
- **Several targets at once.** One call can be linked to both the contact and the deal. A generic FK points at exactly one object.
- **Simple, fast queries.** `Activity.objects.filter(deal=deal)` and `select_related("contact", "deal")` work normally and use plain indexes.

## Consequences

- Adding a new target type (e.g. a custom object later) means a migration: a new column and an updated constraint.
- Comments (Phase 8.6) will use a generic FK instead, because they attach to many more kinds of objects and only ever to one. That ADR will compare the two.
