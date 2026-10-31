# Coding Standards: Brightloop Subscription Management System

**Stack:** Django · PostgreSQL · Vercel
**Audience:** Human developers and AI coding assistants. AI tools must follow this file on every task.
**Companion doc:** `REQUIREMENTS.md` is the source of truth for *what* to build. This file defines *how*.

---

## 0. How the AI Must Work

1. Read `REQUIREMENTS.md` and this file before writing code.
2. Build only what the task asks for. Do not add features, abstractions, or files that were not requested.
3. If a requirement is ambiguous or marked as an Open Item, state the assumption in the PR notes. Do not silently choose.
4. After generating code, complete the **Self-Review Checklist** (Section 9) and include it in the response.
5. Never invent library names, Django APIs, or settings. If unsure, say so.

---

## 1. File and Component Structure

### 1.1 Project layout

```
brightloop/
├── manage.py
├── config/                  # project settings and wiring only
│   ├── settings/
│   │   ├── base.py
│   │   ├── local.py
│   │   └── production.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── accounts/            # users, roles, auth, password reset
│   ├── catalog/             # products, variants, taxes, payment terms
│   ├── plans/               # plans, quotation templates
│   ├── subscriptions/       # subscriptions, lines, lifecycle, proration
│   ├── billing/             # invoices, billing runs, scheduler jobs
│   ├── discounts/           # discount rules, redemptions, stacking engine
│   ├── payments/            # payments, PaymentProvider, mock gateway
│   ├── reports/             # dashboard queries
│   └── notifications/       # email sending, templates, dunning
├── templates/
├── static/
├── tests/                   # or tests/ inside each app
├── requirements/
│   ├── base.txt
│   ├── local.txt
│   └── production.txt
├── vercel.json
└── CODING_STANDARDS.md
```

### 1.2 Inside each app

```
apps/<name>/
├── models.py          # data and invariants only
├── services.py        # business logic (write operations)
├── selectors.py       # read/query logic (complex queries, reports)
├── views.py           # thin: parse request, call service, return response
├── forms.py / serializers.py
├── permissions.py     # role checks
├── urls.py
├── admin.py
├── tasks.py           # scheduled/background entry points (call services)
├── tests/
└── migrations/
```

### 1.3 Rules
- **Views are thin.** No business logic in views, templates, or serializers.
- **Business logic lives in `services.py`.** Example: `billing.services.generate_invoice_for_subscription(subscription, period)`.
- **Complex reads live in `selectors.py`**, not scattered in views.
- **Models hold fields, constraints, and simple properties.** No external calls (email, payment) inside models or `save()`.
- **No circular imports.** Dependency direction: `views → services → models`. Apps may depend on `accounts` and `catalog`, but `catalog` must not import from `billing`.
- One class or one cohesive set of functions per file section. Split files that exceed ~400 lines.
- Names: `snake_case` for functions and variables, `PascalCase` for classes, `UPPER_SNAKE` for constants. Names describe intent (`apply_stacked_discounts`, not `process`).

---

## 2. State Management

Django is server-rendered, so "state" here means **server and data state**, plus any UI state if a frontend layer is used.

### 2.1 Source of truth
- **PostgreSQL is the single source of truth.** No in-memory globals, module-level caches, or local files that hold business state. Vercel functions are stateless and may run in parallel or be recycled at any time.
- No reliance on Django sessions stored in local memory or files. Use database-backed sessions or signed cookies.

### 2.2 Lifecycle state machines
Subscription and invoice statuses follow `REQUIREMENTS.md` Section 7.

- Define statuses as `TextChoices` enums, not free strings.
- **All transitions go through one service function** (e.g., `subscriptions.services.transition(subscription, to_status, actor)`). Never assign `subscription.status = ...` directly elsewhere.
- Allowed transitions live in a single dictionary. Invalid transitions raise a domain error.
- Every transition writes an `AuditLog` entry (user, from, to, timestamp).

### 2.3 Transactions and concurrency
- Wrap multi-step writes in `transaction.atomic()`.
- Use `select_for_update()` when changing a subscription, invoice, or discount redemption that could be touched by two requests or jobs at once.
- **Billing idempotency is enforced by the database:** a `UniqueConstraint` on `(subscription, billing_period)` for invoices. Code must handle the `IntegrityError` gracefully (skip and log), not rely on a pre-check alone.
- Scheduled jobs must be safe to re-run (see Section 8).

