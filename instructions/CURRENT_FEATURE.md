# M9. Taxes and Payment Terms

**Document type:** Feature specification and implementation baseline\
**Product:** Brightloop Subscription Management System\
**Module:** M9 --- Taxes and Payment Terms (Admin Configuration)\
**Requirement coverage:** FR-9.1 through FR-9.3\
**Status:** Derived implementation baseline; unresolved policy details
remain open\
**Sources:** `REQUIREMENTS.md`, `UI_UX.md`, `CODING_STANDARDS.md`

------------------------------------------------------------------------

## 1. Purpose and scope

M9 provides Admin-managed configuration consumed by Product Catalog,
Subscriptions, and Invoicing.

-   **Taxes:** Admin maintains named tax rates. Each Product references
    one Tax. Tax is product-based; there is no customer-location or
    region logic.
-   **Payment terms:** Admin maintains named due-date rules such as
    Immediate, Net 15, and Net 30. A Subscription selects a payment
    term, and M5 derives invoice due dates from it.

M9 owns tax and payment-term configuration. M2 owns Product records and
their tax relationship; M4 owns Subscription configuration and its
selected payment term; M5 owns invoice tax calculation and due-date
generation.

### 1.1 Goals

-   Let Admin manage taxes by name and rate.
-   Ensure each Product references one Tax.
-   Let Admin manage payment terms and make them selectable on
    Subscriptions.
-   Supply M5 with persisted configuration rather than duplicating tax
    rates or payment-term choices in code.
-   Preserve clear ownership boundaries and financial history.

### 1.2 In scope

-   Admin-only tax list, create, and edit.
-   Tax name and rate.
-   One Tax reference per Product.
-   Admin-only payment-term list, create, and edit.
-   Payment-term name and due-date rule / number of days.
-   Examples: Immediate, Net 15, Net 30.
-   Subscription selection of a configured payment term.
-   M5 integration for invoice tax and due-date calculations.
-   Validation, permissions, auditability, migrations, and tests.

### 1.3 Out of scope

Do not add without approval: - Region-, country-, or
customer-location-based tax logic. - Multiple taxes per Product. - Tax
exemptions, reverse charge, withholding tax, filing, or tax registration
workflows. - Multi-currency or multi-company tax handling. - Invoice tax
calculation inside M9; M5 owns it. - Payment collection or payment
gateway functionality. - Business-day calendars, holiday adjustments, or
end-of-month rules not defined by the source. - Customer-managed tax or
payment-term configuration. - Destructive deletion of referenced
configuration without an approved lifecycle policy.

------------------------------------------------------------------------

## 2. Requirement traceability

All M9 requirements are Must priority.

  -----------------------------------------------------------------------
  Requirement             Source requirement      M9 behavior
  ----------------------- ----------------------- -----------------------
  FR-9.1                  Admin manages a list of Admin-only tax
                          taxes (name, rate).     configuration with name
                                                  and rate.

  FR-9.2                  Each Product references Product has one Tax
                          one tax. No region or   reference; no
                          customer logic.         geography-based tax
                                                  lookup.

  FR-9.3                  Admin manages payment   Admin-managed
                          terms used to compute   payment-term records
                          invoice due dates.      are selected on
                                                  Subscriptions and
                                                  consumed by M5.
  -----------------------------------------------------------------------

Related requirements: - FR-2.3: Each Product has an associated tax. -
FR-4.3: Each Subscription has payment terms. - FR-5.4: Tax is calculated
from the tax attached to each Product; each invoice line carries its
Product's tax rate. - FR-5.7: Invoice due date is derived from
Subscription payment terms. - BR-8: Tax comes only from the Product's
tax. - BR-13 / Open Item B: working assumption is tax-exclusive prices,
with tax added on top. - Open Item G: Admin-managed payment-term list,
e.g. Immediate, Net 15, Net 30. - Open Item J / NFR-10: fixed-precision
Decimal money handling; working rounding assumption is per line, 2
decimals, half-up.

------------------------------------------------------------------------

## 3. Roles and permissions

### Admin

Admin can view, create, and edit Tax and PaymentTerm records; select a
Tax on a Product; and configure a Subscription with an available payment
term.

### Staff

Staff cannot manage taxes or payment terms. The role-permission matrix
denies Staff tax/payment-term management. Whether Staff may select an
existing payment term during subscription creation is not fully
explicit; follow M4's established permission behavior and confirm if
unclear.

### Customer

Customers cannot manage configuration. They may see tax amounts and
totals on their own quotations/invoices, but must not access internal
configuration or another customer's records.

### Authorization rules

-   Enforce permissions server-side, not only by hiding UI controls.
-   Default-deny unlisted configuration actions.
-   Resolve actor identity from the authenticated request.
-   Do not trust browser-supplied tax rates, tax amounts, or invoice due
    dates.
-   Validate Product and Subscription foreign-key references against
    persisted records.

------------------------------------------------------------------------

## 4. Domain model and ownership

The following is a logical proposal; align names with existing models
and avoid duplicate fields/models.

### 4.1 Tax

  -----------------------------------------------------------------------
  Field                   Suggested type          Purpose
  ----------------------- ----------------------- -----------------------
  `id`                    Project-standard PK     Stable identifier.

  `name`                  CharField               Tax name.

  `rate`                  DecimalField            Tax rate.

  `created_at`,           DateTimeField           Timestamps, if project
  `updated_at`                                    convention requires.

  `created_by`,           Nullable User FK        Admin audit
  `updated_by`                                    attribution, if stored
                                                  on the record.
  -----------------------------------------------------------------------

The source specifies only name and rate. It does not specify whether 18%
is stored as `18` or `0.18`, permitted range, zero-rate behavior, name
uniqueness, or deletion/archive behavior. Confirm these before
implementation. Use Decimal, never float.

### 4.2 Product relationship

Logical relationship:

``` text
Tax 1 ─── * Product
```

Each Product references one Tax; one Tax may be referenced by multiple
Products. If M2 already has this relationship, M9 should manage the Tax
records and coordinate with M2 rather than add a second relationship.

