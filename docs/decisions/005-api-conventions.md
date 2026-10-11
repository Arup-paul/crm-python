# ADR 005: REST API conventions

- **Status:** Accepted
- **Date:** 2026-10-12

## Context

The React app, tests and (later) outside integrations all talk to the API. Every endpoint should look and behave the same, so the frontend needs one client, not one per endpoint.

## Decision

**URLs**
- Versioned: everything under `/api/v1/`. Health check stays unversioned at `/api/health/`.
- Plural nouns, kebab-case: `/api/v1/contacts/`, `/api/v1/pipeline-stages/`.
- Actions that aren't plain create/update are `POST` sub-paths: `/api/v1/deals/{id}/move-stage/`, `/api/v1/deals/{id}/change-value/`.

**JSON**
- Field names in `snake_case`, the same as the Django models.
- Datetimes in ISO 8601 UTC: `"2026-10-12T09:30:00Z"`. Dates as `"2026-10-12"`.
- Money as strings: `"12500.00"` (DRF's default for `DecimalField`), never floats.
- Related objects are read as `{"id": 3, "name": "ABC Traders"}` and written as a plain id: `"company": 3`.

**Pagination** — one shape for every list:
```json
{ "count": 120, "next": "…?page=3", "previous": "…?page=1", "results": [ … ] }
```
Page-number pagination, 25 per page. Cursor-paginated timelines (Day 59) use the same keys without `count`.

**Errors** — one shape for every error:
```json
{
  "error": {
    "code": "validation_error",
    "message": "Some fields are invalid.",
    "fields": { "email": ["Enter a valid email address."] }
  }
}
```
- `code` is a stable machine-readable string: `validation_error`, `not_authenticated`, `permission_denied`, `not_found`, `throttled`, `server_error`.
- `fields` is present only for validation errors.

**Delete**
- `DELETE /api/v1/contacts/{id}/` archives the record (ADR 003) and returns 204.
- `POST /api/v1/contacts/{id}/restore/` brings it back.

## Why

- **One client.** The frontend's `ApiError` (Day 12+) reads `error.code` and `error.fields` the same way everywhere.
- **No surprises with money and time.** Strings for decimals avoid float rounding; UTC avoids timezone bugs.
- **Versioning from day one** lets a future `/api/v2/` change things without breaking v1 users.
- **snake_case** matches Python, so serializers need no renaming layer.

## Consequences

- A custom DRF exception handler (Day 7) converts every error into this shape, including 401, 404 and 429.
- The frontend uses snake_case keys as they come; no camelCase conversion.
