# M5. Invoicing

**Project:** Brightloop Subscription Management System  
**Module:** M5 — Invoicing  
**Document type:** Current feature specification / implementation baseline  
**Status:** Draft — pending confirmation of the open decisions listed below  
**Primary source:** `REQUIREMENTS.md` v2.0  
**Supporting sources:** `UI_UX.md` and `CODING_STANDARDS.md`

> This document defines the expected behavior and acceptance baseline for M5. It does not claim that the feature has already been implemented. The requirements document remains the source of truth. Where the source documents are silent or explicitly leave a decision open, this specification records the gap instead of silently turning an assumption into a requirement.

---

## 1. Purpose and scope

M5 generates and manages invoices from subscriptions. It automates the creation of invoice records for due subscription billing periods, calculates invoice lines and taxes from subscription/product data, applies eligible discounts and proration adjustments, determines due dates from payment terms, and provides operational billing-run history.

The module must make billing reliable and repeatable. In particular, it must prevent duplicate invoices for the same subscription period, retain the fact that a cancelled invoice's period has already been billed, and isolate failures so one subscription does not stop an entire bulk billing run.

M5 owns invoice generation, invoice records, invoice lifecycle, invoice presentation, and billing-run records. Payment recording and collection are integrated with M7; discount rules are owned by M6; subscription lifecycle and line configuration are owned by M4.

### 1.1 Goals

1. Generate invoices automatically from due subscriptions without requiring Staff to retype customer or product-line information.
2. Process hundreds of due subscriptions in a bulk billing run initiated manually by Admin/Staff or by the scheduler.
3. Guarantee at most one invoice per subscription per billing period through a database uniqueness constraint.
4. Ensure a cancelled invoice does not make its billing period eligible for a replacement invoice.
5. Calculate taxes from the tax attached to each product and retain the tax rate on each invoice line.
6. Apply eligible discounts and proration adjustments to the next invoice.
7. Derive invoice due dates from the subscription's payment terms.
8. Support invoice confirmation, cancellation, email delivery, and PDF printing.
9. Preserve confirmed invoice values as historical financial records.
10. Provide an inspectable billing-run result log with Created, Skipped, and Failed outcomes.
11. Keep invoice and billing operations auditable, transactional, idempotent, and safe under retries or concurrent requests.

### 1.2 In scope

- Invoice creation from subscription billing periods.
- Invoice and invoice-line data required by the requirements.
- Customer and subscription references on invoices.
- Product-line, quantity, unit-price, tax, discount, proration, subtotal, and total snapshots/calculations.
- Due-date calculation from the subscription's payment terms.
- Invoice status workflow: Draft, Confirmed, Paid, and Cancelled.
- Admin/Staff invoice list, detail, confirm, cancel, send, and print actions.
- Customer invoice list, detail, and print access for the authenticated customer's own invoices.
- Scheduled and manually triggered bulk billing runs.
- Billing-run history and per-subscription outcomes.
- Duplicate-period protection and safe handling of cancelled invoices.
- Invoice immutability after confirmation.
- Integration points with M4 subscriptions, M6 discounts, M7 payments, and M8 reporting.
- Automated tests for calculations, transitions, idempotency, access control, and failure isolation.

### 1.3 Out of scope

The following are not M5-owned features and must not be treated as committed M5 functionality without a separate requirement:

- Creating or editing subscriptions, plans, products, product variants, quotation templates, or subscription lines (M2/M3/M4).
- Defining discount rules or redemption policy (M6); M5 consumes eligible discount results and records the invoice breakdown.
- Recording payments, payment-method administration, payment-provider integration, or payment collection workflows (M7). M5 exposes the invoice state and integrates with payment outcomes.
- Customer-facing online payment checkout. The UI/UX source explicitly says an online payment action is not specified for the MVP.
- Dunning policy administration or reminder cadence configuration (M7 / product decision); M5 may expose invoice due/overdue information used by those workflows.
- Revenue dashboards, financial reports, and CSV exports (M8), beyond providing accurate invoice data.
- Credit notes, replacement invoices for cancelled periods, invoice amendments, or post-confirmation line editing. The working correction assumption is cancel-only, and the period remains billed.
- Multi-currency, multi-company, jurisdictional tax, or customer-location tax logic. The source assumes one currency and one company, pending confirmation.
- Inventory, fulfillment, shipment, or purchase-order processes.
- A user-configurable invoice numbering format, invoice branding editor, or PDF template designer; these are not defined by the source requirements.
- Bulk invoice cancellation, bulk editing, or a manual “regenerate this period” action.

---

## 2. Requirement traceability

All M5 requirements below are **Must (M)** except FR-5.10, which is **Should (S)** in `REQUIREMENTS.md`.

| Requirement | Source requirement | M5 behavior |
|---|---|---|
| FR-5.1 | Invoices are created automatically from subscriptions, with customer details, product lines, taxes, and totals prefilled. No manual typing. | Generate invoice records from subscription and related product data; prefill all supported billing information and calculate totals server-side. |
| FR-5.2 | A bulk billing run processes all due subscriptions at once (hundreds per run). It can be triggered by the scheduler or manually by Admin/Staff. | Provide a manual Admin/Staff action and a protected scheduled entry point; process in bounded batches where needed. |
| FR-5.3 | A unique constraint on (subscription, billing period) guarantees one invoice per period. A cancelled invoice still counts as billed for that period; the cycle is skipped and not re-billed. | Enforce a database-level unique constraint and treat a duplicate constraint conflict as a Skipped result. Include Cancelled invoices in the period-already-billed rule. |
| FR-5.4 | Tax is calculated automatically from the tax attached to each product. Each invoice line carries its product's tax rate. | Copy the applicable product tax rate onto each invoice line and calculate tax using the shared money/rounding rules. |
| FR-5.5 | Invoice actions: confirm, cancel, send (email), print (PDF). | Implement the four actions with role/state checks, safe feedback, and appropriate side-effect handling. |
| FR-5.6 | Status workflow: Draft → Confirmed → Paid. Cancelled is a terminal side state. | Centralize and validate invoice transitions; Paid and Cancelled are terminal in the defined workflow. |
| FR-5.7 | Each invoice has a due date derived from the subscription's payment terms. | Resolve the selected payment term and calculate/store the due date according to its configured rule. |
| FR-5.8 | Applicable discounts (M6) and proration adjustments (FR-4.13) are applied automatically to the next invoice. | Consume eligible discount and pending proration data during invoice generation and show each adjustment on the invoice. |
| FR-5.9 | Each billing run produces a result log (created, skipped, failed, with reasons). Failures in one subscription do not stop the rest of the run. | Persist run metadata and per-subscription outcomes; isolate each subscription's processing failure. |
| FR-5.10 | Confirmed invoices are immutable (corrections via cancel and the rules in Open Item I). | Treat confirmed invoice financial/customer/line fields as immutable. Use cancellation under the current working assumption; this requirement is Should priority. |

