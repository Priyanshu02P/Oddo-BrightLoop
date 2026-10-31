# M3. Plans

**Project:** Brightloop Subscription Management System  
**Module:** M3 — Plans  
**Document type:** Current feature specification and implementation baseline  
**Status:** Specification baseline derived from the project source documents  
**Primary sources:** `REQUIREMENTS.md`, `UI_UX.md`, and `CODING_STANDARDS.md`

---

## 1. Purpose and scope

M3 defines how an Admin creates and manages subscription plans. A plan provides the commercial and lifecycle configuration used when a subscription is created and managed.

A plan contains its name, price, billing period, minimum quantity, availability window, renewal mode, and enabled lifecycle options. The system must use these settings when determining whether a plan can be selected for a new subscription and which lifecycle actions are permitted for a subscription using that plan.

M3 also includes the scheduled behavior required to close subscriptions whose plan has the **auto-close at end date** option enabled when the plan's end date passes.

This document describes the expected feature behavior. It is not evidence that the feature has already been implemented.

### 1.1 Goals

- Allow Admin to create plans with the fields defined in FR-3.1.
- Support daily, weekly, monthly, and yearly billing periods.
- Allow Admin to enable or disable lifecycle options independently for each plan.
- Store whether renewal is automatic or manual.
- Restrict plan selection for new subscriptions to the plan's availability dates.
- Automatically close eligible subscriptions after a plan's end date when auto-close is enabled.
- Make plan configuration available to the quotation and subscription workflows in M4.
- Keep plan data persistent in PostgreSQL and follow the project's Django modular-monolith architecture.

### 1.2 In scope

- Admin-only plan management.
- Plan list and plan create/edit form.
- Plan name and price.
- Billing period: daily, weekly, monthly, yearly.
- Minimum quantity.
- Availability start and end dates.
- Per-plan lifecycle settings:
  - Auto-close at end date.
  - Close early.
  - Pause.
  - Renew.
- Renewal mode: `automatic` or `manual`.
- Availability validation for new subscription selection.
- Scheduled auto-close behavior for subscriptions tied to plans configured to auto-close.
- Server-side validation, persistence, audit integration, and automated tests.

### 1.3 Out of scope

The following are not M3 deliverables unless a separate requirement or product decision adds them:

- Product or variant management (M2).
- Tax creation or tax-rate management (M9); plan price must not introduce a separate tax configuration that conflicts with product-level tax rules.
- Payment-term management (M9).
- Quotation-template management (M4).
- Subscription creation, subscription-line editing, or the full subscription lifecycle UI (M4), except that M3 supplies plan data and configuration to those workflows.
- Invoice generation, billing calculations, or payment collection (M5/M7).
- Discount creation or discount calculations (M6).
- A real payment gateway.
- Multi-currency or multi-company support; the requirements currently assume one currency and one company, subject to confirmation.
- Plan marketplace, public plan browsing, self-service plan purchasing, or customer-facing plan administration.
- Plan cloning, version history, scheduled price changes, promotional pricing, trials, usage-based billing, or plan categories unless separately specified.
- Automatically changing the price of an existing subscription when its plan is edited. Historical and in-force subscription pricing behavior is not defined and must be decided before implementation.

---

## 2. Requirement traceability

All M3 requirements below are marked **Must (M)** in `REQUIREMENTS.md`.

| Requirement | Source requirement | Expected M3 behavior |
|---|---|---|
| FR-3.1 | Admin can create plans with name, price, billing period (daily, weekly, monthly, yearly), minimum quantity, and availability start/end dates. | Provide an Admin-only plan form and persist each required field. |
| FR-3.2 | Plans support auto-close at end date, close early, pause, and renew lifecycle options. | Store and expose these four lifecycle capabilities as plan-level options. |
| FR-3.3 | Admin decides, plan by plan, which lifecycle options are enabled. | Each plan has its own independently configurable lifecycle settings. |
| FR-3.4 | Each plan has `renewal_mode` = `automatic` or `manual`. | Store a constrained renewal-mode value and show it in plan management. |
| FR-3.5 | A plan is only selectable for new subscriptions within its availability dates. | Validate availability against the proposed subscription start date on the server; the M4 selection UI should show only eligible plans. |
| FR-3.6 | A plan configured to auto-close is closed by the scheduler when its end date passes. | Provide an idempotent scheduled operation that closes eligible subscriptions according to the plan's auto-close setting. |

### 2.1 Related requirements and business rules

