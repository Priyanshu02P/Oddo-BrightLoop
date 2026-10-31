# M7. Payments

**Document type:** Feature specification and implementation baseline\
**Product:** Brightloop Subscription Management System\
**Module:** M7 --- Payments\
**Requirement coverage:** FR-7.1 through FR-7.9\
**Status:** Derived implementation baseline; unresolved policy details
remain open\
**Primary source documents:** `REQUIREMENTS.md`, `UI_UX.md`,
`CODING_STANDARDS.md`

------------------------------------------------------------------------

## 1. Purpose and scope

M7 provides payment recording, payment collection abstraction, invoice
payment-state updates, payment history, overdue-invoice identification,
and dunning reminders for the Brightloop Subscription Management System.

Staff can record a payment against an invoice by supplying its method,
amount, date, and an optional note. A payment belongs to exactly one
invoice. Partial payments are not allowed: the submitted amount must
equal the invoice total. When payment collection succeeds, the invoice
moves to `Paid`.

M7 owns payment records, payment-provider orchestration, payment
idempotency, payment outcome handling, and overdue/dunning processing.
M5 remains the owner of invoices and their lifecycle/status transitions.
M7 requests the invoice transition through the M5 service boundary; it
must not directly assign invoice status.

The MVP supports manual payment recording and a fake/mock gateway for
development and testing. It does not integrate a real payment gateway.

### 1.1 Goals

-   Let Admin and Staff record and inspect payments.
-   Link every payment to exactly one invoice.
-   Support multiple payment methods and payment dates.
-   Reject partial, excessive, or otherwise mismatched payment amounts.
-   Move an invoice to `Paid` only after successful payment.
-   Abstract payment collection behind a small `PaymentProvider`
    interface.
-   Ship a mock provider that simulates success, failure, and delay.
-   Prevent duplicate payment submissions.
-   Make paid, outstanding, and overdue invoices easy to identify.
-   Send automatic overdue reminders using the configured dunning
    cadence.
-   Keep payment, invoice, and notification failures safe, visible, and
    auditable.

### 1.2 In scope

-   Admin/Staff payment list and payment detail.
-   Admin/Staff record-payment flow.
-   Payment method, amount, date, note, invoice relationship, reference,
    and outcome.
-   Exact invoice-total validation; no partial payments.
-   Successful-payment invoice transition to `Paid`.
-   Multiple methods and dates across payment records.
-   `PaymentProvider` abstraction.
-   Fake/mock payment provider with success, failure, and delay
    outcomes.
-   Duplicate-payment prevention using an idempotency key or equivalent
    duplicate check.
-   Paid vs. outstanding invoice visibility.
-   Overdue definition and overdue invoice follow-up list.
-   Automated overdue reminder emails (dunning).
-   Safe retry behavior and operational logging.
-   Tests for permissions, amount validation, provider outcomes, invoice
    transitions, idempotency, and dunning.

### 1.3 Out of scope

Do not add the following unless a separate requirement or product
decision authorizes them:

-   Real payment-gateway integrations.
-   Customer-facing online payment or checkout.
-   Partial payments, split payments, deposits, or payment allocations
    across invoices.
-   One payment linked to multiple invoices.
-   One invoice settled by multiple separate payment records.
-   Refunds, chargebacks, reversals, credit notes, or payment
    cancellation workflows.
-   Stored cards, bank mandates, wallets, or payment-method
    tokenization.
-   Multi-currency or foreign-exchange handling.
-   Customer-entered payment references as proof of settlement unless an
    explicit verification workflow is defined.
-   A configurable payment-method administration module.
-   A customer payment portal action.
-   Dunning cadence customization UI unless separately approved.
-   Subscription pause/close policy changes beyond the currently
    documented dunning working assumption.

------------------------------------------------------------------------

## 2. Requirement traceability

FR-7.1 through FR-7.8 are Must requirements. FR-7.9 is Should.

  -----------------------------------------------------------------------
  Requirement             Source requirement      M7 behavior
  ----------------------- ----------------------- -----------------------
  FR-7.1                  Staff can record        Provide an Admin/Staff
                          method, amount, date,   payment form with those
                          and note.               fields and an invoice
                                                  selection.

  FR-7.2                  Every payment is linked Require one invoice
                          to exactly one invoice. foreign key; do not
                                                  support unallocated or
                                                  multi-invoice payments.

  FR-7.3                  Multiple payment        Store method and
                          methods and dates are   payment date per
                          supported.              record; do not
                                                  hard-code a single
                                                  method/date.

  FR-7.4                  No partial payments;    Validate exact Decimal
                          amount equals invoice   equality and transition
                          total; successful       the invoice only on a
                          payment moves invoice   successful provider
                          to Paid.                outcome.

  FR-7.5                  Staff can view paid     Provide invoice/payment
                          vs. outstanding         views and filters
                          invoices.               exposing Paid and
                                                  outstanding states.

  FR-7.6                  Overdue means today \>  Derive overdue status
                          due date and invoice    from the invoice due
                          status is not Paid.     date and current
                                                  business date; list
                                                  overdue invoices for
                                                  follow-up.

  FR-7.7                  `PaymentProvider`       Define a small provider
                          abstraction and         boundary and a
                          fake/mock gateway       test/development mock
                          supporting success,     implementation.
                          failure, delay.         

  FR-7.8                  Automatic overdue       Implement scheduled,
                          reminder emails on a    idempotent dunning
                          defined cadence.        reminders; use Open
                                                  Item C's working
                                                  cadence until
                                                  confirmed.

  FR-7.9                  Prevent recording the   Use a database-backed
                          same payment twice.     idempotency key or
                                                  equivalent duplicate
                                                  check; treat this as a
                                                  Should requirement but
                                                  implement where
                                                  feasible.
  -----------------------------------------------------------------------

