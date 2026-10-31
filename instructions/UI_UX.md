# Brightloop Subscription Management System — UI/UX Specification

**Document version:** 1.0  
**Based on:** Brightloop Subscription Management System Requirements Specification v2.0  
**Status:** Draft — pending confirmation of the open items in the requirements  
**Audience:** Product, UX/UI design, frontend, and QA teams

---

## 1. Purpose

This document defines the user experience, information architecture, screen layouts, interaction patterns, and interface states for the Brightloop Subscription Management System.

The product supports the complete subscription-business lifecycle:

**Product and plan setup → Quotation → Subscription → Invoicing → Payment collection → Revenue reporting**

The interface should replace spreadsheet-based subscription tracking, manually prepared invoices, ad hoc renewal follow-ups, and manually assembled revenue reports with a unified workspace.

### 1.1 UX goals

1. Let Admins configure the commercial catalog and system settings without relying on developers.
2. Let Staff handle customer, quotation, subscription, invoice, and payment operations with minimal friction.
3. Let Customers independently review quotations, manage eligible subscription actions, and access invoices.
4. Make operational status immediately understandable: active, paused, payment failed, outstanding, paid, overdue, or expired.
5. Prevent user actions that violate business rules, and explain why an action is unavailable.
6. Make billing operations traceable, safe to retry, and easy to inspect.
7. Keep common pages responsive within the specified two-second target at thousands of subscriptions.

### 1.2 UX principles

- **Clarity over density:** prioritize the next action and the current status; expose detailed information progressively.
- **One source of truth:** show subscription, invoice, payment, and customer records from the same system.
- **Safe financial actions:** confirm consequential actions and clearly explain their effects.
- **Visible automation:** show when a job ran, what it processed, and what failed.
- **Self-service by default:** customers should not need Staff for actions enabled by their plan.
- **Permission-aware UI:** hide or disable unavailable actions, but always enforce authorization on the server.
- **No silent failure:** every save, billing run, payment attempt, and email action must return a visible result.

---

## 2. Users and experience boundaries

### 2.1 Admin

Admin has full system control.

Primary tasks:
- Manage Staff accounts.
- Create and maintain products, variants, plans, taxes, payment terms, discounts, and quotation templates.
- Create and manage subscriptions and invoices.
- Run billing manually when needed.
- Record payments and inspect renewal failures.
- Review dashboard, reports, scheduler activity, and audit history.

### 2.2 Internal Staff

Staff handles day-to-day operations with limited access.

Primary tasks:
- Find and manage customers and subscriptions.
- Use existing quotation templates.
- Send quotations and monitor acceptance or expiry.
- Confirm, cancel, send, and print invoices.
- Run billing and review its result log.
- Record payments.
- Follow up overdue invoices and failed renewals.
- View dashboard and reports.

Staff must not see controls for creating or managing products, variants, plans, taxes, discounts, Staff accounts, or quotation templates. Staff can use quotation templates but cannot create or edit them.

### 2.3 Customer

Customer uses a self-service portal and can access only their own data.

Primary tasks:
- Sign up, sign in, and reset password.
- View their subscriptions and current statuses.
- Review and accept valid quotations.
- View and print their invoices.
- View payment information.
- Pause, resume, cancel, upgrade, downgrade, or change quantity when the associated plan permits the action.
- Review subscription add-ons and request permitted changes through the portal.

Customers cannot run billing, record payments, or access internal dashboards and reports.

### 2.4 Permission behavior

The interface must follow the role–permission matrix in the requirements.

| Area / action | Admin | Staff | Customer |
|---|---:|---:|---:|
| Dashboard and reports | Yes | Yes | No |
| Staff account management | Yes | No | No |
| Product, variant, and plan management | Yes | No | No |
| Tax, payment-term, and discount management | Yes | No | No |
| Quotation-template management | Yes | No | No |
| Use quotation templates | Yes | Yes | No |
| Manage subscriptions | Yes | Yes | Own only, permitted portal actions |
| Accept quotation | Yes | Optional, on behalf | Own quotation |
| Run billing / generate invoices | Yes | Yes | No |
| Confirm, cancel, send, print invoices | Yes | Yes | View / print own |
| Record payments | Yes | Yes | No |

**UX requirement:** Unauthorized controls should not be presented as available actions. Server-side authorization remains mandatory even when the UI hides a control.

---

## 3. Information architecture

### 3.1 Internal application navigation

Use a persistent left sidebar on desktop, a compact header, and a main content area. On smaller screens, collapse the sidebar into a navigation drawer.