- **Role–Permission Matrix, Section 4:** only Admin can manage plans. Staff and Customer do not have plan-management permission.
- **BR-3:** a subscription has exactly one plan and one customer.
- **BR-12:** customers can only perform portal actions that the plan's lifecycle options allow.
- **FR-4.7:** customer portal actions such as pause, resume, cancel, upgrade/downgrade, and quantity changes are permitted only when the plan's lifecycle options allow them.
- **FR-4.8 and FR-4.9:** automatic and manual renewal flows depend on the plan's renewal mode.
- **FR-4.10:** paused subscriptions are excluded from billing; on resume, the next billing date is recalculated.
- **NFR-5:** relevant Admin changes and status changes are logged with actor and timestamp.
- **NFR-7:** scheduled jobs must recover from failure and be safe to rerun.
- **NFR-10:** monetary values use fixed-precision decimals, never floating point.

### 2.2 Source-of-truth boundaries

- `REQUIREMENTS.md` defines the mandatory behavior and business rules.
- `UI_UX.md` describes the plan list, create/edit fields, and how plans are selected in the subscription flow.
- `CODING_STANDARDS.md` defines the Django structure, database, service boundaries, security, scheduler constraints, and test approach.
- Where the documents do not specify a behavior, this specification marks it as an open decision rather than silently inventing a rule.

---

## 3. Roles and permissions

### 3.1 Admin

Admin is the only role permitted to:

- Open the plan-management area.
- View the plan list and plan details.
- Create a plan.
- Edit plan fields and lifecycle settings.
- Configure `renewal_mode`.
- Enable or disable lifecycle options for an individual plan.
- Review plan availability and status.

### 3.2 Internal Staff

Staff may use plans in day-to-day subscription and quotation workflows as allowed by M4, but must not:

- Create plans.
- Edit plans.
- Change plan prices or billing periods.
- Change plan availability dates or minimum quantity.
- Change renewal mode.
- Change lifecycle options.

Staff access to plan information needed to create a subscription is distinct from permission to manage plan configuration. The exact read-only plan detail visibility should follow the M4 workflow and existing project permission conventions.

### 3.3 Customer

Customers do not manage plans. They may interact with their own subscriptions only through actions permitted by the lifecycle settings of the relevant plan and the subscription's current state.

### 3.4 Authorization requirements

- Enforce Admin-only plan-management permissions on the server for every list, detail, create, update, and other management endpoint.
- Hiding a menu item or button is not sufficient authorization.
- Staff and Customer requests to plan-management endpoints must be denied even if they construct the URL manually.
- Apply default-deny behavior to permissions not explicitly granted by the role matrix.
- Do not allow a submitted role, permission, or ownership field to elevate access.

---

## 4. Plan data model

The domain entity is `Plan`. The exact Django model implementation should match the existing repository conventions and any shared base models already present.

### 4.1 Required fields

| Field | Expected type | Required | Description |
|---|---|---:|---|
| `name` | String / `CharField` | Yes | Human-readable plan name. |
| `price` | `DecimalField` | Yes | Plan price, stored using fixed precision. |
| `billing_period` | Constrained string / choices | Yes | One of `daily`, `weekly`, `monthly`, or `yearly`. |
| `minimum_quantity` | Positive integer or project-equivalent type | Yes | Minimum quantity allowed for the plan. |
| `availability_start_date` | Date | Yes, subject to source interpretation | First date on which the plan may be selected for a new subscription. |
| `availability_end_date` | Date | Yes, subject to source interpretation | Last date on which the plan may be selected for a new subscription. |
| `renewal_mode` | Constrained string / choices | Yes | `automatic` or `manual`. |
| `auto_close_at_end_date` | Boolean | Yes | Whether subscriptions using this plan are automatically closed after the plan end date. |
| `allow_close_early` | Boolean | Yes | Whether the plan permits early closure. |
| `allow_pause` | Boolean | Yes | Whether the plan permits pausing. |
| `allow_renew` | Boolean | Yes | Whether the plan permits renewal. |

The source describes the availability start and end dates as plan fields. If the repository uses different field names, retain its established naming convention while preserving the same meaning.

### 4.2 Suggested choices

`billing_period`:

- `daily`
- `weekly`
- `monthly`
- `yearly`

`renewal_mode`:

- `automatic`
- `manual`

Use Django `TextChoices` or the project's established enum convention rather than unrestricted strings.

### 4.3 Lifecycle configuration

Lifecycle settings are plan-level permissions/capabilities. They determine which subscription operations may be offered, subject to the subscription's current state and the rest of the M4 state machine.

| Option | Meaning in M3 | Related workflow |
|---|---|---|
| Auto-close at end date | The plan enables scheduler-driven closure after its end date passes. | M3 scheduled operation and M4 subscription state. |
| Close early | Early closure is permitted for a subscription using the plan. | M4 subscription lifecycle. |
| Pause | Pausing is permitted for a subscription using the plan. | M4 pause/resume and M5 billing exclusion. |
| Renew | Renewal is permitted for a subscription using the plan. | M4 renewal flow; behavior also depends on `renewal_mode`. |

Do not assume that `allow_close_early` is identical to `auto_close_at_end_date`. They represent separate options: one permits an early close action, while the other enables a scheduled close when the plan end date passes.