### 2.1 Related requirements and business rules

-   FR-5.6: Invoice statuses are `Draft → Confirmed → Paid`; `Cancelled`
    is a terminal side state.
-   FR-5.7: Invoice due date is derived from the subscription's payment
    terms.
-   FR-5.10: Confirmed invoices are immutable; corrections follow the
    invoice cancellation policy.
-   FR-4.8: Automatic renewal attempts collection; failure flags the
    subscription `payment_failed`, emails the customer, notifies Staff,
    and applies the grace-period rule.
-   FR-4.14: Subscription moves from Confirmed to Active on its start
    date under the current working assumption, not necessarily on
    payment.
-   BR-6: A payment must equal the invoice total; partial payments are
    not allowed.
-   BR-7: An invoice becomes Paid only after successful payment.
-   Open Item C: Working dunning cadence is 1, 7, and 14 days past due,
    then auto-pause the subscription. This remains subject to
    confirmation.
-   Open Item D: Single currency and single company are working
    assumptions.
-   Open Item I: Invoice corrections use cancel-only working assumption;
    a cancelled invoice's billing period remains billed.
-   Open Item J: Monetary rounding is per line, two decimal places,
    half-up. Payment amount comparison should use stored invoice totals
    and Decimal arithmetic, not floating-point recomputation.

------------------------------------------------------------------------

## 3. Roles and permissions

### 3.1 Admin

Admin can:

-   Open the Payments section.
-   View payment lists and details.
-   Record a payment.
-   View paid, outstanding, and overdue invoices.
-   Review payment outcomes and mock-provider test results where the
    environment permits them.
-   Follow up payment failures and overdue invoices.

The requirements explicitly grant payment recording to Staff and the
role matrix grants it to Admin as well. No separate Admin-only
payment-management restriction is defined.

### 3.2 Internal Staff

Staff can:

-   Open the Payments section.
-   View payment lists and details.
-   Record a payment against an eligible invoice.
-   View paid vs. outstanding invoices.
-   View and follow up overdue invoices.
-   See safe payment failure or validation messages.

Staff cannot change invoice totals, invoice status directly,
payment-provider configuration, or customer ownership.

### 3.3 Customer

Customers cannot record payments through the portal under the current
permission matrix. Customers may view payment information associated
with their own records where exposed by the portal.

The UI/UX specification explicitly says not to add a customer-facing
online payment action to the MVP.

### 3.4 Server-side authorization and data isolation

-   Enforce payment permissions on every view and service boundary.
-   Default-deny unlisted payment actions.
-   Resolve the acting user and role from the authenticated server-side
    context.
-   Do not trust a submitted customer ID, invoice total, payment status,
    provider result, or invoice status.
-   Load the invoice through an ownership/permission-aware selector.
-   Customer-facing payment history must be scoped through the
    authenticated customer's own invoices.
-   Do not expose another customer's payment records by changing a URL
    or identifier.
-   Do not expose provider secrets, raw gateway payloads, or internal
    exception details to users.

------------------------------------------------------------------------

## 4. Domain model

The following is a proposed logical model. Field names are illustrative
and should be aligned with the existing repository conventions before
implementation. Inspect existing M5 invoice and M1 user/customer models
before creating relationships.

### 4.1 Payment

Represents a successful or attempted payment associated with one
invoice.

  -----------------------------------------------------------------------
  Field                   Suggested type          Purpose
  ----------------------- ----------------------- -----------------------
  `id`                    UUID / project-standard Stable identifier.
                          primary key             

  `payment_reference`     Unique CharField        Human-readable payment
                                                  reference.

  `invoice`               ForeignKey to Invoice,  Exactly one invoice per
                          non-null                payment.

  `method`                TextChoices or          Method used to
                          validated CharField     record/collect payment.

  `amount`                DecimalField            Amount submitted; must
                                                  equal the invoice
                                                  total.

  `payment_date`          DateField or            Date supplied for the
                          project-standard        payment.
                          date/time type          

  `note`                  TextField, blank        Optional operational
                          allowed                 note.

  `status`                TextChoices             Proposed outcome state,
                                                  aligned with provider
                                                  response.

  `provider_reference`    Nullable CharField      Provider/mock
                                                  transaction reference,
                                                  if returned.

  `idempotency_key`       Nullable/unique         Prevents repeated
                          CharField               submission where used.

  `recorded_by`           ForeignKey to User      Admin/Staff actor who
                                                  initiated manual
                                                  recording.

  `created_at`            DateTimeField           Record creation
                                                  timestamp.

  `updated_at`            DateTimeField           Last update timestamp.
  -----------------------------------------------------------------------

