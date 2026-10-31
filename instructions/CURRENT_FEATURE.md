# M4. Quotation Templates and Subscriptions

**Document type:** Feature specification and implementation baseline  
**Product:** Brightloop Subscription Management System  
**Module:** M4 — Quotation Templates and Subscriptions  
**Source documents:** `REQUIREMENTS.md`, `UI_UX.md`, and `CODING_STANDARDS.md`  
**Status:** Specification baseline; not a claim that the feature is already implemented

---

## 1. Purpose and scope

M4 manages the commercial agreement between a customer and Brightloop: reusable quotation templates, quotation creation and acceptance, subscription records and lines, subscription lifecycle actions, renewals, add-ons, and mid-cycle changes that generate proration adjustments.

The module connects the catalog and plan configuration to downstream invoicing and payment operations:

**Products and plans (M2/M3) → quotation template / quotation → subscription → invoice and payment (M5/M7).**

M4 owns subscription and quotation business state. It must not duplicate product, plan, tax, payment-term, discount, invoice, or payment administration owned by other modules.

### 1.1 In scope

- Admin creation and editing of quotation templates.
- Staff and Admin use of existing templates when creating subscriptions/quotations.
- Template plan and product lines, plus validity period in days.
- Creation of a subscription from a template, copying all lines into editable subscription lines.
- Subscription identity, customer, plan, dates, payment terms, status, and lines.
- Sequential, never-reused subscription numbers.
- Quotation sending, customer review, acceptance, expiry, and decline/close behavior.
- Subscription status transitions and visibility of current status to every team member.
- Customer portal actions subject to plan lifecycle options: view, accept quotation, pause, resume, cancel, upgrade/downgrade, and quantity change.
- Automatic and manual renewal flows.
- Pause/resume billing behavior.
- Add-on line additions/removals during a subscription's life.
- Proration for mid-cycle quantity, plan, and add-on changes, applied to the next invoice.
- Quote-expiry and renewal scheduled task entry points, following the project deployment standards.

### 1.2 Out of scope

The following belong to other modules or are not specified as M4 functionality:

- Product or variant creation and catalog administration (M2).
- Plan creation, pricing configuration, availability dates, and lifecycle-option administration (M3).
- Tax-rate administration and payment-term list administration (M9); M4 selects and references configured records.
- Discount rule creation and redemption administration (M6). M4/M5 provide the subscription context needed for discount application.
- Invoice creation, invoice status management, invoice PDF/email delivery, and billing-run administration (M5).
- Payment recording or payment-provider implementation (M7). M4 invokes the renewal collection boundary but does not own payment records.
- Dashboard and financial reporting (M8).
- A customer-facing online payment action; the UI/UX source explicitly says not to assume this for the MVP.
- Bulk subscription editing or bulk cancellation; not specified.
- A generic workflow engine, message bus, microservices, or a new task queue. Coding standards require a Django modular monolith and prohibit unnecessary event-bus/queue architecture.

---

## 2. Requirement traceability

All FR-4 requirements below are marked Must (M) in `REQUIREMENTS.md`.

| Requirement | Source requirement | M4 behavior / acceptance target |
|---|---|---|
| FR-4.1 | Templates hold a predefined plan and product lines plus validity days. Admin creates/edits; Staff can use. | Admin-only template management; template selection available to Admin and Staff. |
| FR-4.2 | A subscription can be created from a template; all lines are copied and editable. | Copy template plan and lines into subscription-owned records; later edits must not mutate the template. |
| FR-4.3 | Subscription has unique number, customer, plan, start date, expiry date, payment terms. | Persist and validate all required subscription attributes; generate sequential never-reused number. |
| FR-4.4 | Lines hold product, quantity, unit price, taxes, amount. | Store subscription lines and server-calculate line amounts/tax using product tax association and agreed monetary rules. |
| FR-4.5 | Workflow: Draft → Quotation → Confirmed → Active → Closed. | Centralize and validate lifecycle transitions; support Paused as defined in Section 7. |
| FR-4.6 | Every team member can see current subscription status. | Admin and Staff list/detail views expose status consistently. |
| FR-4.7 | Customer portal actions: view, accept, pause, resume, cancel, upgrade/downgrade, quantity change; each depends on plan lifecycle options. | Enforce ownership, current state, and the associated plan option for every portal action. |
| FR-4.8 | Automatic renewal; generate renewal invoice and attempt collection. Failure by due date sets `payment_failed`, emails customer, notifies Staff, and applies retry/grace rule. | Implement renewal orchestration and failure handling; integrate with M5/M7 and email boundary; make scheduled processing safe to retry. |
| FR-4.9 | Manual renewal triggered by customer or Staff. | Provide Renew action only when manual renewal is enabled and the subscription is eligible. |
| FR-4.10 | Paused subscription excluded from billing; resume recalculates next billing date. | Pause transition affects M5 billing eligibility; resume recalculates and persists next billing date. |
| FR-4.11 | Customer accepts quote in portal; Quotation → Confirmed; expired quote cannot be accepted. | Validate expiry on the server at acceptance time and transition atomically. |
| FR-4.12 | Add-ons are subscription lines and may be added/removed during subscription life. | Represent add-ons as subscription lines; apply eligibility and proration rules. |
| FR-4.13 | Mid-cycle quantity, plan, or add-on changes create prorated charge or credit on next invoice. | Calculate daily-basis proration under current working assumption and persist adjustment for M5. |
| FR-4.14 | Confirmed → Active on start date or first payment (Open Item H). | Use start date under the current documented working assumption; keep activation logic centralized. |
| FR-4.15 | Subscription numbers sequential and never reused. | Use a concurrency-safe database-backed sequence/allocator; do not derive numbers from row count or reuse deleted values. |

### 2.1 Related business rules and non-functional requirements

- **BR-3:** exactly one Plan and one Customer per Subscription.
- **BR-6:** a Paused subscription is never billed; billing resumes from a recalculated date.
- **BR-8:** tax comes only from the Product's tax.
- **BR-11:** a quotation cannot be accepted after its validity period.
- **BR-12:** Customers can perform only portal actions allowed by the Plan lifecycle options.
- **BR-13:** prices are tax-exclusive; tax is added on top (working assumption in the requirements).
- **BR-14:** one currency and one company are assumed, subject to the requirements' confirmation item.
- **NFR-1:** pages respond in under two seconds with thousands of subscriptions.
- **NFR-3 / NFR-7:** transactional, idempotent operations and safe scheduled-job retries.
- **NFR-4:** server-side RBAC, customer data isolation, and common web-security protections.
- **NFR-5:** status changes and relevant actions are audited with actor and timestamp.
- **NFR-9:** email and scheduler integrations remain behind replaceable boundaries.
- **NFR-10:** fixed-precision decimal money handling; never use floating point.