### 2.4 Money and derived state
- Use `DecimalField` (e.g., `max_digits=12, decimal_places=2`). **Never `float`.**
- Keep one rounding helper (`money.round()`) and use it everywhere (see Open Item J).
- Totals on invoices are stored at confirmation time. Do not recompute historical invoices from current prices.

### 2.5 Frontend state (if applicable)
- Prefer server-rendered templates with small, targeted JS (e.g., HTMX/Alpine). Do not introduce a SPA framework unless the task requires it.
- Keep client state minimal and disposable. The server is authoritative.

---

## 3. Unused Imports and Dead Code

- **No unused imports, variables, functions, classes, URLs, templates, or settings.** Remove them in the same change that makes them unused.
- No commented-out code blocks. Version control is the history.
- No placeholder functions (`pass`, `TODO` stubs) unless the task explicitly asks for a scaffold, in which case each stub must be listed in the PR notes.
- No leftover debug code: `print()`, `breakpoint()`, `pdb`, stray `console.log`.
- No `from module import *`.
- Import order: standard library → third party → Django → local apps, one blank line between groups.
- Tooling (must pass before code is accepted):
  - `ruff check .` (lint, unused imports, import order)
  - `ruff format .` or `black .` (formatting)
  - `python manage.py makemigrations --check --dry-run` (no missing migrations)
  - Optional: `vulture` to detect dead code

---

## 4. Dependencies

- **Prefer Django and the standard library.** Add a package only when it clearly saves meaningful effort and is well maintained.
- Before adding any dependency, the AI must state: what it is for, why Django/stdlib is not enough, and its maintenance status.
- Pin exact versions in `requirements/*.txt`. Separate `base`, `local` (dev/test tools), and `production`.
- Do not add overlapping packages (two HTTP clients, two task libraries).
- Do not add a dependency for a single small function.

**Approved baseline:**

| Purpose | Package |
|---|---|
| Framework | `Django` (current LTS) |
| Database driver | `psycopg[binary]` (v3) |
| Config / env | `django-environ` or `python-decouple` |
| Static files on serverless | `whitenoise` |
| Lint / format | `ruff` |
| Tests | `pytest`, `pytest-django`, `factory-boy` |
| API (only if needed) | `djangorestframework` |
| PDF invoices (when required) | `weasyprint` or `reportlab` (confirm Vercel size limits first) |

**Vercel-specific constraints**
- Serverless bundles have a size limit. Avoid heavy packages and check bundle size when adding dependencies.
- Packages that need system libraries (some PDF/imaging tools) may not run on Vercel. Verify before adopting.

---

## 5. Avoid Over-Engineering

- Solve the current requirement, not hypothetical future ones.
- No generic frameworks, plugin systems, or abstract base classes unless at least **two** concrete uses exist today.
- Exceptions that are *required by the requirements*: the `PaymentProvider` interface (real vs. mock gateway) and email/scheduler boundaries (NFR-9). Keep them as small as possible.
- No microservices, message queues, or event buses. A modular monolith is the design.
- No premature caching. Measure first (NFR-1), then add indexes or caching where data shows a need.
- Prefer Django built-ins: `User` model extension, `permissions`, `forms`, `admin`, `ORM` constraints, `TextChoices`.
- No deep inheritance. Prefer small functions and composition.
- If a function needs more than ~4 parameters or ~40 lines, reconsider its design, but do not split things into meaningless fragments either.
- Each PR should be reviewable. Large, sweeping rewrites are not allowed unless requested.

---

## 6. Security