Recommended navigation:

| Navigation item | Contents | Visibility |
|---|---|---|
| Dashboard | Operational and finance overview | Admin, Staff |
| Customers | Customer directory and customer details | Admin, Staff |
| Subscriptions | Subscription list and details | Admin, Staff |
| Quotations | Quotations and their statuses | Admin, Staff |
| Invoices | Invoice list, overdue list, invoice details | Admin, Staff |
| Payments | Recorded payments and payment details | Admin, Staff |
| Billing runs | Run history and per-run results | Admin, Staff |
| Reports | Filtered financial and subscription reports | Admin, Staff |
| Catalog | Products and variants | Admin |
| Plans | Plan configuration | Admin |
| Discounts | Discount rules and redemptions | Admin |
| Configuration | Taxes and payment terms | Admin |
| Quotation templates | Template management | Admin |
| User management | Staff accounts | Admin |
| Activity log | Audit and operational events | Admin; Staff access subject to implementation decision |

The requirements specify audit logging but do not explicitly define an audit-log screen or Staff access to it. Treat the Activity log navigation as an implementation proposal; confirm its visibility before release.

### 3.2 Customer portal navigation

Use a simplified portal with no internal operational navigation.

- Overview
- My subscriptions
- My quotations
- My invoices
- Account / security

A customer must never be able to navigate to another customer's records by changing an identifier or URL.

### 3.3 Global application elements

Internal application:
- Brand and application name.
- Current user's name and role.
- Profile and sign-out actions.
- Main navigation.
- Page title and contextual primary action.
- Notifications or activity indicator, if implemented.
- Breadcrumbs on nested detail and configuration pages.

Customer portal:
- Brand and account menu.
- Portal navigation.
- Clear account context.
- Support/contact entry point only if the product team provides one; support workflow is not specified in the requirements.

---

## 4. Shared visual and interaction system

### 4.1 Layout

- Use a consistent page container and spacing scale.
- Use tables for operational lists and cards for high-level summary metrics.
- Keep primary actions in a predictable location near the page title.
- Keep filters above the table and preserve them when the user returns from a record detail page, where feasible.
- Use a responsive table strategy: allow horizontal scrolling or switch to stacked record summaries on narrow screens.
- Avoid placing every field on the initial view; group secondary information into sections or tabs.

### 4.2 Status presentation

Use text labels with consistent visual treatment. Do not communicate status by color alone.

| Record | Statuses / flags | UX treatment |
|---|---|---|
| Subscription | Draft, Quotation, Confirmed, Active, Paused, Closed | Persistent status label on list rows and detail header |
| Subscription | `payment_failed` flag | Separate warning indicator; it is an additional flag, not a replacement lifecycle status |
| Invoice | Draft, Confirmed, Paid, Cancelled | Persistent status label |
| Invoice | Overdue | Derived indicator when today is after due date and status is not Paid |
| Quotation | Valid / expired / declined | Show validity date and acceptance availability |
| Billing run | In progress, completed, completed with failures, failed | Show run outcome and counts; exact run-state model is an implementation detail |

Suggested semantic colors:
- Active / Paid / successful: green.
- Draft / pending / quotation: neutral or blue.
- Paused / overdue / payment failed: amber.
- Closed / cancelled / failed: red or muted red.

Always include readable status text and accessible contrast.

### 4.3 Forms

- Group fields by purpose.
- Mark required fields and show validation beside the relevant field.
- Preserve valid input when validation fails.
- Use searchable selects for long lists such as customers, products, taxes, and plans.
- Show calculated values as read-only previews where appropriate.
- Display money with the configured currency and two decimal places; the currency itself is not specified yet.
- Do not use floating-point calculations in the UI for authoritative totals; display server-calculated decimal values.
- Explain date constraints and unavailable plan options before submission.

### 4.4 Tables and lists

Common list behavior:
- Search by the most useful identifying fields.
- Filters relevant to the record type.
- Sortable columns where useful.
- Pagination or server-side loading for large datasets.
- Empty, loading, and error states.
- Row click opens details; action menus contain secondary actions.
- Destructive actions require confirmation.

Do not assume bulk editing or bulk cancellation; these capabilities are not specified.

### 4.5 Feedback and confirmations

Every action must have a clear result:
- Success confirmation after a successful save or state transition.
- Inline validation for invalid fields.
- Error message with a safe next step when an operation fails.
- Loading state and disabled submit control while a request is processing.
- Confirmation dialog for cancellation, closing, pausing, or other consequential lifecycle changes.
- No duplicate submission when a user clicks repeatedly.