### 4.4 Monetary representation

- Store `price` in a Django `DecimalField` with precision consistent with the project standards (the coding standards give `max_digits=12, decimal_places=2` as an example).
- Never use Python `float` for plan prices or calculations.
- Parse and validate submitted monetary values as decimals.
- Use the project's shared money-rounding helper when a calculation requires rounding.
- Currency is currently assumed to be a single system-wide currency; multi-currency support is not part of M3.

### 4.5 Relationships

- A `Plan` can be referenced by subscriptions. Each subscription has exactly one plan (BR-3).
- A plan may be referenced by quotation templates under M4.
- M3 must not create duplicate Product, Tax, PaymentTerm, Subscription, or QuotationTemplate entities.
- Plan deletion/archival behavior when existing subscriptions or templates reference it is not fully specified. See Open Decisions.

---

## 5. Plan management UI/UX

**Audience:** Admin only.

### 5.1 Plan list

The plan list should display the following columns, as specified in `UI_UX.md`:

| Column | Display |
|---|---|
| Plan name | Name of the plan. |
| Price | Formatted plan price. |
| Billing period | Daily, weekly, monthly, or yearly. |
| Minimum quantity | Configured minimum quantity. |
| Availability window | Start and end dates. |
| Renewal mode | Automatic or Manual. |
| Lifecycle options | Clearly indicate which options are enabled. |
| Status | Current plan status, if the application maintains one. The exact status model is an open decision. |

Available actions:

- Create plan.
- Open plan details.
- Edit plan.

Do not add archive/delete actions as mandatory behavior: the M3 requirements do not explicitly define plan archival or deletion. If the existing application already has a general archive convention, confirm how it should apply to plans that are referenced by subscriptions before implementing it.

### 5.2 Plan create/edit form

The form must include:

1. Name.
2. Price.
3. Billing period selector with Daily, Weekly, Monthly, and Yearly.
4. Minimum quantity.
5. Availability start date.
6. Availability end date.
7. Renewal mode selector with Automatic and Manual.
8. Lifecycle options:
   - Auto-close at end date.
   - Close early.
   - Pause.
   - Renew.

Each lifecycle option must be configurable independently for the plan. The form should make it clear that these settings control actions on subscriptions using the plan.

### 5.3 Form behavior

- Show field-level validation errors.
- Preserve entered values after recoverable validation errors.
- Do not silently replace invalid or missing values with defaults unless a default is explicitly approved.
- Require confirmation for consequential changes if the application design uses confirmation for such actions.
- Display a clear success or error state after save.
- Do not rely on client-side validation alone; the server is authoritative.

### 5.4 Availability explanation

The UI should explain that a plan is selectable for **new subscriptions only within its availability dates**.

When a user selects a subscription start date in M4, the plan selector should show only plans available on that selected date. If an unavailable plan is requested through a direct or manipulated request, the backend must reject it.

Existing subscriptions may continue to reference a plan outside its new-subscription availability window. The source UI/UX document explicitly notes that precise edit/archive behavior for plans already in use requires confirmation. Do not automatically invalidate existing subscriptions merely because the plan is no longer available for new subscriptions.

### 5.5 Lifecycle options in downstream UI

M4 should use the plan configuration when deciding which subscription actions to display or permit. The UI may hide or disable unavailable actions and explain that the plan does not permit the action. The backend must enforce the same rule.

The lifecycle configuration does not replace validation of the subscription state machine. For example, an enabled Pause option does not mean every subscription state can be paused; only valid transitions are allowed.

---

## 6. Core business logic

### 6.1 Create plan

Expected flow:

1. Admin opens Plan Management.
2. Admin selects Create Plan.
3. System displays the plan form.
4. Admin enters the required plan details.
5. Admin chooses a billing period.
6. Admin sets the minimum quantity and availability dates.
7. Admin selects automatic or manual renewal.
8. Admin configures each lifecycle option.
9. Server validates all fields and permission.
10. System persists the plan.
11. System records the relevant Admin action through the existing audit mechanism.
12. UI returns a success response and displays the created plan.

The operation must not be available to Staff or Customers.

### 6.2 Edit plan

Expected flow:

1. Admin opens an existing plan.
2. System loads the persisted plan configuration.
3. Admin changes one or more editable fields.
4. Server checks Admin permission and validates the complete resulting configuration.
5. System saves the update.
6. System records the actor, plan, operation, and timestamp using the shared audit approach.
7. UI displays the updated plan.

The requirements do not specify whether editing a plan changes existing subscriptions that reference it. Do not silently recalculate or rewrite existing subscription prices, invoices, or historical records. Confirm the intended policy before implementing such behavior.

### 6.3 Determine plan availability

A plan may be selected for a new subscription only when the proposed subscription start date falls within the plan's availability window.

Conceptual rule:

```text
is_available_for_new_subscription(plan, start_date):
    return plan.availability_start_date <= start_date
       and start_date <= plan.availability_end_date
```