---

## 3. Roles and permissions

### 3.1 Admin

Admin can:

- Create, view, and edit quotation templates.
- Use quotation templates.
- Create and manage subscriptions.
- View subscription status, details, lines, linked billing history, and activity history.
- Send quotations and perform permitted internal lifecycle operations.
- Accept a quotation on behalf of a customer where the workflow permits it.
- Manage subscription changes, renewal operations, and customer-facing actions as authorized by the business rules.

### 3.2 Internal Staff

Staff can:

- View and manage subscriptions for operational work.
- Use existing quotation templates while creating a subscription/quotation.
- Send quotations and monitor acceptance or expiry.
- View current status and subscription history.
- Perform permitted subscription operations and trigger manual renewal where allowed.

Staff cannot create, edit, or manage quotation templates. The UI must not present template-management controls to Staff, and server-side endpoints must deny direct attempts.

### 3.3 Customer

Customer can access only their own subscription and quotation records. Through the portal, a Customer can:

- View their subscriptions and current status.
- Review and accept their own valid quotations.
- View permitted subscription details and add-ons.
- Pause, resume, cancel, upgrade/downgrade, change quantity, and request permitted add-on changes only when the selected Plan enables the relevant lifecycle action.
- Trigger manual renewal where manual renewal is enabled and the subscription is eligible.

Customer cannot access another customer's data, create or edit quotation templates, run billing, record payments, or access internal dashboards/reports.

### 3.4 Permission matrix for M4

| Action | Admin | Staff | Customer |
|---|---:|---:|---:|
| List/view quotation templates | Yes | No template management; may select/use | No |
| Create/edit quotation templates | Yes | No | No |
| Use a quotation template | Yes | Yes | No |
| Create/manage subscriptions | Yes | Yes | Own records and permitted portal actions only |
| View subscription status | Yes | Yes | Own subscriptions |
| Send quotation | Yes | Yes | No |
| Accept quotation | Yes, on behalf where permitted | Optional/on behalf where permitted | Own valid quotation |
| Pause/resume/cancel | Subject to workflow and Plan options | Subject to workflow and Plan options | Own subscription, Plan option required |
| Upgrade/downgrade/change quantity | Subject to workflow and Plan options | Subject to workflow and Plan options | Own subscription, Plan option required |
| Add/remove add-ons | Subject to workflow and Plan options | Subject to workflow and Plan options | Own subscription, permitted action required |
| Manual renewal | Yes, where eligible | Yes, where eligible | Own subscription, where enabled |
| Automatic renewal job | System task under protected execution | No direct job administration implied | No |

**Authorization rule:** the table is a capability boundary, not a substitute for checking state and Plan options. Every protected view, service operation, and object lookup must enforce authorization server-side. Default deny for unlisted capabilities.

---

## 4. Domain model and data requirements

The following is the logical model required by the source documents. Field names can follow repository conventions, but persisted behavior must remain equivalent. Do not create duplicate entities if the project already has equivalent models.

### 4.1 QuotationTemplate

| Attribute | Required | Description / rule |
|---|---:|---|
| `id` | Yes | Database identifier. |
| `name` | Yes | Human-readable template name; reject blank values. |
| `plan` | Yes | Reference to one configured Plan. |
| `validity_days` | Yes | Number of days the generated quotation remains valid. Must be a positive integer unless the product decision defines another boundary. |
| `lines` | Yes | Predefined product lines associated with the template. |
| `created_at`, `updated_at` | Recommended | Standard timestamps, if consistent with project conventions. |
| audit metadata | Required behavior | Admin create/edit actions identify actor, object, operation, and timestamp through the shared audit mechanism. |

Template line data must carry the product and the commercial defaults needed to initialize subscription lines. The source specifies plan and product lines but does not enumerate a separate template-line schema or all editable line attributes. Reuse the subscription-line structure where appropriate, and confirm whether template lines need variant, quantity, unit-price override, or tax snapshot fields before fixing the schema.

### 4.2 Subscription

| Attribute | Required | Description / rule |
|---|---:|---|
| `id` | Yes | Database identifier. |
| `number` | Yes | Sequential business identifier; unique and never reused. |
| `customer` | Yes | Exactly one Customer (BR-3). |
| `plan` | Yes | Exactly one Plan (BR-3). |
| `start_date` | Yes | Start/activation date. |
| `expiry_date` | Yes | Subscription expiry date. Exact relationship to Plan end date must follow confirmed business semantics. |
| `payment_terms` | Yes | Reference to configured PaymentTerm. |
| `status` | Yes | Controlled lifecycle status; use Django `TextChoices` or equivalent enum. |
| `renewal_mode` | Yes, from Plan | Automatic or manual as configured on the selected Plan; avoid an independent conflicting setting unless the domain design requires a snapshot. |
| `next_billing_date` | Required operationally | Used by billing and recalculated on resume; exact initial calculation follows billing rules. |
| `payment_failed` | Optional flag | Additional boolean/status flag for automatic-renewal failure; not a lifecycle status. Cleared on payment. |
| quotation validity metadata | Required for quote | Persist enough information to determine the quote's `valid_until` and reject late acceptance. |
| audit timestamps | Recommended | Standard creation/update timestamps and shared audit events for transitions/actions. |

The requirements explicitly list unique number, customer, plan, start date, expiry date, and payment terms. Other fields above are derived from required workflows and should be reconciled with existing project models before migration.

### 4.3 SubscriptionLine

| Attribute | Required | Description / rule |
|---|---:|---|
| `id` | Yes | Database identifier. |
| `subscription` | Yes | Parent Subscription. |
| `product` | Yes | Product reference from M2. |
| `quantity` | Yes | Positive quantity; exact decimal/integer precision should follow the product decision and existing catalog conventions. |
| `unit_price` | Yes | Fixed-precision decimal. Server-authoritative, not trusted from the browser. |
| `tax` / tax rate snapshot | Required behavior | Tax is sourced from the Product's tax (BR-8); invoice creation must preserve the applicable tax rate per invoice line under M5. |
| `amount` | Yes | Server-calculated line amount; do not accept a client-computed total as authoritative. |
| line type / add-on marker | Needed to distinguish add-ons if required | Add-ons are subscription lines (FR-4.12). Exact marker/schema may follow existing model design. |

### 4.4 Related entities owned elsewhere

- `Plan` and lifecycle options: M3.
- `Product`, `ProductVariant`, and product tax association: M2/M9.
- `PaymentTerm`: M9.
- `Invoice`, `InvoiceLine`, `BillingRun`: M5.
- `Payment` and payment-provider boundary: M7.
- `Discount` and `DiscountRedemption`: M6.
- `AuditLog` and notification/email log: shared system entities.