For financial actions, show the amount and target invoice/subscription in the confirmation step.

---

## 5. Screen specifications — internal application

## 5.1 Authentication

### Sign in

Fields:
- Email
- Password

Actions:
- Sign in
- Forgot password
- Customer sign-up link

Behavior:
- Validate required fields.
- Use case-insensitive email identity.
- Show a generic authentication error that does not reveal whether an email is registered.
- Route users to the correct experience based on role.

### Customer sign-up

Fields:
- Email
- Password
- Confirm password, recommended for usability

Password guidance must state the actual policy:
- More than 8 characters.
- At least one uppercase letter.
- At least one lowercase letter.
- At least one special character.

Public signup always creates a Customer account. Do not offer a role selector.

### Forgot password / reset password

- User submits registered email.
- Show a neutral confirmation that instructions will be sent if the account exists.
- Reset link is single-use and time-limited.
- Reset page accepts a new password and confirmation.
- Expired or already-used links show an explanation and a route to request another link.

## 5.2 Dashboard

Audience: Admin and Staff.

Purpose: answer the key finance and operations questions quickly.

### Summary cards

- Active subscriptions
- Revenue collected for the selected period
- Outstanding amount
- Overdue invoice count
- Subscriptions with failed renewals

MRR may be included as a secondary metric because it is a Should requirement, not a Must requirement.

### Main dashboard sections

1. **Invoice status overview:** paid, outstanding, and overdue counts or totals.
2. **Overdue invoices:** customer, invoice number, due date, amount, and status; link to invoice detail.
3. **Failed renewals:** affected customer, subscription, failure indicator, and available follow-up.
4. **Recent billing activity:** recent billing runs and their outcomes.
5. **Subscription overview:** active, paused, and closed counts where useful.

### Filters

- Date range
- Customer
- Plan
- Status

Filters should update all relevant dashboard metrics and lists consistently. The dashboard should make the selected date range visible.

### Dashboard interactions

- Clicking a metric opens the corresponding filtered list.
- Clicking an overdue invoice opens its detail page.
- Clicking a failed renewal opens the subscription detail page.
- Show an explicit empty state when there are no overdue invoices or failed renewals.

## 5.3 Customer directory and customer detail

Audience: Admin and Staff.

### Customer list

Recommended columns:
- Customer name / account identifier
- Email
- Subscription count
- Active subscription count
- Outstanding invoice amount
- Most recent activity, if available

The requirements define Customer and User entities but do not specify the complete customer-profile fields. Confirm the profile schema before finalizing the form and columns.

### Customer detail

Suggested sections:
- Customer profile
- Subscriptions
- Quotations
- Invoices
- Payments

Show only data associated with the selected customer. Provide contextual links to related records.

## 5.4 Product catalog

Audience: Admin only.

### Product list

Columns:
- Product name
- Type
- Sales price
- Cost price
- Tax
- Variant count
- Status (active / archived)

Actions:
- Create product
- Edit product
- Archive product
- Open product details

### Product create / edit form

Fields:
- Name
- Type
- Sales price
- Cost price
- Notes
- Associated tax
- Variants

### Variant editor

Allow Admin to add variant dimensions/values and their price adjustments.

Example from the requirements:
- Variant value: Odoo
- Price adjustment: +560

Show the base price and adjusted price preview. The exact rules for multiple variant dimensions and how adjustments combine are not specified; confirm before implementing a complex variant configurator.

Archived products should not be offered for new subscription lines. Existing subscription and invoice history must remain understandable; do not silently rewrite historical line items.

## 5.5 Plans

Audience: Admin only.

### Plan list

Columns:
- Plan name
- Price
- Billing period
- Minimum quantity
- Availability window
- Renewal mode
- Lifecycle options
- Status

### Plan create / edit form

Fields:
- Name
- Price
- Billing period: daily, weekly, monthly, yearly
- Minimum quantity
- Availability start date
- Availability end date
- Renewal mode: Automatic / Manual
- Lifecycle options:
  - Auto-close at end date
  - Close early
  - Pause
  - Renew

Explain that a plan is selectable for new subscriptions only within its availability dates. Existing subscriptions may still reference a plan outside its new-subscription availability window; the precise edit/archive behavior for plans already in use should be confirmed.

## 5.6 Quotation templates

Audience: Admin manages; Admin and Staff use.

### Template list