Suggested payment outcomes are `PENDING`, `SUCCEEDED`, and `FAILED`. The
requirements do not prescribe exact payment status names or whether
failed attempts are persisted as Payment rows. Confirm this before
treating the proposed enum as final.

A successful payment must be retained as a durable record. Failed
attempts may be recorded for operational traceability, but they must not
cause the invoice to become Paid.

### 4.2 Payment method

FR-7.1 requires a method field and FR-7.3 requires support for multiple
methods, but the source does not enumerate the methods.

Implementation options include a validated text field or a `TextChoices`
enum. Do not invent a fixed business list without confirmation. If an
enum is used for the initial MVP, document it as a configurable
implementation assumption and keep the model easy to extend.

### 4.3 PaymentProvider boundary

A small interface abstracts the act of collecting/processing a payment.

Conceptual responsibilities:

-   Accept the invoice/payment context and requested amount.
-   Invoke the selected provider implementation.
-   Return a normalized outcome such as success, failure, or
    pending/delayed.
-   Return a provider reference where applicable.
-   Avoid writing invoice status directly.
-   Avoid owning the database transaction for the invoice lifecycle.

The mock provider must implement the same contract as any future
provider. Keep the interface minimal; do not introduce a generic plugin
framework or real gateway integration.

### 4.4 Mock payment outcome

The fake/mock gateway must be able to simulate:

-   **Success:** payment succeeds and the invoice can transition to
    Paid.
-   **Failure:** payment fails; invoice remains unpaid and the failure
    is visible/logged.
-   **Delay:** provider response is delayed. The system must not
    prematurely mark the invoice Paid.

Mock outcomes must be clearly labelled as test-mode behavior. A
simulated payment must never appear to be a real external transaction.

The source does not define whether delay means a synchronous sleep, a
pending result, or a later callback. Prefer a deterministic
test-friendly pending/delayed result rather than tying production
request handling to long sleeps; confirm the exact behavior as an
implementation decision.

### 4.5 Relationships

``` text
Customer 1 ─── * Invoice
Invoice 1 ─── 0..1 successful Payment (working MVP interpretation)
Payment * ─── 1 Invoice
User 1 ─── * Payment (recorded_by)
```

The requirement says every payment is linked to exactly one invoice. It
does not explicitly state whether an invoice can have more than one
successful payment record. Since partial payments are prohibited and
successful payment settles the full invoice, the working interpretation
is at most one successful payment per invoice. Failed attempts may be
multiple if persisted. Confirm whether the domain should enforce one
successful payment or one payment attempt total per invoice.

------------------------------------------------------------------------

## 5. Payment lifecycle and business rules

### 5.1 Invoice payment eligibility

Payment recording should be offered for an invoice that is eligible to
receive payment under the invoice lifecycle.

The defined invoice workflow is:

-   `Draft → Confirmed → Paid`
-   `Draft → Cancelled`
-   `Confirmed → Cancelled`
-   `Paid` is final.
-   `Cancelled` is terminal.

The UI/UX describes payment against an invoice, and the workflow implies
payment follows confirmation. Therefore, the working implementation
should accept payment only for a `Confirmed` invoice. Do not accept
payment for Draft, Paid, or Cancelled invoices.

### 5.2 Exact amount; no partial payments

-   The submitted amount must equal the invoice's authoritative stored
    total.
-   A lower amount is rejected as a partial payment.
-   A higher amount is rejected as an overpayment.
-   Do not accept a payment amount supplied by the browser as
    authoritative.
-   Load the invoice total from the database on the server.
-   Compare using `Decimal`, never `float`.
-   Do not silently round a mismatched payment into equality.
-   Display a clear validation error when the amount differs from the
    invoice total.
-   The payment form may prefill the invoice total as a convenience, but
    server-side validation remains mandatory.

### 5.3 Successful payment

Only after the provider reports success:

1.  Persist the successful payment outcome and reference.
2.  Transition the invoice from Confirmed to Paid through the M5 invoice
    lifecycle service.
3.  Record the actor/provider context required for auditability.
4.  Make the updated Paid state visible in invoice and payment views.

The payment record and invoice transition must be coordinated safely. A
failed database write must not leave a successful payment record with an
unpaid invoice or a Paid invoice without its successful payment record.
Use a transaction and define the provider/database boundary carefully.

### 5.4 Failed payment

-   A failed provider outcome must not transition the invoice to Paid.
-   Preserve the invoice's current eligible unpaid status.
-   Return a clear, safe failure message to Admin/Staff.
-   Log the failure with relevant invoice/payment identifiers.
-   Do not expose stack traces, provider credentials, or raw internal
    errors.
-   If the attempt is persisted, mark it failed and ensure it cannot be
    mistaken for a successful payment.
-   A retry must be safe and must not duplicate a successful payment.

### 5.5 Delayed payment

-   A delayed/pending result is not success.
-   Do not transition the invoice to Paid until success is confirmed.
-   Show a pending/delayed state if the application persists such an
    attempt.
-   Define how a delayed result is reconciled before implementing
    asynchronous callbacks or polling; this is not fully specified in
    the source documents.

### 5.6 Duplicate prevention and concurrency