M4 should use foreign keys and shared services rather than copy or reimplement those modules' administration responsibilities.

---

## 5. Quotation template management

### 5.1 Template list

Admin-only management screen should provide:

- Template name.
- Associated Plan.
- Validity period in days.
- Product-line summary/count.
- Search, pagination, and useful sorting.
- Create and edit actions.

The source specifies create and edit. It does not specify archive/delete behavior, template versioning, or whether an existing template can be deleted after use. Do not add destructive behavior without a product decision.

### 5.2 Create/edit template form

Capture:

- Template name.
- Plan selection.
- Validity period in days.
- One or more predefined product lines.

Use searchable selects for long product/plan lists. Validate all values server-side. Display calculated line previews using server-calculated decimal values. If product or plan availability is date-dependent, validate against the selected subscription start date when the template is used; M3 owns plan availability rules.

### 5.3 Template permissions

- Admin can create and edit templates.
- Staff can select and use existing templates in subscription creation, but cannot manage them.
- Customer cannot access template management or template selection.
- Deny unauthorized direct URL/API/service calls, even if the UI hides the relevant controls.

### 5.4 Template copy semantics

When a template is selected:

1. Read the template and its current plan/lines.
2. Validate that the Plan is usable for the intended subscription start date.
3. Copy the Plan reference and all configured lines into the new subscription context.
4. Make the copied subscription lines independently editable.
5. Save the subscription and its copied lines atomically.

Editing a template later must not silently alter already-created subscriptions or quotations. Historical subscription commercial values must remain stable according to the subscription/invoice snapshot rules; exact snapshot boundaries should align with M5's invoice immutability requirements.

---

## 6. Subscription creation and management

### 6.1 Create flow

The UI/UX specification recommends this sequence:

1. Select a Customer.
2. Choose a Plan. Show only plans available for new subscriptions on the selected start date.
3. Choose creation method: start blank or use a quotation template.
4. Configure subscription lines: products, variants, quantities, and add-ons.
5. Review pricing: unit prices, line amounts, taxes, and total.
6. Set dates and payment terms.
7. Save as Draft or create/send a Quotation, depending on the selected action.

The system must validate the Plan's availability on the server; filtering options in the browser is not sufficient. M3 owns the availability configuration and lifecycle options.

### 6.2 Subscription number generation

- Generate subscription numbers sequentially.
- A number must never be reused, including after deletion/closure or failed downstream operations.
- Enforce uniqueness in PostgreSQL.
- Use a database sequence or another concurrency-safe allocator. Do not calculate `MAX(number) + 1` without locking/atomic allocation.
- Number allocation must remain safe under parallel Vercel function invocations.
- Decide the display format/prefix separately; the requirements specify sequential uniqueness, not a literal format.

### 6.3 Subscription detail

Header:
- Subscription number.
- Customer.
- Plan.
- Current status.
- Separate `payment_failed` warning when applicable.

Suggested sections:
- **Overview:** start date, expiry date, renewal mode, payment terms, next billing date.
- **Subscription lines:** products, variants, quantities, prices, taxes, and add-ons.
- **Billing history:** linked invoices.
- **Activity history:** status changes and other audited actions.

Every team member with internal subscription access must be able to see the current status (FR-4.6).

### 6.4 Subscription list

Recommended columns and filters from the UI/UX specification:

- Subscription number.
- Customer.
- Plan.
- Status.
- Start/expiry or next billing information where useful.
- Renewal mode.
- Payment-failed indicator.

Filters:
- Customer.
- Plan.
- Status.
- Renewal mode.
- Payment-failed flag.

Search:
- Subscription number.
- Customer name or email.

Use pagination/server-side filtering. Avoid N+1 queries with `select_related` and `prefetch_related`.

### 6.5 Editing subscription data

The source allows copied lines to be editable and defines live quantity/plan/add-on changes. It does not fully specify unrestricted editing of every field after quotation or activation. Restrict editable fields according to the current state and lifecycle workflow; do not permit direct mutation of status, totals, or protected fields through arbitrary form payloads.

---

## 7. Lifecycle and state transitions

### 7.1 Canonical lifecycle

The requirements define the main workflow:

`Draft → Quotation → Confirmed → Active → Closed`

Paused is an additional lifecycle state connected to Active. `payment_failed` is a separate flag, not a replacement lifecycle status.

| From | To | Trigger | Validation / behavior |
|---|---|---|---|
| Draft | Quotation | Admin/Staff sends quotation | Calculate/persist validity deadline; send quotation through email boundary; record transition. |
| Quotation | Confirmed | Customer accepts in portal | Must be customer's own quote and not expired; transition atomically. |
| Quotation | Closed | Quotation expires or is declined | Scheduled expiry or permitted decline operation; preserve history. |
| Confirmed | Active | Start date reached (current assumption) | Use shared transition service; activation on first payment remains an alternative only if Open Item H changes. |
| Active | Paused | Customer/Staff pauses, if Plan allows; may also occur after grace period | Exclude from billing while paused. |
| Paused | Active | Resume | Recalculate next billing date and resume eligibility. |
| Active / Paused | Closed | Cancel, close early, plan end date/auto-close, or final renewal failure | Validate role, state, and relevant Plan lifecycle option. |

### 7.2 Centralized transition service

All subscription state changes must pass through one service function (for example, `transition_subscription(subscription, to_status, actor, ...)`). The exact name may follow repository conventions.

The transition service must:

1. Load/lock the subscription as needed (`select_for_update`).
2. Check actor authorization and customer ownership.
3. Check the current status and the allowed transition table.
4. Check the relevant Plan lifecycle option (M3) for customer-triggered or plan-governed actions.
5. Apply state-specific side effects, such as billing exclusion or next-date recalculation.
6. Persist the change inside `transaction.atomic()`.
7. Write an `AuditLog` entry with actor/system identity, from-status, to-status, and timestamp.
8. Raise a domain exception for invalid transitions; views convert it to a safe user-facing response.

Never assign `subscription.status` directly in views, forms, tasks, or unrelated modules.

### 7.3 `payment_failed` flag

- Set when automatic renewal collection fails or payment is not received by the due date, as specified by FR-4.8.
- Display independently from the lifecycle status.
- Clear when payment succeeds/is recorded according to the payment workflow.
- Do not imply that the subscription is Paused or Closed unless its actual status has transitioned.
- Show the next step or grace-period state when available.

### 7.4 Plan lifecycle options

M3 stores Plan lifecycle settings; M4 enforces them. For each customer action, validate:

- Pause option before pausing.
- Resume option/valid state according to the Plan configuration and transition rules.
- Cancel/close-early option before early closure.
- Renew option and renewal mode before renewal.
- Upgrade/downgrade and quantity-change permissions before applying those changes.

