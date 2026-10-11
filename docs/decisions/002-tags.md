# ADR 002: Tags as a Tag model with many-to-many

- **Status:** Accepted
- **Date:** 2026-10-12

## Context

Companies, contacts and deals can be tagged ("VIP", "Hot lead", "Partner"). Users filter lists by tag, and admins manage the tag list.

## Options

1. **`Tag` model + `ManyToManyField`** — one shared tags table; Django creates a join table per entity.
2. **Postgres `ArrayField`** — store `["vip", "hot lead"]` directly in each row.

## Decision

A single `Tag` model (`name` unique, `color`) shared by Company, Contact and Deal, linked with `ManyToManyField`.

## Why

- **Rename once.** Renaming "Hot lead" to "Hot" is one row update. With an array, every tagged row must be rewritten.
- **No typo tags.** Users pick from existing tags, so "VIP" and "vip " can't both appear by accident.
- **Tags can carry data** (a color now, maybe a description later) and can be managed in the admin panel.
- **Easy counts.** "How many deals have this tag?" is a normal query on the join table.

## Consequences

- Filtering by tag is a join. With proper indexes (Django adds them on the join table) this is fast.
- Lists that show tags need `prefetch_related("tags")` to avoid N+1 queries.