-   Prevent the same payment submission from being processed twice.
-   Prefer a client-generated idempotency key persisted with a database
    uniqueness constraint, or a clearly defined duplicate check if keys
    are not used.
-   A repeated request with the same idempotency key must return the
    original outcome rather than create a second payment.
-   Protect the invoice/payment operation against concurrent requests
    using `transaction.atomic()` and `select_for_update()` on the
    invoice.
-   Enforce the one-successful-payment-per-invoice rule at the database
    level if confirmed.
-   Do not rely only on a pre-check in Python; concurrent requests can
    pass the same check.
-   A duplicate or already-paid invoice attempt must return a safe
    domain-level error.

### 5.7 Multiple methods and dates

-   Store the method and payment date on each payment record.
-   Support different methods across different payments.
-   Support payment dates supplied by the Staff workflow.
-   The source does not define whether backdating is restricted, whether
    future dates are permitted, or which timezone applies to date/time
    values. Keep those as open decisions.

### 5.8 Overdue definition

An invoice is overdue exactly when:

`today > invoice.due_date AND invoice.status != Paid`

Consequences:

-   An invoice due today is not overdue.
-   A Paid invoice is never overdue.
-   A Confirmed invoice past its due date is overdue.
-   A Cancelled invoice is not Paid; the literal requirement would
    satisfy the status condition, but whether cancelled invoices should
    appear in overdue follow-up is not explicitly addressed. Exclude
    cancelled invoices from operational follow-up only after confirming
    this interpretation; otherwise preserve the literal rule and flag
    the ambiguity.
-   Overdue is a derived condition, not necessarily a persisted invoice
    status.
-   Use the agreed business timezone/date basis consistently.
-   Display the due date and, if calculated, the number of days overdue.

### 5.9 Dunning

The system automatically sends reminder emails for overdue invoices.

The current working assumption from Open Item C is:

  Reminder              Timing
  --------------------- --------------------------------------
  First reminder        1 day past due
  Second reminder       7 days past due
  Third reminder        14 days past due
  After final failure   Automatically pause the subscription

This cadence and final action are not confirmed product decisions. Do
not hard-code UI copy that presents them as final until approved.

Dunning must:

-   Run through the scheduler/cron mechanism, not an in-process
    scheduler.
-   Select overdue, unpaid invoices eligible for the next reminder.
-   Avoid sending the same reminder more than once when a job is re-run.
-   Record which reminder stage was sent and when.
-   Avoid sending reminders for invoices that have become Paid.
-   Log and safely handle email failures.
-   Avoid rolling back payment or invoice transactions because an email
    failed.
-   Respect the notification retry policy.
-   Keep the subscription pause action behind the confirmed grace-period
    policy and the subscription lifecycle service.

------------------------------------------------------------------------

## 6. Payment and invoice integration

### 6.1 Ownership boundary

-   M7 owns Payment and payment-provider orchestration.
-   M5 owns Invoice, invoice totals, invoice due dates, and invoice
    status transitions.
-   M7 must not duplicate invoice fields or independently implement the
    invoice state machine.
-   M7 calls the M5 service to transition an invoice to Paid after
    confirmed success.
-   M8 may consume payment and overdue data for dashboard/reporting.
-   M10 owns the shared scheduler and notification infrastructure; M7
    supplies payment/dunning task entry points and relevant email
    context.

### 6.2 Record-payment service flow

A recommended high-level flow:

1.  Resolve the authenticated Admin/Staff actor.
2.  Load and lock the target invoice.
3.  Verify the invoice is Confirmed and not already Paid or Cancelled.
4.  Read the authoritative invoice total.
5.  Validate the submitted amount equals that total.
6.  Validate method and payment date.
7.  Check idempotency/duplicate submission.
8.  Invoke the configured `PaymentProvider`.
9.  Normalize the provider result.
10. If success, persist the payment and invoke the M5 Confirmed → Paid
    transition within the coordinated transaction.
11. If failure or delay, persist/return the non-success outcome without
    changing invoice status.
12. Return a safe result to the view.

The exact ordering of external provider calls and database commits
requires care. A database transaction cannot roll back an external
payment side effect. The mock provider should make failure paths
testable, and the implementation should document how an external success
followed by a database failure is reconciled if a real provider is ever
introduced. Do not pretend this MVP solves real-gateway reconciliation.

### 6.3 Service and selector boundaries

Suggested `apps/payments/` structure:

``` text
apps/payments/
├── models.py
├── services.py          # record/process payment, idempotency, outcomes
├── selectors.py         # payment list/detail and invoice follow-up queries
├── providers.py         # PaymentProvider contract and mock implementation
├── forms.py
├── views.py
├── permissions.py
├── urls.py
├── tasks.py             # dunning scheduled entry point
├── tests/
└── migrations/
```

Keep views thin. Business logic belongs in services; complex reads
belong in selectors. The provider boundary belongs in the payments app
and should remain small.

------------------------------------------------------------------------

## 7. User experience

### 7.1 Audience and navigation

Audience: Admin and Staff.

The internal application navigation includes Payments. Customers do not
receive payment-recording controls.

### 7.2 Payment list

Recommended columns:

-   Payment reference
-   Invoice number
-   Customer
-   Method
-   Amount
-   Date
-   Status, if the payment provider returns one

Expected behavior:

-   Search by payment reference, invoice number, or customer-identifying
    fields where permitted.
-   Filter by method, date, and status where useful.
-   Paginate the list.
-   Open a payment detail view from a row.
-   Show empty, loading, and error states.
-   Do not expose another customer's payment information to customer
    users.

### 7.3 Record-payment flow

Fields:

-   Invoice
-   Payment method
-   Amount
-   Payment date
-   Note

Behavior:

-   Invoice selection should show enough context to identify the invoice
    and customer.
-   The amount may be prefilled from the selected invoice's
    server-provided total.
-   The payment is linked to exactly one invoice.
-   The amount must equal the invoice total.
-   Partial payments are not allowed.
-   A successful payment moves the invoice to Paid.
-   Prevent duplicate payment submission.
-   Show a clear validation error if the amount does not equal the
    invoice total.
-   Disable repeated submission while a request is processing.
-   Show a clear success, failure, or pending result.
-   Consequential payment actions should clearly identify the target
    invoice and amount.

### 7.4 Mock gateway presentation

-   Clearly label mock/simulated outcomes as test-mode behavior.
-   Never make a mock payment look like a real external payment.
-   Make success, failure, and delay behavior available in
    development/test environments.
-   Do not expose test outcome controls to production users unless
    explicitly required and protected.

### 7.5 Invoice list and overdue follow-up

Staff must be able to view Paid vs. outstanding invoices at any time.

The invoice list/follow-up view should expose:

-   Invoice number
-   Customer
-   Invoice date
-   Due date
-   Total amount
-   Invoice status
-   Overdue indicator
-   Days overdue, if calculated

Overdue invoices must be listed for follow-up. Do not label an invoice
due today as overdue.

### 7.6 Customer portal

-   Customers may view payment information associated with their own
    invoices if exposed.
-   Customers cannot record payments through the portal under the
    current permission matrix.
-   Do not add a Pay Now, checkout, or online-payment action to the MVP.

------------------------------------------------------------------------

## 8. Notifications and scheduled jobs

### 8.1 Dunning task

Provide a task entry point that can be invoked by the project's Vercel
Cron/protected endpoint arrangement.

The task should:

1.  Select a bounded batch of invoices that are overdue and eligible for
    a reminder.
2.  Determine the next reminder stage from persisted reminder
    history/state.
3.  Skip invoices already Paid.
4.  Skip invoices not yet due for the next reminder.
5.  Send the reminder through the notification service.
6.  Record successful dispatch so reruns do not duplicate the same
    reminder.
7.  Record/log failures and allow safe retry according to the
    notification policy.
8.  Continue processing other invoices if one email fails.

The task must be idempotent and resumable. Do not use Celery workers,
APScheduler, or in-process background workers on Vercel.

### 8.2 Reminder tracking

A proposed reminder log may contain:

-   Invoice
-   Reminder stage/sequence
-   Scheduled/eligible date
-   Sent timestamp
-   Delivery outcome
-   Failure reason safe for internal logs

A unique constraint such as `(invoice, reminder_stage)` can prevent
duplicate stage dispatches, subject to the approved retry design. If
failed attempts must be retried, distinguish an attempted dispatch from
a successfully sent reminder so the unique constraint does not
permanently block retries.

### 8.3 Email failure behavior

-   Email failures must not roll back a payment or invoice state
    transition.
-   Log failures with invoice/customer identifiers as appropriate,
    without secrets.
-   Mark the reminder for retry or leave it eligible for a safe retry.
-   Continue processing other invoices.
-   Do not send duplicate reminders after a successful send when the
    cron endpoint is invoked again.

------------------------------------------------------------------------

## 9. Validation and error handling

### 9.1 User/input errors

Return friendly, field-specific errors for:

-   Missing invoice.
-   Invoice not eligible for payment.
-   Invoice already Paid.
-   Invoice Cancelled.
-   Amount lower than invoice total.
-   Amount higher than invoice total.
-   Invalid payment method.
-   Invalid payment date.
-   Duplicate/idempotent request.
-   Permission denied.

### 9.2 Provider errors

-   Normalize provider success, failure, and delay into a small internal
    result.
-   Catch only expected provider exceptions.
-   Log unexpected provider failures with context and re-raise/handle
    safely.
-   Never mark an invoice Paid on timeout, unknown outcome, or failure.
-   Do not expose provider stack traces or secrets to the user.
-   Keep the mock provider deterministic and configurable in tests.

### 9.3 Domain exceptions

Suggested domain exceptions:

-   `InvoiceNotPayable`
-   `PaymentAmountMismatch`
-   `DuplicatePayment`
-   `PaymentProviderError`
-   `PaymentPending`

Use existing project conventions if equivalent exceptions already exist.
Do not create redundant exception hierarchies.

------------------------------------------------------------------------

## 10. Data integrity, transactions, and security

-   PostgreSQL is the source of truth for payment records, idempotency,
    and reminder history.
-   Use `DecimalField`; never use `float` for money.
-   Compare payment amount with the stored invoice total.
-   Wrap multi-step writes in `transaction.atomic()`.
-   Use `select_for_update()` when processing payment against an
    invoice.