The requirements use lifecycle options as the permission gate but do not fully enumerate the exact option names for every portal action. Match the actual M3 model and confirm any missing option mapping; do not invent additional Plan flags.

---

## 8. Quotation lifecycle and acceptance

### 8.1 Sending a quotation

- Admin/Staff can send a quotation from a Draft subscription.
- Set the quotation validity period from the selected template's `validity_days` (or another explicitly approved source when no template is used).
- Persist a deterministic `valid_until` value so acceptance and expiry jobs use the same deadline.
- Send the quotation email through the project's email boundary.
- Record send/transition activity and visible delivery state where available.
- Email failure must not silently lose the business record or roll back unrelated committed data; log and mark for retry under the shared email pattern.

The requirements define template validity days but do not specify the default validity period for quotations created without a template. Treat that as an open decision.

### 8.2 Customer acceptance

1. Customer opens their own quotation in the portal.
2. System displays lines, Plan, dates, totals, and validity deadline.
3. Acceptance is available only while the quotation is valid.
4. On acceptance, server rechecks ownership, current status, and expiry.
5. Transition Quotation → Confirmed atomically and audit it.
6. Display confirmation and scheduled start date.

Do not rely on a disabled browser button as the expiry check. A crafted request after expiry must be rejected.

### 8.3 Expiry and decline

- An expired quotation cannot be accepted (FR-4.11 / BR-11).
- State machine defines Quotation → Closed when expired or declined.
- Quote expiry is a scheduled task under the coding standards' Vercel Cron approach.
- Expiry processing must be idempotent: repeated or overlapping runs must not duplicate transition/audit effects.
- Decline action details and whether Customers have a dedicated decline control are not fully specified; confirm before implementing beyond the state-machine behavior.

### 8.4 Quotation list and detail UX

Quotation list recommended columns:
- Quotation/subscription number.
- Customer.
- Plan.
- Created date.
- Valid until.
- Status: awaiting response, accepted, expired, declined.

Quotation detail should show:
- Customer and Plan.
- Subscription/product lines and pricing breakdown.
- Created date and validity deadline.
- Current quotation status.
- Accept action for the owning Customer while valid.
- Internal send/monitoring actions for Admin/Staff.

Expired quotations show the expiry date and disabled acceptance. Status must be represented with text, not color alone.

---

## 9. Renewal behavior

### 9.1 Renewal mode source

Plan M3 defines `renewal_mode` as `automatic` or `manual`, and a distinct lifecycle option determines whether renewal is permitted at all. M4 must honor both:

- `allow_renew` (or the corresponding Plan lifecycle option) controls whether renewal is allowed.
- `renewal_mode` controls how renewal is initiated.

Automatic mode must not override a disabled Renew option.

### 9.2 Automatic renewal

FR-4.8 requires the system to:

1. Identify an eligible subscription configured for automatic renewal.
2. Generate the renewal invoice through M5's billing/invoice services.
3. Attempt collection through M7's payment-provider boundary.
4. If payment fails or is not received by the invoice due date, set `payment_failed`.
5. Email the Customer.
6. Notify Staff.
7. Apply the configured grace-period/retry rule.
8. After the final failure, pause or close according to the configured rule.

The coding standards specifically require automatic-renewal failures to follow this behavior and never fail silently. Email failures must be logged/retried without rolling back the business transaction.

### 9.3 Manual renewal

- Customer or Staff opens an eligible subscription and selects Renew.
- Validate that the Plan permits renewal, the mode is manual, the actor is authorized, and the current state permits the operation.
- Start the renewal/invoice flow using M5 services.
- Show the updated status and next step.

The requirements specify the trigger but do not fully define the detailed manual-renewal sequence, whether renewal creates a new subscription record or extends the existing record, or exactly when the new term begins. These are product decisions; do not silently choose a data model that makes them irreversible.

### 9.4 Grace period, retries, and final action

The requirements' Open Item C contains a working assumption:

- Reminders at 1, 7, and 14 days past due.
- Then automatically pause.

Other text describes retry N times and then pause or close, and the UI/UX says the final action remains configurable/open. Therefore:

- Keep retry count, timing, and final action configurable rather than hard-coded into UI copy.
- Treat 1/7/14 days and auto-pause as provisional working assumptions until confirmed.
- Ensure notification and lifecycle effects are idempotent to avoid duplicate emails or repeated state transitions.

---

## 10. Pause, resume, cancellation, and closure

### 10.1 Pause

- Pause only when the Plan permits it and the transition is valid.
- Explain before confirmation that a paused subscription is excluded from billing runs.
- Transition to Paused through the shared state service.
- Record actor and timestamp.
- M5 billing selection must exclude Paused subscriptions (BR-6 / FR-4.10).

### 10.2 Resume

- Resume only from Paused and when allowed by the Plan/workflow.
- Recalculate and persist the next billing date.
- The backend calculation is authoritative; show the updated schedule to the user.
- Use the agreed proration/date calculation helpers rather than browser-only calculations.

The exact formula for recalculating next billing date after a pause is not specified in the source documents and requires confirmation with the billing-period rules.

### 10.3 Cancel / close

- Customer-facing cancellation is subject to the Plan's lifecycle option.
- Internal Admin/Staff actions must also obey valid state transitions and role permissions.
- Closed is terminal in the documented state machine; display history read-only.
- Do not conflate cancellation/early close with expiry of a quotation.
- Exact effective date, immediate-vs-end-of-period cancellation, and any refund behavior are not specified; do not invent them.

---

## 11. Add-ons, plan changes, quantity changes, and proration

### 11.1 Add-ons

- Add-ons are represented as SubscriptionLine records (FR-4.12).
- A permitted add-on can be added or removed during the subscription's life.
- Validate product eligibility and any relevant Plan/lifecycle permission on the server.
- Recalculate subscription pricing using server-side decimal arithmetic.
- Persist the change and its effective date/history so the next invoice can apply the correct adjustment.

The source does not fully define whether every product can be an add-on, whether variant selection is mandatory, or whether add-on changes require approval. Follow existing catalog/product rules and record unresolved policy decisions.

### 11.2 Upgrade/downgrade and quantity changes

- Show current and proposed configurations side by side.
- Preview the expected prorated charge or credit where possible.
- Explain that the adjustment is applied to the next invoice.
- Require confirmation before applying a change.
- Validate Plan lifecycle options and current state.
- Persist the change and proration detail for M5 to consume.

Do not promise an immediate refund. The requirements' working assumption is that downgrade credits are applied to the next invoice.

### 11.3 Proration calculation

FR-4.13 requires mid-cycle changes to quantity, plan, or add-ons to produce a prorated charge or credit on the next invoice.

Current working assumptions from `REQUIREMENTS.md`:

- Daily-basis proration (Open Item K).
- Downgrade credit is applied to the next invoice.
- Tax and proration rounding is per line, two decimal places, half-up (Open Item J).

Implementation requirements:

- Use `Decimal` and shared money/rounding helpers; never float.
- Keep the calculation in a server-side service, not browser-only JavaScript.
- Record enough detail for the next invoice to explain the adjustment (change type, effective date, remaining/elapsed period basis, charge/credit amount, related subscription/line).
- Apply the adjustment on the next invoice via M5's established invoice-generation path.
- Avoid applying the same adjustment twice if a billing job is retried.
- Add tests for mid-cycle upgrade, downgrade, quantity increase/decrease, add-on addition/removal, date boundaries, and rounding.

The exact day-count convention (inclusive/exclusive boundaries, timezone/date basis, treatment of leap days, and partial first/last days) is not specified. Confirm before treating the calculation as final.

---

## 12. Validation rules

| Area | Required validation |
|---|---|
| Template name | Required; reject blank/whitespace-only values. |
| Template Plan | Must reference an existing valid Plan. |
| Validity days | Positive integer unless product confirms a different rule. |
| Template lines | At least the required configured product lines; each Product reference must be valid. Exact minimum line count is not explicit and should be confirmed. |
| Customer | Required; exactly one Customer per Subscription. |
| Plan | Required; exactly one Plan per Subscription; validate availability on selected start date. |
| Dates | Start date and expiry date required; enforce any confirmed ordering/Plan-boundary rules. |
| Payment terms | Must reference an existing configured PaymentTerm. |
| Subscription number | Generated by server; unique; never reused. Ignore client-supplied number. |
| Quantity | Positive; exact numeric precision must follow agreed product rules. |
| Unit price | Server-authoritative Decimal; do not trust client-submitted price. |
| Tax | Source from the Product's configured tax; do not accept an arbitrary client tax rate. |
| Line amount/total | Recalculate server-side using Decimal and shared rounding policy. |
| Quote acceptance | Must belong to current Customer, remain in Quotation state, and not be expired. |
| Lifecycle action | Actor authorized; valid current-state transition; Plan option permits action. |
| Renewal | Renewal permitted by Plan; renewal mode matches selected flow; subscription eligible. |
| Pause | Valid state and Plan option; paused records excluded from billing. |
| Resume | Valid Paused state; recalculate next billing date. |
| Add-on/change | Validate product/Plan eligibility, state, permissions, and effective date. |
| Proration | Server-calculated Decimal; adjustment recorded once and consumed once by next invoice. |

---

## 13. UI/UX behavior

### 13.1 Navigation and page layout

- Internal app uses persistent left sidebar on desktop, compact header, and main content; collapse sidebar into a navigation drawer on smaller screens.
- Internal navigation includes Subscriptions and Quotations for Admin/Staff.
- Quotation Templates management is Admin-only.
- Customer portal uses simplified navigation: Overview, My subscriptions, My quotations, My invoices, Account/security.
- Use tables for operational lists and cards for high-level metrics; preserve filters when returning from detail where feasible.
- Provide loading, empty, error, and success states.

### 13.2 Status presentation

Use readable text labels and do not communicate state by color alone.

| Record | Status / flag | Presentation |
|---|---|---|
| Subscription | Draft | Not yet sent; edit/send quotation actions where allowed. |
| Subscription | Quotation | Awaiting customer response; show expiry. |
| Subscription | Confirmed | Accepted; awaiting start date. |
| Subscription | Active | Active subscription; show permitted management actions. |
| Subscription | Paused | Billing paused; show resume action if allowed. |
| Subscription | Closed | Closed/terminal; read-only history. |
| Subscription | `payment_failed` | Separate prominent warning; not a lifecycle status. |
| Quotation | Valid / expired / declined | Show validity date and acceptance availability. |

Suggested semantic colors from the UI/UX source may be used, but always pair color with text and accessible contrast.

### 13.3 Forms and feedback

- Group fields by purpose and mark required fields.
- Show field-level validation and preserve valid input after errors.
- Use searchable selects for Customers, Products, and Plans.
- Show calculated values as read-only previews where appropriate.
- Display money with configured currency and two decimal places; currency is not specified in the source.
- Destructive actions require confirmation.
- No silent failures: saves, sends, renewals, and lifecycle actions must return visible outcomes.

### 13.4 Subscription lifecycle UX

- Draft: Edit and send quotation.
- Quotation: Customer can accept while valid; show expiry.
- Confirmed: Show scheduled start date.
- Active: Show only Plan-permitted actions valid in the current state.
- Paused: Explain billing is stopped; show resume where allowed.
- Closed: Read-only history.
- Payment failure: Show warning and next step/grace-period state when available.

### 13.5 Change preview UX

For upgrade/downgrade, quantity, and add-on changes:

- Present current vs proposed configuration.
- Preview expected charge/credit where possible.
- Explain next-invoice application.
- Require confirmation.
- Make clear that the server's final proration amount is authoritative.

---

## 14. Architecture and implementation guidance

### 14.1 Architectural constraints

Follow the coding standards:

- Django modular monolith backed by PostgreSQL.
- Server-rendered templates with small targeted JavaScript (HTMX/Alpine if already used); do not introduce a SPA without a requirement.
- PostgreSQL is the source of truth.
- Keep views thin; business writes in services; complex reads in selectors.
- Use Django ORM and database constraints; no formatted raw SQL.
- No microservices, generic event bus, message queue, Celery worker, or in-process scheduler.
- Use Vercel Cron for scheduled task invocation through protected endpoints.

### 14.2 Suggested app structure

Adapt to the repository's existing layout; do not duplicate equivalent files.

```text
apps/subscriptions/
├── models.py          # Subscription, SubscriptionLine, lifecycle enums
├── services.py        # creation, template copy, transitions, renewal, changes
├── selectors.py       # subscription/quotation list and detail queries
├── forms.py           # server-side validation
├── permissions.py     # only if shared permission layer does not cover it
├── tasks.py           # quote expiry and renewal task entry points
├── views.py           # thin request handlers
├── urls.py
├── admin.py
├── tests/
└── migrations/

apps/quotations/       # only if repository/module boundaries justify a separate app
├── models.py          # QuotationTemplate and template-line model
├── services.py        # template create/update and copy operations
├── selectors.py
├── forms.py
├── views.py
├── urls.py
└── tests/
```

The exact app split is not prescribed by the source documents. Prefer the repository's existing modular boundaries and avoid splitting apps without a concrete benefit.

### 14.3 Service boundaries

Suggested focused service responsibilities (names illustrative, not mandatory):