### 2.1 Related business rules

- **BR-4:** One invoice per subscription per billing period, enforced by a database constraint.
- **BR-5:** A cancelled invoice's period is considered billed and is not re-billed.
- **BR-6:** A paused subscription is never billed; billing resumes from a recalculated date.
- **BR-7:** Payment amount must equal invoice total (payment enforcement belongs to M7).
- **BR-8:** Tax comes only from the product's tax.
- **BR-9:** Total stacked discount never exceeds the cap; the default assumption is a 100% cap so totals never go below zero.
- **BR-13:** Prices are tax-exclusive and tax is added on top (working assumption; Open Item B).
- **BR-14:** The system uses a single currency and a single company (working assumption; Open Item D).

### 2.2 Related non-functional requirements

| ID | Requirement | M5 implication |
|---|---|---|
| NFR-1 | Every page responds in under 2 seconds with thousands of subscriptions on the books. | Paginate invoice lists, index common filters, avoid N+1 queries, and keep detail queries bounded. |
| NFR-2 | A billing run handles hundreds of subscriptions per run without timeouts, using batching or background jobs. | Use bounded/resumable processing appropriate to Vercel execution limits. |
| NFR-3 | Billing is transactional and idempotent; no duplicate or missed invoices. | Use database constraints, transactions, safe retry behavior, and per-subscription result tracking. |
| NFR-4 | Server-side RBAC, customer data isolation, and protection against common web attacks. | Enforce invoice permissions and ownership in every view and service. |
| NFR-5 | Status changes, billing actions, payments, and admin changes are logged with user and timestamp. | Audit invoice transitions and billing-run actions with actor/time context. |
| NFR-7 | Scheduled jobs recover from failure and can be re-run safely. | Billing scheduler entry point must be idempotent and resumable. |
| NFR-9 | Payment provider, email provider, and scheduler are behind interfaces so they can be swapped. | Keep email and scheduler dependencies behind existing project boundaries; do not implement payment-provider behavior inside M5. |
| NFR-10 | Monetary values use fixed-precision decimals, never floating point. | Use Decimal-based calculations and a shared rounding helper. |

---

## 3. Roles and permissions

M5 follows the role–permission matrix in `REQUIREMENTS.md` and `UI_UX.md`. The server is authoritative; hiding a button is not a security boundary.

### 3.1 Admin

Admin can:

- View all invoices and billing runs.
- Confirm and cancel invoices.
- Send invoices by email.
- Print/download invoice PDFs.
- Trigger a billing run manually.
- Review billing-run summaries and per-subscription results.
- Inspect invoice history and relevant audit events.

### 3.2 Internal Staff

Staff can:

- View invoices and billing-run results needed for day-to-day operations.
- Confirm and cancel invoices.
- Send invoices by email.
- Print/download invoice PDFs.
- Trigger a billing run manually.
- Review created, skipped, and failed billing outcomes.
- Follow up outstanding and overdue invoices.

Staff cannot change catalog, plan, tax, discount, or quotation-template configuration. Invoice generation must consume those records without exposing their administration through M5.

### 3.3 Customer

A Customer can:

- View only invoices belonging to their own Customer record.
- Open invoice details.
- Print/download their own invoice PDF.
- View invoice number, invoice date, due date, amount, status, and overdue indicator.

A Customer cannot:

- Confirm or cancel invoices.
- Send invoices by email through internal controls.
- Record payments.
- Run billing or access billing-run logs.
- Access another customer's invoice by changing a URL, identifier, or request payload.

The requirements do not specify a customer-facing online payment action. Do not add one to the MVP without an explicit scope change.

### 3.4 Permission matrix

| Action | Admin | Staff | Customer |
|---|---:|---:|---:|
| List all invoices | Yes | Yes | No |
| View any invoice detail | Yes | Yes | No |
| View own invoice detail | Yes | Yes | Yes |
| Confirm invoice | Yes | Yes | No |
| Cancel invoice | Yes | Yes | No |
| Send invoice email | Yes | Yes | No |
| Print/download invoice | Yes | Yes | Own only |
| Record payment | Through M7 workflow | Through M7 workflow | No |
| Run billing manually | Yes | Yes | No |
| View billing-run history/results | Yes | Yes | No |

Any Admin/Staff actions performed on behalf of another user must be attributed to the authenticated internal actor in the audit record.

---

## 4. Domain model and data ownership

The requirements identify `Invoice`, `InvoiceLine`, `Subscription`, `SubscriptionLine`, `Payment`, `BillingRun`, `Discount`, `DiscountRedemption`, `Tax`, `PaymentTerm`, `Notification`, and `AuditLog` as core domain entities. This section describes the M5-owned invoice and billing-run responsibilities without prescribing unapproved schema details.

### 4.1 Invoice

An invoice represents the bill for exactly one subscription and one billing period.

Required relationships and information supported by the source documents:

- One subscription reference.
- One customer reference, available from the subscription.
- A billing-period identity sufficient to enforce one invoice per subscription period.
- Invoice number.
- Invoice date.
- Due date derived from the subscription's payment terms.
- Status: Draft, Confirmed, Paid, or Cancelled.
- Invoice lines.
- Subtotal, tax, discount, proration, and total values as applicable.
- Links to payment history.
- Creation/confirmation/cancellation metadata and audit history as required by the shared audit design.

The exact invoice-number format, whether invoice date is the billing-run date or a separately configured date, and the exact set of stored header snapshot fields are not specified. Confirm these before finalizing the model.

### 4.2 InvoiceLine

Each invoice line must preserve the financial basis used for that invoice:

- Product reference or product identity.
- Description/name snapshot sufficient to render historical invoices.
- Quantity.
- Unit price.
- Product tax rate copied to the invoice line.
- Line amount and tax amount.
- Discount detail when a discount applies to the line or subscription.
- Proration adjustment detail where applicable.

The requirements explicitly state that each invoice line carries its product's tax rate. The source does not prescribe whether tax amount, pre-tax line amount, and post-tax line amount are all separate persisted fields; select a consistent representation and document it.

### 4.3 BillingRun

A BillingRun records one bulk billing execution. It should provide enough information for Admin/Staff to inspect:

- Run identifier.
- Start and completion timestamps, where available.
- Trigger type: Scheduled or Manual.
- Actor for a manual run; system identity for a scheduled run.
- Number of subscriptions processed.
- Number of invoices created.
- Number of subscriptions skipped.
- Number of failures.
- Per-subscription result entries with outcome, invoice reference when created, and reason for skip/failure.

The exact run status enum and storage format for per-item results are implementation decisions. The UI/UX source suggests run states such as In progress, Completed, Completed with failures, and Failed, but explicitly treats the exact run-state model as an implementation detail.

### 4.4 Relationships with adjacent modules