### 4.3 PaymentTerm

  -----------------------------------------------------------------------
  Field                   Suggested type          Purpose
  ----------------------- ----------------------- -----------------------
  `id`                    Project-standard PK     Stable identifier.

  `name`                  CharField               E.g. Immediate, Net 15,
                                                  Net 30.

  `days`                  IntegerField, if        Number of days used by
                          approved                the due-date rule.

  `created_at`,           DateTimeField           Timestamps, if project
  `updated_at`                                    convention requires.

  `created_by`,           Nullable User FK        Admin audit
  `updated_by`                                    attribution, if stored
                                                  on the record.
  -----------------------------------------------------------------------

The UI calls the field "Due-date rule / number of days." A day-count is
a plausible representation, but calendar vs business days, the base
date, boundary behavior, and date adjustments are not defined. Do not
silently decide these semantics.

### 4.4 Ownership boundaries

  -----------------------------------------------------------------------
  Concern                 Owner                   Responsibility
  ----------------------- ----------------------- -----------------------
  Tax records             M9                      Maintain tax
                                                  configuration.

  Product-to-Tax          M2                      Product references one
  relationship                                    Tax.

  Subscription            M4                      Store selected
  payment-term selection                          PaymentTerm.

  Invoice tax calculation M5                      Calculate tax using
                                                  Product's Tax.

  Invoice due date        M5                      Derive from
                                                  Subscription's
                                                  PaymentTerm.

  Reporting               M8                      Consume persisted
                                                  financial data as
                                                  defined by reporting
                                                  requirements.
  -----------------------------------------------------------------------

M9 must not duplicate invoice calculations or subscription lifecycle
behavior.

------------------------------------------------------------------------

## 5. Tax configuration behavior

### 5.1 Tax list and form

Audience: Admin only.

Required list/form information: - Tax name. - Tax rate.

Expected behavior: - Admin can view, create, and edit taxes. - Show an
empty state when no taxes exist. - Validate input on the server and show
field-specific errors. - Preserve form input after validation failure
where possible. - Do not expose management actions to Staff or
Customers.

The source does not require specific search, filters, sorting,
pagination, or a status column.

### 5.2 Validation

-   Name is required.
-   Rate is required and must be numeric.
-   Store/process rate with Decimal.
-   Enforce the approved rate representation and range once confirmed.
-   Reject malformed input.
-   Never accept a client-computed tax amount as authoritative.

The exact range, zero-rate policy, and name uniqueness remain open.

### 5.3 Product tax assignment

-   Product create/edit uses the configured Tax list.
-   Each Product must reference one valid Tax.
-   Reject missing/invalid Tax references where the one-tax-per-product
    rule applies.
-   M5 reads the Product's Tax when generating invoice lines.
-   Each invoice line carries its Product's tax rate under FR-5.4.

### 5.4 Tax calculation integration

M9 stores configuration; M5 calculates invoice tax.

Preserve these rules: - Tax comes only from the Product's Tax. - Do not
use customer address or region. - The working assumption is
tax-exclusive prices (Open Item B). - Use Decimal and the shared
money-rounding helper. - The working rounding assumption is per line, 2
decimal places, half-up (Open Item J), pending confirmation.

### 5.5 Historical behavior

The source does not define whether editing a Tax changes draft
subscriptions, draft invoices, or future calculations. Confirm this
policy.

Confirmed invoices are treated as immutable under FR-5.10's working
policy. M5 must preserve the tax details used by a confirmed invoice
rather than recomputing historical totals from a subsequently edited Tax
record. Do not retroactively recalculate confirmed invoices.

------------------------------------------------------------------------

## 6. Payment-term configuration behavior

### 6.1 Payment-term list and form

Audience: Admin only.

Required fields: - Name. - Due-date rule / number of days.

Examples from the source: - Immediate. - Net 15. - Net 30.

Admin can view, create, and edit payment terms. The source does not
define additional status or lifecycle fields.

### 6.2 Validation

-   Name is required.
-   Due-date rule is required.
-   If represented as a day count, validate the approved integer range.
-   Reject malformed or negative values unless a separately approved
    rule permits them.
-   Do not infer calendar-day/business-day behavior from the label.

Allowed values, uniqueness, and date semantics remain open.

### 6.3 Subscription selection

-   Subscription stores a PaymentTerm reference under FR-4.3.
-   Subscription workflow selects from Admin-managed records.
-   M5 uses the selected persisted term to derive invoice due dates.
-   Do not hard-code Immediate / Net 15 / Net 30 in frontend code.
-   Validate the selected reference server-side.

Staff's ability to select/change a term during subscription creation is
not fully explicit. Follow M4 permissions and record the decision.

### 6.4 Invoice due-date integration

FR-5.7 assigns due-date derivation to the Subscription's payment terms.
M5 owns the calculation; M9 only supplies the configuration.

Do not silently assume: - The base date is invoice creation,
confirmation, or another event. - Immediate always means a particular
timestamp. - Net N means calendar days rather than business days. -
Weekends/holidays are adjusted. - Editing a Subscription's payment term
rewrites existing invoice due dates.

Existing confirmed invoices should retain their due dates. Changes to
terms should apply to future invoices unless an approved policy says
otherwise.

------------------------------------------------------------------------

## 7. User experience

### Taxes

Audience: Admin only. Show Tax name and rate, with create/edit actions.
Product create/edit should reference configured taxes.

### Payment terms

Audience: Admin only. Show name and due-date rule / number of days, with
create/edit actions. Subscription workflows use the configured list.

### Validation/error states

  -----------------------------------------------------------------------
  Situation                           Expected behavior
  ----------------------------------- -----------------------------------
  Missing tax name                    Field-specific validation error.

  Missing/malformed tax rate          Reject and explain expected numeric
                                      input.

  Invalid Product tax reference       Prevent save and request a valid
                                      Tax.

  Missing payment-term name           Field-specific validation error.

  Invalid due-date rule               Reject using the confirmed accepted
                                      representation.

  Invalid Subscription term reference Prevent save and request a valid
                                      term.

  Non-Admin management request        Server-side access denied.

  Referenced Tax/PaymentTerm is being Do not silently invalidate existing
  deleted                             records; follow approved lifecycle
                                      policy.

  Network/server error                Preserve form data where possible
                                      and provide safe retry.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 8. Data integrity, security, and performance