- `create_quotation_template(...)`
- `update_quotation_template(...)`
- `create_subscription_from_template(...)`
- `create_subscription(...)`
- `send_quotation(...)`
- `accept_quotation(...)`
- `expire_quotations(...)`
- `transition_subscription(...)`
- `pause_subscription(...)`
- `resume_subscription(...)`
- `renew_subscription(...)`
- `apply_subscription_change(...)`
- `calculate_proration(...)`
- `process_automatic_renewals(...)`

Do not create thin wrappers that add no policy or reuse. Keep the number of parameters and function length manageable, consistent with coding standards.

### 14.4 Transactions and concurrency

Use `transaction.atomic()` for multi-record writes, including:

- Creating a subscription and copying template lines.
- Sending a quotation and recording its state/validity metadata.
- Accepting a quotation and transitioning it to Confirmed.
- Applying plan/quantity/add-on changes and recording proration adjustments.
- Processing renewal state and its related records where transaction boundaries permit.

Use `select_for_update()` when concurrent requests/jobs could update the same subscription or quotation. Enforce uniqueness at the database level, not only with pre-checks.

### 14.5 Scheduled jobs

Coding standards specify Vercel Cron calling protected endpoints that invoke `tasks.py` entry points for quote expiry and renewals.

- Protect cron endpoints with a secret (for example, `CRON_SECRET` header check); never expose publicly callable job endpoints.
- Jobs must be idempotent and safe for overlapping/repeated invocations.
- Keep each invocation within serverless execution limits; batch/resume long work if needed.
- Do not use a permanent in-process scheduler or local filesystem state.
- Log job outcomes and per-record failures with useful IDs, not secrets or unnecessary personal data.
- Do not send duplicate customer emails when a job is retried.

### 14.6 Integration contracts

| Module | M4 integration |
|---|---|
| M1 Authentication/User Management | Resolve actor role and current Customer identity; enforce role checks and customer ownership. |
| M2 Product Catalog | Select valid Products/Variants; use product price and associated tax as source inputs. |
| M3 Plans | Select Plan; validate availability, lifecycle options, billing period, and renewal mode. |
| M5 Invoicing | Provide due subscriptions, line snapshots, proration adjustments, and renewal invoice requests through M5 services. M5 owns invoice records and billing runs. |
| M6 Discounts | Do not manage discount rules; provide subscription context for applicable discounts to be handled by M5/M6. |
| M7 Payments | Automatic renewal collection uses payment-provider boundary; payment state remains M7-owned. |
| M9 Taxes/Payment Terms | Reference configured tax through Product and configured PaymentTerm; do not duplicate configuration CRUD. |
| Shared email/scheduler | Use replaceable email boundary and protected Vercel Cron task entry points. |

### 14.7 Database and query performance

- PostgreSQL is the source of truth.
- Use `UniqueConstraint` for subscription number and any clearly defined unique business keys.
- Add database constraints for clear invariants; do not rely only on forms.
- Use `select_related`/`prefetch_related` and paginate list views.
- Add indexes only for demonstrated query patterns; common subscription filters include status, customer, plan, and billing date.
- Every model change ships with a migration. Never edit an applied migration.
- Run migrations as an explicit deployment step, not during a request.

---

## 15. Security, auditability, and error handling

### 15.1 Authorization and customer isolation

- Enforce role permissions on every view and service.
- Customer-facing queries must scope records to the authenticated Customer; never fetch by ID alone.
- A Customer changing a URL/object ID must not access another Customer's quotation, subscription, lines, or activity.
- Write/action endpoints must repeat ownership checks.
- Unauthorized responses must not reveal whether another customer's record exists.
- Hiding UI controls is not authorization.

### 15.2 Input and financial integrity

- Validate all submitted fields with Django forms/serializers.
- Never trust client-sent subscription number, status, price, tax rate, line amount, total, or proration result.
- Use ORM/parameterized SQL only.
- Keep Django template auto-escaping enabled; CSRF protection remains on for state-changing browser requests.
- Use `DecimalField` and shared rounding helper; never float.
- Use transactions and row locks for concurrent lifecycle/financial changes.

### 15.3 Auditability

Record at least:

- Subscription lifecycle transition: actor/system identity, from status, to status, timestamp.
- Template creation/edit: Admin actor, template, operation, timestamp.
- Quotation send, acceptance, expiry, and decline where implemented.
- Pause/resume/cancel/renew and plan/quantity/add-on changes.
- Renewal failure and `payment_failed` set/clear events.

Reuse the existing shared `AuditLog` mechanism; the source does not define a new M4-specific audit schema.

### 15.4 Error handling

- Define narrow domain exceptions for invalid transitions, expired quotations, disallowed Plan actions, unavailable Plan, and invalid renewal state where useful.
- Catch the narrowest exception; never use bare `except:` or silently swallow exceptions.
- Return friendly validation/permission messages; never expose stack traces or SQL details.
- Use module-level Python loggers, not `print()`.
- Log useful context such as subscription/quotation/customer IDs; do not log secrets or unnecessary personal data.
- Email failures must not roll back committed business transactions; log and mark for retry.
- A failed record in a scheduled batch should not prevent unrelated eligible records from being processed where per-record isolation is supported.

---

## 16. Acceptance criteria

M4 is acceptable only when all applicable criteria below are demonstrated.

### 16.1 Quotation templates

- [ ] Admin can list, create, and edit quotation templates.
- [ ] A template stores a Plan, predefined product lines, and validity period in days.
- [ ] Blank template names and invalid validity values are rejected.
- [ ] Staff can use an existing template during subscription creation.
- [ ] Staff cannot create or edit templates through UI or direct requests.
- [ ] Customers cannot access template management.
- [ ] Editing a template does not mutate already-created subscriptions.

### 16.2 Subscription creation and identity

- [ ] Admin and Staff can create a subscription for a selected Customer.
- [ ] A subscription references exactly one Customer and one Plan.
- [ ] Subscription stores number, start date, expiry date, and payment terms.
- [ ] Creating from a template copies all configured lines.
- [ ] Copied lines are editable independently of the template.
- [ ] Plan availability is checked for the selected start date on the server.
- [ ] Subscription number is sequential, unique, and never reused.
- [ ] Concurrent creation cannot allocate duplicate subscription numbers.

### 16.3 Subscription lines and pricing

- [ ] Each line stores Product, quantity, unit price, tax association/rate behavior, and amount.
- [ ] Add-ons are represented as subscription lines.
- [ ] Product tax is the source of tax; client-supplied tax is ignored/rejected.
- [ ] Unit prices, amounts, and totals are server-calculated using Decimal.
- [ ] Invalid products, quantities, and prices are rejected.

### 16.4 Lifecycle and status visibility