This inclusive-boundary expression reflects the ordinary meaning of start/end dates, but the requirements do not explicitly state boundary inclusivity or whether either date may be omitted. Confirm these details before treating the expression as final business policy.

Availability validation must happen on the server, not only in the plan selector UI.

### 6.4 Lifecycle permission checks

When a subscription action is requested, the application must check:

1. The actor's role and ownership/authorization rules.
2. The subscription's current state and whether the requested transition is valid.
3. The relevant lifecycle option on the subscription's plan.
4. Any additional requirement-specific conditions for that operation.

For example:

- Pause requires the plan's Pause option and a valid transition to Paused.
- Early close requires the plan's Close early option and a valid transition to Closed.
- Renewal requires the plan's Renew option and the applicable renewal-mode flow.
- Scheduled auto-close requires the plan's Auto-close at end date option and a passed end date.

M3 stores and exposes these settings; M4 owns the subscription transition workflows.

### 6.5 Automatic versus manual renewal mode

`renewal_mode` must be one of:

- `automatic`: the subscription follows the automatic-renewal flow defined in M4, including renewal invoice generation and payment collection behavior.
- `manual`: the customer or Staff triggers renewal as described in M4.

The plan's `allow_renew` lifecycle option and `renewal_mode` are distinct settings. The first controls whether renewal is permitted; the second controls how the renewal is initiated. Do not infer that setting `renewal_mode=automatic` alone overrides a disabled Renew option. The combined rule should be enforced consistently and clarified in the product decision log if necessary.

### 6.6 Scheduled auto-close

FR-3.6 requires a scheduler to close subscriptions using plans configured for auto-close after the plan end date passes.

The scheduled operation should:

1. Run through the project's approved scheduler mechanism.
2. Identify plans with auto-close enabled and an end date that has passed.
3. Identify subscriptions associated with those plans that are eligible for the close transition.
4. Transition each eligible subscription to Closed using the M4 subscription lifecycle service/state machine, rather than assigning status directly.
5. Record the actor/system identity and transition timestamp using the existing audit mechanism.
6. Be safe to run more than once; already-closed subscriptions must not be processed as new transitions.
7. Log failures and continue processing other eligible subscriptions where the existing job conventions permit per-record isolation.

The coding standards specify Vercel Cron calling protected endpoints that invoke task entry points. They prohibit relying on long-running in-process schedulers or persistent local filesystem state. Follow the project's actual deployment conventions.

M3 must not invent a new scheduler framework or add Celery/another worker system unless the project requirements and deployment architecture are explicitly changed.

### 6.7 Scheduled job idempotency and safety

- A repeated scheduler invocation must not create duplicate transitions or duplicate audit events for a subscription already closed.
- The operation should use the shared transition service and its validation rules.
- Use database transactions for multi-step writes.
- If concurrent executions are possible, use the project's established locking/claiming strategy so two invocations do not race to transition the same subscription.
- Log execution outcome and per-record failures in the project's existing operational logging/job-result pattern, if present.
- The exact schedule frequency is not specified by the source documents and must be configured/confirmed separately.

---

## 7. Validation rules

The following table separates required validation from details that remain unspecified.

| Field / operation | Validation |
|---|---|
| Name | Required; reject blank or whitespace-only values. |
| Price | Required decimal value; reject malformed values and values outside the agreed decimal precision. |
| Billing period | Required; accept only `daily`, `weekly`, `monthly`, or `yearly`. |
| Minimum quantity | Required; validate as a quantity and reject values that violate the chosen positive-integer rule. The source calls it a minimum quantity but does not explicitly define whether zero is allowed. |
| Availability start date | Required or optional according to the final interpretation of the source field; validate as a date. |
| Availability end date | Required or optional according to the final interpretation of the source field; validate as a date. |
| Availability window | If both dates are present, reject an end date earlier than the start date. |
| Renewal mode | Required; accept only `automatic` or `manual`. |
| Lifecycle options | Persist explicit boolean values; do not accept arbitrary client-supplied option names. |
| Plan selection | Reject a new subscription if its selected start date is outside the plan's availability window. |
| Lifecycle action | Reject if the plan option is disabled, the actor lacks permission, or the state transition is invalid. |
| Scheduled auto-close | Process only plans with auto-close enabled whose end date has passed; do not repeat a completed close transition. |

### 7.1 Validation details not specified by the source

The requirements do not define:

- Whether price may be zero or negative.
- Whether minimum quantity must be at least 1 or may be zero.
- Whether availability start and end dates are mandatory or can be open-ended.
- Whether the start and end dates are inclusive.
- Whether a plan can have an end date without a start date, or vice versa.
- Whether duplicate plan names are allowed.
- Maximum plan-name length.
- Whether a plan can be deleted or archived.
- Whether a plan's price or configuration may be edited after it is used by subscriptions.
- The exact recurrence/calendar calculation for daily, weekly, monthly, and yearly periods.
- The exact scheduler frequency/time zone.