-   PostgreSQL is the source of truth.
-   Use Decimal for rates and all monetary calculations.
-   Enforce Admin-only management on the server.
-   Validate foreign-key references.
-   Use constraints only for confirmed business rules.
-   Do not delete or mutate referenced configuration in a way that
    corrupts Product, Subscription, or Invoice history.
-   Ship migrations; never edit applied migrations.
-   Audit Admin configuration changes consistent with NFR-5.
-   Use ORM/parameterized queries; no raw SQL string formatting.
-   Avoid N+1 queries.
-   Do not add a dependency for basic configuration CRUD.

------------------------------------------------------------------------

## 9. Testing strategy

### Tax tests

-   Valid Tax creation succeeds.
-   Missing name, missing rate, and malformed rate are rejected.
-   Decimal precision is preserved.
-   Approved range and uniqueness rules are enforced once decided.
-   Product references one valid Tax.
-   Missing/invalid Tax reference is rejected.
-   Admin can manage; Staff and Customer cannot.

### Tax integration tests

-   M5 reads the Product's Tax during invoice generation.
-   Each invoice line carries the Product's tax rate.
-   Tax is not derived from customer location/region.
-   Decimal and shared rounding helper are used.
-   Confirmed invoice tax details remain stable after Tax edits.

### Payment-term tests

-   Admin can create/edit a PaymentTerm.
-   Missing name or invalid due-date rule is rejected.
-   Subscription stores a valid PaymentTerm.
-   Invalid reference is rejected.
-   Staff/Customer cannot manage terms.
-   Immediate / Net N semantics are tested after product confirms them.

### Due-date integration tests

-   M5 derives due date from Subscription's selected term.
-   Approved base-date and calendar semantics are tested.
-   Editing a term does not silently rewrite confirmed invoice due
    dates.
-   Agreed timezone/date basis is applied consistently.

### General checks

-   Migrations are consistent.
-   `ruff check .`, `ruff format .`,
    `python manage.py makemigrations --check --dry-run`, and `pytest`
    pass, or are explicitly reported as not run.
-   Run dependency audit before release.

------------------------------------------------------------------------

## 10. Dependencies and implementation sequence

### Upstream

-   M1: authenticated Admin identity and server-side RBAC.
-   M2: Product model and Product-to-Tax relationship.
-   M4: Subscription model and payment-term selection.
-   M5: invoice tax calculation and due-date calculation.

### Downstream

-   M2 consumes Tax records.
-   M4 consumes PaymentTerm records.
-   M5 consumes Product tax and Subscription payment terms.
-   M8 may consume persisted invoice financial data as defined by
    reporting requirements.

### Sequence

1.  Inspect existing `apps/catalog/` models, forms, services, selectors,
    permissions, and migrations.
2.  Confirm whether Tax/PaymentTerm already exist; avoid duplicates.
3.  Confirm tax-rate representation, range, and uniqueness.
4.  Confirm Immediate / Net N semantics.
5.  Implement or complete Tax configuration.
6.  Implement or complete PaymentTerm configuration.
7.  Enforce Admin-only create/edit.
8.  Integrate Product-to-Tax selection with M2.
9.  Integrate Subscription-to-PaymentTerm selection with M4.
10. Verify M5 consumes configuration rather than duplicating it.
11. Add audit, validation, and integration tests.
12. Run lint, formatting, migration checks, tests, and dependency audit.
13. Obtain approval for unresolved policies.

------------------------------------------------------------------------

## 11. Open decisions and assumptions

  -----------------------------------------------------------------------------------------
  \#                Topic                     Source position    Decision needed
  ----------------- ------------------------- ------------------ --------------------------
  1                 Rate representation       Tax has name and   Store 18 for 18%, or 0.18?
                                              rate.              Choose one canonical
                                                                 representation.

  2                 Rate range                Not specified.     Are zero rates allowed?
                                                                 What is the maximum?

  3                 Tax name uniqueness       Not specified.     Must names be
                                                                 unique/case-insensitive?

  4                 Tax lifecycle             Create/manage      How to retire referenced
                                              required;          taxes?
                                              deletion/archive   
                                              unspecified.       

  5                 Tax edits                 Historical         Do edits affect future
                                              behavior           calculations only? What
                                              unspecified.       about drafts?

  6                 Day basis                 Due-date rule /    Calendar days or business
                                              number of days.    days?

  7                 Immediate                 Example only.      Which date/time is the due
                                                                 date?

  8                 Net N                     Examples Net       Which event is the base
                                              15/Net 30.         date for adding N days?

  9                 Date adjustments          Not specified.     Weekends, holidays,
                                                                 end-of-month?

  10                Term edits                Not specified.     Future invoices only, or
                                                                 drafts too?

  11                Staff selection           Staff manages      Can Staff select an
                                              subscriptions but  existing term during
                                              cannot manage      subscription creation?
                                              terms.             

  12                Rounding                  Open Item J        Confirm per-line, 2
                                              working            decimals, half-up.
                                              assumption.        

  13                Tax-inclusive/exclusive   Open Item B        Confirm.
                                              working            
                                              assumption:        
                                              exclusive.         
  -----------------------------------------------------------------------------------------

### Assumptions to avoid

-   Do not assume a rate representation, maximum rate, or uniqueness
    policy.
-   Do not add geography/customer tax rules or multiple taxes per
    Product.
-   Do not assume calendar/business days or a due-date base event.
-   Do not retroactively recalculate confirmed invoices.
-   Do not assume deletion of referenced configuration is safe.
-   Do not grant Staff configuration-management permissions.

------------------------------------------------------------------------

## 12. Definition of Done