| Entity/module | M5 responsibility boundary |
|---|---|
| M2 Product Catalog / Tax | Read product identity, sales price, and associated tax. Preserve the applicable product tax rate on the invoice line. M5 does not manage products or tax rates. |
| M3 Plans | Consume billing cadence/plan context through the subscription. M5 does not configure plans. |
| M4 Subscriptions | Select due, eligible subscriptions and copy their customer, plan, and subscription-line information into an invoice. Exclude paused subscriptions. |
| M6 Discounts | Ask the discount domain/service for eligible discounts and include the resulting discount breakdown on the invoice. M5 does not own discount rules or redemption eligibility. |
| M7 Payments | Expose invoice totals and state for payment recording/collection. Successful full payment moves Confirmed → Paid through the invoice transition service. |
| M8 Reporting | Provide invoice, due-date, total, status, and billing-run data for reporting. |
| M9 Configuration | Read payment terms and configured currency/company context. |

### 4.5 Historical snapshot rule

The coding standards state that invoice totals are stored at confirmation time and historical invoices must not be recomputed from current prices. M5 must therefore retain the financial values used when an invoice is confirmed. Later edits to a product, tax rate, subscription line, discount rule, or plan must not silently alter an already confirmed invoice.

The exact snapshot strategy for customer billing address/name and product descriptions should be aligned with the project's invoice model before implementation; the source requires customer details to be prefilled but does not enumerate every snapshot field.

---

## 5. Invoice lifecycle and business logic

### 5.1 Status workflow

The required invoice state machine is:

```text
Draft ──► Confirmed ──► Paid
   │          │
   └──────────┴──► Cancelled
```

| From | To | Trigger | Actor |
|---|---|---|---|
| Draft | Confirmed | Invoice is confirmed manually or auto-confirmed by a billing run | Admin/Staff or billing process |
| Confirmed | Paid | Full payment is recorded successfully | M7 payment workflow |
| Draft | Cancelled | Invoice is cancelled | Admin/Staff |
| Confirmed | Cancelled | Invoice is cancelled | Admin/Staff |

Paid and Cancelled are terminal in the defined workflow. The source does not define a transition out of either state.

### 5.2 Centralized transition service

All invoice status changes must pass through one domain service, for example:

```python
invoices.services.transition(invoice, to_status, actor)
```

The exact module path should follow the existing repository layout. The service must:

1. Lock the invoice when concurrent changes are possible.
2. Validate the requested transition against one centralized transition map.
3. Reject invalid transitions with a domain-specific exception.
4. Apply the status change atomically.
5. Write an AuditLog entry with actor, previous status, new status, and timestamp.
6. Preserve immutable financial fields once the invoice is Confirmed.

Do not assign `invoice.status` directly from views, templates, tasks, or unrelated services.

### 5.3 Invoice generation from a subscription

When a subscription is due for billing, M5 should:

1. Load the subscription and the billing period being processed.
2. Confirm that the subscription is eligible for billing and is not Paused.
3. Check the subscription/billing-period uniqueness rule as an optimization only; the database constraint remains authoritative.
4. Load the subscription's customer, plan context, payment terms, and subscription lines.
5. Create invoice lines from the subscription lines without asking Staff to retype them.
6. Resolve each product's associated tax and copy the applicable rate to its invoice line.
7. Obtain eligible discounts from M6 and include their breakdown.
8. Include pending proration adjustments from M4 and show them on the invoice.
9. Calculate subtotal, discounts, taxes, adjustments, and total using Decimal-based server logic.
10. Derive the due date from the subscription's payment terms.
11. Persist the invoice and its lines transactionally.
12. Record the result as Created in the active BillingRun.

The requirements say billing runs can auto-confirm invoices. The exact policy for whether generated invoices are Draft by default or auto-confirmed by a billing run must be represented consistently in the billing-run implementation. The source does not specify a global default beyond allowing the run to auto-confirm in the state machine; confirm this behavior before making it configurable or fixed.

### 5.4 Duplicate-billing protection

This is a core data-integrity requirement.

- Add a database `UniqueConstraint` on `(subscription, billing_period)` for invoices.
- Do not rely only on a prior existence query; two concurrent requests can pass a pre-check simultaneously.
- If the insert hits the unique constraint, catch the narrow `IntegrityError`, roll back the failed unit of work as needed, record the subscription as Skipped, and include a reason such as “This billing period has already been invoiced.”
- A Cancelled invoice still occupies the subscription/billing-period uniqueness slot.
- A billing rerun must not create a second invoice for a period already represented by Draft, Confirmed, Paid, or Cancelled invoice records.
- Do not provide a “regenerate” action for a period already billed.

The source explicitly states that a cancelled invoice's period remains billed and must not be billed again. Do not implement replacement invoice generation for that same period unless the business rule is changed.

### 5.5 Paused subscriptions

- Paused subscriptions must be excluded from billing runs.
- A paused subscription must not receive a new invoice while paused.
- M4 owns pause/resume and next-billing-date recalculation.
- When the subscription resumes, M5 uses the recalculated billing date supplied by the subscription domain; it must not invent a separate pause-duration algorithm.

### 5.6 Tax calculation

- Tax comes only from the tax attached to each product (BR-8).
- Every invoice line carries the product's applicable tax rate (FR-5.4).
- The working assumption is that prices are tax-exclusive and tax is added on top (Open Item B / BR-13).
- Use the shared money-rounding helper and Decimal values; never use Python floats for financial calculations.
- The working rounding assumption is per line, two decimal places, half-up (Open Item J). This is not a finalized decision until confirmed.
- Preserve the rate used on the invoice line so later product-tax edits do not rewrite historical invoices.

M5 must not add location-based tax logic or multiple tax jurisdictions; the source says tax is attached to the product.

### 5.7 Discounts

M6 owns discount rules and eligibility. M5 must consume the approved calculation result and render it clearly.

- Apply eligible discounts automatically to the next invoice (FR-5.8).
- Show applied discounts in the invoice breakdown.
- Respect product-specific or whole-subscription scope as resolved by M6.
- Do not apply expired, exhausted, or ineligible discounts; the coding standards say these should be skipped with a log entry rather than blocking invoice generation.
- The working stacking order is fixed amount first, then percentage on the remainder (Open Item F).
- The working combined cap is 100% of the amount, so the total cannot go below zero (Open Item A / BR-9).
- Discount redemption counts increment when the invoice using the discount is confirmed (FR-6.8); coordinate the exact redemption call with M6 rather than incrementing from an unconfirmed draft.

### 5.8 Proration adjustments

M4 owns subscription changes and the calculation inputs; M5 includes pending adjustments in the next invoice.

- Mid-cycle changes to quantity, plan, or add-ons produce a prorated charge or credit on the next invoice (FR-4.13).
- Show proration adjustments as identifiable invoice detail, not as an unexplained change to the subscription line total.
- The working assumption is daily-basis proration, with downgrade credits applied to the next invoice (Open Item K).
- Use the shared rounding rule (Open Item J) and server-calculated Decimal values.
- Do not promise an immediate refund for a downgrade credit; the source assumption applies the credit to the next invoice.
- Do not calculate authoritative proration in browser-only JavaScript.