### 6.1 Authentication and authorization
- Passwords: Django's default hashers (PBKDF2/Argon2). Never store or log plain text.
- Enforce the password policy (FR-1.3) with a custom validator: more than 8 chars, at least 1 uppercase, 1 lowercase, 1 special character.
- Email uniqueness is enforced at the database level (case-insensitive unique index), not only in forms.
- Password reset uses Django's token generator: single-use, expiring links. Reset responses must not reveal whether an email exists.
- **Authorization is enforced server-side on every view and service.** Hiding a button is not security.
- Use a central permission layer (`permissions.py`, decorators or mixins) mapped to the RBAC matrix in `REQUIREMENTS.md` Section 4. **Default deny.**
- **Customer data isolation:** every customer-facing query must filter by the current user's customer. Prevent IDOR (never fetch by ID alone, e.g., use `get_object_or_404(Invoice, pk=pk, customer=request.user.customer)`).
- Only Admin can create staff accounts. Public signup can only create Customers; ignore any `role` field in the signup payload.

### 6.2 Input and output
- Use the ORM or parameterized queries. **No raw SQL string formatting.**
- Validate all input with forms/serializers. Never trust client-sent prices, totals, tax rates, or statuses; calculate them on the server.
- Keep Django's auto-escaping on. Do not use `|safe` or `mark_safe` on user-supplied data.
- Keep CSRF protection enabled. Any exemption must be justified in a comment and PR notes.

### 6.3 Secrets and configuration
- No secrets in code or in the repo. Use Vercel environment variables.
- `DEBUG = False` in production. `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` set explicitly.
- Production settings: `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`, `SECURE_CONTENT_TYPE_NOSNIFF`.
- Do not log passwords, tokens, reset links, or full payment details.

### 6.4 Rate limiting and abuse
- Apply throttling or lockout to login, signup, and password reset.
- Scheduler/cron endpoints on Vercel must be protected by a secret (e.g., `CRON_SECRET` header check), never publicly callable.

### 6.5 Dependencies
- Run `pip-audit` (or equivalent) before release. Update packages with known vulnerabilities.

---

## 7. Error Handling

### 7.1 General
- **Never use bare `except:` or silently swallow exceptions.** Catch the narrowest exception, then log or re-raise.
- Define domain exceptions in each app (e.g., `InvalidStatusTransition`, `DiscountNotApplicable`, `PaymentAmountMismatch`) and handle them at the view layer to produce clear user messages.
- Distinguish **user errors** (validation, permissions: return 400/403/404 with a friendly message) from **system errors** (log, return a generic 500 page with no internals).
- Use `get_object_or_404` for lookups tied to a request.
- Never expose stack traces or SQL errors to users.

### 7.2 Logging
- Use Python's `logging` module with module-level loggers, not `print()`.
- Log with context: IDs (subscription, invoice, customer), never secrets or personal data beyond what is needed.
- Vercel captures stdout/stderr, so configure logging to stream there with a clear level policy (`INFO` normal, `WARNING` recoverable, `ERROR` failures).

### 7.3 Domain-specific error handling

| Area | Required behavior |
|---|---|
| **Billing run** | One failing subscription must not abort the run. Catch per subscription, log, record it in `BillingRun` results with the reason, and continue. |
| **Duplicate invoice** | On a unique-constraint hit, treat as "already billed": skip and log (FR-5.3). |
| **Payment amount** | Reject any payment not equal to the invoice total with `PaymentAmountMismatch` (FR-7.4). |
| **Duplicate payment** | Reject a repeated submission (idempotency key / duplicate check). |
| **Automatic renewal failure** | Follow FR-4.8: flag `payment_failed`, email the customer, notify staff, apply retry/grace rules. Never fail silently. |
| **Email sending** | Failures must not roll back business transactions. Log, mark for retry, continue. |
| **Mock gateway** | Must be able to simulate success, failure, and timeout so every error path is testable. |
| **Discounts** | An expired, exhausted, or ineligible discount is skipped with a log entry, not an error that blocks the invoice. |

### 7.4 Vercel/serverless considerations
- Serverless functions have execution time limits. Long jobs (large billing runs) must be **batched** and resumable. Each invocation processes a limited chunk and can be continued by the next cron trigger.
- Handle database connection errors and timeouts with clear logging and safe retries on idempotent operations only.

---

## 8. Django + PostgreSQL + Vercel Specifics