-   [ ] FR-9.1 through FR-9.3 implemented.
-   [ ] Admin manages Tax records with name and rate.
-   [ ] Each Product references one Tax.
-   [ ] No region/customer-location tax logic is added.
-   [ ] Admin manages PaymentTerm records.
-   [ ] Payment terms expose name and due-date rule / number of days.
-   [ ] Subscription references a configured PaymentTerm.
-   [ ] M5 derives invoice due dates from the selected term.
-   [ ] M5 continues to calculate invoice-line tax from Product tax.
-   [ ] Decimal is used for financial calculations.
-   [ ] Management is Admin-only and server-enforced.
-   [ ] Confirmed invoice history is not silently recalculated.
-   [ ] Validation, permission, and integration tests exist.
-   [ ] Migrations and project checks pass, or unrun checks are
    documented.
-   [ ] No unapproved dependencies or out-of-scope features.
-   [ ] Open decisions are approved or explicitly deferred.

------------------------------------------------------------------------

## 13. Developer self-review

  -----------------------------------------------------------------------
  Area                    Review question         Status
  ----------------------- ----------------------- -----------------------
  Ownership               No duplication of       Verify during
                          M2/M4/M5                implementation
                          responsibilities?       

  Integrity               Each Product has one    Verify
                          valid Tax; each         
                          Subscription has a      
                          valid term?             

  Tax behavior            Tax comes only from     Verify
                          Product tax?            

  Due dates               M5 calculates due dates Verify
                          from the selected term? 

  Money                   Decimal and shared      Verify
                          rounding helper used?   

  Permissions             Management is           Verify
                          Admin-only server-side? 

  History                 Confirmed invoice       Verify
                          details remain          
                          immutable?              

  Dead code               No unused imports,      Verify
                          stubs, debug prints, or 
                          dead code?              

  Dependencies            New packages justified, Verify
                          pinned,                 
                          Vercel-compatible?      

  Tests                   Model, permission,      Verify
                          integration, and date   
                          tests present?          
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 14. Source of truth

Derived from: 1. `REQUIREMENTS.md`: FR-9.1--FR-9.3, FR-2.3, FR-4.3,
FR-5.4, FR-5.7, BR-8, BR-13, Open Items B/G/J, and NFR-10. 2.
`UI_UX.md`: Section 5.13 Taxes and Payment Terms, Product and
Subscription forms. 3. `CODING_STANDARDS.md`: modular-monolith
structure, PostgreSQL, Decimal, server-side RBAC, migrations,
auditability, and Vercel constraints.

Requirements define what to build; coding standards define
implementation constraints; UI/UX defines the interface. Open decisions
are recorded rather than silently resolved. This is an implementation
baseline, not a claim that M9 is implemented.

---

# M10. Notifications and Scheduler

**Document type:** Feature specification and implementation baseline\
**Product:** Brightloop Subscription Management System\
**Module:** M10 --- Notifications and Scheduler\
**Requirement coverage:** FR-10.1 through FR-10.4\
**Status:** Derived implementation baseline; unresolved policies remain
open\
**Sources:** `REQUIREMENTS.md`, `UI_UX.md`, `CODING_STANDARDS.md`

------------------------------------------------------------------------

## 1. Purpose and scope

M10 provides shared notification delivery and scheduled execution for
Brightloop.

It has two responsibilities:

1.  **Scheduler:** run billing, renewals, plan auto-close, quotation
    expiry, and dunning reminders.
2.  **Notifications:** send and track email events for password reset,
    invoice delivery, payment failure, overdue reminders, and Staff
    alerts.

M10 owns shared infrastructure and orchestration. Domain modules retain
their business rules and task entry points. M10 must call those entry
points rather than reimplement billing, subscription, invoice, payment,
or quotation logic.

The deployment target is Django + PostgreSQL + Vercel. Use protected
Vercel Cron endpoints and bounded, resumable tasks. Do not use
in-process schedulers or long-running workers.

### 1.1 Goals

-   Run all scheduled tasks required by FR-10.1.
-   Make scheduled jobs idempotent under reruns and overlapping
    invocations.
-   Send all required email categories.
-   Log email delivery failures and support retry behavior.
-   Keep email provider and scheduler behind small replaceable
    boundaries.
-   Operate within Vercel serverless execution limits.

### 1.2 In scope

-   Protected cron endpoints and scheduler integration.
-   Task entry points for billing, renewals, plan auto-close, quotation
    expiry, and dunning.
-   Idempotency, bounded batches, and resumability.
-   Shared email-provider boundary.
-   Emails for password reset, invoice delivery, payment failure,
    overdue reminders, and Staff alerts.
-   Notification delivery logging.
-   Retry handling for failed email delivery (Should priority).
-   Tests for scheduling, notifications, security, and failure paths.

### 1.3 Out of scope

Do not add without approval: - Celery workers, Redis queues, message
brokers, event buses, APScheduler, or in-process schedulers. - A general
workflow engine. - SMS, WhatsApp, push, or in-app notification center. -
Marketing campaigns or newsletters. - New payment checkout
functionality. - New renewal retry/grace-period or dunning policies. - A
scheduler-management UI, cron editor, or job calendar unless separately
required. - Automatic retries of non-idempotent operations without a
safe retry design.

------------------------------------------------------------------------

## 2. Requirement traceability

  -----------------------------------------------------------------------------
  Requirement           Priority      Source            M10 behavior
                                      requirement       
  ----------------- ----------------- ----------------- -----------------------
  FR-10.1                 Must        Scheduler runs    Configure scheduled
                                      billing,          invocations for each
                                      renewals, plan    operation and call the
                                      auto-close, quote owning app's task entry
                                      expiry, and       point.
                                      dunning.          

  FR-10.2                 Must        Scheduled jobs    Enforce idempotency at
                                      are idempotent    domain/database level
                                      and safe to       and handle
                                      re-run.           duplicate/overlapping
                                                        cron invocations.

  FR-10.3                 Must        Emails for        Shared email dispatch
                                      password reset,   boundary and
                                      invoice delivery, event-specific
                                      payment failure,  templates/context.
                                      overdue           
                                      reminders, and    
                                      Staff alerts.     

  FR-10.4                Should       Email failures    Persist/log failures
                                      are logged and    and support retry under
                                      retried.          an approved policy.
  -----------------------------------------------------------------------------