### 5.9 Due-date calculation

- Every invoice has a due date derived from the subscription's payment terms (FR-5.7).
- Payment terms are Admin-managed configuration (M9), with examples such as Immediate, Net 15, and Net 30.
- M5 reads the selected payment term and applies its configured due-date rule.
- Store the due date used by the invoice so later changes to a payment-term definition do not silently change an existing invoice.

The source does not define timezone handling, whether “Immediate” means the invoice date or same-day end-of-day, or the exact calendar-day/business-day convention. These details must be confirmed and implemented consistently.

### 5.10 Overdue indicator

The requirements define:

```text
overdue = today > due_date AND invoice.status != Paid
```

Consequences:

- An invoice due today is not overdue under the stated rule.
- Paid invoices are not overdue.
- Draft, Confirmed, and Cancelled invoice treatment should follow the literal rule only if those records appear in the relevant invoice views; the product team should confirm whether Cancelled invoices should be excluded from overdue lists, because the stated formula excludes only Paid.
- Display the due date and, if calculated by the application, the number of days overdue.
- Use a consistent application/business timezone for the meaning of “today”; the source does not specify which timezone.

Do not substitute a different overdue formula without a requirements decision.

### 5.11 Invoice immutability

FR-5.10 is Should priority, and the coding standards additionally state that invoice totals are stored at confirmation time and historical invoices are not recomputed from current prices.

Once Confirmed:

- Financial totals and line values are immutable.
- Product tax rates and applied discount/proration values used for the invoice remain historical values.
- Corrections follow the cancel-only working assumption in Open Item I.
- A cancelled invoice remains associated with its original billing period and that period is not re-billed.

The source does not define a credit-note workflow. Do not add one to M5 without a product decision.

---

## 6. Bulk billing runs

### 6.1 Trigger methods

A billing run can be started by:

- Admin or Staff using the “Run billing now” action.
- The approved scheduler using a protected Vercel Cron endpoint.

Customers cannot start billing runs.

### 6.2 Billing-run processing flow

```text
Start billing run
       │
       ▼
Find due subscriptions
       │
       ▼
Exclude paused / ineligible subscriptions
       │
       ▼
Resolve billing period and check invoice uniqueness
       │
       ▼
Generate invoice lines, tax, discounts, proration, due date
       │
       ▼
Persist invoice transactionally
       │
       ▼
Record Created / Skipped / Failed result
       │
       ▼
Continue with next subscription
       │
       ▼
Complete run and show summary
```

### 6.3 Per-subscription isolation

A failure for one subscription must not abort the full run.

For each subscription:

1. Execute the required reads and writes in a bounded transaction.
2. Catch only expected, narrow domain/database exceptions at the per-subscription boundary.
3. Roll back that subscription's incomplete invoice work.
4. Record Failed with a safe reason and relevant IDs.
5. Log the exception with operational context.
6. Continue to the next subscription.

Do not use a broad bare `except:` or silently swallow an exception. Unexpected failures must be logged and represented safely in the run outcome.

### 6.4 Billing-run result log

Every run must persist Created, Skipped, and Failed outcomes with reasons (FR-5.9).

Per-item fields required by the UI/UX specification:

- Subscription number.
- Customer.
- Outcome: Created / Skipped / Failed.
- Invoice number, if created.
- Reason, especially for skipped or failed items.

Run-level information shown in the UI:

- Run date/time.
- Trigger type (Scheduled or Manual).
- Subscriptions processed.
- Invoices created.
- Subscriptions skipped.
- Failures.

The exact run-state enum is an implementation detail. The UI/UX document suggests In progress, Completed, Completed with failures, and Failed as useful presentations.

### 6.5 Manual billing UX

Before starting a manual run:

- Explain that the action processes all due subscriptions and may create invoices.
- Require a deliberate action to start the run.
- Prevent repeated clicks from launching duplicate work from the same UI submission where possible; database idempotency remains mandatory.

After completion:

- Show created, skipped, and failed counts.
- Link to the detailed result log.
- Make the result accessible after the user navigates away.
- Do not imply that a partially failed run wholly failed if some invoices were successfully created.

### 6.6 Batching and resumability

The coding standards prohibit long-running background workers and in-process schedulers on Vercel. They specify protected Vercel Cron endpoints that call `tasks.py` entry points, and require long jobs to be batched and resumable.

Therefore:

- Do not introduce Celery workers, APScheduler, a message queue, or a separate event bus for M5.
- Process a limited chunk per serverless invocation where execution limits require it.
- Persist enough progress/result state to continue safely on a later invocation.
- Make each invocation safe if repeated or overlapping.
- Use database constraints and locking rather than in-memory run state.
- Protect the cron endpoint with a secret such as `CRON_SECRET`; it must never be publicly callable without authentication.
- The exact batch size, cron frequency, and continuation mechanism are not specified and must be configured for the deployment environment.

### 6.7 Concurrency and idempotency

- The database is the source of truth; Vercel functions are stateless and may run in parallel.
- Use `transaction.atomic()` for invoice creation and related multi-step writes.
- Use `select_for_update()` where a subscription, invoice, or related discount redemption can be changed concurrently.
- The unique `(subscription, billing_period)` constraint is the final duplicate safeguard.
- Handle a uniqueness `IntegrityError` as an already-billed/Skipped outcome, not as a fatal run error.
- Scheduled runs must be safe if triggered twice or overlap.
- Avoid duplicate emails or repeated external side effects when a job retries; email delivery must be coordinated through the notification/email boundary.

---

## 7. User interface and screen behavior

Follow the shared UI/UX specification: persistent internal navigation, responsive layouts, permission-aware controls, readable status text, paginated tables, field-level validation, and clear feedback for every action.

### 7.1 Internal invoice list

Audience: Admin and Staff.

Recommended columns:

- Invoice number.
- Customer.
- Subscription number.
- Invoice date.
- Due date.
- Total.
- Status.
- Overdue indicator.

Filters:

- Status.
- Overdue only.
- Customer.
- Date range.
- Subscription.

Behavior:

- Search by useful invoice/customer/subscription identifiers.
- Sort relevant columns where useful.
- Paginate results; do not load an unbounded invoice table.
- Clicking a row opens invoice detail.
- Keep filters when returning from a detail page where feasible.
- Provide loading, empty, and error states.
- Do not offer a regenerate action for a billing period already billed.

### 7.2 Invoice detail

Header:

- Invoice number.
- Customer.
- Status.
- Due date.
- Overdue indicator when applicable.

Sections:

1. Customer billing details.
2. Subscription reference and billing period.
3. Invoice lines.
4. Tax and discount breakdown.
5. Proration adjustments.
6. Subtotal and total.
7. Payment history.