- [ ] Draft can transition to Quotation through the send action.
- [ ] A valid quotation can transition to Confirmed through acceptance.
- [ ] An expired quotation cannot be accepted.
- [ ] Confirmed transitions to Active on start date under the current working assumption.
- [ ] Active can transition to Paused only when permitted.
- [ ] Paused can resume to Active and recalculates next billing date.
- [ ] Valid closure paths transition Active/Paused to Closed.
- [ ] Invalid transitions are rejected by the centralized service.
- [ ] Every team member with subscription access sees current status.
- [ ] `payment_failed` is displayed independently of lifecycle status.
- [ ] Every transition is audited.

### 16.5 Customer portal

- [ ] Customer can view only their own subscriptions and quotations.
- [ ] Customer can accept only their own valid quotation.
- [ ] Customer portal actions are available only when both state and Plan lifecycle options permit them.
- [ ] Customer cannot change a URL/object identifier to view another customer's data.
- [ ] Direct requests cannot bypass portal permission or Plan-option checks.

### 16.6 Renewal and pause behavior

- [ ] Automatic renewal creates/requests the renewal invoice through M5 and attempts collection through M7 boundary.
- [ ] Failed/unpaid renewal sets `payment_failed`.
- [ ] Customer email and Staff notification are triggered for renewal failure.
- [ ] Retry/grace policy is applied according to configured/confirmed values.
- [ ] Final failure pauses or closes according to the configured policy.
- [ ] Manual renewal can be triggered by eligible Customer or Staff.
- [ ] Paused subscriptions are excluded from billing runs.
- [ ] Resume recalculates and persists next billing date.
- [ ] Repeated scheduled runs do not duplicate transitions, invoices, or emails.

### 16.7 Add-ons and proration

- [ ] Permitted add-ons can be added/removed as subscription lines.
- [ ] Mid-cycle quantity, Plan, and add-on changes create a charge or credit adjustment.
- [ ] Proration adjustment is applied to the next invoice, not an immediate refund.
- [ ] Proration uses Decimal and the approved daily-basis/rounding rules.
- [ ] Retried operations do not apply the same adjustment twice.
- [ ] Customer sees a proposed configuration and an estimated charge/credit before confirming.

### 16.8 Security, reliability, and performance

- [ ] Server-side RBAC is enforced on all protected endpoints/services.
- [ ] Customer data isolation applies to reads and writes.
- [ ] Database constraints protect subscription number uniqueness.
- [ ] Multi-record writes are atomic.
- [ ] Cron endpoints are secret-protected.
- [ ] Quote expiry and renewal tasks are idempotent and safe under overlap.
- [ ] Email failure is logged/retried without rolling back business data.
- [ ] Subscription and quotation list pages are paginated and avoid N+1 queries.
- [ ] Relevant pages meet the under-two-second target at thousands of subscriptions, subject to representative performance testing.

---

## 17. Test plan

Use `pytest`, `pytest-django`, and `factory-boy` as specified by the coding standards. Tests must not call real external services. Use a test email backend and mock payment-provider boundary. Monetary assertions must use `Decimal`, never float.

### 17.1 Template management and permissions

1. Admin creates a valid template.
2. Admin edits name, Plan, validity, and lines.
3. Blank name rejected.
4. Invalid/zero/negative validity days rejected (subject to confirmed boundary).
5. Staff can select/use a template.
6. Staff cannot create/edit template through UI or direct endpoint/service call.
7. Customer cannot access template routes.
8. Template update after subscription creation does not mutate copied subscription lines.

### 17.2 Subscription creation and numbering

1. Create subscription without template.
2. Create subscription from template.
3. All template lines copied.
4. Copied lines can be edited without changing template.
5. Invalid Customer/Plan/Product references rejected.
6. Plan unavailable on selected start date rejected server-side.
7. Required start date, expiry date, and payment terms validated.
8. Sequential subscription numbers generated.
9. Concurrent creation attempts do not produce duplicate numbers.
10. Deleted/closed/failed records do not cause number reuse.

### 17.3 Subscription lines and monetary behavior

1. Valid line amount calculation.
2. Quantity boundary and invalid quantity.
3. Client-forged unit price ignored/rejected.
4. Client-forged tax rate ignored/rejected.
5. Tax sourced from Product tax.
6. Decimal precision and rounding behavior.
7. Add-on line addition and removal.
8. Multi-line creation rolls back atomically on a failing line.

### 17.4 Lifecycle transitions

1. Draft → Quotation.
2. Quotation → Confirmed.
3. Quotation → Closed on expiry.
4. Confirmed → Active at start date.
5. Active → Paused when Plan allows.
6. Active → Paused denied when Plan disallows.
7. Paused → Active and next billing date recalculated.
8. Active/Paused → Closed through permitted closure paths.
9. Invalid transitions rejected.
10. Concurrent transition attempts do not corrupt status or duplicate audit records.
11. Every successful transition creates the expected audit event.

### 17.5 Quote acceptance and expiry

1. Customer accepts own valid quotation.
2. Customer cannot accept another Customer's quotation.
3. Expired quotation rejected even if browser submits acceptance manually.
4. Wrong current status rejected.
5. Boundary test at exact `valid_until` according to the confirmed time semantics.
6. Expiry task closes eligible quotations.
7. Repeated/overlapping expiry task does not duplicate transition or email.
8. Email delivery failure is logged and retriable.

### 17.6 Renewal and payment failure

1. Automatic renewal selects only eligible automatic-mode subscriptions.
2. Disabled Plan renewal option prevents renewal even if mode is automatic.
3. Renewal invoice request delegates to M5.
4. Payment collection delegates to M7 provider interface.
5. Simulated success clears `payment_failed` as appropriate.
6. Simulated failure sets `payment_failed`.
7. Customer notification generated.
8. Staff notification generated.
9. Retry/grace policy advances correctly.
10. Final failure pauses/closes according to configured policy.
11. Repeated job invocation does not duplicate invoices, state transitions, or notifications.
12. Manual renewal is available to eligible Customer/Staff and denied otherwise.

### 17.7 Pause, resume, and billing interaction

1. Paused subscription excluded from M5 billing eligibility.
2. Resume recalculates next billing date.
3. Invalid resume from non-Paused state rejected.
4. Unauthorized pause/resume rejected.
5. Plan option disabled prevents portal action.
6. Concurrent pause/resume requests remain consistent.

### 17.8 Add-ons and proration

1. Add an add-on mid-cycle.
2. Remove an add-on mid-cycle.
3. Increase/decrease quantity mid-cycle.
4. Upgrade Plan mid-cycle.
5. Downgrade Plan mid-cycle produces next-invoice credit under current assumption.
6. Daily-basis day-count boundaries.
7. Per-line two-decimal half-up rounding under current assumption.
8. Multiple changes in one cycle do not double-apply adjustments.
9. Failed transaction leaves subscription and adjustment records consistent.
10. M5 consumes each proration adjustment once.

### 17.9 Isolation and performance