Columns:
- Template name
- Plan
- Number of predefined lines
- Validity period in days
- Last updated, if available

### Template create / edit

Fields:
- Template name
- Plan
- Predefined product lines
- Quantity and pricing details as supported
- Validity period in days

Staff should see templates in a selection flow but must not see create, edit, or delete controls.

## 5.7 Subscriptions

Audience: Admin and Staff; Customers see their own subscriptions in the portal.

### Subscription list

Recommended columns:
- Subscription number
- Customer
- Plan
- Start date
- Expiry date
- Next billing date, if available
- Renewal mode
- Status
- Payment-failed indicator

Filters:
- Customer
- Plan
- Status
- Renewal mode
- Payment-failed flag

Search:
- Subscription number
- Customer name or email

### Create subscription flow

Recommended sequence:

1. **Select customer.**
2. **Choose a plan.** Show only plans available for new subscriptions on the selected start date.
3. **Choose creation method.** Start blank or use a quotation template.
4. **Configure subscription lines.** Add products, variants, quantities, and add-ons.
5. **Review pricing.** Show unit prices, line amounts, taxes, and total.
6. **Set dates and payment terms.**
7. **Save as Draft** or **Create quotation**, depending on the selected action.

When a template is selected, copy its plan and product lines into the subscription. The copied lines remain editable.

### Subscription detail

Header:
- Subscription number
- Customer
- Plan
- Current status
- `payment_failed` indicator, when set

Suggested sections:
- Overview: dates, renewal mode, payment terms, next billing date
- Subscription lines: products, variants, quantities, prices, taxes, add-ons
- Billing history: linked invoices
- Activity history: status changes and other audited actions

Available actions depend on role and current state:
- Send quotation
- Accept quotation on behalf of customer, where permitted
- Confirm / activate, where the workflow permits
- Pause
- Resume
- Cancel / close
- Renew
- Upgrade / downgrade
- Change quantity
- Add / remove add-ons

Only show actions enabled by the plan's lifecycle configuration and valid for the current subscription state. The requirements do not define every transition's exact UI permission by state; use the state machine and plan options as the source of truth.

### Subscription lifecycle UX

| Current state | User-facing presentation | Relevant action / explanation |
|---|---|---|
| Draft | Draft; not yet sent | Edit and send quotation |
| Quotation | Awaiting customer response; show expiry | Customer can accept while valid |
| Confirmed | Accepted; awaiting start date | Show scheduled start date |
| Active | Active subscription | Show permitted management actions |
| Paused | Billing paused | Show resume action if allowed |
| Closed | Closed; terminal | Read-only history |

Additional payment-failure flag:
- Display a prominent `Payment failed` warning independently of the lifecycle status.
- Explain that the renewal payment was not received and show the next step or current grace-period state when that information is available.
- Do not imply that the subscription is Closed or Paused unless its actual lifecycle status has changed.

### Pause and resume

Before pausing, explain that the subscription is excluded from billing runs while paused.

On resume, show the recalculated next billing date before or immediately after confirmation. The backend calculation is authoritative.

### Upgrade, downgrade, quantity, and add-on changes

- Show the current configuration and proposed configuration side by side.
- Preview the expected prorated charge or credit where possible.
- Explain that the adjustment is applied to the next invoice.
- Do not promise an immediate refund; the working assumption is that downgrade credits apply to the next invoice.
- Require confirmation before applying the change.

Proration uses a daily basis under the current working assumption. The final amount must come from the billing calculation, not a browser-only estimate.

## 5.8 Quotations

Audience: Admin and Staff internally; Customers in their portal.

### Quotation list

Recommended columns:
- Quotation / subscription number
- Customer
- Plan
- Created date
- Valid until
- Status: awaiting response, accepted, expired, declined

### Quotation detail

Show:
- Customer and subscription details
- Plan and line items
- Taxes, discounts, and total
- Validity end date
- Current quotation status

Actions:
- Admin / Staff: create from subscription, send, view, print if supported.
- Customer: review and accept while valid.

An expired quotation must not present an active Accept action. Explain that the validity period has ended and direct the customer to contact the company or request a revised quotation; the exact re-quotation process is not specified.

## 5.9 Invoices

Audience: Admin and Staff internally; Customers can view and print their own.

### Invoice list

Recommended columns:
- Invoice number
- Customer
- Subscription number
- Invoice date
- Due date
- Total
- Status
- Overdue indicator

Filters:
- Status
- Overdue only
- Customer
- Date range
- Subscription

### Invoice detail

