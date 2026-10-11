# ADR 001: Custom fields stored in a JSONField

- **Status:** Accepted
- **Date:** 2026-10-12

## Context

Every business wants a few extra fields on contacts, companies and deals ("LinkedIn URL", "Budget", "Industry"). We can't add a database column for each customer's wish, so the values need a flexible home.

## Options

1. **JSONField** — one `custom_fields` column per table, e.g. `{"linkedin_url": "...", "budget": "5000.00"}`.
2. **EAV (Entity–Attribute–Value)** — a separate table with one row per value: `(entity_id, field_id, value)`.

## Decision

Use a `custom_fields = JSONField(default=dict)` column on Contact, Company and Deal now. Add a `CustomFieldDefinition` table later (Phase 7.3, Day 134) that describes which keys exist and their types.

## Why

- **No joins.** EAV needs one join per field to show a list with 5 custom columns; JSON is already in the row.
- **Postgres is good at JSON.** A GIN index makes `custom_fields @> {"industry": "retail"}` fast.
- **Simple now, structured later.** The definition table can be added without moving any data: values stay in the JSON under a stable `key`.

## Consequences

- The database doesn't check the types inside the JSON. Validation happens in Python (serializers built from the definitions, Day 136).
- Keys must never change after creation; labels can be renamed freely.
- Money and dates inside JSON are stored as strings (`"5000.00"`, `"2026-10-12"`), never floats.