### 8.1 Database
- Use PostgreSQL features where they help: `UniqueConstraint`, `CheckConstraint`, partial indexes, `select_for_update`.
- Add indexes for the common filters from the dashboard (status, due date, customer, plan, billing date). Prove with `EXPLAIN` when performance is in question (NFR-1).
- Avoid N+1 queries: use `select_related` and `prefetch_related`. List views must be paginated.
- Every model change ships with a migration. Never edit applied migrations. Data migrations are separate and reversible where possible.
- **Connection pooling:** serverless functions open many short-lived connections. Use a pooled connection string (PgBouncer/pooler from the database host) and sensible `CONN_MAX_AGE`/pool settings.
- Use `DATABASE_URL` from environment variables, with SSL required in production.

### 8.2 Vercel deployment
- Entry point is the WSGI app via `config/wsgi.py`, wired in `vercel.json`.
- **No writes to the local filesystem** for persistent data. Uploaded files and generated PDFs go to external object storage if they must persist.
- Static files served via WhiteNoise (`collectstatic` during build).
- **No long-running background workers or in-process schedulers** (no Celery workers, no APScheduler in-process). Use **Vercel Cron** hitting protected endpoints that call `tasks.py` entry points (billing run, renewals, dunning, plan auto-close, quote expiry).
- Scheduled jobs must be **idempotent** (FR-10.2): safe if triggered twice or overlapping.
- Run migrations as an explicit deploy step, not at request time.
- Keep environment parity: same settings structure for local and production, differing only by env vars.

---

## 9. Testing Standards

- Use `pytest` + `pytest-django` with `factory-boy` for test data.
- Each service function has tests for the success path and at least one failure path.
- **Mandatory test areas** (derived from the requirements):
  - Password policy and unique email
  - RBAC: each role is allowed and denied the right actions; customer cannot read another customer's data
  - Subscription and invoice state transitions (valid and invalid)
  - Billing run: no double billing, no skipped subscriptions, paused subscriptions excluded, cancelled-invoice period not re-billed
  - Tax per product; discount stacking, cap, and per-customer usage limit
  - Proration calculations
  - Payment must equal invoice total; invoice becomes Paid
  - Overdue detection and dunning triggers
  - Automatic renewal failure flow using the mock gateway
- Tests must not call real external services.
- Money assertions use `Decimal`, never float.

---

## 10. AI Self-Review Checklist (include in every response)

The AI must end each task with this review, mapped to the review areas we track.

### 10.1 What to look at in generated code

| Area | Check |
|---|---|
| **File/component structure** | Does code follow Section 1? Views thin, logic in services, selectors for reads? |
| **State management** | Is the DB the source of truth? Are transitions centralized, atomic, and audited? |
| **Unused imports / dead code** | Any unused imports, variables, stubs, commented code, or debug prints? Did `ruff` pass? |
| **Dependencies** | Any new package? Justified, pinned, Vercel-compatible? |
| **Over-engineering** | Anything built "just in case"? Any abstraction with fewer than two real uses? |
| **Security** | Server-side permission checks? Customer data isolation? Input validated? No secrets? |
| **Error handling** | Narrow exceptions, domain errors, logging, per-item failure isolation in batch jobs? |

### 10.2 What it got right / wrong

At the end of each response, the AI must report honestly:

```
## Self-Review
**Requirements covered:** FR-x.x, FR-y.y
**Assumptions made:** (list, referencing Open Items where relevant)
**Got right:** (what is solid and why)
**Uncertain / possibly wrong:** (anything unverified, untested, or guessed)
**Not done / out of scope:** (anything intentionally skipped)
**New dependencies:** none | (name, reason)
**Tests added:** (list) | none (explain)
**Checks run:** ruff ✔/✘, migrations check ✔/✘, tests ✔/✘
```

If a check was not actually run, the AI must say "not run" instead of claiming it passed.

---

## 11. Definition of Done

A change is done only when:

- [ ] It satisfies the referenced requirement IDs.
- [ ] It follows the structure and layering in Section 1.
- [ ] `ruff` passes, with no unused imports or dead code.
- [ ] Migrations are included and consistent.
- [ ] Tests for success and failure paths pass.
- [ ] Permissions and customer data isolation are verified.
- [ ] Errors are handled and logged appropriately.
- [ ] No secrets, debug code, or unnecessary dependencies.
- [ ] Works within Vercel serverless constraints (stateless, no local writes, time-limited).
- [ ] The Self-Review (Section 10.2) is included.
