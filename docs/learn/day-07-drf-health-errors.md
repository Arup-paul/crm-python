# Day 7 — DRF setup, health check & error shape

## Today in one minute

- We installed **Django REST framework (DRF)**. It lets Django answer with **JSON** (data) instead of HTML pages, which is what the React app needs.
- We made **`/api/health/`**, a page that says whether the database and Redis are working.
- We made **every error look the same**, so React only needs one way to read errors.

---

## The big picture

Until today, Django only made web pages (like `/admin/`). From now on, it also answers **API requests**:

```
React app  ──asks──▶  /api/...  ──▶  Django + DRF  ──answers──▶  JSON
                                                              {"db": "ok"}
```

> **Think of it like a restaurant:** React is the customer, the API is the waiter, and JSON is the dish on the plate. Today we hired the waiter (DRF) and taught them how to say sorry politely when something goes wrong (the error shape).

---

## Part 1 — Installing new packages

**What we did:** added two lines to [requirements.txt](../../backend/requirements.txt):

```
djangorestframework>=3.18,<3.19    ← makes the API
redis>=8.0,<9                      ← lets Python talk to Redis
```

**The important lesson:** packages are installed **inside the Docker image**, so after changing `requirements.txt` you must **rebuild**:

```bash
docker compose build web     # make a new image with the new packages
docker compose up -d         # start the container from the new image
```

| You changed… | What to do |
|---|---|
| A `.py` file | Nothing. Django reloads by itself. |
| `requirements.txt` | `build`, then `up -d` |

> ⚠️ `docker compose restart web` is **not** enough. It restarts the **old** image, which doesn't have the new package.

💡 VS Code may say *"Package Django is not installed"*. Ignore it. VS Code is looking at your computer, but the packages are inside the container.

---

## Part 2 — DRF settings (the house rules)

In [settings.py](../../backend/config/settings.py) we gave DRF some rules that apply to **every** API page:

| Rule | In plain words |
|---|---|
| **Login required** | Every API page is locked unless we unlock it on purpose. Forgetting means locked, never leaked. |
| **25 per page** | A list of 10,000 contacts comes in pages of 25, not all at once |
| **Browsable API only in development** | On your laptop you get a nice clickable page. On the real server, only JSON. |
| **Our error handler** | Every error uses our shape (Part 4) |

> **Think of it like an office building:** every door is locked by default. To make a door public, you must put up a sign saying "open to everyone" (`AllowAny`).

---

## Part 3 — The health check

**What is it?** A page that answers one question: *"Is everything working?"*

**Who uses it?** Monitoring tools (and Docker on the real server). They visit it every few seconds. If the answer is bad, someone gets an alert.

**What it checks:**
- **Database:** asks Postgres the simplest question possible (`SELECT 1`)
- **Redis:** says "PING" and waits for "PONG"

**What it answers:**

| Situation | Answer |
|---|---|
| Everything works | ✅ `200` `{"db": "ok", "redis": "ok"}` |
| Redis is down | ❌ `503` `{"db": "ok", "redis": "error"}` |

**Why it's public:** a monitoring tool has no username or password, so this one door is unlocked (`AllowAny`).

**Why 503?** The number tells the monitoring tool "something is broken" without it having to read the text.

The code is in [core/views.py](../../backend/core/views.py) and the URL is in [config/urls.py](../../backend/config/urls.py).

### 🧪 Try it yourself

```bash
curl http://localhost:8000/api/health/          # should say ok, ok

docker compose stop redis                        # break Redis on purpose
curl http://localhost:8000/api/health/          # now redis says "error"

docker compose start redis                       # fix it again
```

You can also just open http://localhost:8000/api/health/ in your browser.

---

## Part 4 — One shape for every error

**The problem:** without this, DRF sends errors in different shapes, so React would need different code for each one.

**The fix:** every error now looks like this:

```json
{
  "error": {
    "code": "not_found",
    "message": "Not found."
  }
}
```