Header:
- Invoice number
- Customer
- Status
- Due date
- Overdue indicator when applicable

Sections:
- Customer billing details
- Subscription reference and billing period
- Invoice lines
- Tax and discount breakdown
- Proration adjustments
- Subtotal and total
- Payment history

Actions:
- Confirm
- Cancel
- Send by email
- Print / download PDF
- Record payment (Staff/Admin workflow)

### Invoice creation

Invoices are generated from subscriptions. The UI must not ask Staff to retype invoice lines.

Show:
- Billing period
- Subscription and customer
- Generated lines
- Product tax rates
- Applicable discounts
- Proration adjustments
- Final total

### Invoice status and immutability

- Draft can be confirmed or cancelled.
- Confirmed can be paid or cancelled.
- Paid is final in the defined workflow.
- Cancelled is terminal.
- Confirmed invoices are treated as immutable; corrections follow the cancel-only working assumption.
- A cancelled invoice still counts as billed for that subscription period. Clearly warn Staff that cancelling it will not cause the system to generate a replacement invoice for the same period.

### Overdue behavior

An invoice is overdue when today is later than its due date and its status is not Paid. Display the due date and number of days overdue if the application calculates it. Do not mark an invoice due today as overdue under the stated rule.

## 5.10 Billing runs

Audience: Admin and Staff.

### Billing run page

Primary action:
- Run billing now

Before starting, show a concise explanation that the operation processes all due subscriptions and may create invoices.

Show:
- Most recent run
- Run date/time
- Trigger type (scheduled or manual)
- Subscriptions processed
- Invoices created
- Subscriptions skipped
- Failures

### Billing run result detail

Use a result table with:
- Subscription number
- Customer
- Outcome: Created / Skipped / Failed
- Invoice number, if created
- Reason, especially for skipped or failed items

A failure for one subscription must not obscure successful processing of others. Make the result log accessible after completion.

### Duplicate-billing safeguards

- Do not offer a UI action to regenerate an invoice for a period already billed.
- If a subscription is skipped because that period has already been billed, explain the reason.
- If the original invoice was cancelled, explain that the period remains billed and will not be billed again.
- Re-running a billing operation must be safe and must not create duplicate invoices.

## 5.11 Payments

Audience: Admin and Staff.

### Payment list

Recommended columns:
- Payment reference
- Invoice number
- Customer
- Method
- Amount
- Date
- Status, if the payment provider returns one

### Record payment flow

Fields:
- Invoice
- Payment method
- Amount
- Payment date
- Note

Behavior:
- The payment is linked to exactly one invoice.
- The amount must equal the invoice total.
- Partial payments are not allowed.
- On successful payment, invoice status moves to Paid.
- Prevent duplicate payment submission.
- Show a clear validation error if the amount does not equal the invoice total.

### Mock payment gateway

For test/development environments, the mock gateway can simulate:
- Success
- Failure
- Delay

Clearly label simulated outcomes as test-mode behavior. Never make a mock payment look like a real external payment.

## 5.12 Discounts

Audience: Admin only.

### Discount list

Recommended columns:
- Name / identifier
- Type
- Value
- Scope
- Validity dates
- Per-customer usage limit
- Active / expired status

### Discount create / edit

Fields:
- Discount type: fixed amount or percentage
- Value
- Minimum purchase amount and/or minimum quantity
- Start date and end date
- Per-customer usage limit
- Scope: selected products or whole subscription

Show a preview of how the discount applies to an example eligible amount.

### Discount stacking explanation

The current working rule is:
1. Apply fixed-amount discounts first.
2. Apply percentage discounts to the remaining amount.
3. Cap the combined discount at 100% so the total cannot go below zero.

Show applied discounts and their order on the invoice. The redemption count increments when an invoice using the discount is confirmed. A discount stops applying when it expires or its per-customer usage limit is reached.

## 5.13 Taxes and payment terms

Audience: Admin only.

### Taxes

Fields:
- Tax name
- Tax rate

Each product references one tax. The UI should not imply that taxes vary by customer location or region.

### Payment terms

Fields:
- Name
- Due-date rule / number of days

Examples include Immediate, Net 15, and Net 30. Admin manages the available list. Selecting a payment term on a subscription determines invoice due dates.

---

## 6. Customer portal specifications

## 6.1 Portal overview

Show a concise summary:
- Active subscriptions
- Quotations awaiting acceptance
- Outstanding invoices
- Overdue invoices, if any

Only include records belonging to the signed-in customer.

## 6.2 My subscriptions