Actions for Admin/Staff:

- Confirm.
- Cancel.
- Send by email.
- Print / download PDF.
- Record payment through the M7 workflow.

Only actions valid for the invoice's current status and the actor's role should be shown as available.

### 7.3 Invoice creation presentation

Invoices are generated from subscriptions. The UI must not ask Staff to retype invoice lines.

Show the generated:

- Billing period.
- Subscription and customer.
- Product lines and quantities.
- Product tax rates.
- Applicable discounts.
- Proration adjustments.
- Due date.
- Final total.

The server is authoritative for all calculations. Display read-only calculated values and do not trust client-submitted prices, tax rates, totals, or statuses.

### 7.4 Customer invoice list

Customers see only their own invoices.

Recommended columns:

- Invoice number.
- Invoice date.
- Due date.
- Amount.
- Status.
- Overdue indicator.

Customers can open, view, and print their own invoices. Do not expose Confirm, Cancel, Send, Record payment, or Run billing controls in the customer portal.

### 7.5 Invoice PDF / print view

The requirement supports printing (PDF), and the UI/UX source says customers and internal users can print/download invoices.

The printable representation should include the invoice details needed to understand the charge: invoice number, customer billing details, subscription/billing period, line items, quantity, unit price, tax, discount/proration detail, subtotal, total, due date, and status where appropriate.

The exact company branding, logo, legal text, tax identifiers, invoice-number format, PDF page layout, and storage/retention policy are not defined. Confirm these before treating them as required fields or building a template editor.

Vercel deployment constraint: generated PDFs must not be stored persistently on the local filesystem. If PDFs need persistent storage, use approved external object storage. The source allows a PDF library such as WeasyPrint or ReportLab only after confirming Vercel bundle/system-library constraints; do not add a heavy dependency without review.

### 7.6 Email sending

- Admin/Staff can send an invoice by email.
- Email delivery failure must not roll back the invoice or other completed business transaction.
- Log delivery failure, mark it for retry, and expose delivery/retry state to internal users where available.
- Avoid duplicate customer emails when a scheduled or manual operation is safely retried.
- Never log secrets, tokens, reset links, or full payment details.

The exact email provider, subject/body template, attachment-versus-link behavior, retry count, and sender identity are not specified by M5 and must follow the project's email-provider boundary and product configuration.

### 7.7 Status presentation

Use readable status labels; color must not be the only status indicator.

| Status / flag | Presentation |
|---|---|
| Draft | Neutral/pending label; can be confirmed or cancelled. |
| Confirmed | Confirmed label; financial details read-only; can be paid or cancelled. |
| Paid | Paid/success label; terminal state in the defined workflow. |
| Cancelled | Cancelled label; terminal state; billing period remains billed. |
| Overdue | Derived warning indicator when today is later than due date and status is not Paid under the stated formula. |

### 7.8 Confirmation and feedback

- Confirming an invoice should clearly identify the invoice and total being confirmed.
- Cancelling an invoice must require confirmation and warn that the billing period remains billed and will not be invoiced again.
- Sending an invoice should show a visible result and delivery state where available.
- Printing should open or provide the generated PDF using the approved project pattern.
- Failed validation should preserve valid form input where possible.
- Disable repeat submission while an action is processing, but do not rely on UI disabling for idempotency.

---

## 8. Validation and error handling

| Situation | Expected behavior |
|---|---|
| Subscription is not due | Do not generate an invoice; record a skip reason if it was considered by the run. |
| Subscription is Paused | Exclude it from billing; record a clear skip reason when included in the run's considered set. |
| Billing period already has an invoice | Skip and record “already billed” or equivalent reason. |
| Existing invoice for period is Cancelled | Skip; explicitly explain that the cancelled period remains billed. |
| Concurrent duplicate invoice attempt | Database unique constraint wins; catch `IntegrityError`, roll back that item, and record Skipped. |
| Product has no usable tax association | Fail that subscription's invoice generation with a clear operational reason; do not silently invent a tax rate. The exact nullability rule should follow M2's approved model. |
| Discount expired/exhausted/ineligible | Do not apply it; log/record the reason according to M6 behavior; do not block invoice creation solely for an ineligible discount. |
| Proration data unavailable or invalid | Fail safely or follow the agreed M4/M6 integration contract; do not invent a charge or credit. |
| Payment term missing or invalid | Do not fabricate a due date; report a per-subscription failure and resolve the configuration. |
| Invoice total calculation error | Roll back the invoice item, log safely, and continue the run. |
| Invalid invoice transition | Reject with a domain error and a friendly message. |
| Confirmed invoice edit attempted | Reject changes to immutable financial fields. |
| Paid or Cancelled invoice action attempted | Reject invalid actions; terminal states remain terminal. |
| Customer requests another customer's invoice | Deny access without disclosing whether the invoice exists. |
| Email delivery fails | Preserve invoice state, log the failure, and mark for retry. |
| PDF generation fails | Show a safe error; do not alter invoice financial state. |
| Billing run partially fails | Show Created, Skipped, and Failed outcomes separately; successful invoices remain successful. |
| Cron endpoint called without valid secret | Reject the request; do not start billing. |
| Database timeout during run | Log with context and retry only safe/idempotent work; allow later invocation to resume. |

Use domain exceptions for expected business failures, narrow exception handling, and Python's `logging` module. Never expose SQL errors, stack traces, or internal implementation details to users.

---

## 9. Architecture and implementation guidance

### 9.1 Approved architecture

Follow the project's Django modular-monolith architecture:

- Django current LTS.
- PostgreSQL as the single source of truth.
- Server-rendered templates with small targeted JavaScript where applicable.
- Thin views; business logic in services; read/query logic in selectors.
- No microservices, message queues, or event buses.
- No long-running in-process background workers or schedulers on Vercel.

### 9.2 Suggested app organization

Adapt names to the repository's actual app layout; do not create duplicate layers if equivalent modules already exist.

```text
apps/
  invoices/
    models.py          # Invoice, InvoiceLine, BillingRun, result records if owned here
    services.py        # generation, totals, transitions, confirm/cancel/send orchestration
    selectors.py       # invoice lists, detail queries, billing-run history
    forms.py           # internal filters/actions if server-rendered
    views.py           # thin request handlers
    urls.py
    tasks.py           # bounded billing-run task entry point
    permissions.py     # invoice and billing-run access rules
    exceptions.py      # invalid transition / generation errors
    pdf.py             # printable invoice rendering boundary, if needed
    tests/
      test_generation.py
      test_billing_runs.py
      test_transitions.py
      test_calculations.py
      test_permissions.py
      test_pdf_and_email.py
```

If the project has separate `billing` or `subscriptions` apps, place BillingRun orchestration according to existing ownership and keep invoice domain operations in one clear service boundary. Do not create an additional app solely to match this illustrative tree.

### 9.3 Service boundaries