-   Enforce idempotency with a database uniqueness constraint where
    applicable.
-   If the business confirms at most one successful payment per invoice,
    enforce it with a conditional unique constraint or equivalent
    database guarantee.
-   Do not directly assign invoice status; call the M5 transition
    service.
-   Do not call external email/payment services from model `save()`
    methods.
-   Keep external side effects outside model methods and define failure
    handling explicitly.
-   Enforce Admin/Staff permissions server-side.
-   Scope customer-facing reads to the current customer's invoices.
-   Do not trust client-sent totals, statuses, provider outcomes, or
    customer identifiers.
-   Do not log credentials, provider secrets, full payment details, or
    sensitive personal data.
-   Use parameterized ORM operations; no raw SQL string formatting.

------------------------------------------------------------------------

## 11. Performance and deployment constraints

-   Use PostgreSQL indexes for common payment and invoice filters, such
    as invoice, payment date, status, method, due date, and customer
    where justified by query patterns.
-   Avoid N+1 queries using `select_related` and `prefetch_related`.
-   Paginate payment and overdue-invoice lists.
-   Batch dunning work to fit Vercel execution limits.
-   Make dunning jobs resumable and safe to re-run.
-   Protect scheduler/cron endpoints with the configured cron secret.
-   Do not rely on in-memory globals, local files, or in-process
    schedulers.
-   Do not introduce a message queue or background worker for this
    module.
-   Do not add dependencies unless necessary; use Django and the
    standard library where practical.
-   Confirm any provider SDK or dependency against Vercel bundle/runtime
    constraints before adoption. The MVP mock provider should not
    require a gateway SDK.

------------------------------------------------------------------------

## 12. Testing strategy

### 12.1 Payment model and validation tests

-   Payment requires exactly one invoice.
-   Payment amount is stored as Decimal.
-   Payment method and date are required.
-   Note is optional.
-   Amount equal to invoice total is accepted.
-   Amount below invoice total is rejected.
-   Amount above invoice total is rejected.
-   Payment cannot be recorded for Draft, Paid, or Cancelled invoices
    under the working eligibility rule.

### 12.2 Provider tests

-   Mock provider success returns a normalized success result.
-   Mock provider failure returns a normalized failure result.
-   Mock provider delay returns a non-success pending/delayed result.
-   Failure and delay never mark the invoice Paid.
-   Mock outcomes are visibly distinguishable from real provider
    transactions.

### 12.3 Payment service tests

-   Successful payment creates a successful Payment and transitions
    invoice to Paid through M5.
-   Failed payment does not transition invoice to Paid.
-   Delayed payment does not transition invoice to Paid.
-   Duplicate idempotency key does not create a second payment.
-   Repeated request returns the original result where idempotency
    semantics require it.
-   Concurrent payment attempts cannot create duplicate successful
    payments.
-   A Paid invoice cannot be paid again.
-   Payment persistence and invoice transition remain consistent on
    database errors.

### 12.4 Permissions and data isolation tests

-   Admin can record and view payments.
-   Staff can record and view payments.
-   Customer cannot record payments.
-   Customer cannot view another customer's payment or invoice.
-   Unauthorized direct requests are rejected even if the UI control is
    hidden.

### 12.5 Overdue and dunning tests

-   Due today is not overdue.
-   Due date before today and status not Paid is overdue.
-   Paid invoice is not overdue.
-   The treatment of Cancelled invoices follows the confirmed policy.
-   Reminder stages are selected at the configured timing.
-   A rerun does not send the same successful reminder twice.
-   Paid invoices are skipped by dunning.
-   Email failure does not abort processing of other invoices.
-   Failed email dispatch can be retried safely.
-   Final subscription action is applied only after Open Item C is
    confirmed.

------------------------------------------------------------------------

## 13. Implementation sequence

1.  Inspect the existing repository, especially M1 authentication, M5
    invoices, M10 notifications/scheduler, and current model/service
    conventions.
2.  Confirm the payment-method list, invoice payment eligibility,
    successful-payment cardinality, and payment-date policy.
3.  Define the minimal `PaymentProvider` contract and normalized result
    type.
4.  Implement the mock provider with deterministic success, failure, and
    delayed outcomes.
5.  Implement the Payment model and migrations.
6.  Add idempotency and database constraints.
7.  Implement payment validation and domain exceptions.
8.  Implement the payment service using atomic transactions and invoice
    row locking.
9.  Integrate successful payment with the M5 invoice transition service.
10. Implement payment selectors and Admin/Staff list/detail/record
    views.
11. Add paid/outstanding/overdue invoice visibility.
12. Implement reminder tracking and the dunning task entry point.
13. Integrate reminder email dispatch with the shared notification
    service.
14. Add protected Vercel Cron invocation and batching/resume behavior.
15. Add unit, integration, permission, concurrency, and scheduler tests.
16. Run lint, formatting, migration checks, tests, and dependency audit.
17. Record all unresolved decisions and obtain product approval before
    treating working assumptions as final.

------------------------------------------------------------------------

## 14. Open decisions and assumptions