List each subscription with:
- Subscription number
- Plan
- Start and expiry dates
- Status
- Payment-failed warning, if applicable
- Next billing date, if available

Selecting a subscription opens its detail page.

### Customer subscription detail

Show:
- Plan and subscription lines
- Add-ons
- Quantity
- Billing frequency
- Start and expiry dates
- Renewal mode
- Linked invoices
- Current status and relevant warnings

Display only actions permitted by the plan:
- Pause
- Resume
- Cancel
- Upgrade / downgrade
- Change quantity
- Add / remove add-ons
- Renew, for manual-renewal plans

If an action is unavailable, either omit it or show it disabled with a concise reason. Do not expose internal controls such as billing runs or payment recording.

## 6.3 My quotations

Show quotations awaiting acceptance and their validity dates.

Quotation detail must make the commercial terms easy to review:
- Plan
- Product lines and quantities
- Taxes
- Discounts
- Total
- Valid-until date

Acceptance:
- Present a clear Accept quotation action while valid.
- Ask for confirmation before accepting.
- On success, show the confirmed state and next expected step.
- If expired, disable acceptance and explain why.

## 6.4 My invoices

List the customer's invoices with:
- Invoice number
- Invoice date
- Due date
- Amount
- Status
- Overdue indicator

Customers can open, view, and print their own invoices. They cannot confirm, cancel, email, or record payments through the portal under the current permission matrix.

The requirements do not specify a customer-facing online payment action. Do not add one to the MVP unless the product scope is updated.

## 6.5 Account and security

Provide:
- Account email
- Password reset/change entry point, subject to the authentication implementation
- Sign out

Editing customer profile details is not specified and should not be assumed.

---

## 7. Notifications and system feedback

### 7.1 Email-triggered events

The system sends emails for:
- Password reset
- Invoice delivery
- Payment failure
- Overdue reminders
- Staff alerts

The UI should reflect relevant delivery state when available, especially for invoice delivery and reminder failures.

### 7.2 Dunning

Working assumption:
- First reminder: 1 day past due.
- Second reminder: 7 days past due.
- Third reminder: 14 days past due.
- After the final failure: automatically pause the subscription.

This cadence and final action are open for confirmation. The UI should not hard-code explanatory copy that presents these values as final until confirmed.

### 7.3 Notification and job failures

- Log email delivery failures.
- Retry according to the configured retry policy.
- Show a visible failure state to Admin/Staff where operational follow-up is needed.
- Avoid duplicate customer emails when a scheduled job is safely re-run.

---

## 8. Important user flows

### 8.1 Create and activate a subscription

1. Staff opens Subscriptions and selects Create.
2. Staff selects a customer.
3. Staff selects an available plan.
4. Staff optionally selects a quotation template.
5. The system copies the template's plan and lines.
6. Staff edits lines, quantities, add-ons, dates, and payment terms.
7. Staff reviews the calculated totals.
8. Staff saves a Draft or sends a Quotation.
9. Customer reviews the quotation in the portal.
10. Customer accepts before expiry.
11. Subscription becomes Confirmed.
12. Subscription becomes Active on its start date under the current working assumption.

### 8.2 Scheduled billing

1. Scheduler starts a billing run.
2. System identifies due subscriptions.
3. Paused subscriptions are excluded.
4. System checks whether the subscription period has already been billed.
5. System creates invoices for eligible subscriptions.
6. System applies product taxes, eligible discounts, and proration adjustments.
7. System records Created / Skipped / Failed outcomes.
8. One subscription failure does not stop the rest of the run.
9. Staff/Admin reviews the run log.

### 8.3 Automatic renewal failure

1. Renewal invoice is generated.
2. Payment collection is attempted through the configured provider interface.
3. If collection fails or payment is not received by the due date, set `payment_failed`.
4. Notify the customer by email.
5. Notify Staff.
6. Apply the configured grace-period and retry policy.
7. After the final failure, pause or close according to the configured rule.

The exact retry count and final lifecycle action remain configurable/open until the relevant policy is confirmed.

### 8.4 Manual renewal

1. Customer or Staff opens the subscription.
2. User selects Renew.
3. System validates that manual renewal is enabled and the subscription can be renewed.
4. System creates the renewal flow and invoice as defined by the billing process.
5. User sees the updated status and next step.

The exact manual-renewal sequence beyond the trigger is not fully specified in the requirements and needs product confirmation.

### 8.5 Record a payment

