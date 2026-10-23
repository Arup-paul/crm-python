# Day 4 — Design decisions (ADRs)

## What we built

Five short **Architecture Decision Records** in [docs/decisions/](../decisions/).

**What's an ADR?** A one-page note: *the problem → the options → what we chose → why → the cost*. Six months later, when you think "why didn't we just use X?", the answer is already written — no re-arguing.

---

## The five decisions in one table

| ADR | Question | Choice | One-line reason |
|-----|----------|--------|-----------------|
| [001](../decisions/001-custom-fields.md) | Where do custom fields go? | `JSONField` on each table | No join per field; Postgres indexes JSON well |
| [002](../decisions/002-tags.md) | How are tags stored? | `Tag` model + many-to-many | Rename once; no typo duplicates |
| [003](../decisions/003-soft-delete.md) | Delete or archive? | Archive (`is_active=False`) | Undo is possible; past reports stay correct |
| [004](../decisions/004-activity-relations.md) | How does an activity point to its record? | 3 nullable FKs + "at least one" rule | Real FKs; one call can link a contact *and* a deal |
| [005](../decisions/005-api-conventions.md) | What does the API look like? | `/api/v1/`, snake_case, one error shape | The frontend needs only one API client |

---

## The ideas behind them

### JSON vs EAV (ADR 001)

```
JSON:  contacts | id=42 | custom_fields = {"budget": "5000.00", "linkedin": "..."}

EAV:   values   | entity_id=42 | field_id=8 | value="5000.00"
                | entity_id=42 | field_id=7 | value="..."
```

- JSON: one row, no joins. EAV: one row *per value* — 10,000 contacts × 50 fields = 500,000 rows.
- Values are stored under a stable **key** (`"budget"`), never the definition's id — readable and portable.
- Cost: the database doesn't check types inside JSON → Python validates (Day 136).

### Soft delete (ADR 003)

- `objects` → active rows only (default, safe). `all_objects` → everything.
- **Gotcha:** `deal.company` still returns an archived company; `company.contacts.all()` hides archived contacts.

### Explicit FKs vs generic FK (ADR 004)

- Generic FK = `content_type` + `object_id`: two numbers the database can't check, and only one target.
- Explicit FKs = real database links, simple queries, several targets at once.

### API conventions (ADR 005)

One error shape for **every** error:
```json
{"error": {"code": "validation_error", "message": "...", "fields": {"email": ["..."]}}}
```
Money as strings (`"12500.00"`), datetimes in UTC (`"2026-10-12T09:30:00Z"`), `DELETE` = archive.

---

## Why roles are static for now

`User.role` is a fixed list (admin / manager / rep). Dynamic roles need a permission system (which role can do what, with own / team / all scope) — and there's nothing to give permissions on until contacts and deals exist. Planned for **Phase 7.5 (Day 150–165)**, migrated with the *expand → contract* pattern.

---

## Check yourself

<details>
<summary>1. What are the two must-have sections of every ADR?</summary>

**Decision** and **Why**. Options and consequences help, but without "why" the record is useless later.
</details>

<details>
<summary>2. If a customer wants 500 custom fields, is JSON still OK?</summary>

Yes, better than EAV. Mind the costs: big JSON is read whole, so don't send all fields to list pages; add a per-entity limit (e.g. 200) in Phase 7.3.
</details>

<details>
<summary>3. Why does the API return money as a string?</summary>

JSON numbers are floats in JavaScript, which can't store money exactly. A string keeps `"12500.10"` precise.
</details>
