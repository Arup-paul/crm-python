# Day 3 — Domain map

## What we built

A written plan of every table in the CRM, *before* writing models: [docs/domain.md](../domain.md) — 11 entities, their fields, the relationships, and an ER diagram.

**Why plan first?** Changing a model after it has data means migrations and data fixes. Changing a line in a document is free.

---

## Relationship types

| Type | Example | Where the link lives | Django field |
|------|---------|----------------------|--------------|
| **One-to-many** | One Company → many Contacts | On the "many" side: `Contact.company` | `ForeignKey` |
| **Many-to-many** | Contacts ↔ Tags | In a hidden join table Django creates | `ManyToManyField` |
| **One-to-one** | (not used yet) | Either side | `OneToOneField` |

**Trick to find the FK side:** ask "does one X have many Y?" → the FK goes on Y.

---

## Choosing field types

| Data | Field | Why |
|------|-------|-----|
| Money | `DecimalField(max_digits=14, decimal_places=2)` | `float` can't store money exactly: `0.1 + 0.2 = 0.30000000000000004` |
| Phone | `CharField(30)` | Not a number: keeps `+880` and leading zeros |
| A day (close date) | `DateField` | No time needed |
| A moment (call happened) | `DateTimeField` | Exact time, stored in **UTC** |
| Fixed list (role, type) | `CharField` + `choices` | Only allowed values; dropdown in forms |
| Flexible extras | `JSONField(default=dict)` | Custom fields (ADR 001) |

**UTC:** `USE_TZ = True` stores every datetime in UTC. The frontend converts to the user's local time. One timezone in the database = no confusion.

---

## `null` vs `blank` — the classic confusion

| | Rule for | Means |
|---|---|---|
| `null=True` | The **database** | The column may store `NULL` |
| `blank=True` | **Forms / validation** | The field may be left empty |

**Convention:**
- Optional **text** → `blank=True` only. Empty is stored as `""`, so there's only one kind of "empty".
- Optional **FK, number, date** → `null=True, blank=True`. These have no "empty string", so they need `NULL`.

---

## `on_delete` — what happens to children when the parent is deleted

| Option | Effect | We use it for |
|--------|--------|---------------|
| `CASCADE` | Delete the children too | History rows, activities (meaningless without their record) |
| `PROTECT` | Block the delete | Owners, pipeline stages (reassign first) |
| `SET_NULL` | Keep the child, clear the link | Contact → Company (the person still exists) |

Because we **archive** instead of deleting (ADR 003), real deletes are rare — but the rule must still be chosen.

---

## `default=dict`, not `default={}`

`{}` is created **once** and shared by every row — change one, and you've changed the default for all. `dict` is a function: Django calls it to make a **fresh** `{}` for each row.

---

## Mermaid ER diagram symbols

```
||  exactly one        o|  zero or one
|{  one or many        o{  zero or many
```

`COMPANY |o--o{ CONTACT` = a contact has zero or one company; a company has zero or many contacts.

---

## Check yourself

<details>
<summary>1. Why is <code>DealStageHistory.from_stage</code> nullable?</summary>

A brand-new deal has no previous stage. Its first history row goes from "nothing" to "New".
</details>

<details>
<summary>2. Why is <code>expected_close_date</code> a DateField but <code>occurred_at</code> a DateTimeField?</summary>

"Expected to close on 15 Nov" is a day. "Called at 14:30" is an exact moment.
</details>

<details>
<summary>3. Contact email is optional and not unique. Why?</summary>

Some contacts only have a phone number, and colleagues can share one office email. Duplicates get a warning in the UI later instead of being blocked.
</details>