These must be treated as open decisions rather than silently resolved in implementation.

---

## 8. Integration with other modules

### 8.1 M2 — Product Catalog

M2 manages sellable products and variants. M3 manages plans. Do not duplicate product fields or product CRUD in the Plan model.

### 8.2 M4 — Quotation Templates and Subscriptions

M4 is the primary consumer of plan data:

- A subscription references exactly one plan.
- A quotation template references a plan.
- New subscription creation must offer only plans available on the selected start date.
- Subscription lifecycle actions must respect the plan's lifecycle options.
- Renewal behavior must respect `renewal_mode` and the enabled Renew option.
- Subscription closure at the plan end date must use the subscription state-transition mechanism.

### 8.3 M5 — Invoicing and Billing

M5 uses subscription billing dates and the subscription's plan context. M3 supplies the billing period and plan configuration, but does not generate invoices or run billing calculations.

Paused subscriptions are excluded from billing under FR-4.10 and BR-6; that behavior belongs to the subscription/billing integration, not to a separate plan-side billing process.

### 8.4 M7 — Payments

Automatic renewal may invoke the payment-provider flow defined in M7. M3 stores the renewal mode but does not implement payment collection or gateway behavior.

### 8.5 M8 — Reporting and Dashboard

Plan data may be used by reports or filters if required by M8. M3 does not define dashboard metrics or reporting calculations.

---

## 9. Architecture and implementation guidance

The coding standards define a Django modular monolith backed by PostgreSQL. Follow the existing repository structure and avoid introducing a separate service or microservice for plans.

### 9.1 Suggested app location

The coding standards place plans in `apps/plans/`.

Suggested structure, adapted to the actual repository:

```text
apps/plans/
├── models.py          # Plan fields, choices, constraints, simple properties
├── services.py        # create/update plan operations and plan-specific writes
├── selectors.py       # plan list/detail and availability queries
├── views.py           # thin request handlers
├── forms.py           # server-side form validation
├── permissions.py     # only if shared permission layer does not cover it
├── urls.py
├── admin.py
├── tasks.py           # scheduled auto-close entry point, calling lifecycle services
├── tests/
└── migrations/
```

Do not create duplicate files if the project already has equivalent modules. If the existing repository places Plan in another app, follow the existing architecture rather than moving code solely to match this illustrative tree.

### 9.2 Model responsibilities

- Store plan fields and lifecycle settings.
- Define constrained choices for billing period and renewal mode.
- Use `DecimalField` for price.
- Add database constraints for clear invariants where appropriate.
- Keep models free of email, payment, scheduler, or other external side effects.
- Do not put multi-step lifecycle transitions in model `save()` methods.

### 9.3 Service responsibilities

Write operations belong in services. Suggested service operations include:

- `create_plan(...)`
- `update_plan(...)`
- `is_plan_available_for_start_date(plan, start_date)`
- `get_enabled_lifecycle_options(plan)`

The names are illustrative, not mandatory public APIs. Match repository conventions and avoid unnecessary abstractions.

Subscription state changes must go through the M4 subscription transition service. The plan app should not directly assign `subscription.status` or duplicate the subscription state machine.

Wrap multi-step writes in `transaction.atomic()`.

### 9.4 Selector responsibilities

Use selectors for non-trivial reads, such as:

- Admin plan list with pagination.
- Plan detail with the relevant configuration.
- Plans available for a proposed subscription start date.
- Plans whose end dates have passed and auto-close is enabled, where this query is owned by the plan app.

Use appropriate `select_related`/`prefetch_related` when relations are needed. Avoid N+1 queries and speculative indexes.

### 9.5 Task/scheduler responsibilities

- Expose a protected task entry point for scheduled auto-close.
- Keep the task thin: identify eligible records and call the shared subscription transition service.
- Make it idempotent and safe for overlapping/repeated invocations.
- Follow the coding standards' Vercel Cron approach.
- Do not run a permanent scheduler inside a serverless process.
- Do not use local files or in-memory globals as persistent job state.

### 9.6 Auditability

Relevant Admin changes must integrate with the project's existing audit mechanism. At minimum, plan create/update actions should identify:

- Actor.
- Plan.
- Operation performed.
- Timestamp.

The scheduler-driven subscription closure must be auditable through the existing subscription transition/audit mechanism. The source does not prescribe a separate plan audit schema or exact event names; reuse the shared approach.

### 9.7 Database and migrations

- PostgreSQL is the source of truth.
- Every model change must include a migration.
- Never edit an applied migration; create a new migration instead.
- Run migrations as an explicit deployment step, not at request time.
- Use database constraints for clear invariants that must survive concurrent requests.
- Keep the application compatible with the project's Vercel/serverless deployment constraints.