Related requirements: - FR-1.4: password reset email contains a
single-use, time-limited reset link. - FR-3.6: scheduler closes plans
configured to auto-close after their end date. - FR-4.8: automatic
renewal failure sets `payment_failed`, emails customer, notifies Staff,
and applies grace/retry policy. - FR-4.11: expired quotation cannot be
accepted. - FR-5.2: billing run can be scheduler-triggered or manually
triggered by Admin/Staff. - FR-5.9: billing-run results record
created/skipped/failed; one subscription failure does not stop others. -
FR-7.8: overdue invoices receive automatic reminder emails. - NFR-2:
hundreds of subscriptions per billing run with batching/background
processing. - NFR-5: status changes, billing actions, payments, and
Admin changes are logged. - NFR-7: scheduled jobs recover and safely
rerun. - NFR-9: email provider and scheduler are replaceable.

Open Item C's working dunning cadence (1, 7, 14 days past due, then
auto-pause) is not confirmed. Renewal retry count, intervals, grace
period, and final lifecycle action are also open.

------------------------------------------------------------------------

## 3. Roles and access boundaries

### System execution

Scheduled tasks execute under a protected server-side context, not an
arbitrary browser-supplied user.

-   Cron endpoints require the configured secret.
-   Reject missing/invalid authorization.
-   Do not accept arbitrary task names or untrusted parameters that
    permit privileged task dispatch.
-   Each task validates its own inputs and calls the relevant domain
    service.

### Admin and Staff

Admin/Staff can manually trigger billing as specified by FR-5.2 and the
role-permission matrix. M10 does not grant users permission to edit cron
schedules.

Use existing billing-run results and notification/job logs for
operational visibility. The source does not specify a
scheduler-management screen.

### Customer

Customers cannot access scheduler endpoints or internal notification
infrastructure. They receive relevant transactional emails and can
access only their own portal records.

------------------------------------------------------------------------

## 4. Architecture and ownership

### 4.1 M10 responsibilities

M10 provides: - Email-provider selection and dispatch. - Notification
rendering/template integration. - Delivery outcome logging. - Retry
state/entry point where required. - Protected cron invocation. - Shared
task execution conventions and bounded processing.

M10 does not own business eligibility, billing calculations, renewal
decisions, quotation state transitions, plan lifecycle, or overdue
calculation.

### 4.2 Domain task ownership

  -----------------------------------------------------------------------
  Scheduled operation /   Domain owner            M10 responsibility
  email                                           
  ----------------------- ----------------------- -----------------------
  Billing run             M5 Billing              Schedule and invoke
                                                  billing task.

  Automatic renewals      M4 Subscriptions and    Schedule and invoke
                          relevant payment flow   renewal task.

  Plan auto-close         M3 Plans / subscription Schedule and invoke
                          lifecycle service       auto-close task.

  Quotation expiry        M4 Quotations /         Schedule and invoke
                          Subscriptions           expiry task.

  Dunning                 M7 Payments / overdue   Schedule and invoke
                          workflow                dunning; provide email
                                                  dispatch.

  Password reset email    M1 Accounts             Deliver email; M1 owns
                                                  token generation and
                                                  validation.

  Invoice delivery        M5 Billing              Deliver email; M5 owns
                                                  invoice content and
                                                  send eligibility.

  Payment failure         M4/M7 renewal-payment   Deliver email; domain
                          flow                    supplies event context.

  Staff alerts            Originating domain      Deliver alert; domain
                          module                  determines event and
                                                  recipient context.
  -----------------------------------------------------------------------

### 4.3 Suggested structure

Align with existing app layout; reuse existing modules if present.

``` text
apps/
├── notifications/
│   ├── models.py       # notification/delivery records, if persisted
│   ├── services.py     # dispatch, template rendering, retry
│   ├── providers.py    # small email-provider boundary
│   ├── selectors.py    # delivery history / retry candidates
│   ├── tasks.py        # retry task, if required
│   ├── templates/
│   └── tests/
└── billing/
    └── tasks.py        # domain-owned billing entry point
```

Cron routing/configuration belongs in the existing project wiring. Do
not create a generic scheduler framework without a concrete need.

------------------------------------------------------------------------

## 5. Scheduler design

### 5.1 Required scheduled operations

FR-10.1 requires: 1. Billing runs. 2. Renewals. 3. Plan auto-close. 4.
Quotation expiry. 5. Dunning reminders.

Each operation needs a clear task entry point owned by its domain
module. Exact cron frequencies and times are not specified; obtain
approval rather than inventing a product schedule.

### 5.2 Vercel execution model

Coding standards require: - Vercel Cron calling protected endpoints. -
Endpoints invoking `tasks.py` entry points. - No Celery workers,
APScheduler, or in-process background workers. - No reliance on
in-memory globals or local files for persistent state.

Use environment configuration for cron secrets and deployment-specific
settings.

### 5.3 Protected endpoints

-   Protect each scheduled endpoint with the configured secret
    (e.g. `CRON_SECRET`).
-   Reject missing or invalid secrets.
-   Never expose secrets or stack traces in responses/logs.
-   Do not allow arbitrary task dispatch from public query parameters.
-   Keep endpoints thin: authenticate request, call a known task entry
    point, return a safe result.
-   Manual billing remains governed by Admin/Staff permissions,
    separately from cron authentication.

### 5.4 Idempotency and overlapping invocations

FR-10.2 is Must priority. A job must be safe if: - Cron delivers the
same invocation more than once. - A previous invocation times out after
processing some records. - Two invocations overlap. - A task is retried
after transient failure. - A record changes state between selection and
processing.

Implementation principles: - PostgreSQL is the source of truth. - Use
database uniqueness constraints where appropriate. - Use
`transaction.atomic()` for multi-step writes. - Use
`select_for_update()` when concurrent operations can change the same
domain record. - Re-check eligibility immediately before state
transitions or notifications. - Make each record's operation
independently safe to retry. - Do not rely on pre-checks alone to
prevent duplicates. - Persist progress/outcomes where needed; do not
rely on process memory.