And when a form has mistakes, it also says **which field** is wrong:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Some fields are invalid.",
    "fields": {
      "email": ["Enter a valid email address."]
    }
  }
}
```

| Part | Who reads it |
|---|---|
| `code` | **The React app.** It's a fixed word like `not_found` or `not_authenticated`, and it never changes. |
| `message` | **The human.** Plain text that can be reworded or even translated to Bangla later. |
| `fields` | **The form.** Shows each error under the right input box. |

**How it works:** when anything goes wrong in an API page, DRF calls our function in [core/exceptions.py](../../backend/core/exceptions.py), and it repackages the error into our shape.

> **Think of it like a complaints desk:** whatever the problem is, the customer always gets the same printed form back, with a problem code, an explanation, and which box they filled in wrong.

**Two extra things it does:**
- **A real bug in our code?** On your laptop you see Django's full error page (to help you fix it). On the real server, users only see "Something went wrong," and the details go to the logs. Users should never see our code.
- **Errors from services** (Day 6) are turned into the same shape too.

### Unknown API pages

Before today, visiting a wrong address like `/api/v1/nothing/` gave an **HTML** page, which React can't read. Now it gives:

```json
{"error": {"code": "not_found", "message": "Not found."}}
```

This "catch-all" line sits at the **very bottom** of [config/urls.py](../../backend/config/urls.py). Django checks addresses from top to bottom, so if this line moved up, it would catch real pages too.

### 🧪 Try it yourself

```bash
curl http://localhost:8000/api/v1/nothing/           # not_found
curl -X POST http://localhost:8000/api/health/       # method_not_allowed (health only allows GET)
```

---

## Part 5 — A small surprise: 401 or 403?

When you're **not logged in**, the API can answer with either number:

| Number | Means |
|---|---|
| **401** | "Who are you? Please log in." |
| **403** | "I know who you are, but you're not allowed." |

Today a logged-out visitor gets **403**, even though "not logged in" should really be 401. That's because today's login method uses cookies, and the 401 rule requires telling the visitor *how* to log in, which cookies can't do.

**Tomorrow (Day 8)** we add token login (JWT), and it will correctly say **401**.

**Why this doesn't matter for React:** the `code` is `not_authenticated` both times. React checks the **code**, not the number. That's exactly why we have codes.

---

## Problems we hit

| What happened | Why | Fix |
|---|---|---|
| VS Code said "package not installed" | It looks at your computer, not the container | Ignore it |
| Test pages answered 403 instead of showing the error we wanted to test | Every page needs login by default, and the test wasn't logged in | Logged in for the test. It also proved the "locked by default" rule works. |
| Logged out gave 403, not 401 | The cookie login can't say *how* to log in | Normal for now; fixed on Day 8 |

---

## New words

| Word | Meaning |
|---|---|
| **API** | A way for one program (React) to ask another (Django) for data |
| **JSON** | The text format for that data: `{"name": "Arup"}` |
| **DRF** | Django REST framework, the add-on that makes Django an API |
| **Endpoint** | One API address, like `/api/health/` |
| **Status code** | The number on every answer: `200` OK, `400` bad input, `401` log in, `403` not allowed, `404` not found, `503` broken |
| **Decorator** | The `@something` line above a function. It adds extra behaviour, like "public" or "GET only". |
| **Exception** | Python's way of saying "something went wrong, stop here" (`raise ...`) |
| **Exception handler** | The function that decides what the user sees when an exception happens |
| **Image rebuild** | Making a new Docker image so it includes new packages |

---

## Files changed today

| File | What changed |
|---|---|
| [requirements.txt](../../backend/requirements.txt) | Two new packages |
| [config/settings.py](../../backend/config/settings.py) | DRF added, its rules, `REDIS_URL` |
| [core/views.py](../../backend/core/views.py) | The health check and the "unknown page" view |
| [core/exceptions.py](../../backend/core/exceptions.py) | The error handler (new file) |
| [config/urls.py](../../backend/config/urls.py) | `api/health/` and the catch-all at the bottom |

---

## Check yourself

<details>
<summary>1. You added a package and ran <code>docker compose restart web</code>. Why doesn't it work?</summary>

`restart` uses the old image, which doesn't have the package. Run `docker compose build web`, then `docker compose up -d`.
</details>

<details>
<summary>2. Why is the health check public when everything else needs a login?</summary>

Monitoring tools have no username or password. And the page only says "ok" or "error", so nothing secret is shown.
</details>

<details>
<summary>3. Why does every error have a <code>code</code> as well as a <code>message</code>?</summary>

The code is a fixed word for the React app to check. The message is for humans and can be reworded or translated without breaking anything.
</details>

<details>
<summary>4. Why must the catch-all line stay at the bottom of <code>urls.py</code>?</summary>

Django checks addresses from top to bottom and stops at the first match. The catch-all matches every `/api/` address, so anything below it would never be reached.
</details>