### 9.8 Dependencies

- Prefer Django and the standard library.
- Do not add a package for basic plan CRUD, date validation, or decimal handling.
- Do not introduce a task queue or scheduler dependency without explicit approval and a demonstrated need consistent with the deployment standards.

---

## 10. Security and data integrity

- Plan management endpoints are Admin-only and protected server-side.
- Staff and Customer cannot create or modify plans through direct requests.
- Validate all submitted fields on the server.
- Never trust a client-provided price, lifecycle permission, or renewal mode without authorization and validation.
- Use Django ORM or parameterized SQL; never interpolate untrusted input into SQL.
- Keep Django template auto-escaping enabled.
- Apply CSRF protection to state-changing browser requests.
- Use database transactions for multi-record operations.
- Avoid exposing internal stack traces or sensitive data in error responses.
- Keep plan price calculations in `Decimal`, never float.
- Prevent invalid subscription transitions through the shared state machine.
- Ensure scheduled auto-close cannot repeatedly close or corrupt already-closed subscriptions.

---

## 11. Acceptance criteria

M3 is functionally acceptable when all applicable criteria below pass.

### 11.1 Plan management

- [ ] Admin can open Plan Management.
- [ ] Admin can create a plan.
- [ ] Admin can edit an existing plan.
- [ ] The form captures name, price, billing period, minimum quantity, availability dates, renewal mode, and lifecycle options.
- [ ] Billing period accepts only Daily, Weekly, Monthly, and Yearly.
- [ ] Renewal mode accepts only Automatic and Manual.
- [ ] Each lifecycle option can be configured independently per plan.
- [ ] Saved values persist after reload.
- [ ] Plan list shows the fields described in the UI/UX specification.
- [ ] Validation errors are clear and preserve entered values where possible.

### 11.2 Permissions

- [ ] Admin can create and edit plans.
- [ ] Staff cannot create or edit plans.
- [ ] Customer cannot create or edit plans.
- [ ] Direct requests to protected plan-management endpoints are denied for unauthorized roles.
- [ ] Plan configuration is not writable through forged client-side role or permission values.

### 11.3 Availability

- [ ] A plan is available for a new subscription only within its configured availability dates.
- [ ] The M4 plan selector filters plans for the selected subscription start date.
- [ ] The server rejects a new subscription that references an unavailable plan.
- [ ] Existing subscriptions are not automatically invalidated merely because the plan is outside its new-subscription availability window.

### 11.4 Lifecycle configuration

- [ ] Admin can enable or disable Auto-close at end date per plan.
- [ ] Admin can enable or disable Close early per plan.
- [ ] Admin can enable or disable Pause per plan.
- [ ] Admin can enable or disable Renew per plan.
- [ ] M4 action availability respects the plan configuration.
- [ ] The backend rejects lifecycle actions disabled by the plan.
- [ ] A disabled lifecycle option does not bypass the subscription state machine.

### 11.5 Renewal mode

- [ ] Every plan stores either `automatic` or `manual` as its renewal mode.
- [ ] The selected mode is displayed in plan management.
- [ ] M4 receives the plan's renewal mode and follows the appropriate renewal flow.
- [ ] Renewal remains subject to the plan's Renew lifecycle option.

### 11.6 Scheduled auto-close

- [ ] A plan with auto-close disabled is not selected for automatic closure by this M3 task.
- [ ] A plan with auto-close enabled and an end date that has passed is eligible for processing.
- [ ] Eligible subscriptions are closed through the shared subscription transition service.
- [ ] A plan whose end date has not passed does not trigger closure.
- [ ] Already-closed subscriptions are not transitioned again.
- [ ] Re-running the task does not create duplicate transitions or duplicate audit entries.
- [ ] A failure for one subscription does not silently prevent other eligible records from being processed, subject to the established task error-handling pattern.
- [ ] Task execution and failures are logged using the existing operational conventions.

### 11.7 Quality

- [ ] Loading, empty, success, validation, and error states are handled.
- [ ] Consequential changes use confirmation where required by the shared UX conventions.
- [ ] Keyboard navigation and visible focus states work.
- [ ] Status and lifecycle state are not communicated by color alone.
- [ ] Plan list queries are paginated where appropriate.
- [ ] No N+1 query issue is introduced in the plan list/detail flows.
- [ ] Migrations are present and pass the project's migration checks.

---

## 12. Test plan

Use `pytest`, `pytest-django`, and `factory-boy` as specified by the coding standards. Tests must not call real external services. Use `Decimal` for monetary assertions.

### 12.1 Model and field tests

1. Create a plan with all valid required fields.
2. Reject a blank plan name.
3. Reject a malformed price.
4. Verify price is stored and returned as a `Decimal`.
5. Accept each supported billing period: daily, weekly, monthly, yearly.
6. Reject an unsupported billing period.
7. Accept `automatic` renewal mode.
8. Accept `manual` renewal mode.
9. Reject an unsupported renewal mode.
10. Persist all four lifecycle option values independently.
11. Verify date fields are stored correctly.
12. Verify any implemented database constraints.