1. Staff opens an outstanding invoice.
2. Staff selects Record payment.
3. System displays the invoice total.
4. Staff enters method, amount, date, and optional note.
5. System validates that the amount equals the invoice total.
6. Staff confirms.
7. On success, invoice status becomes Paid.
8. Payment appears in invoice and payment history.

### 8.6 Pause and resume a subscription

1. User opens an eligible subscription.
2. User selects Pause.
3. UI explains that billing will stop while paused.
4. User confirms.
5. Subscription status becomes Paused.
6. On resume, system recalculates the next billing date.
7. UI displays the updated schedule.

---

## 9. Validation and error-state requirements

| Situation | Expected UI behavior |
|---|---|
| Email already registered | Explain that the email cannot be used for another account without exposing another user's data |
| Password does not meet policy | Show the unmet password rules |
| Reset link expired / already used | Explain and offer a new reset request |
| Plan outside availability dates | Prevent selection and explain the valid date window |
| Lifecycle action disabled by plan | Hide or disable action and explain that the plan does not permit it |
| Quotation expired | Disable acceptance and show expiry date |
| Invoice amount does not equal payment amount | Block submission and show the exact invoice total required |
| Invoice already Paid or Cancelled | Prevent invalid payment or status actions |
| Invoice period already billed | Skip duplicate generation and show the reason |
| Subscription Paused | Explain that it is excluded from billing |
| Discount expired / usage limit reached | Do not apply it; show the reason in Admin-facing pricing details |
| Billing run partially fails | Show successful, skipped, and failed records separately |
| Email delivery fails | Log the failure and show retry / delivery status where available |
| User lacks permission | Do not expose the action; if a direct request is made, show an access-denied page |
| Customer requests another customer's record | Deny access without disclosing whether the record exists |
| Network or server error | Preserve form data where possible and provide a retry path |

---

## 10. Accessibility and responsive behavior

The requirements specify usability but do not define a formal accessibility standard. Use the following baseline:

- All interactive controls must be keyboard accessible.
- Provide visible focus indicators.
- Associate labels and validation messages with form fields.
- Use semantic headings and table headers.
- Do not rely on color alone for status.
- Maintain readable contrast and scalable text.
- Provide accessible names for icon-only controls.
- Dialogs must manage focus and support keyboard dismissal where safe.
- Status and result changes should be announced to assistive technology.
- On mobile, prioritize customer self-service and essential Staff workflows; complex catalog and reporting tables may use responsive layouts.

Formal WCAG conformance level should be confirmed as a project requirement.

---

## 11. Performance and usability requirements

- Every page should respond in under two seconds with thousands of subscriptions, as required by NFR-1.
- Lists should use server-side pagination/filtering where necessary.
- Dashboard aggregates should avoid requiring the browser to download every subscription or invoice.
- Billing runs should process hundreds of subscriptions without blocking the interface.
- Long-running operations should show progress or a clear processing state and allow users to inspect the completed result.
- Prevent repeated submissions while an action is processing.
- Use clear empty states that explain how records are created or why no results match the filters.

---

## 12. Auditability and trust

The requirements require audit logs for status changes, billing actions, payments, and Admin changes.

UX implications:
- Show actor and timestamp for important history events where the data is available.
- Keep a chronological activity history on subscription and invoice detail pages.
- Make billing-run outcomes inspectable.
- Distinguish user-triggered actions from scheduler-triggered actions.
- Do not silently overwrite confirmed invoice information.
- Clearly communicate when a cancellation does not undo the fact that a billing period was processed.

The exact audit-event schema and which roles can view the global audit log require confirmation.

---

## 13. MVP screen inventory

The following screen inventory maps the requirements to a practical implementation sequence.

| Phase | Screens / modules |
|---|---|
| 1. Foundation | Sign in, customer sign-up, forgot/reset password, user management, access-denied state |
| 2. Catalog | Product list/form, variant editor, plan list/form, tax configuration, payment terms, discount list/form, quotation templates |
| 3. Subscriptions | Customer directory/detail, subscription list/create/detail, quotation list/detail, customer quotation acceptance |
| 4. Billing engine | Invoice list/detail, billing-run start/result/history, invoice PDF/print view |
| 5. Payments and portal | Payment list/record payment, mock gateway test states, customer portal overview, subscription management, customer invoice list/detail |
| 6. Reporting | Dashboard, filters, overdue follow-up, failed-renewal overview, reports and CSV export if included |

---

## 14. Open UX/product decisions

The requirements contain unresolved items. The UI should be designed to accommodate them without presenting working assumptions as permanently approved policy.