Suggested service responsibilities:

- `generate_invoice_for_period(subscription, billing_period, actor_or_system)` — create one invoice from a subscription period; enforce eligibility and database uniqueness.
- `run_billing_batch(run, batch_cursor_or_scope)` — process a bounded set of due subscriptions and append per-item results.
- `transition(invoice, to_status, actor)` — validate and audit invoice status changes.
- `confirm_invoice(invoice, actor)` — validate and confirm; freeze the financial snapshot and coordinate discount redemption confirmation with M6.
- `cancel_invoice(invoice, actor, reason_if_supported)` — cancel under the state machine and preserve the billing-period uniqueness record.
- `calculate_invoice_totals(lines, discounts, proration)` — use Decimal and the shared rounding helper; keep calculations deterministic.
- `send_invoice(invoice, actor)` — call the configured email boundary after appropriate state/permission checks; delivery failure must not undo the invoice.
- `build_invoice_pdf(invoice)` — render a printable representation without persistent local-filesystem dependence.

These are suggested responsibilities, not mandatory public function names. Keep abstractions small and consistent with existing project conventions.

### 9.4 Database integrity and indexes

Use PostgreSQL constraints and indexes where appropriate:

- `UniqueConstraint(subscription, billing_period)` on Invoice.
- Appropriate foreign keys from Invoice to Subscription/Customer and InvoiceLine to Invoice/Product where the domain model supports them.
- Check constraints for non-negative quantities/amounts only where compatible with legitimate credit/proration lines; do not prohibit valid negative credit adjustments by assumption.
- Index invoice status, due date, customer, subscription, and invoice date/billing period according to actual query patterns.
- Index BillingRun creation/start time and result lookups as appropriate.
- Use `select_related` and `prefetch_related` to avoid N+1 queries.
- Paginate all invoice and billing-run result lists.

Every model change requires a migration. Never edit an applied migration. Use separate reversible data migrations where practical.

### 9.5 Money handling

- Use `DecimalField` for monetary values (the coding standards give `max_digits=12, decimal_places=2` as an example).
- Never use `float` for prices, tax, discounts, proration, totals, or assertions.
- Use the shared `money.round()` helper consistently.
- The current working rounding assumption is per line, two decimals, half-up; confirm Open Item J.
- Store totals at confirmation time and never recompute historical confirmed invoices from current product/subscription prices.
- Currency is single-currency under the working assumption; the actual currency code is not specified in the source and must not be invented.

### 9.6 Scheduler and Vercel

- Use Vercel Cron to call a protected endpoint which invokes a `tasks.py` entry point.
- Protect the endpoint with a secret header check such as `CRON_SECRET`.
- No Celery worker, APScheduler in-process, or persistent local job state.
- Batch and resume large runs within serverless execution limits.
- Ensure safe re-runs and overlapping invocation behavior.
- Do not write persistent invoice PDFs or billing state to local disk.
- Run migrations as an explicit deploy step, not at request time.
- Use environment variables for secrets and `DATABASE_URL`; production database connections require SSL and should use the project's pooler settings.

### 9.7 Email and PDF dependencies

- Email sending must be behind the project's email-provider boundary.
- Email failure must not roll back invoice creation/confirmation.
- Generated PDFs may use WeasyPrint or ReportLab only after confirming Vercel package size and system-library compatibility.
- Do not add a new PDF or email package without checking whether the repository already has an approved dependency or implementation.

---

## 10. Security, auditability, and privacy

1. Enforce Admin/Staff invoice permissions on every view and service.
2. Scope every customer-facing invoice query to the authenticated user's linked Customer record.
3. Never retrieve a customer invoice by primary key alone and then rely on the template to hide it.
4. Use ORM queries or parameterized queries; no raw SQL string formatting.
5. Validate all request input. Never trust client-sent prices, tax rates, totals, statuses, billing periods, or ownership identifiers.
6. Keep CSRF protection enabled for state-changing browser actions.
7. Keep Django template auto-escaping enabled; do not render user-supplied content with `safe`/`mark_safe`.
8. Do not expose stack traces, SQL errors, secrets, or internal logs to users.
9. Do not log full payment details, secrets, tokens, or unnecessary personal data.
10. Audit invoice status transitions, manual billing triggers, cancellation, and other consequential invoice actions with actor and timestamp.
11. Scheduled billing must record a system actor or equivalent source identity.
12. Confirmed invoice snapshots must remain stable when upstream catalog or subscription records change.

---

## 11. Acceptance criteria

M5 is functionally acceptable only when the applicable criteria below are demonstrated.

### 11.1 Invoice generation

- [ ] A due eligible subscription can produce an invoice without Staff retyping customer or product-line information.
- [ ] The invoice references the correct customer and subscription.
- [ ] The invoice contains the billing period being processed.
- [ ] Subscription lines are represented as invoice lines with correct quantities and unit prices.
- [ ] Each invoice line carries the applicable product tax rate.
- [ ] Subtotal, tax, discounts, proration adjustments, and total are calculated server-side using Decimal.
- [ ] Due date is derived from the subscription's configured payment terms.
- [ ] The generated invoice can be opened from the invoice list and subscription context.

### 11.2 Duplicate-billing safety

- [ ] PostgreSQL enforces uniqueness on `(subscription, billing_period)`.
- [ ] A second attempt to invoice the same period cannot create another invoice.
- [ ] A uniqueness conflict is handled as Skipped and logged with a reason.
- [ ] A cancelled invoice still blocks a replacement invoice for that period.
- [ ] A repeated billing run does not create duplicate invoices.
- [ ] Concurrent billing attempts cannot bypass the database constraint.
- [ ] Paused subscriptions are excluded from billing.

### 11.3 Invoice lifecycle

- [ ] Draft can transition to Confirmed.
- [ ] Draft can transition to Cancelled.
- [ ] Confirmed can transition to Paid only through successful full payment in M7.
- [ ] Confirmed can transition to Cancelled.
- [ ] Invalid transitions are rejected.
- [ ] Paid and Cancelled are terminal under the defined state machine.
- [ ] Each transition writes an audit record with actor, from/to states, and timestamp.
- [ ] Confirmed invoice financial fields cannot be edited.

### 11.4 Invoice actions

- [ ] Admin and Staff can confirm valid Draft invoices.
- [ ] Admin and Staff can cancel valid Draft or Confirmed invoices.
- [ ] Cancellation warns that the period remains billed and cannot be regenerated.
- [ ] Admin and Staff can send invoices by email.
- [ ] Email failure does not roll back invoice state and is visible/logged for follow-up.
- [ ] Admin and Staff can print/download invoice PDFs.
- [ ] Customers can view and print only their own invoices.
- [ ] Customers cannot confirm, cancel, send, record payment, or run billing.

### 11.5 Billing runs