The source documents leave several M7 policies open. Keep these visible
and do not silently turn assumptions into requirements.

  ----------------------------------------------------------------------------
  \#                Topic               Source position /   Decision needed
                                        working assumption  
  ----------------- ------------------- ------------------- ------------------
  1                 Payment methods     A method field and  Which methods
                                        multiple methods    should be
                                        are required; no    selectable in the
                                        method list is      MVP?
                                        supplied.           

  2                 Payment statuses    UI says show status Confirm whether to
                                        if the provider     persist Pending,
                                        returns one;        Succeeded, and
                                        requirements do not Failed, and
                                        define payment      whether failed
                                        states.             attempts are
                                                            Payment records.

  3                 Invoice eligibility Invoice workflow    Confirm that Draft
                                        implies Confirmed   invoices cannot
                                        invoices are        receive payment.
                                        payable.            

  4                 Payment cardinality Partial payments    Can an invoice
                                        are prohibited;     have multiple
                                        multiple payment    failed attempts
                                        dates/methods are   but only one
                                        supported.          successful
                                                            payment?

  5                 Duplicate           FR-7.9 suggests     Choose
                    prevention          idempotency key or  idempotency-key
                                        duplicate check.    contract and
                                                            define behavior
                                                            when the same key
                                                            is reused with
                                                            different data.

  6                 Payment date        Staff supplies a    Can dates be
                                        date.               backdated or
                                                            future-dated? Is
                                                            it a date or
                                                            timestamp, and
                                                            what timezone
                                                            applies?

  7                 Payment reference   UI recommends a     Define format and
                                        payment reference.  sequential/UUID
                                                            strategy.

  8                 Delayed mock result Mock must simulate  Does delay mean
                                        delay.              pending result,
                                                            delayed
                                                            synchronous
                                                            response, or later
                                                            status update?

  9                 External            No real gateway is  Define
                    success/database    in scope.           reconciliation
                    failure                                 strategy before
                                                            any real provider
                                                            is integrated.

  10                Overdue cancelled   Literal rule says   Should Cancelled
                    invoices            status not Paid;    invoices be
                                        cancelled is not    excluded from
                                        Paid.               overdue follow-up?

  11                Dunning cadence     Open Item C working Confirm reminder
                                        assumption: 1, 7,   timing and whether
                                        14 days past due.   reminders are
                                                            calendar-day
                                                            based.

  12                Dunning final       Open Item C working Confirm pause
                    action              assumption:         behavior, affected
                                        auto-pause          subscription(s),
                                        subscription after  and whether manual
                                        final               review is
                                        reminder/failure.   required.

  13                Dunning retries     Email failures must Define retry
                                        be retried safely;  count/backoff and
                                        exact retry policy  when a reminder is
                                        is not stated.      considered sent.

  14                Reminder            Email reminders are Confirm
                    recipient/content   required; exact     recipient(s),
                                        recipient/content   template fields,
                                        is not defined      sender, and
                                        here.               staff-copy
                                                            behavior.

  15                Currency            Single currency is  Confirm currency
                                        a working           and formatting
                                        assumption;         source.
                                        currency is not     
                                        specified in M7.    

  16                Manual vs provider  Staff records       Clarify which
                    payment             payments and a mock methods are
                                        gateway is          manually confirmed
                                        required.           versus sent
                                                            through the
                                                            provider
                                                            abstraction.
  ----------------------------------------------------------------------------

### 14.1 Explicit non-assumptions

Do not assume:

-   That partial payments are allowed.
-   That a payment can be split across invoices.
-   That an invoice can be paid more than once successfully.
-   That any browser-submitted total is authoritative.
-   That a failed or delayed provider response means payment succeeded.
-   That a customer can record or initiate online payment.
-   That a real payment gateway is part of this MVP.
-   That a specific set of payment methods is approved.
-   That cancelled invoices should automatically be treated as overdue
    follow-up items without resolving the ambiguity.
-   That the 1/7/14-day dunning cadence and automatic pause are final
    policy.
-   That a delayed mock response requires production-style asynchronous
    callback infrastructure.
-   That an email failure should roll back a successful payment.
-   That an external payment side effect can be rolled back by a
    database transaction.

------------------------------------------------------------------------

## 15. Definition of Done

M7 is ready for acceptance when:

-   [ ] FR-7.1 through FR-7.8 are implemented and verified.
-   [ ] FR-7.9 duplicate prevention is implemented or explicitly
    deferred with approval.
-   [ ] Admin and Staff can record payments with invoice, method,
    amount, date, and note.
-   [ ] Every payment is linked to exactly one invoice.
-   [ ] Multiple payment methods and dates are supported according to
    the approved method policy.
-   [ ] Partial and overpayments are rejected; amount must exactly equal
    the stored invoice total.
-   [ ] Monetary handling uses Decimal and never float.
-   [ ] Successful payment moves the invoice to Paid through the M5
    transition service.
-   [ ] Failed and delayed payments do not mark invoices Paid.
-   [ ] The mock provider simulates success, failure, and delay.
-   [ ] Mock outcomes are clearly labelled as test-mode behavior.
-   [ ] Duplicate submissions are prevented with database-backed
    idempotency/duplicate protection.
-   [ ] Concurrent payment attempts cannot create duplicate successful
    payment records.