| ID | Decision needed | Current working assumption | UX impact |
|---|---|---|---|
| A | Discount cap: 100% or 100 currency units? | 100% cap | Discount preview and invoice breakdown |
| B | Tax-inclusive or tax-exclusive prices? | Tax-exclusive; tax added on top | Price previews, forms, invoice totals |
| C | Dunning cadence and final action | Reminders at 1, 7, 14 days; then auto-pause | Reminder timeline and payment-failure messaging |
| D | Single currency and company? | Yes | Currency display and company settings |
| E | Which portal actions are allowed? | Only actions enabled per plan | Action visibility and lifecycle controls |
| F | Discount stacking order | Fixed amount, then percentage | Discount breakdown |
| G | Payment-term options | Admin-managed list | Payment-term selector |
| H | Confirmed → Active trigger | Start date | Subscription status messaging |
| I | Correction of confirmed invoices | Cancel only; period remains billed | Cancellation warning and correction workflow |
| J | Tax/proration rounding | Per line, 2 decimals, half-up | Amount previews and invoice totals |
| K | Proration method and downgrade credit | Daily basis; credit on next invoice | Change preview and adjustment explanation |

Additional UX details to confirm:
- Customer profile fields and whether customers can edit them.
- Whether Staff can view the global audit log.
- Exact manual-renewal flow.
- Whether customers can initiate a renewal payment or only trigger renewal.
- Exact variant-combination and price-adjustment rules.
- Whether quotations and invoices need PDF templates/branding controls.
- Accessibility conformance target.
- Whether the product needs a dedicated support/contact workflow.

---

## 15. UX acceptance checklist

### Access and navigation
- [ ] Public signup always creates a Customer.
- [ ] Only Admin can create Staff accounts.
- [ ] Staff cannot access catalog, tax, discount, plan, template-management, or user-management screens.
- [ ] Customers can access only their own records.
- [ ] Customer portal does not expose internal operations.

### Catalog and plans
- [ ] Admin can create/edit/archive products.
- [ ] Product variants show their price adjustments.
- [ ] Products have an associated tax.
- [ ] Plans expose billing period, minimum quantity, availability, renewal mode, and lifecycle options.
- [ ] Plans outside their availability window cannot be selected for new subscriptions.

### Quotations and subscriptions
- [ ] Staff can create a subscription from a template and edit copied lines.
- [ ] Subscription status is visible on list and detail views.
- [ ] Customers can accept valid quotations.
- [ ] Expired quotations cannot be accepted.
- [ ] Portal actions follow the plan's enabled lifecycle options.
- [ ] Paused subscriptions clearly show that billing is stopped.
- [ ] Resume shows the recalculated next billing date.
- [ ] Add-on and mid-cycle changes show proration information.

### Invoices and payments
- [ ] Invoice details are generated from subscription data without manual retyping.
- [ ] Tax, discounts, and proration are visible in the invoice breakdown.
- [ ] Invoice status and overdue state are clear.
- [ ] Cancelling an invoice warns that its billing period remains billed.
- [ ] Payment recording requires the full invoice amount.
- [ ] Successful payment marks the invoice Paid.
- [ ] Customers can view and print only their own invoices.

### Billing, notifications, and reporting
- [ ] Admin and Staff can run billing manually.
- [ ] Billing results distinguish created, skipped, and failed records.
- [ ] One failed subscription does not hide successful billing results.
- [ ] Re-running a billing job does not create duplicate invoices.
- [ ] Failed renewals are visible to Staff/Admin.
- [ ] Dashboard answers the required subscription, revenue, outstanding, and overdue questions.
- [ ] Dashboard filters work consistently.
- [ ] Email and scheduler failures are logged and surfaced where relevant.

### Quality
- [ ] Loading, empty, success, validation, and error states are designed.
- [ ] Consequential actions require confirmation.
- [ ] Forms preserve entered values after recoverable errors.
- [ ] Status is not communicated by color alone.
- [ ] Keyboard navigation and visible focus states work.
- [ ] Performance target is met for the specified data volume.

---

## 16. Source of truth

This UI/UX specification is derived from **Brightloop Subscription Management System: Requirements Specification v2.0**.

Where the requirements define a behavior, this document translates it into interface behavior. Where the requirements leave a decision open, the relevant assumption is explicitly marked as provisional or the detail is identified for confirmation. This document does not authorize out-of-scope features such as real payment-gateway integration, partial payments, multi-currency support, multi-company operation, or spreadsheet data migration.