### 12.2 Plan CRUD and permission tests

1. Admin can access the plan list.
2. Admin can view plan details.
3. Admin can create a plan.
4. Admin can edit a plan.
5. Staff cannot access plan create/update endpoints.
6. Customer cannot access plan create/update endpoints.
7. Anonymous users cannot access protected management endpoints.
8. Direct URL/API requests enforce the same permissions as the UI.
9. A forged role or lifecycle field does not grant additional privileges.
10. Create/update actions integrate with the audit mechanism.

### 12.3 Availability tests

1. A start date inside the availability window is accepted.
2. A date before the availability start is rejected.
3. A date after the availability end is rejected.
4. The configured boundary dates behave according to the confirmed inclusive/exclusive policy.
5. The M4 plan selector returns only plans available for the selected subscription start date.
6. A manipulated request referencing an unavailable plan is rejected server-side.
7. Existing subscriptions can still be read when their plan is outside its new-subscription availability window.

### 12.4 Lifecycle option tests

1. Each option can be enabled independently.
2. Each option can be disabled independently.
3. A disabled Pause option blocks a pause request.
4. An enabled Pause option still respects valid subscription-state transitions.
5. A disabled Close early option blocks an early-close request.
6. An enabled Close early option still respects the state machine.
7. A disabled Renew option blocks renewal.
8. An enabled Renew option allows the M4 renewal flow to proceed when other conditions pass.
9. Auto-close is evaluated independently from Close early.
10. Customer portal action permissions follow the plan settings.

### 12.5 Renewal mode tests

1. Automatic mode is persisted and exposed to M4.
2. Manual mode is persisted and exposed to M4.
3. Unsupported values are rejected.
4. The renewal flow uses the configured mode.
5. Renewal is blocked when the plan's Renew option is disabled, according to the agreed combined rule.

### 12.6 Scheduler tests

1. No auto-close processing for plans with the option disabled.
2. No auto-close processing before the plan end date.
3. Eligible subscriptions are closed after the end date passes.
4. Closure is performed through the shared subscription transition service.
5. Already-closed subscriptions are skipped.
6. Repeated task invocation is idempotent.
7. Concurrent/repeated invocations do not produce duplicate transitions.
8. Each successful closure is auditable.
9. A failed record is logged and other eligible records are handled according to the task's per-record error policy.
10. The protected scheduled endpoint rejects unauthorized requests.

### 12.7 Regression and integration tests

- M4 can reference a valid Plan.
- Quotation templates can reference a valid Plan.
- M4 plan selection respects availability dates.
- M4 lifecycle actions respect plan settings.
- M4 renewal flow respects `renewal_mode`.
- M5 billing continues to exclude paused subscriptions.
- M3 changes do not rewrite historical invoice or subscription-line data.

---

## 13. Open decisions and assumptions

The following questions are not fully answered by the source documents and must be confirmed before the corresponding implementation is finalized.

| ID | Open decision | Why it matters | Safe handling until confirmed |
|---|---|---|---|
| M3-O1 | Are availability start/end dates both mandatory, or can either be empty to represent an open-ended window? | Affects schema, form validation, and availability queries. | Preserve the source fields; do not invent open-ended semantics. |
| M3-O2 | Are availability boundaries inclusive? | Determines whether a plan is selectable on the exact start and end dates. | Make the policy explicit before implementation; UI wording should match it. |
| M3-O3 | Is the end date the last date for new subscription selection, the date subscriptions must close, or both? | FR-3.5 and FR-3.6 use the plan end date in two related but distinct ways. | Implement only the stated behaviors and confirm the intended date semantics. |
| M3-O4 | Does auto-close close every subscription tied to the plan, or only subscriptions whose own expiry date has passed? | FR-3.6 says the plan is closed by the scheduler, while the state machine refers to plan end date as a closure trigger. | Do not add an extra subscription-expiry filter unless confirmed. |
| M3-O5 | What happens to subscriptions already Closed, Paused, or not yet Active when auto-close runs? | Determines eligibility and state-transition handling. | Use the existing state machine; define eligible source states with M4. |
| M3-O6 | What is the scheduler frequency and timezone? | Determines when after the end date the close occurs. | Follow the deployment scheduler convention; do not invent an exact schedule. |
| M3-O7 | What are the allowed price range and decimal precision? | Affects model constraints and form validation. | Use the project-wide money convention; confirm zero/negative policy. |
| M3-O8 | Must minimum quantity be at least 1? | Affects model field and validation. | Treat it as a quantity and confirm the lower bound. |
| M3-O9 | Can plan names repeat? | Affects uniqueness constraints and lookup UX. | Do not add a uniqueness constraint without a decision. |
| M3-O10 | Can plans be archived or deleted? | Existing subscriptions and templates may reference a plan. | Do not add mandatory archive/delete behavior from inference. |
| M3-O11 | Can plan fields/prices be edited after the plan is used? If yes, do existing subscriptions retain snapshots or follow updates? | Prevents unintended price changes and historical inconsistency. | Do not rewrite existing subscriptions or invoices automatically. |
| M3-O12 | If `renewal_mode=automatic` but `allow_renew=false`, what takes precedence? | The two settings are distinct and could conflict. | Enforce renewal permission and confirm the intended configuration rule. |
| M3-O13 | What calendar arithmetic defines monthly/yearly periods, including month-end and leap-year cases? | Required for next billing dates in M4/M5. | Do not invent date arithmetic in M3; centralize and confirm the shared billing-period rule. |
| M3-O14 | Does the plan price include any tax? | M3 requirements do not specify tax treatment for plan price in isolation; overall requirements assume product taxes are applied per product and prices are tax-exclusive. | Follow the global tax rules and confirm how plan price is represented in subscription lines. |