-   [ ] Staff can view paid and outstanding invoices.
-   [ ] Overdue calculation follows
    `today > due_date AND status != Paid`, subject to the
    cancelled-invoice policy decision.
-   [ ] Overdue invoices are listed for follow-up.
-   [ ] Dunning reminders are scheduled, tracked, and safe to re-run.
-   [ ] Reminder email failures do not roll back payments or stop
    unrelated reminders.
-   [ ] The dunning cadence and final subscription action are confirmed
    or clearly marked as deferred.
-   [ ] Payment and invoice records are protected by server-side
    permissions and customer data isolation.
-   [ ] No provider secrets or sensitive payment data are logged or
    exposed.
-   [ ] Tests cover validation, provider outcomes, invoice transitions,
    duplicate/concurrent submissions, permissions, overdue logic, and
    dunning.
-   [ ] Migrations are present and consistent.
-   [ ] `ruff check .`, `ruff format .`,
    `python manage.py makemigrations --check --dry-run`, and `pytest`
    pass, or any unavailable check is explicitly recorded with its
    reason.
-   [ ] Dependency audit is run before release.
-   [ ] No unapproved dependencies or out-of-scope features are
    introduced.
-   [ ] All unresolved product decisions are recorded and approved or
    explicitly deferred.

------------------------------------------------------------------------

## 16. Developer self-review checklist

Complete this checklist when implementing M7, in line with
`CODING_STANDARDS.md`.

  -------------------------------------------------------------------------
  Area                      Review question         Status
  ------------------------- ----------------------- -----------------------
  File/component structure  Are models, services,   To verify during
                            selectors, providers,   implementation
                            forms, views,           
                            permissions, tasks, and 
                            tests placed according  
                            to the project          
                            structure? Are views    
                            thin?                   

  State management          Is PostgreSQL the       To verify during
                            source of truth for     implementation
                            payments, idempotency,  
                            and reminder history?   

  Payment integrity         Is the amount compared  To verify during
                            with the stored invoice implementation
                            total using Decimal?    
                            Are                     
                            partial/overpayments    
                            rejected?               

  Invoice lifecycle         Does M7 use the M5      To verify during
                            transition service      implementation
                            rather than assigning   
                            invoice status          
                            directly?               

  Provider boundary         Is `PaymentProvider`    To verify during
                            minimal, with a mock    implementation
                            implementation for      
                            success, failure, and   
                            delay?                  

  Idempotency/concurrency   Are duplicate           To verify during
                            submissions and         implementation
                            concurrent payment      
                            attempts protected by   
                            database constraints    
                            and row locking?        

  Dunning                   Are reminder stages     To verify during
                            persisted, retries      implementation
                            safe, and cron          
                            execution               
                            bounded/idempotent?     

  Email behavior            Can email failures      To verify during
                            occur without rolling   implementation
                            back payment            
                            transactions or         
                            stopping other          
                            reminders?              

  Unused imports / dead     Are unused imports,     To verify during
  code                      variables, stubs, debug implementation
                            prints, and dead code   
                            removed?                

  Dependencies              Were new packages       To verify during
                            avoided unless          implementation
                            justified, approved,    
                            pinned, and compatible  
                            with Vercel?            

  Over-engineering          Were real gateways,     To verify during
                            customer checkout,      implementation
                            partial payments,       
                            wallets, and            
                            speculative payment     
                            abstractions avoided?   

  Security                  Are payment actions     To verify during
                            Admin/Staff-only? Are   implementation
                            customer payment reads  
                            ownership-scoped? Are   
                            provider secrets        
                            protected?              

  Performance               Are payment and overdue To verify during
                            lists paginated,        implementation
                            indexed where           
                            justified, and free of  
                            N+1 behavior? Are       
                            dunning batches         
                            bounded?                
  -------------------------------------------------------------------------

------------------------------------------------------------------------

## 17. Source of truth and conflict handling

This document is derived from the Brightloop Subscription Management
System source documents:

1.  `REQUIREMENTS.md` --- M7 Payments (FR-7.1 through FR-7.9),
    role--permission matrix, invoice lifecycle in FR-5.6, due-date rule
    in FR-5.7, automatic renewal failure behavior in FR-4.8, and Open
    Items C, D, and I.
2.  `CODING_STANDARDS.md` --- Django modular-monolith structure,
    `apps/payments/` ownership, services/selectors boundaries, the
    required `PaymentProvider` interface and mock gateway, PostgreSQL
    constraints and transactions, Decimal money handling, concurrency,
    logging, Vercel Cron, and test standards.
3.  `UI_UX.md` --- Section 5.11 Payments, Admin/Staff audience, payment
    list columns, record-payment fields and behavior, mock gateway
    presentation, and customer portal restriction against online
    payment.

`REQUIREMENTS.md` defines what the product must do.
`CODING_STANDARDS.md` defines how implementation must be structured and
validated. `UI_UX.md` defines the expected interface and interaction
behavior.

Where the sources define behavior, this document preserves it. Where the
sources leave a decision open, the uncertainty is recorded in Section 14
instead of being silently replaced with an invented business rule. This
document is an implementation baseline; it does not claim that M7 is
already implemented.