Examples: - Billing uses unique `(subscription, billing_period)` invoice
constraint; duplicate means already billed and should be
logged/skipped. - Quotation expiry must not repeat an invalid
transition. - Plan auto-close must not repeat an invalid lifecycle
transition. - Dunning must not send the same successful reminder stage
twice. - Email retry must not resend a known successful delivery merely
because cron ran again.

### 5.5 Batching and resumability

Vercel functions have execution time limits. Long jobs, especially
billing runs, must be bounded and resumable.

-   Process a limited batch per invocation.
-   Persist sufficient progress/outcome state to continue safely.
-   Continue through later invocations/cron triggers.
-   Isolate failures per subscription/invoice/record.
-   One failed record must not abort unrelated records.
-   Billing records Created / Skipped / Failed outcomes under FR-5.9.
-   Retry only operations designed to be idempotent.

Batch size, execution budget, and continuation mechanism are
deployment/implementation decisions. Measure them against actual Vercel
limits.

### 5.6 Task results and logs

Operational logs should identify: - Task name and execution time. -
Completion/failure outcome. - Processed count where relevant. - Failed
records and safe reason. - Whether a retry is possible.

The requirements do not mandate a `SchedulerRun` model or scheduler UI.
Reuse `BillingRun` for billing. Add persisted job-run records only if
needed for reliability/auditability, not speculatively.

------------------------------------------------------------------------

## 6. Notification and email design

### 6.1 Required email events

  -----------------------------------------------------------------------
  Event                   Domain owner            Purpose
  ----------------------- ----------------------- -----------------------
  Password reset          M1 Accounts             Deliver the single-use,
                                                  time-limited reset
                                                  link.

  Invoice delivery        M5 Billing              Deliver invoice when
                                                  sent.

  Payment failure         M4/M7 renewal-payment   Inform customer
                          flow                    automatic renewal
                                                  payment failed.

  Overdue reminder        M7 Payments / dunning   Remind customer of
                                                  overdue invoice using
                                                  approved cadence.

  Staff alert             Relevant domain app     Notify Staff of
                                                  relevant operational
                                                  event, including
                                                  renewal failures.
  -----------------------------------------------------------------------

M10 supplies delivery infrastructure. The originating module supplies
event, recipient, and domain-specific content.

### 6.2 Email provider boundary

NFR-9 requires the email provider to be replaceable. Keep the contract
small and aligned with actual use.

A conceptual dispatch input may include: - Recipient. - Subject. -
Rendered text/HTML body or template plus context. - Stable
event/notification identifier where duplicate handling requires it.

Use existing repository conventions for the exact signature. Do not
create a generic plugin framework or redundant provider abstractions.

Provider credentials come from environment variables. Never hard-code or
log them.

### 6.3 Notification record

`Notification` is listed as a core domain entity for email logs. A
proposed record may include:

  -----------------------------------------------------------------------
  Field                               Purpose
  ----------------------------------- -----------------------------------
  `id`                                Stable identifier.

  `notification_type`                 Password reset, invoice, payment
                                      failure, dunning, Staff alert.

  `recipient`                         Delivery destination; protect as
                                      personal data.

  `related_object` reference          Invoice, subscription, user, or
                                      other relevant record.

  `status`                            Delivery state; exact choices are
                                      not specified.

  `attempt_count`                     Number of attempts, if retries are
                                      persisted.

  `last_attempt_at`                   Last dispatch attempt.

  `sent_at`                           Successful dispatch time, if
                                      available.

  `failure_reason`                    Safe internal failure detail.

  `created_at`, `updated_at`          Timestamps.
  -----------------------------------------------------------------------

This is a proposed logical shape, not a mandated schema. Reuse an
existing notification model if present.

For password reset, never persist/log the raw reset token or complete
reset URL in notification logs.

### 6.4 Templates and content

Provide event-specific transactional email content. It must: - Identify
the relevant action/record without exposing unrelated customer data. -
Use server-derived values, not browser-supplied totals/statuses. - Avoid
secrets, reset tokens in logs, and internal stack traces. - Reflect
actual domain state. - Avoid claiming a lifecycle transition that has
not occurred.

The source does not define exact copy, branding, localization, HTML
design, sender identity, or Staff recipient selection. Follow existing
project conventions and obtain product decisions where needed.

### 6.5 Delivery failures and retries

FR-10.4 is Should priority. It requires failures to be logged and
retried, but retry count, interval, backoff, maximum age, and terminal
state are unspecified.

Implementation should: - Record failed attempts safely. - Preserve
enough context to retry without reconstructing business state
incorrectly. - Retry only under a documented policy. - Avoid duplicate
successful sends after reruns. - Continue processing unrelated
notifications when one email fails. - Never roll back a successful
payment, invoice transition, or password-reset operation because email
failed. - Catch expected provider exceptions narrowly; log unexpected
failures safely. - Never expose provider stack traces or secrets.

A timeout may leave delivery uncertain. Do not claim exactly-once
delivery unless the provider supports it. Document duplicate handling
for uncertain outcomes.

### 6.6 Dunning and reminder tracking

M7 owns overdue eligibility and dunning rules; M10 supplies scheduled
invocation and email delivery.

Open Item C working assumption: - First reminder: 1 day past due. -
Second reminder: 7 days past due. - Third reminder: 14 days past due. -
After final failure: automatically pause the subscription.

This cadence and final action are not confirmed. Do not hard-code UI
copy presenting them as final.

Reminder handling must: - Select overdue invoices eligible for the next
reminder. - Skip Paid invoices. - Record reminder stage and send time. -
Avoid duplicate successful reminder stages after cron reruns. - Log
failures and allow safe retry. - Continue other invoices if one email
fails. - Apply subscription pause only through the subscription
lifecycle service and only after Open Item C is confirmed.

Reminder history may belong to M7 because it represents invoice-specific
dunning state. M10 should not duplicate it.

------------------------------------------------------------------------

## 7. User experience and operational feedback