- Two Customers with separate quotations/subscriptions; verify each sees only own records.
- Attempt IDOR on detail, line, acceptance, and lifecycle endpoints.
- Staff/Admin role matrix tests for all M4 operations.
- Paginated list queries use appropriate related-object loading.
- Representative load/performance test with thousands of subscriptions for the NFR-1 target.

---

## 18. Open decisions and assumptions

The following must remain visible in the decision log. Do not convert an assumption into a hidden implementation rule.

| Topic | Source position / working assumption | Required confirmation |
|---|---|---|
| Quote validity without template | FR-4.1 defines template validity days; no-template default is not defined. | Define default validity days when a quotation is created without a template. |
| Exact quote expiry boundary | “Past validity days” cannot be accepted; exact timestamp/timezone boundary is not explicit. | Define whether acceptance is valid through the end of `valid_until` and which timezone is authoritative. |
| Template line schema | Template has plan and product lines; complete line attributes are not enumerated. | Confirm whether variants, quantity, unit price overrides, and tax snapshots belong on template lines. |
| Template archive/delete | Create/edit specified; archive/delete not specified. | Decide whether templates can be archived/deleted and how used templates are retained. |
| Subscription expiry semantics | Subscription has expiry date; its exact relationship to Plan end date/term is not fully defined. | Confirm expiry calculation and inclusive/exclusive date semantics. |
| Activation trigger (Open Item H) | Working assumption: Confirmed → Active on start date. Alternative: first payment. | Confirm before implementation; this document follows start date provisionally. |
| Renewal record model | Manual renewal trigger defined; whether it extends same record or creates a new subscription is not specified. | Decide renewal identity/history behavior and term dates. |
| Automatic renewal retry policy (Open Item C) | Working assumption: reminders at 1, 7, 14 days past due, then auto-pause; requirement also refers to retry N times and pause/close. | Confirm retry count, intervals, grace period, and final action. Keep configurable until confirmed. |
| Pause/resume date calculation | Resume recalculates next billing date; formula is not specified. | Define how paused duration affects billing period and next due date. |
| Cancellation effective date | Cancel/close is supported, but immediate vs end-of-period effect/refund is unspecified. | Define effective date and any financial adjustment behavior. |
| Plan lifecycle option mapping | M3 provides lifecycle options; exact mapping to all M4 actions must match the actual Plan schema. | Confirm the option controlling each portal action; do not add speculative flags. |
| Add-on eligibility | Add-ons are subscription lines; universal product eligibility and approval flow are not defined. | Define eligible product types/variants and whether approval is required. |
| Proration day-count | Working assumption: daily basis; exact boundary/timezone convention unspecified. | Define inclusive/exclusive day counts, leap-day handling, and effective-date rules. |
| Proration rounding (Open Item J) | Working assumption: per line, 2 decimals, half-up. | Confirm and use shared money helper consistently. |
| Downgrade credit | Working assumption: credit applied to next invoice, not immediate refund. | Confirm accounting treatment and behavior if no next invoice is generated. |
| Currency/company | Requirements assume single currency and one company (Open Item D). | Confirm system-wide assumption; M4 should not add multi-currency behavior. |
| Quantity precision | Requirement says quantity but does not specify integer vs decimal. | Confirm permitted quantity precision based on products/use cases. |

---

## 19. Definition of Done

- [ ] All FR-4.1 through FR-4.15 behaviors are implemented or explicitly tracked as blocked by an unresolved product decision.
- [ ] Admin-only template management and Staff template use are enforced in UI and server-side.
- [ ] Subscription creation supports blank and template-based flows.
- [ ] Template lines copy into editable subscription lines without mutating the source template.
- [ ] Subscription number allocation is sequential, unique, concurrency-safe, and never reused.
- [ ] Subscription lifecycle transitions are centralized, validated, transactional, and audited.
- [ ] Quote acceptance checks ownership, state, and expiry server-side.
- [ ] Customer portal actions enforce ownership and Plan lifecycle options.
- [ ] Automatic/manual renewal paths integrate with M5/M7 boundaries.
- [ ] Pause excludes subscription from billing; resume recalculates next billing date.
- [ ] Add-ons and mid-cycle changes create next-invoice proration adjustments.
- [ ] Decimal arithmetic and approved rounding are used throughout.
- [ ] Quote-expiry and renewal tasks use protected, idempotent Vercel Cron entry points.
- [ ] Tests cover success, failure, permissions, concurrency, idempotency, and customer isolation.
- [ ] `ruff check .` and formatter pass.
- [ ] `python manage.py makemigrations --check --dry-run` reports no missing migrations.
- [ ] No secrets, debug prints, dead code, unused imports, or unnecessary dependencies remain.
- [ ] No persistent local filesystem or in-process scheduler is introduced.
- [ ] Relevant pages are paginated and avoid N+1 queries.
- [ ] Deployment migrations are run as an explicit deployment step.

---

## 20. Developer self-review checklist

Before considering an M4 change complete, review it against the coding standards:

| Area | Review question |
|---|---|
| File/component structure | Do views remain thin, with writes in services and complex reads in selectors? Does the implementation fit the existing app structure? |
| State management | Is PostgreSQL the source of truth? Are all lifecycle transitions centralized, atomic, and audited? |
| Unused imports / dead code | Are there unused imports, variables, functions, stubs, commented code, or debug prints? Does Ruff pass? |
| Dependencies | Was any package added? Is it justified, pinned, and compatible with Vercel/serverless limits? |
| Over-engineering | Were unnecessary frameworks, abstractions, event buses, queues, or speculative features introduced? |
| Security | Are permissions checked server-side? Is Customer ownership enforced on reads and writes? Are submitted prices/statuses ignored or validated? |
| Error handling | Are exceptions narrow and logged? Are batch jobs idempotent? Can one record's failure be isolated from other records? |
| Money | Are all prices and proration values Decimal-based, with one shared rounding policy? |
| Concurrency | Are subscription number allocation and lifecycle/renewal mutations safe under concurrent requests/jobs? |
| Scheduled work | Are cron endpoints protected, bounded, resumable where necessary, and safe to run repeatedly? |

---

## 21. Source-of-truth hierarchy

When implementation details conflict, use this order:

1. `REQUIREMENTS.md` for functional requirements, business rules, role permissions, state machines, and open items.
2. `UI_UX.md` for screen structure, user flows, status presentation, and interaction behavior, provided it does not contradict requirements.
3. `CODING_STANDARDS.md` for architecture, security, database, deployment, testing, and code-quality constraints.
4. Existing repository conventions and implemented shared services, provided they do not violate the documents above.
5. Explicit product decisions recorded after these documents; update the specification when a decision changes an assumption.

If a behavior is not specified, record it as an open decision rather than silently inventing a requirement.