- [ ] Admin and Staff can start a manual billing run.
- [ ] The approved scheduler can start a protected scheduled run.
- [ ] A billing run records trigger type and run timing.
- [ ] A run records processed, created, skipped, and failed counts.
- [ ] Each considered subscription has a Created, Skipped, or Failed result with a reason where applicable.
- [ ] A failure for one subscription does not stop other subscriptions from being processed.
- [ ] The result log remains accessible after the run completes.
- [ ] Large runs are bounded/resumable within serverless execution limits.
- [ ] Repeated or overlapping scheduled invocations are safe.

### 11.6 Calculation and history

- [ ] Tax is derived only from each product's tax association.
- [ ] Eligible M6 discounts appear on the invoice automatically.
- [ ] Pending M4 proration adjustments appear on the next invoice.
- [ ] Confirmed totals are stored and do not change when current product or tax configuration changes.
- [ ] Overdue status follows `today > due_date AND status != Paid` unless the requirement is formally revised.
- [ ] The UI does not mark an invoice due today as overdue.

### 11.7 Quality and security

- [ ] Every customer invoice query is scoped to the authenticated customer.
- [ ] Direct-ID access to another customer's invoice is denied without disclosing record existence.
- [ ] State-changing actions use server-side permission checks and CSRF protection.
- [ ] Invoice lists are paginated and avoid N+1 queries.
- [ ] No persistent invoice/PDF data is written to Vercel local filesystem.
- [ ] No secrets or full payment details appear in logs.

---

## 12. Test plan

Use `pytest`, `pytest-django`, and `factory-boy`. Each service function must have success and at least one failure-path test. Tests must not call real external services. Money assertions must use `Decimal`, never float.

### 12.1 Invoice generation tests

- Generate an invoice from a valid due subscription.
- Verify customer, subscription, billing period, invoice date, due date, and line references.
- Verify product, quantity, unit price, and product tax rate are copied correctly.
- Verify calculated line totals, subtotal, tax, discount, proration, and invoice total.
- Verify payment terms determine the due date.
- Verify no manual invoice-line input is required from Staff.
- Verify missing/invalid required source data fails safely and is recorded in the billing result.

### 12.2 Uniqueness and idempotency tests

- Generate the same subscription period twice; assert one invoice only.
- Attempt a second insert at the database constraint; assert graceful Skipped behavior.
- Cancel the first invoice and rerun; assert no replacement invoice is created.
- Run two concurrent generation attempts where practical; assert the unique constraint prevents duplication.
- Repeat the same billing-run task; assert no duplicate invoice or duplicate side effect.
- Verify paused subscriptions are excluded.

### 12.3 State-transition tests

- Draft → Confirmed succeeds.
- Draft → Cancelled succeeds.
- Confirmed → Paid succeeds only through the payment integration path.
- Confirmed → Cancelled succeeds.
- Draft → Paid is rejected.
- Paid → Cancelled is rejected.
- Cancelled → Confirmed/Paid is rejected.
- Confirmed invoice financial-field edits are rejected.
- AuditLog entries are written for each successful transition.

### 12.4 Calculation tests

- Product-specific tax rate is applied to the corresponding line.
- Different product lines can carry different tax rates.
- Tax uses Decimal arithmetic and the shared rounding helper.
- Fixed discount is applied before percentage discount under the working assumption.
- Combined discount is capped under the working assumption.
- Expired/exhausted/ineligible discount is skipped without blocking invoice generation.
- Positive proration charge is included on the next invoice.
- Negative proration credit is represented correctly under the agreed invoice-line convention.
- Rounding edge cases follow the confirmed rule.
- Historical invoice totals remain unchanged after product price/tax changes.

### 12.5 Billing-run tests

- Manual Admin trigger succeeds.
- Manual Staff trigger succeeds.
- Customer cannot trigger a billing run.
- Scheduled endpoint rejects a missing/invalid cron secret.
- Scheduled endpoint accepts a valid secret and starts the task.
- Run summary counts match per-item outcomes.
- One subscription failure does not prevent later subscriptions from being processed.
- Skipped and failed results include reasons.
- A batch can resume after a simulated timeout or interrupted invocation.
- Overlapping invocations do not duplicate invoices.

### 12.6 Invoice action and access tests

- Admin/Staff can confirm, cancel, send, and print where state permits.
- Customer can list and view own invoices.
- Customer cannot access another customer's invoice by changing the ID.
- Customer cannot confirm, cancel, email, or record payment.
- Email provider failure leaves invoice state intact and records retry/failure status.
- PDF generation failure returns a safe error without changing invoice state.
- Cancellation confirmation communicates that the period remains billed.

### 12.7 Performance and query tests

- Invoice list is paginated.
- Common filters use appropriate indexes where query plans justify them.
- Invoice detail does not produce avoidable N+1 queries.
- Billing batches process a representative hundreds-of-subscriptions fixture without exceeding configured execution limits.
- Verify page performance against NFR-1 in a representative environment; do not claim the two-second target without measurement.

### 12.8 Suggested commands

```bash
ruff check .
ruff format .
python manage.py makemigrations --check --dry-run
pytest
```

Run commands using the project's actual environment and scripts. Record any command that cannot be run and why; do not claim a check passed without executing it.

---

## 13. Open decisions and assumptions

The following items are taken from the source requirements/UI specification. They are not silently promoted to finalized product policy.

| ID | Decision / uncertainty | Current source assumption or guidance | M5 impact |
|---|---|---|---|
| A | Does the discount cap mean 100% or 100 currency units? | 100% cap; total cannot go below zero. | Discount and total calculation. |
| B | Are prices tax-inclusive or tax-exclusive? | Tax-exclusive; tax added on top. | Invoice line and total calculation. |
| C | Dunning cadence and final action? | Reminders at 1, 7, and 14 days past due; then auto-pause. | Overdue display and reminder integration; policy is owned outside M5. |
| D | Single currency and single company? | Yes, as working assumption. | Currency display and invoice header. |
| F | Discount stacking order? | Fixed amount first, then percentage on the remainder. | Invoice discount breakdown. |
| G | Payment-term options? | Admin-managed list, examples Immediate, Net 15, Net 30. | Due-date derivation. |
| I | How are mistakes on confirmed invoices corrected? | Cancel only; period remains billed. | Cancellation warning and no replacement invoice. |
| J | Tax/proration rounding rule? | Per line, two decimals, half-up. | Invoice totals and calculation tests. |
| K | Proration method and downgrade credit handling? | Daily basis; credit applied to next invoice. | Invoice adjustments. |

Additional M5 implementation decisions not fully specified by the source:

1. Invoice-number format, prefix, sequence scope, and whether numbers are allocated at Draft creation or confirmation.
2. Exact invoice date semantics and timezone.
3. Exact billing-period representation and how periods are calculated for each plan frequency.
4. Whether scheduled billing always auto-confirms generated invoices or creates Draft invoices by default.
5. Exact payment-term day-count convention, timezone, weekend, and holiday behavior.
6. Whether Cancelled invoices should appear in overdue lists. The literal overdue formula excludes only Paid, but the UI intent for Cancelled records is not explicit.
7. Whether a missing product tax association is invalid at product creation (M2) or can be encountered at invoice generation.
8. Exact invoice customer/address snapshot fields.
9. PDF branding, legal/company details, storage/retention, and whether PDFs are generated on demand or stored externally.
10. Email subject/body, sender identity, attachment-versus-link delivery, retry policy, and delivery-state model.
11. Billing batch size, cron frequency, run continuation mechanism, and maximum execution window.
12. Exact BillingRun status model and whether each per-subscription result is a separate table or structured data.
13. Whether Staff can view all audit history; UI_UX marks global activity-log Staff access as a decision.
14. Exact behavior for zero-total invoices or a fully discounted invoice; the source does not state whether these are auto-confirmed or treated specially.
15. Exact treatment of negative invoice totals if proration credits exceed the current charge; do not assume a refund or carry-forward policy beyond the stated next-invoice credit assumption.

---

## 14. Dependencies and implementation sequence

### 14.1 Required upstream capabilities

- M2 must provide products and product-to-tax associations.
- M3 must provide plans and billing cadence/configuration.
- M4 must provide subscription status, due/next billing date, customer, payment terms, subscription lines, pause/resume recalculation, and pending proration information.
- M6 must provide eligible discount calculation and redemption confirmation behavior.
- M9 must provide payment terms and the configured currency/company context.

### 14.2 Downstream integrations

- M7 consumes invoice totals and statuses for payment recording/collection and marks invoices Paid after successful full payment.
- M7 owns overdue reminder/dunning workflow and payment-provider abstraction.
- M8 consumes invoice and billing-run data for dashboards and reports.

### 14.3 Suggested implementation order

1. Confirm invoice/billing-period model fields and invoice-number strategy.
2. Implement Invoice, InvoiceLine, BillingRun, and per-item result persistence with migrations.
3. Add the unique `(subscription, billing_period)` constraint and supporting indexes.
4. Implement Decimal calculation helpers and invoice-line snapshot behavior.
5. Implement due-date calculation from PaymentTerm.
6. Implement invoice generation for one subscription period.
7. Implement invoice state machine, audit integration, and immutability checks.
8. Implement bounded billing-run orchestration with per-item failure isolation and idempotency.
9. Implement Admin/Staff invoice list/detail and billing-run result screens.
10. Implement customer-owned invoice list/detail/print views with strict data isolation.
11. Implement email and PDF boundaries using approved dependencies/services.
12. Integrate M6 discounts, M4 proration, M7 payment state, and M8 reporting.
13. Complete unit, integration, permission, concurrency, and performance tests.
14. Verify deployment constraints and run the project's lint, migration, and test commands.

---

## 15. Definition of Done

M5 is ready for acceptance when:

- [ ] FR-5.1 through FR-5.9 are implemented and verified.
- [ ] FR-5.10 invoice immutability is implemented or its Should-priority deferral is explicitly approved and documented.
- [ ] Invoice generation is driven by subscription data and requires no manual re-entry of invoice lines.
- [ ] Tax, discounts, and proration are represented correctly on invoice lines/totals.
- [ ] Due dates derive from payment terms.
- [ ] Database-level duplicate-period protection is active and tested.
- [ ] Cancelled invoices continue to block billing for their period.
- [ ] Paused subscriptions are excluded.
- [ ] Invoice transitions are centralized, validated, transactional, and audited.
- [ ] Billing runs persist Created/Skipped/Failed results and continue after per-subscription failures.
- [ ] Manual and protected scheduled triggers are available to authorized actors.
- [ ] Billing work is batched/resumable and safe under retries/overlapping invocations.
- [ ] Admin/Staff invoice and billing-run screens meet the UI/UX requirements.
- [ ] Customers can view/print only their own invoices.
- [ ] Email/PDF failures do not corrupt invoice financial state.
- [ ] No secrets, stack traces, or unnecessary personal data are exposed in logs or UI errors.
- [ ] All migrations are present; no applied migration was edited.
- [ ] `ruff check .`, `ruff format .`, `python manage.py makemigrations --check --dry-run`, and `pytest` pass, or any unavailable check is explicitly recorded with its reason.
- [ ] No unapproved dependencies or out-of-scope features are introduced.
- [ ] Open decisions affecting implementation are recorded for product confirmation.

---

## 16. Developer self-review checklist

Complete this checklist when implementing M5, in line with `CODING_STANDARDS.md`.

| Area | Review question | Status |
|---|---|---|
| File/component structure | Are models, services, selectors, views, forms, tasks, permissions, and tests placed according to the existing project structure? Are views thin? | To verify during implementation |
| State management | Is PostgreSQL the source of truth? Are invoice transitions centralized, atomic, and audited? | To verify during implementation |
| Billing integrity | Is `(subscription, billing_period)` protected by a database constraint? Are cancelled periods still treated as billed? | To verify during implementation |
| Money handling | Are all financial calculations Decimal-based and routed through the shared rounding helper? | To verify during implementation |
| Historical data | Are confirmed invoice totals and line/tax snapshots immutable? | To verify during implementation |
| Unused imports / dead code | Are unused imports, variables, stubs, debug prints, and dead code removed? | To verify during implementation |
| Dependencies | Were new PDF/email packages avoided unless justified, approved, pinned, and compatible with Vercel? | To verify during implementation |
| Over-engineering | Were unnecessary abstractions, queues, worker systems, and speculative features avoided? | To verify during implementation |
| Security | Are Admin/Staff permissions enforced server-side? Are customer queries ownership-scoped? Is the cron endpoint protected? | To verify during implementation |
| Error handling | Are exceptions narrow, failures logged, and per-subscription billing failures isolated? | To verify during implementation |
| Deployment | Are billing jobs bounded/resumable? Is persistent PDF storage external to the Vercel local filesystem? | To verify during implementation |

---

## 17. Source of truth

This document is derived from the Brightloop Subscription Management System source documents:

- `REQUIREMENTS.md` — M5 Invoicing (FR-5.1 through FR-5.10), business rules BR-4 through BR-14, invoice state machine in Section 7.2, non-functional requirements, core domain entities, and Open Items A–K.
- `UI_UX.md` — Section 5.9 Invoices, Section 5.10 Billing Runs, invoice status/immutability and overdue behavior, customer invoice portal behavior, scheduled billing flow, validation/error states, and PDF/email feedback requirements.
- `CODING_STANDARDS.md` — Django modular-monolith structure, service/selector boundaries, PostgreSQL constraints and transactions, Decimal money handling, invoice immutability, Vercel Cron and batching constraints, error handling, logging, and pytest standards.

Where these sources define behavior, this document preserves it. Where they leave a decision open, the uncertainty is recorded above instead of being silently replaced with an invented rule.