UI/UX principles require visible automation and no silent failure: -
Show when a job ran, what it processed, and what failed where
relevant. - Log email delivery failures. - Show a visible failure state
to Admin/Staff where operational follow-up is needed. - Avoid duplicate
customer emails on safe reruns.

Reuse existing operational surfaces: - Billing-run list/result detail
for billing outcomes. - Subscription detail for `payment_failed`,
lifecycle status, and warnings. - Invoice detail/history for invoice
delivery and payment/reminder context where available. - Existing
notification delivery state where available.

The source does not define a scheduler-management screen, cron editor,
job calendar, or manual retry console. These are not required
deliverables unless separately approved.

Do not expose provider internals. An email failure must not encourage
Staff to repeat a payment or billing action if the business transaction
already succeeded.

------------------------------------------------------------------------

## 8. Error handling, security, and reliability

### Scheduled task errors

-   Catch failures at individual-record boundaries where possible.
-   Log the failed record and safe reason.
-   Continue unrelated records.
-   Never use bare `except:` or silently swallow exceptions.
-   Catch the narrowest expected exception.
-   Safely surface unexpected failures after logging.
-   Ensure partial batches can resume without duplicating completed
    work.

### Email errors

-   Email failure must not roll back the associated business
    transaction.
-   Log failure and mark for retry when configured.
-   Continue unrelated notifications.
-   Do not expose stack traces, provider secrets, or credentials.
-   Do not log password-reset tokens or full reset URLs.

### Endpoint security

-   Protect cron endpoints with the configured secret.
-   Validate request inputs.
-   Do not trust caller-supplied task names, recipients, event types, or
    object IDs.
-   Enforce permissions for manual actions separately from cron
    authentication.
-   Use environment variables for cron and provider secrets.
-   Any CSRF exemption must be justified and documented under project
    standards.

### State and concurrency

-   PostgreSQL is the source of truth.
-   No in-memory scheduler locks or global state.
-   Use database constraints and row locking where required.
-   Jobs must be safe under duplicate and overlapping invocations.
-   Use persistent state for retry eligibility/progress where required.

------------------------------------------------------------------------

## 9. Suggested implementation sequence

1.  Inspect repository, `vercel.json`, Django settings, email
    configuration, and domain `tasks.py` modules.
2.  Identify existing email dispatch and notification logs; reuse where
    suitable.
3.  Map each scheduled operation to its domain owner and task entry
    point.
4.  Confirm cron frequencies and operational timezone.
5.  Implement/complete a small email-provider boundary.
6.  Implement shared dispatch and delivery logging.
7.  Add templates for the five required email categories.
8.  Implement/complete protected cron endpoints.
9.  Configure cron invocations for billing, renewals, plan auto-close,
    quotation expiry, and dunning.
10. Ensure each domain task is bounded, resumable, and idempotent.
11. Add safe notification retry according to approved policy.
12. Verify duplicate/overlapping invocations do not duplicate business
    operations or successful reminder stages.
13. Add endpoint, idempotency, batch continuation, email, and retry
    tests.
14. Validate Vercel execution limits and cron configuration.
15. Run lint, formatting, migration checks, tests, and dependency audit.
16. Record unresolved policies for approval.

------------------------------------------------------------------------

## 10. Testing strategy

### Scheduler and cron tests

-   Valid cron secret permits the intended endpoint.
-   Missing/invalid secret is rejected.
-   Public caller cannot invoke privileged tasks.
-   Endpoint dispatches only its predefined task.
-   Duplicate invocation is safe.
-   Overlapping invocation does not duplicate state changes.
-   Task processing is bounded and resumable.
-   One record failure does not stop unrelated records.
-   Billing preserves Created / Skipped / Failed results.
-   Plan auto-close and quotation expiry do not repeat invalid
    transitions.
-   Renewal follows approved retry/grace policy.
-   Dunning does not resend the same successful reminder stage.

### Email provider tests

-   Success returns normalized success.
-   Failure is logged.
-   Timeout/unknown result is handled without exposing internals.
-   Credentials come from environment configuration.
-   Secrets, reset tokens, and reset URLs are absent from logs.
-   Email failure does not roll back business state.
-   One failed email does not stop unrelated notifications.

### Notification event tests

-   Password reset event dispatches email while M1 owns token
    generation/validation.
-   Invoice delivery sends the correct invoice email.
-   Payment failure sends customer notification.
-   Overdue reminder sends the correct reminder stage.
-   Staff alert uses intended Staff recipient/context.
-   Customer-specific content is scoped correctly.
-   Content does not claim a state transition that did not occur.

### Retry tests

-   Failed delivery is persisted/logged.
-   Eligible failed delivery can be retried.
-   Retry policy limits attempts as configured.
-   Successful notification is not resent on cron rerun.
-   Uncertain provider outcomes follow documented duplicate policy.
-   Retry processing is bounded and resumable.

### Deployment checks

-   `vercel.json` contains intended cron configuration.
-   Production cron endpoints are protected.
-   No in-process scheduler or long-running worker is introduced.
-   No persistent business state is stored in local filesystem/process
    memory.
-   Vercel execution limits are respected.
-   `ruff check .`, `ruff format .`,
    `python manage.py makemigrations --check --dry-run`, and `pytest`
    pass, or unrun checks are explicitly marked.
-   Dependency audit is run before release.

------------------------------------------------------------------------