### 13.1 Explicit working assumptions

Until the open items are resolved:

- A plan is selectable for a new subscription only within its configured availability window.
- Existing subscriptions are not automatically invalidated solely because a plan is no longer available for new subscriptions.
- Lifecycle options are independent per-plan settings.
- `renewal_mode` is stored separately from the Renew lifecycle option.
- Automatic closure must use the subscription state machine and be idempotent.
- Plan prices use fixed-precision decimal storage.
- The project remains a Django modular monolith with PostgreSQL and the existing Vercel-compatible scheduler approach.

---

## 14. Definition of Done

M3 is complete when:

- [ ] All six requirements FR-3.1 through FR-3.6 are implemented.
- [ ] Admin-only plan CRUD/configuration is enforced server-side.
- [ ] Plan fields and constrained choices are persisted correctly.
- [ ] Lifecycle options are configurable independently for each plan.
- [ ] Renewal mode is stored as `automatic` or `manual`.
- [ ] New subscription plan selection enforces availability dates on the server.
- [ ] M4 can consume the plan's availability, lifecycle, and renewal configuration.
- [ ] Scheduled auto-close is implemented using the existing task/scheduler architecture.
- [ ] Scheduled closure uses the shared subscription transition service.
- [ ] The scheduled operation is safe to rerun and produces appropriate audit/log records.
- [ ] Database migrations are included.
- [ ] Unit, permission, availability, lifecycle, scheduler, and integration tests pass.
- [ ] `ruff check .` passes.
- [ ] `ruff format .` or the repository's chosen formatter passes.
- [ ] `python manage.py makemigrations --check --dry-run` reports no missing migrations.
- [ ] No unapproved dependencies or out-of-scope features are introduced.
- [ ] Open decisions affecting implementation are recorded for product confirmation.

---

## 15. Developer self-review checklist

Complete this checklist when implementing M3 code, in line with `CODING_STANDARDS.md`.

| Area | Review question | Status |
|---|---|---|
| File/component structure | Are models, services, selectors, views, forms, tasks, and tests placed according to the existing project structure? | To verify during implementation |
| State management | Is PostgreSQL the source of truth? Are subscription transitions delegated to the shared state machine? | To verify during implementation |
| Unused imports / dead code | Are unused imports, variables, stubs, debug prints, and dead code removed? | To verify during implementation |
| Dependencies | Were new dependencies avoided unless justified, approved, pinned, and compatible with Vercel? | To verify during implementation |
| Over-engineering | Were unnecessary abstractions, speculative features, and duplicate domain logic avoided? | To verify during implementation |
| Security | Are Admin-only operations enforced server-side? Are all inputs validated? Is the scheduled endpoint protected? | To verify during implementation |
| Error handling | Are invalid transitions rejected, scheduler failures logged, and repeated executions safe? | To verify during implementation |

### Required implementation checks

```bash
ruff check .
ruff format .
python manage.py makemigrations --check --dry-run
pytest
```

Run the commands using the project's actual environment and scripts. Record any command that cannot be run and why; do not claim a check passed without executing it.

---

## 16. Source of truth

This document is derived from the Brightloop Subscription Management System source documents:

- `REQUIREMENTS.md` — M3 Plans (FR-3.1 through FR-3.6), role–permission matrix, business rules, subscription state machine, and non-functional requirements.
- `UI_UX.md` — Section 5.5 Plans, subscription plan selection flow, lifecycle action behavior, and validation/error-state requirements.
- `CODING_STANDARDS.md` — Django modular-monolith structure, PostgreSQL persistence, service/selector boundaries, decimal money handling, auditability, Vercel Cron constraints, idempotency, and testing standards.

Where these sources define behavior, this document preserves it. Where they leave a decision open, the uncertainty is recorded above instead of being silently replaced with an invented rule.
