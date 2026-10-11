# ADR 003: Soft delete (archive) instead of real deletes

- **Status:** Accepted
- **Date:** 2026-10-12

## Context

In a CRM, a deleted record often had deals, activities and history attached. A misclick should be undoable, and reports about the past must stay correct.

## Options

1. **Hard delete** — `DELETE` the row; `on_delete` rules decide what happens to children.
2. **Soft delete** — mark the row as archived and hide it from normal queries.

## Decision

Soft delete for all domain models, through `SoftDeleteModel` in the `core` app (Day 6):

- Fields: `is_active` (default True), `archived_at`, `archived_by`.
- Methods: `archive(user)` and `restore()`.
- Managers: `objects` returns active rows only (the default); `all_objects` returns everything.
- The API's `DELETE` archives; `POST /{id}/restore/` brings a row back (ADR 005).

Users are not soft-deleted: they are disabled with `AbstractUser.is_active`.

## Why

- **Undo.** An archived contact can be restored with all its deals and activities still attached.
- **History stays true.** Reports for last quarter still count deals whose company was archived later.
- **Safe by default.** Because `objects` hides archived rows, forgetting a filter can't leak them into lists.

## Consequences

- **Watch for these gotchas:**
  - `deal.company` (a forward FK) still returns an archived company. That's usually what we want.
  - `company.contacts.all()` (a reverse relation) uses the default manager, so it hides archived contacts.
  - The Django admin must use `all_objects` if developers need to see archived rows.
- Unique fields include archived rows: an archived tag "VIP" blocks creating a new "VIP". The answer is to restore it.
- Real deletes are still possible for admin cleanup and GDPR erasure (Phase 9.2), so `on_delete` rules still matter.