## 11. Open decisions and assumptions

  ---------------------------------------------------------------------------
  \#                Topic             Source position     Decision needed
  ----------------- ----------------- ------------------- -------------------
  1                 Cron frequency    Required tasks      Define schedule for
                                      listed;             each task.
                                      times/frequencies   
                                      absent.             

  2                 Business timezone Not defined         Confirm timezone
                                      globally.           for date-based jobs
                                                          and due-date
                                                          comparisons.

  3                 Cron overlap      Jobs must be        Decide whether
                                      idempotent.         run-level
                                                          locks/records are
                                                          needed in addition
                                                          to per-record
                                                          protection.

  4                 Batch size        Hundreds of         Measure safe batch
                                      subscriptions;      size and
                                      Vercel time limits  continuation
                                      apply.              strategy.

  5                 Email provider    Replaceable         Select provider and
                                      provider required;  verify runtime
                                      no provider named.  compatibility.

  6                 Sender identity   Not specified.      Confirm sender
                                                          name/address and
                                                          reply-to.

  7                 Staff recipients  Staff alerts        Define which Staff
                                      required;           receive each alert.
                                      recipients          
                                      unspecified.        

  8                 Retry policy      Failures            Define retry count,
                                      logged/retried;     backoff, max age,
                                      details absent.     terminal state.

  9                 Duplicate email   Successful reminder Define
                                      reruns must not     uncertain-timeout
                                      duplicate.          handling and
                                                          provider
                                                          idempotency
                                                          support.

  10                Notification      Not specified.      Define
                    retention                             retention/access
                                                          policy for delivery
                                                          logs.

  11                Dunning cadence   Open Item C: 1, 7,  Confirm cadence and
                                      14 days, then       final action.
                                      auto-pause (working 
                                      assumption).        

  12                Renewal retry     FR-4.8 leaves retry Confirm retry
                                      N and final action  count, intervals,
                                      open.               grace period,
                                                          pause/close
                                                          behavior.

  13                Quote expiry      Expired quotes      Confirm job
                    frequency         cannot be accepted. frequency and exact
                                                          validity boundary.

  14                Plan auto-close   Scheduler closes    Confirm frequency
                    frequency         eligible plans      and date/time
                                      after end date.     boundary.

  15                Scheduler         UI asks for visible Decide if existing
                    visibility        automation; no      logs suffice or an
                                      scheduler screen    operational view is
                                      specified.          needed.
  ---------------------------------------------------------------------------

### Assumptions to avoid

-   Do not assume a cron hour, timezone, or frequency.
-   Do not assume Vercel Cron is exactly-once.
-   Do not assume a timeout means an email was not delivered.
-   Do not claim exactly-once email delivery without provider support.
-   Do not roll back business state because email failed.
-   Do not add a queue, worker, or scheduler library without approval.
-   Do not move domain business logic into M10.
-   Do not treat Open Item C or renewal retry policies as finalized.
-   Do not assume a scheduler administration UI is required.

------------------------------------------------------------------------

## 12. Definition of Done

-   [ ] FR-10.1 through FR-10.3 implemented.
-   [ ] FR-10.4 failure logging/retry implemented or explicitly deferred
    with approval.
-   [ ] Scheduler invokes billing runs.
-   [ ] Scheduler invokes automatic renewals.
-   [ ] Scheduler invokes plan auto-close.
-   [ ] Scheduler invokes quotation expiry.
-   [ ] Scheduler invokes dunning reminders.
-   [ ] Each task calls its owning domain entry point.
-   [ ] Jobs are idempotent under reruns and overlapping invocations.
-   [ ] Long work is bounded and resumable within Vercel limits.
-   [ ] Cron endpoints are protected by configured secret.
-   [ ] No Celery, Redis queue, APScheduler, or in-process scheduler
    introduced.
-   [ ] Emails cover password reset, invoice delivery, payment failure,
    overdue reminders, and Staff alerts.
-   [ ] Email provider is behind a small replaceable boundary.
-   [ ] Delivery failures are logged and retried according to approved
    policy.
-   [ ] Email failure does not roll back originating business
    transactions.
-   [ ] Successful reminders are not duplicated on reruns.
-   [ ] Secrets and reset tokens are not logged/exposed.
-   [ ] Tests cover endpoint protection, idempotency, overlap, batching,
    email failures, and retries.
-   [ ] Migrations and project checks pass, or unrun checks are
    documented.
-   [ ] No unapproved dependencies or out-of-scope channels are
    introduced.
-   [ ] Open schedule/retry/dunning policies are approved or explicitly
    deferred.

------------------------------------------------------------------------

## 13. Developer self-review

  -----------------------------------------------------------------------
  Area                    Review question         Status
  ----------------------- ----------------------- -----------------------
  Ownership               Does M10 orchestrate    Verify during
                          without duplicating     implementation
                          domain logic?           

  Scheduler               Are all five scheduled  Verify
                          operations configured?  

  Idempotency             Are reruns and overlaps Verify
                          safe at database/domain 
                          level?                  

  Batching                Are long jobs bounded   Verify
                          and resumable?          

  Vercel                  Protected cron          Verify
                          endpoints; no           
                          in-process workers?     

  Email boundary          Is provider contract    Verify
                          small and replaceable?  

  Event coverage          Are all five email      Verify
                          categories implemented? 

  Retry                   Are failures            Verify
                          logged/retryable        
                          without duplicate       
                          successful sends?       

  Transactions            Can email fail without  Verify
                          rolling back business   
                          state?                  

  Security                Are cron/provider       Verify
                          secrets, reset tokens,  
                          and customer data       
                          protected?              

  Error handling          Are exceptions narrow   Verify
                          and failures isolated   
                          per record?             

  Dependencies            Are packages justified, Verify
                          pinned,                 
                          Vercel-compatible?      

  Tests                   Are scheduler,          Verify
                          notification, retry,    
                          and failure-path tests  
                          present?                
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 14. Source of truth

Derived from: 1. `REQUIREMENTS.md`: FR-10.1--FR-10.4, FR-1.4, FR-3.6,
FR-4.8, FR-4.11, FR-5.2, FR-5.9, FR-7.8, NFR-2, NFR-5, NFR-7, NFR-9, and
Open Items C/G/H. 2. `UI_UX.md`: notification events and failure
behavior, dunning working assumption, scheduled billing/renewal flows,
visible automation, and no-silent-failure principles. 3.
`CODING_STANDARDS.md`: modular-monolith structure, task/service
boundaries, PostgreSQL source of truth, transactions/locking, protected
Vercel Cron, batching/resumability, error handling, and test standards.

Requirements define what to build; coding standards define
implementation constraints; UI/UX defines expected interaction and
operational feedback. Unresolved decisions are recorded rather than
silently resolved. This is an implementation baseline, not a claim that
M10 is implemented.