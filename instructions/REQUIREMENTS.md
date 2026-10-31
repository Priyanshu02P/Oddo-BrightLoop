# Brightloop Subscription Management System: Requirements Specification

| | |
|---|---|
| **Document version** | 2.0 |
| **Status** | Draft, pending confirmation of open items |
| **Client** | Brightloop Software |
| **Prepared by** | Solution Architecture |

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Scope](#2-scope)
3. [Users and Roles](#3-users-and-roles)
4. [Role–Permission Matrix](#4-rolepermission-matrix)
5. [Functional Requirements](#5-functional-requirements)
6. [Business Rules](#6-business-rules)
7. [State Machines](#7-state-machines)
8. [Non-Functional Requirements](#8-non-functional-requirements)
9. [Core Domain Entities](#9-core-domain-entities)
10. [Assumptions and Decision Log](#10-assumptions-and-decision-log)
11. [Open Items](#11-open-items)
12. [Suggested Delivery Phases](#12-suggested-delivery-phases)
13. [Glossary](#13-glossary)

---

## 1. Project Overview

### 1.1 Goal
Build one unified platform that runs the full lifecycle of a subscription business:

**Product & plan setup → Quotation → Subscription → Invoicing → Payment collection → Revenue reporting**

### 1.2 Client Background
Brightloop Software sells everything on subscription:
- Business software billed monthly or yearly
- Add-ons that customers switch on and off
- Products that come in variants

Customers range from small shops on monthly plans to large companies on yearly contracts.

### 1.3 Current State and Pain Points

| Area | Today | Problem |
|---|---|---|
| Customer subscriptions | Spreadsheet | No single source of truth |
| Renewals | Remembered by whoever notices first | Renewals get missed |
| Invoices | Typed by hand every month | Wrong or inconsistent invoices |
| Payments | Matched by scrolling bank statements | Slow and error-prone |
| Revenue reports | Built manually each quarter | Nobody knows the true recurring revenue |

### 1.4 Success Criteria
- No renewal is missed; no invoice is created twice or skipped.
- Invoices are generated automatically with no manual typing.
- Staff can see paid vs. outstanding vs. overdue invoices at any moment.
- The finance lead can answer "how many active subscriptions, how much revenue, how much owed, which invoices are overdue" from one screen in seconds, not days.
- Every page responds in under 2 seconds at thousands of subscriptions.

---

## 2. Scope

### 2.1 In Scope
- Authentication, user management, role-based access
- Product catalog with variants, plans, taxes, discounts
- Quotation templates and subscription lifecycle
- Automated invoice generation (billing runs) with tax and discount application
- Proration for mid-cycle changes
- Manual payment recording and a mock payment gateway for testing
- Automatic renewals with failure handling
- Overdue detection and automated reminder emails (dunning)
- Customer self-service portal
- Finance dashboard and reporting
- Scheduler (billing runs, renewals, reminders) and email notifications

### 2.2 Out of Scope
- Data migration from the existing spreadsheet
- Multi-currency and foreign-exchange handling
- Multi-company / multi-tenant operation
- Region-based or customer-based tax logic
- Real payment-gateway integration (mock gateway only for now)
- Partial payments

---

## 3. Users and Roles

| Role | Description |
|---|---|
| **Admin** | Controls the whole system. Sets up products, plans, taxes, discounts, and staff accounts. |
| **Internal Staff** | Small internal team handling customers day to day, with limited access. Cannot manage catalog, taxes, discounts, or users. |
| **Customer** | External user. Uses the portal to see and manage only their own subscriptions and invoices. |

---

## 4. Role–Permission Matrix

| Capability | Admin | Staff | Customer |
|---|:-:|:-:|:-:|
| Create staff accounts | ✅ | ❌ | ❌ |
| Manage products, variants, plans | ✅ | ❌ | ❌ |
| Manage taxes and payment terms | ✅ | ❌ | ❌ |
| Create discount rules | ✅ | ❌ | ❌ |
| Create / manage quotation templates | ✅ | ✅ (use only, see FR-4.1) | ❌ |
| Create / manage subscriptions | ✅ | ✅ | Own only (portal) |
| Accept a quotation | ✅ | ✅ (on behalf, optional) | Own only |
| Run billing / generate invoices | ✅ | ✅ | ❌ |
| Confirm / cancel / send / print invoices | ✅ | ✅ | View / print own |
| Record payments | ✅ | ✅ | ❌ |
| View dashboard and reports | ✅ | ✅ | ❌ |

> Staff scope follows this matrix. Any boundary not listed here is **denied by default**.

---

## 5. Functional Requirements

Priority key: **M** = Must, **S** = Should, **C** = Could.

### M1. Authentication and User Management

| ID | Requirement | Priority |
|---|---|:-:|
| FR-1.1 | A customer can sign up with an email and a password. | M |
| FR-1.2 | Each email can belong to only one account (unique, case-insensitive). | M |
| FR-1.3 | Password policy: more than 8 characters, with at least one uppercase letter, one lowercase letter, and one special character. | M |
| FR-1.4 | Forgot password: a reset link is sent to the registered email. The link is single-use and time-limited. | M |
| FR-1.5 | Role-based access control with three roles (Admin, Staff, Customer) enforced server-side per the matrix in Section 4. | M |
| FR-1.6 | Only an Admin can create Staff accounts. Public signup always creates a Customer. | M |
| FR-1.7 | Customers can only access their own subscriptions, invoices, and payments (data isolation). | M |
| FR-1.8 | Passwords are stored as salted hashes, never in plain text. | M |

### M2. Product Catalog

| ID | Requirement | Priority |
|---|---|:-:|
| FR-2.1 | Admin can create, edit, and archive products with: name, type, sales price, cost price, notes. | M |
| FR-2.2 | A product can have variants (e.g., by brand) with a price adjustment per variant value. Example: choosing the "Odoo" brand adds 560 to the price. | M |
| FR-2.3 | Each product has an associated tax (see M9). | M |
| FR-2.4 | Products can be used as recurring items or add-ons on subscription lines. | M |

### M3. Plans

| ID | Requirement | Priority |
|---|---|:-:|
| FR-3.1 | Admin can create plans with: name, price, billing period (daily, weekly, monthly, yearly), minimum quantity, and availability start/end dates. | M |
| FR-3.2 | Plans support these lifecycle options: auto-close at end date, close early, pause, renew. | M |
| FR-3.3 | Admin decides, plan by plan, which lifecycle options are enabled. | M |
| FR-3.4 | Each plan has `renewal_mode` = `automatic` or `manual`. | M |
| FR-3.5 | A plan is only selectable for new subscriptions within its availability dates. | M |
| FR-3.6 | A plan configured to auto-close is closed by the scheduler when its end date passes. | M |

### M4. Quotation Templates and Subscriptions

| ID | Requirement | Priority |
|---|---|:-:|
| FR-4.1 | Quotation templates hold a predefined plan and product lines, plus a validity period in days. Admin creates and edits templates; staff can use them. | M |
| FR-4.2 | A subscription can be created from a template, with all lines copied over and editable. | M |
| FR-4.3 | Each subscription has: unique number, customer, plan, start date, expiry date, payment terms. | M |
| FR-4.4 | Subscription lines hold: product, quantity, unit price, taxes, amount. | M |
| FR-4.5 | Status workflow: **Draft → Quotation → Confirmed → Active → Closed** (see Section 7). | M |
| FR-4.6 | Every team member can see a subscription's current status. | M |
| FR-4.7 | Customer portal actions: view, accept quote, pause, resume, cancel, upgrade/downgrade, change quantity. Each action is allowed only if the plan's lifecycle options (FR-3.3) permit it. | M |
| FR-4.8 | **Automatic renewal.** The system generates the renewal invoice and attempts collection. If payment is not received by the due date, it (1) flags the subscription `payment_failed`, (2) emails the customer, (3) notifies staff, (4) applies the grace-period rule (retry N times, then pause or close). | M |
| FR-4.9 | **Manual renewal.** The customer or staff triggers the renewal. | M |
| FR-4.10 | **Pause.** A paused subscription is excluded from billing runs. On resume, the next billing date is recalculated. | M |
| FR-4.11 | **Quote acceptance.** The customer accepts the quote in the portal; status moves Quotation → Confirmed. An expired quotation (past validity days) cannot be accepted. | M |
| FR-4.12 | **Add-ons** are subscription lines and can be added or removed during the subscription's life. | M |
| FR-4.13 | **Proration.** Mid-cycle changes to quantity, plan, or add-ons produce a prorated charge or credit on the next invoice. | M |
| FR-4.14 | A subscription moves Confirmed → Active on its start date (or on first payment, see Open Item H). | M |
| FR-4.15 | Subscription numbers are generated sequentially and are never reused. | M |

### M5. Invoicing

| ID | Requirement | Priority |
|---|---|:-:|
| FR-5.1 | Invoices are created automatically from subscriptions, with customer details, product lines, taxes, and totals prefilled. No manual typing. | M |
| FR-5.2 | A bulk billing run processes all due subscriptions at once (hundreds per run). It can be triggered by the scheduler or manually by Admin/Staff. | M |
| FR-5.3 | **No double billing, no skipped billing.** A unique constraint on (subscription, billing period) guarantees one invoice per period. A cancelled invoice still counts as billed for that period; the cycle is skipped and not re-billed. | M |
| FR-5.4 | Tax is calculated automatically from the tax attached to each product. Each invoice line carries its product's tax rate. | M |
| FR-5.5 | Invoice actions: confirm, cancel, send (email), print (PDF). | M |
| FR-5.6 | Status workflow: **Draft → Confirmed → Paid** (see Section 7). Cancelled is a terminal side state. | M |
| FR-5.7 | Each invoice has a due date derived from the subscription's payment terms. | M |
| FR-5.8 | Applicable discounts (M6) and proration adjustments (FR-4.13) are applied automatically to the next invoice. | M |
| FR-5.9 | Each billing run produces a result log (created, skipped, failed, with reasons). Failures in one subscription do not stop the rest of the run. | M |
| FR-5.10 | Confirmed invoices are immutable (corrections via cancel and the rules in Open Item I). | S |

### M6. Discounts

| ID | Requirement | Priority |
|---|---|:-:|
| FR-6.1 | Only Admin can create discount rules. | M |
| FR-6.2 | Discount types: fixed amount or percentage. | M |
| FR-6.3 | Conditions: minimum purchase amount or minimum quantity, start date, end date, and a **per-customer** usage limit. | M |
| FR-6.4 | Scope: specific products or whole subscriptions. | M |
| FR-6.5 | When a discount applies, it appears on the next invoice automatically. | M |
| FR-6.6 | A discount stops applying when it expires or when the customer's usage limit is reached. | M |
| FR-6.7 | Multiple discounts can stack. The combined discount is capped at 100 (see Open Item A). | M |
| FR-6.8 | Redemptions are tracked per customer per discount (counter increments when an invoice using it is confirmed). | M |
| FR-6.9 | Stacking order is fixed amount first, then percentage on the remainder (see Open Item F). | M |

### M7. Payments

| ID | Requirement | Priority |
|---|---|:-:|
| FR-7.1 | Staff can record a payment with: method, amount, date, note. | M |
| FR-7.2 | Every payment is linked to exactly one invoice. | M |
| FR-7.3 | Multiple payment methods and dates are supported. | M |
| FR-7.4 | **No partial payments.** The payment amount must equal the invoice total. A successful payment moves the invoice to Paid. | M |
| FR-7.5 | Staff can view paid vs. outstanding invoices at any time. | M |
| FR-7.6 | **Overdue** = today > due date and invoice status ≠ Paid. Overdue invoices are listed for follow-up. | M |
| FR-7.7 | A `PaymentProvider` interface abstracts payment collection. A **fake/mock gateway** ships for testing and can simulate success, failure, and delay. | M |
| FR-7.8 | **Dunning.** Automatic reminder emails go out for overdue invoices on a defined cadence (see Open Item C). | M |
| FR-7.9 | Recording the same payment twice is prevented (idempotency key or duplicate check). | S |

### M8. Reporting and Dashboard

| ID | Requirement | Priority |
|---|---|:-:|
| FR-8.1 | One dashboard shows active subscriptions, revenue, payments, and overdue invoices. | M |
| FR-8.2 | The dashboard supports filters (date range, customer, plan, status) and a summary view. | M |
| FR-8.3 | It answers: how many subscriptions are active, how much revenue was collected, how much is still owed, which invoices are overdue. | M |
| FR-8.4 | It also shows the count of subscriptions with failed renewals (`payment_failed`). | M |
| FR-8.5 | Recurring-revenue metrics (e.g., MRR) are derived from active subscriptions. | S |
| FR-8.6 | Report lists can be exported (CSV). | C |

### M9. Taxes and Payment Terms (Admin Configuration)

| ID | Requirement | Priority |
|---|---|:-:|
| FR-9.1 | Admin manages a list of taxes (name, rate). | M |
| FR-9.2 | Each product references one tax. No region or customer logic. | M |
| FR-9.3 | Admin manages payment terms (e.g., Immediate, Net 15, Net 30) used to compute invoice due dates. | M |

### M10. Notifications and Scheduler

| ID | Requirement | Priority |
|---|---|:-:|
| FR-10.1 | A scheduler runs: billing runs, renewals, auto-close of plans, quote expiry, and dunning reminders. | M |
| FR-10.2 | Scheduled jobs are idempotent and safe to re-run. | M |
| FR-10.3 | Emails are sent for: password reset, invoice delivery, payment failure, overdue reminders, and staff alerts. | M |
| FR-10.4 | Email delivery failures are logged and retried. | S |

---

## 6. Business Rules

| ID | Rule |
|---|---|
| BR-1 | One account per email address. |
| BR-2 | Only Admin creates Staff; signup creates Customers only. |
| BR-3 | A subscription has exactly one plan and one customer. |
| BR-4 | One invoice per subscription per billing period (enforced by a database constraint). |
| BR-5 | A cancelled invoice's period is considered billed and is not re-billed. |
| BR-6 | A paused subscription is never billed; billing resumes from a recalculated date. |
| BR-7 | Payment amount must equal invoice total. |
| BR-8 | Tax comes only from the product's tax. |
| BR-9 | Total stacked discount never exceeds the cap (default assumption: 100% of the amount, so totals never go below zero). |
| BR-10 | A discount's usage limit is counted per customer. |
| BR-11 | A quotation cannot be accepted after its validity period. |
| BR-12 | Customers can only perform portal actions that the plan's lifecycle options allow. |
| BR-13 | Prices are tax-exclusive; tax is added on top (default assumption, Open Item B). |
| BR-14 | The system uses a single currency and a single company. |

---

## 7. State Machines

### 7.1 Subscription

```
Draft ──► Quotation ──► Confirmed ──► Active ──► Closed
                                        │  ▲
                                        ▼  │
                                      Paused
```

| From | To | Trigger |
|---|---|---|
| Draft | Quotation | Staff/Admin sends the quotation |
| Quotation | Confirmed | Customer accepts in the portal |
| Quotation | Closed | Quotation expires or is declined |
| Confirmed | Active | Start date reached (or first payment, Open Item H) |
| Active | Paused | Customer or staff pauses (if plan allows); also after the grace period if configured |
| Paused | Active | Resume; next billing date recalculated |
| Active / Paused | Closed | Cancel, close early, plan end date (auto-close), or final renewal failure |

Additional flag: `payment_failed` (set by automatic-renewal failure, cleared on payment).

### 7.2 Invoice

```
Draft ──► Confirmed ──► Paid
   │          │
   └──────────┴──► Cancelled
```

| From | To | Trigger |
|---|---|---|
| Draft | Confirmed | Staff/Admin confirms (or auto-confirm in a billing run) |
| Confirmed | Paid | Payment recorded in full |
| Draft / Confirmed | Cancelled | Staff/Admin cancels (period stays billed) |

---

## 8. Non-Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-1 | Performance | Every page responds in under 2 seconds with thousands of subscriptions on the books. |
| NFR-2 | Scalability | A billing run handles hundreds of subscriptions per run without timeouts, using batching or background jobs. |
| NFR-3 | Data integrity | Billing is transactional and idempotent; no duplicate or missed invoices. |
| NFR-4 | Security | Server-side RBAC, hashed passwords, expiring single-use reset tokens, customer data isolation, protection against common web attacks (injection, XSS, CSRF). |
| NFR-5 | Auditability | Status changes, billing actions, payments, and admin changes are logged with user and timestamp. |
| NFR-6 | Usability | Low-friction UI for staff; customers can self-serve without contacting support. |
| NFR-7 | Reliability | Scheduled jobs recover from failure and can be re-run safely. |
| NFR-8 | Testability | The mock payment gateway can deterministically simulate success, failure, and delay. |
| NFR-9 | Maintainability | Payment provider, email provider, and scheduler are behind interfaces so they can be swapped. |
| NFR-10 | Money handling | Monetary values use fixed-precision decimals, never floating point. A consistent rounding rule is defined. |

---

## 9. Core Domain Entities

| Entity | Purpose |
|---|---|
| `User` | Login identity with a role (Admin, Staff, Customer) |
| `Customer` | Customer profile linked to a user |
| `Product` | Sellable item (name, type, sales price, cost price, notes, tax) |
| `ProductVariant` | Variant value with a price adjustment |
| `Tax` | Named tax rate |
| `PaymentTerm` | Due-date rule (e.g., Net 30) |
| `Plan` | Billing period, price, minimum quantity, availability, lifecycle options, renewal mode |
| `QuotationTemplate` | Predefined plan and lines, validity days |
| `Subscription` | Customer's contract (number, plan, dates, status) |
| `SubscriptionLine` | Product, quantity, unit price, tax, amount (includes add-ons) |
| `Discount` | Rule (type, value, conditions, scope, dates) |
| `DiscountRedemption` | Per-customer usage count per discount |
| `Invoice` | Bill for one subscription period |
| `InvoiceLine` | Line with tax and discount detail |
| `Payment` | Method, amount, date, note, linked invoice |
| `BillingRun` | Record of a batch run and its results |
| `Notification` | Email log (reset, invoice, dunning, failure) |
| `AuditLog` | Who changed what and when |

---

## 10. Assumptions and Decision Log

| # | Topic | Decision |
|---|---|---|
| 1 | Staff permissions | Follow the RBAC matrix in Section 4. |
| 2 | Customer self-service | Customers can view and manage their own subscriptions, within plan options. |
| 3 | Pause / renew | Pause stops billing. Auto or manual renewal is set per plan. Auto-renew failures must be handled. |
| 4 | Quote acceptance | Through the customer portal. |
| 5 | Partial payments | Not allowed. |
| 6 | Overdue and dunning | Overdue is based on due date; reminders are sent. |
| 7 | Tax rules | Per product only. |
| 8 | Discount stacking | Allowed, capped at 100, usage limit per customer. |
| 9 | Proration | Required. |
| 10 | Payments | No real gateway; manual recording plus a fake gateway for testing. |
| 11 | Currency / tenancy | Single currency, single company (to be confirmed, Open Item D). |
| 12 | Add-ons | Modeled as subscription lines. |
| 13 | Cancelled invoices | Cycle is skipped, not re-billed. |
| 14 | Data migration | Not needed. |

---

## 11. Open Items

Working assumptions are used in the design until confirmed. Items **A** and **C** affect the data model most.

| ID | Question | Working assumption |
|---|---|---|
| **A** | Does "shouldn't go above 100" mean **100%** or a fixed **100 currency units**? | 100% cap; total never goes below zero. |
| **B** | Are prices tax-inclusive or tax-exclusive? | Exclusive (tax added on top). |
| **C** | Dunning cadence and grace period: how many reminders, how many days apart, and what happens after the last failure? | Reminders at 1, 7, 14 days past due; then auto-pause. |
| **D** | Confirm single currency and single company. | Yes. |
| **E** | Are all customer portal actions allowed, or restricted per plan by Admin? | Only if the plan's lifecycle options enable them. |
| **F** | Discount stacking order. | Fixed first, then percentage on the remainder. |
| **G** | Payment terms list. | Admin-managed list (Immediate, Net 15, Net 30, etc.). |
| **H** | When does Confirmed become Active: on start date or on first payment? | On start date. |
| **I** | How are mistakes on confirmed invoices corrected (credit note, or cancel only)? | Cancel only; the period stays billed (consistent with decision 13). |
| **J** | Rounding rule for tax and proration (per line or per invoice)? | Round per line, 2 decimals, half-up. |
| **K** | Proration method (daily basis vs. period fraction) and whether downgrades issue credits or wait until the next cycle. | Daily basis; credit applied to the next invoice. |

---

## 12. Suggested Delivery Phases

| Phase | Scope |
|---|---|
| 1. Foundation | Auth, RBAC, user management, audit log |
| 2. Catalog | Products, variants, taxes, payment terms, plans, discounts |
| 3. Subscriptions | Templates, subscription lifecycle, quote acceptance |
| 4. Billing engine | Invoice generation, tax and discount application, idempotent billing runs, scheduler |
| 5. Payments and portal | Payment recording, mock gateway, renewal-failure flow, customer portal actions, proration |
| 6. Reporting | Dashboard, filters, dunning emails, performance tuning |

---

## 13. Glossary

| Term | Meaning |
|---|---|
| **Plan** | Pricing and billing-frequency definition a subscription follows. |
| **Subscription** | A customer's recurring contract for products under a plan. |
| **Quotation** | A subscription in the offer stage, awaiting customer acceptance. |
| **Billing run** | A batch job that creates invoices for all due subscriptions. |
| **Proration** | Adjusting a charge or credit for the unused or partial part of a billing period. |
| **Dunning** | Automated reminders for unpaid or overdue invoices. |
| **MRR** | Monthly Recurring Revenue. |
| **RBAC** | Role-Based Access Control. |
| **Idempotent** | Safe to run repeatedly with the same result and no duplicates. |
