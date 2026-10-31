# M6. Discounts

**Document type:** Feature specification and implementation baseline  
**Product:** Brightloop Subscription Management System  
**Module:** M6 — Discounts  
**Requirement coverage:** FR-6.1 through FR-6.9  
**Status:** Derived implementation baseline; unresolved policy details remain open  
**Primary source documents:** `REQUIREMENTS.md`, `UI_UX.md`, `CODING_STANDARDS.md`

---

## 1. Purpose and scope

M6 provides the discount-rule configuration, eligibility evaluation, stacking, application, and redemption-tracking capabilities used by subscription billing.

The module allows an Admin to define fixed-amount and percentage discounts, specify their conditions and scope, and control how many times each customer may use a discount. During invoice generation, the billing workflow evaluates eligible discounts and applies them automatically. The invoice must preserve enough detail to explain which discounts were applied and in what order.

M6 owns discount rules, discount eligibility, stacking calculations, and redemption usage records. M5 remains the owner of invoice generation, invoice lines, invoice totals, invoice confirmation, and billing-run orchestration. M6 supplies discount calculation/application data to M5 through a clear service boundary.

### 1.1 Goals

- Let Admins create and maintain discount rules without developer intervention.
- Support fixed-amount and percentage discount types.
- Evaluate minimum purchase amount, minimum quantity, validity dates, and per-customer usage limits.
- Support discounts scoped to selected products or to a whole subscription.
- Apply eligible discounts automatically to the next invoice.
- Allow multiple eligible discounts to stack in a deterministic order.
- Cap the combined discount at 100% of the eligible amount so the discounted amount does not become negative.
- Track usage per customer and per discount.
- Increment redemption usage only when an invoice using the discount is confirmed.
- Make discount outcomes visible and auditable.

### 1.2 In scope

- Admin-only discount rule creation and editing.
- Discount list and detail views.
- Fixed-amount and percentage discount definitions.
- Minimum purchase amount and minimum quantity conditions.
- Start date and end date eligibility.
- Per-customer usage limits.
- Product-specific and whole-subscription scope.
- Automatic eligibility evaluation during invoice generation.
- Fixed-first, percentage-second stacking.
- Combined discount cap of 100%.
- Per-customer redemption records and confirmation-time usage increments.
- Discount detail in invoice calculations and presentation.
- Validation, permissions, auditability, and automated tests.

### 1.3 Out of scope

Do not add the following unless a separate requirement or product decision authorizes them:

- Customer-created or customer-entered coupon codes.
- Public promotional-code entry or redemption URLs.
- Discount management by Staff or Customers.
- Global usage limits across all customers; the requirement specifies a per-customer limit.
- Referral programs, loyalty points, store credit, gift cards, or rewards wallets.
- Customer segmentation, geography-based eligibility, or marketing campaign automation.
- Arbitrary rule expressions or a user-configurable rule engine.
- Discount stacking priorities configurable by Admin; the source defines fixed-amount-first, then percentage.
- Multi-currency discount conversion.
- Retroactive recalculation of confirmed invoices.
- Refunds or credit notes for discounts already applied to confirmed invoices.
- A customer-facing discount marketplace.

---

## 2. Requirement traceability

All M6 requirements are Must priority in `REQUIREMENTS.md`.

| Requirement | Source requirement | M6 behavior |
|---|---|---|
| FR-6.1 | Only Admin can create discount rules. | Enforce Admin-only create and edit permissions on the server; hide management controls from Staff and Customers. |
| FR-6.2 | Discount types are fixed amount or percentage. | Store an explicit discount type and a validated Decimal value. |
| FR-6.3 | Conditions include minimum purchase amount or minimum quantity, start date, end date, and a per-customer usage limit. | Evaluate all configured eligibility conditions for the relevant customer and invoice context. |
| FR-6.4 | Scope is specific products or whole subscriptions. | Match a rule either to its selected product set or to the whole eligible subscription amount. |
| FR-6.5 | When a discount applies, it appears on the next invoice automatically. | M5 invokes M6 during invoice calculation; no manual re-entry is required. |
| FR-6.6 | A discount stops applying when it expires or the customer's usage limit is reached. | Exclude expired and exhausted rules from eligibility evaluation. |
| FR-6.7 | Multiple discounts can stack; combined discount is capped at 100 (see Open Item A). | Apply eligible discounts in the defined order and cap the aggregate reduction at 100% of the eligible amount, following the documented working assumption. |
| FR-6.8 | Redemptions are tracked per customer per discount; counter increments when an invoice using it is confirmed. | Persist usage by `(discount, customer)` and increment exactly once on successful invoice confirmation. |
| FR-6.9 | Stacking order is fixed amount first, then percentage on the remainder (see Open Item F). | Sort fixed discounts before percentage discounts; calculate each percentage against the remaining eligible amount. |

### 2.1 Related requirements and business rules

- BR-9: Total stacked discount never exceeds the cap; the working assumption is 100% of the amount, so totals never go below zero.
- BR-10: A discount's usage limit is counted per customer.
- FR-5.8: Applicable discounts are applied automatically to the next invoice.
- FR-5.10: Confirmed invoices are immutable; correction follows the invoice cancellation policy.
- FR-5.9: A discount that is expired, exhausted, or ineligible is skipped with a log entry and must not block invoice generation.
- Open Item A: “100” may mean 100% or 100 currency units; the working assumption is 100%.
- Open Item F: The working stacking order is fixed amount first, then percentage on the remainder.
- Open Item J: The working rounding rule is per line, two decimal places, half-up.

---

## 3. Roles and permissions

### 3.1 Admin

Admin is the only role authorized to create or edit discount rules.

Admin can:

- Open the Discounts section.
- View the discount list and details.
- Create a discount rule.
- Edit a discount rule.
- Configure type, value, conditions, validity dates, usage limit, and scope.
- Review discount redemption usage.
- Inspect validation errors and eligibility/application outcomes available through invoice or audit records.

The source explicitly grants Admin discount-rule creation. Editing is shown in the UI/UX create/edit specification and is treated as part of Admin management. Delete, archive, and deactivate behavior is not specified and remains an open decision.

### 3.2 Internal Staff

Staff cannot create, edit, or manage discount rules.

Staff may encounter discount results through permitted operational workflows, such as:

- Viewing invoice discount lines and totals.
- Reviewing why a discount was or was not applied, if the application exposes that explanation.
- Running billing through M5 without changing discount configuration.

The Staff role must not receive a working discount-management endpoint merely because a control is hidden in the UI.

### 3.3 Customer

Customers cannot manage discount rules or directly alter discount eligibility.

Customers may see discounts reflected in their own quotations or invoices where those records include them. Customers must only see their own commercial records.

### 3.4 Server-side authorization

- Enforce permissions in the view/service boundary, not only in templates.
- Default-deny all unlisted discount-management actions.
- Do not trust a submitted role, customer ID, discount ID, usage count, discount amount, or scope from the browser.
- Resolve the acting user and customer identity from the authenticated server-side context.
- Scope customer-visible invoice/quotation information through ownership-aware selectors.

---

## 4. Domain model

The following is a proposed logical model. Field names are illustrative and should be aligned with existing repository conventions before implementation.

### 4.1 Discount

Represents an Admin-configured discount rule.

| Field | Suggested type | Purpose |
|---|---|---|
| `id` | UUID / project-standard primary key | Stable identifier. |
| `name` | CharField | Human-readable rule name or identifier. |
| `discount_type` | TextChoices | `FIXED_AMOUNT` or `PERCENTAGE`. |
| `value` | DecimalField | Fixed monetary amount or percentage value. |
| `minimum_purchase_amount` | Nullable DecimalField | Minimum qualifying purchase amount, if configured. |
| `minimum_quantity` | Nullable positive integer / DecimalField | Minimum qualifying quantity, if configured. |
| `start_date` | DateField | First eligible date, subject to boundary decision. |
| `end_date` | DateField | Last eligible date, subject to boundary decision. |
| `usage_limit_per_customer` | Positive integer | Maximum confirmed uses by one customer. |
| `scope_type` | TextChoices | `SELECTED_PRODUCTS` or `WHOLE_SUBSCRIPTION`. |
| `is_active` | BooleanField, if approved | Operational enable/disable flag; not explicitly specified. |
| `created_at` | DateTimeField | Creation timestamp. |
| `updated_at` | DateTimeField | Last update timestamp. |
| `created_by` | ForeignKey to User | Admin actor responsible for creation. |
| `updated_by` | Nullable ForeignKey to User | Admin actor responsible for last edit. |

#### Validation expectations

- `discount_type` must be one of the two supported values.
- `value` must be positive.
- Percentage values must not exceed 100 unless a product decision explicitly allows a different stored value; the effective combined discount remains capped at 100%.
- Fixed-amount values must use the configured system currency and Decimal arithmetic.
- `usage_limit_per_customer` must be a positive integer unless unlimited usage is explicitly approved as a separate representation.
- `end_date` must not precede `start_date`.
- At least one eligibility condition may be configured, but whether either minimum is mandatory is not specified.
- Whole-subscription scope must not require selected product rows.
- Selected-product scope must reference at least one valid product.
- The meaning of omitted minimum conditions must be consistent: an omitted condition is not evaluated as a zero-value restriction.

### 4.2 DiscountProduct

A many-to-many through model linking a discount to products when the scope is selected products.

Suggested fields:

| Field | Purpose |
|---|---|
| `discount` | Discount rule. |
| `product` | Product included in the rule's scope. |
| `created_at` | Link creation timestamp, if required by project conventions. |

Add a uniqueness constraint on `(discount, product)`.

A rule scoped to selected products applies only to qualifying invoice/subscription lines for those products. It must not silently discount unrelated products.

### 4.3 DiscountRedemption

Tracks confirmed usage per customer and discount.

| Field | Suggested type | Purpose |
|---|---|---|
| `id` | UUID / project-standard primary key | Stable identifier. |
| `discount` | ForeignKey to Discount | Rule being redeemed. |
| `customer` | ForeignKey to Customer/User profile | Customer whose usage is counted. |
| `usage_count` | Positive integer | Number of confirmed invoice uses. |
| `created_at` | DateTimeField | First record creation. |
| `updated_at` | DateTimeField | Last count update. |

Add a database uniqueness constraint on `(discount, customer)`.

The record is created when the first confirmed redemption occurs, or when a reservation mechanism is separately approved. The source specifies a counter increment on invoice confirmation; it does not specify a reservation at draft generation time.

### 4.4 Invoice discount snapshot

M5 owns invoices. The invoice must retain the discount details used for its financial calculation.

A proposed invoice discount snapshot may contain:

- Discount rule reference, where retaining the relationship is appropriate.
- Discount name at calculation/confirmation time.
- Discount type and configured value at the time of application.
- Scope or affected product/line references.
- Amount reduced.
- Application order.
- Customer and invoice context.
- Whether the invoice has confirmed the redemption.

The confirmed invoice must remain historically explainable even if the Admin later edits the source Discount rule. Do not recompute historical invoice totals using current rule values.

Whether snapshot rows are stored as a dedicated invoice-discount model or embedded in an existing invoice-line representation is an implementation decision for M5/M6 coordination. The persisted financial snapshot must be durable either way.

### 4.5 Relationships

```text
Discount 1 ─── * DiscountProduct * ─── 1 Product
Discount 1 ─── * DiscountRedemption * ─── 1 Customer
Discount 1 ─── * InvoiceDiscountSnapshot
Customer 1 ─── * Invoice
Invoice 1 ─── * InvoiceLine
```

`InvoiceDiscountSnapshot` is a proposed logical entity; exact ownership and table design should follow the existing billing app structure.

---

## 5. Discount lifecycle and eligibility

### 5.1 Rule lifecycle

The requirements define validity dates and usage exhaustion, but do not define a complete rule status state machine.

At minimum, eligibility must consider:

1. Whether the rule is available for use (including any approved active/archived state).
2. Whether the invoice's relevant date falls within the rule's validity window.
3. Whether the customer has reached the per-customer usage limit.
4. Whether the purchase amount meets the configured minimum, if present.
5. Whether the qualifying quantity meets the configured minimum, if present.
6. Whether the rule's scope matches the subscription or invoice lines.
7. Whether the rule has a valid type/value configuration.

A rule that is expired, exhausted, or otherwise ineligible is skipped. It must not cause the entire invoice generation to fail.

### 5.2 Date eligibility

- `start_date` and `end_date` define the discount's eligibility window.
- The exact inclusivity of the start and end dates is not explicitly stated in the source documents.
- A consistent date basis and timezone must be selected before implementation.
- Do not silently interpret a date-only end value as an arbitrary UTC timestamp.
- Record the selected boundary semantics in implementation notes after product confirmation.

### 5.3 Minimum purchase amount

When `minimum_purchase_amount` is configured, compare it against the qualifying purchase amount for the discount's scope.

The source does not explicitly define whether the qualifying amount is measured before tax, after tax, before other discounts, or after earlier stacked discounts. The calculation base must be confirmed and used consistently.

Do not use binary floating-point arithmetic.

### 5.4 Minimum quantity

When `minimum_quantity` is configured, compare it against the qualifying quantity for the discount's scope.

For selected-product scope, the likely candidate is the combined quantity of matching product lines. For whole-subscription scope, the likely candidate is the subscription's qualifying total quantity. These interpretations should be confirmed where product lines can have different units or fractional quantities.

Do not count unrelated products toward a selected-product rule.

### 5.5 Per-customer usage limit

- Usage is counted separately for each customer and each discount.
- A customer's usage of one discount must not reduce their limit for a different discount.
- Another customer's redemption must not affect the current customer's limit.
- A rule stops applying to a customer once that customer's confirmed usage count reaches the configured limit.
- Draft invoice generation must not increment the confirmed redemption count.
- Confirmation must increment the count once for each applied discount redemption.
- Repeated confirmation requests or concurrent confirmation attempts must not increment usage more than once for the same invoice/discount/customer combination.

The requirements do not state whether a cancelled invoice restores usage. Treat this as an open decision; do not silently decrement the counter.

### 5.6 Discount scope

**Selected products**

- Admin selects one or more products for the rule.
- Only matching product lines are eligible for the discount.
- The discount must not leak onto unrelated lines.
- The calculation must retain a clear mapping between the discount amount and affected invoice lines.

**Whole subscription**

- The rule applies to the qualifying subscription amount as defined by the confirmed calculation policy.
- The scope must be evaluated against the subscription represented by the invoice.
- Do not apply the same rule twice by treating it as both a whole-subscription discount and a product-level discount.

### 5.7 Multiple eligibility conditions

The source lists minimum purchase amount or minimum quantity, dates, and a per-customer usage limit. It does not explicitly state whether both minimum conditions may be configured together and must both pass, or whether the Admin must choose one.

Until confirmed:

- Keep the model capable of representing both fields.
- Treat each configured minimum as a condition that must pass.
- Do not require either minimum to be populated unless product confirms that requirement.
- Document the exact AND/OR policy before release.

---

## 6. Calculation and stacking rules

### 6.1 Required stacking order

FR-6.9 defines the order:

1. Apply all eligible fixed-amount discounts first.
2. Apply eligible percentage discounts to the remaining amount.

Within each type, the source does not specify a secondary ordering rule. Use a deterministic order, such as stable rule ID or creation order, only after the product team confirms it. Do not allow database row order to determine financial results accidentally.

### 6.2 Calculation sequence

A conceptual calculation for one eligible amount:

1. Determine the eligible invoice amount for the rule's scope.
2. Evaluate all configured eligibility conditions.
3. Collect eligible fixed-amount discounts.
4. Apply fixed discounts in a deterministic order.
5. Do not allow the remaining eligible amount to fall below zero.
6. Collect eligible percentage discounts.
7. Apply each percentage to the remaining amount after earlier discounts.
8. Cap the total discount at 100% of the eligible amount.
9. Apply the project's approved monetary rounding helper.
10. Return an itemized result for M5 to persist on the invoice.

### 6.3 Fixed-amount discounts

For a fixed discount:

- The configured value represents a monetary amount.
- The applied amount must not exceed the remaining eligible amount.
- If the remaining amount is smaller than the configured fixed amount, apply only the remaining amount under the 100% cap working assumption.
- A fixed discount must not create a negative line or invoice total.
- Allocation across multiple matching lines requires a defined allocation policy; the source does not specify whether to apply to the first line, proportionally, or through another deterministic method.

### 6.4 Percentage discounts

For a percentage discount:

- The configured value represents a percentage.
- Calculate it against the remaining eligible amount after fixed discounts and any earlier percentage discounts.
- Use Decimal arithmetic.
- The total discount must remain within the 100% cap.
- Do not calculate every percentage against the original pre-discount amount; FR-6.9 explicitly says percentage discounts apply to the remainder.

### 6.5 Combined discount cap

The working assumption for Open Item A is a 100% cap of the eligible amount, so the discounted amount cannot become negative.

For a given eligible base:

```text
total_discount <= eligible_amount
remaining_amount = eligible_amount - total_discount
remaining_amount >= 0
```

This assumption must be revisited if product confirms that “100” meant a fixed currency amount rather than 100%.

### 6.6 Example: fixed followed by percentage

Illustrative example only:

- Eligible amount: 1,000.00
- Fixed discount: 100.00
- Percentage discount: 10%

Calculation:

```text
Starting amount                 1,000.00
After fixed discount              900.00
10% of remaining amount            90.00
Final discount                    190.00
Remaining amount                  810.00
```

The percentage is calculated on 900.00, not the original 1,000.00.

### 6.7 Example: cap prevents negative total

Illustrative example only:

- Eligible amount: 500.00
- Fixed discount: 400.00
- Percentage discount: 50%

Calculation:

```text
Starting amount                   500.00
After fixed discount              100.00
50% of remaining amount             50.00
Total discount                    450.00
Remaining amount                   50.00
```

If the fixed discount alone exceeds the eligible amount, the applied fixed discount is capped at 500.00 and no remaining amount exists for later percentage discounts.

### 6.8 Tax interaction

M5's requirements state that product tax is calculated from the tax attached to each product and that invoice prices are tax-exclusive under the current working assumption.

M6 must not invent a separate tax policy. The exact order of discount allocation and tax calculation must be consistent with the invoice calculation contract and confirmed with M5. The invoice must display tax and discount detail without double-counting a discount or applying it twice.

### 6.9 Rounding

- Use `DecimalField` and Python `Decimal`.
- Never use `float` for money or percentage calculations.
- Use the shared `money.round()` helper specified by `CODING_STANDARDS.md`.
- The current working assumption in Open Item J is per-line rounding to two decimal places using half-up.
- Ensure that the sum of displayed line discounts reconciles with the invoice-level discount total.
- Test edge cases where rounding a percentage across multiple lines could differ from rounding once at invoice level.

### 6.10 Calculation result contract

M6 should return structured calculation data to M5, rather than writing invoice records directly.

Suggested result information:

- Eligible discount identifiers.
- Rejected/skipped discount identifiers and safe reason codes.
- Applied discount type and configured value snapshot.
- Application sequence.
- Affected product/line scope.
- Amount applied per affected line or eligible base.
- Total applied discount.
- Remaining eligible amount.
- Any rounding/allocation metadata required to reproduce the result.

The exact Python return type is implementation-specific. Keep it explicit, typed where practical, and covered by tests.

---

## 7. Redemption confirmation and concurrency

### 7.1 Confirmation-time increment

FR-6.8 requires the redemption counter to increment when an invoice using the discount is confirmed.

The intended sequence is:

1. M5 prepares a draft invoice and its discount snapshots.
2. The invoice is confirmed through the M5 invoice service.
3. The confirmation transaction identifies the discounts actually applied to the invoice.
4. For each applied discount, M6 increments the `(discount, customer)` usage record.
5. The invoice confirmation and redemption increments commit atomically where they share the database transaction.
6. If confirmation fails, the usage increment must not be committed.

### 7.2 Exactly-once behavior

The counter must not increment more than once for the same invoice/discount/customer redemption.

Use a database-backed idempotency design. A proposed implementation is a unique redemption-use record keyed by invoice and discount, alongside the aggregate `DiscountRedemption` counter. If a separate use record is not introduced, the invoice snapshot must still provide a reliable uniqueness boundary.

Do not rely only on a pre-check in application code.

### 7.3 Concurrent confirmations

Two requests may attempt to confirm the same invoice, or different invoices may attempt to consume the final available use for the same customer and discount.

Use:

- `transaction.atomic()` for the confirmation and usage update.
- `select_for_update()` on the relevant invoice and redemption row where appropriate.
- Database uniqueness constraints for per-invoice redemption identity.
- A fresh usage-limit check while holding the relevant lock.
- A clear domain exception or conflict outcome if the limit has been consumed before confirmation.

If a draft invoice contains a discount that becomes exhausted before confirmation, the source does not define whether confirmation should fail, remove the discount and recalculate, or permit an already-generated draft to use it. This must be resolved before implementation.

### 7.4 Cancelled invoices

The source explicitly says the redemption count increments when an invoice using a discount is confirmed. It does not say whether later cancellation restores the customer's usage.

Do not automatically decrement usage on cancellation without product approval. Record the policy as an open decision.

### 7.5 Rule edits after use

The source does not specify whether an Admin may edit a discount after it has been used, whether edits apply to existing drafts, or whether historical redemption records retain a snapshot of the rule.

Confirmed invoice snapshots must remain unchanged. The edit policy for active rules and draft invoices remains open.

---

## 8. UI/UX behavior

### 8.1 Navigation and audience

- Discounts appears in the internal application navigation.
- The section is visible to Admin only.
- Staff and Customers must not see discount-management navigation or controls.
- The customer portal does not expose discount configuration.

### 8.2 Discount list

Recommended columns from `UI_UX.md`:

| Column | Description |
|---|---|
| Name / identifier | Human-readable rule name. |
| Type | Fixed amount or percentage. |
| Value | Configured amount or percentage. |
| Scope | Selected products or whole subscription. |
| Validity dates | Start and end dates. |
| Per-customer usage limit | Maximum confirmed uses per customer. |
| Active / expired status | Eligibility-oriented status display. |

The source recommends an Active/Expired status but does not define whether this is a stored status or derived from dates and other rule state. Prefer a derived display unless a separate activation field is approved.

List behavior:

- Paginate results.
- Provide a clear empty state when no discounts exist.
- Display type and value unambiguously (for example, currency amount versus percentage).
- Show validity dates in the agreed timezone/date format.
- Do not expose unnecessary internal identifiers as the primary label.
- Provide an Admin-only Create discount action.
- Edit behavior must follow the approved rule-edit policy.

### 8.3 Discount create/edit form

Fields specified in `UI_UX.md`:

| Field | UI behavior |
|---|---|
| Discount type | Required selector: Fixed amount or Percentage. |
| Value | Required numeric/decimal input with type-aware label and validation. |
| Minimum purchase amount | Optional amount condition, if allowed by the final condition policy. |
| Minimum quantity | Optional quantity condition, if allowed by the final condition policy. |
| Start date | Required or optional according to the confirmed date policy. |
| End date | Required or optional according to the confirmed date policy. |
| Per-customer usage limit | Required positive integer under the stated requirement. |
| Scope | Required selector: Selected products or Whole subscription. |
| Products | Show product selector only for Selected products scope. |

Form behavior:

- Changing scope to Whole subscription hides or clears selected-product values.
- Changing scope to Selected products requires at least one product.
- Show field-level validation messages.
- Preserve valid entered values after a validation error.
- Prevent duplicate submissions while a save is in progress.
- Confirm consequential edits if they may affect active drafts or future invoices, once the edit policy is approved.
- Do not imply that Staff can save the form.

### 8.4 Discount preview

The UI/UX source requires a preview of how the discount applies to an example eligible amount.

Preview should show:

- Example eligible amount.
- Selected discount type and value.
- Amount reduced.
- Remaining amount.
- For stacked previews, fixed discounts first and percentages against the remainder.
- The 100% cap behavior.

The preview is illustrative and must not create a redemption or alter customer usage. Clearly label sample values as an example, not a quote or invoice.

### 8.5 Invoice presentation

When M5 applies discounts:

- Show applicable discounts in the invoice breakdown.
- Show the discount name or snapshot label, type/value where appropriate, and applied amount.
- Preserve the fixed-first / percentage-second order.
- Show the subtotal, tax, discount, proration, and final total in a way that reconciles with M5's invoice calculation contract.
- Do not expose internal rule-management controls to Customers.
- Customer invoice views show only the customer's own invoice.

### 8.6 Feedback and error states

| Scenario | Expected UI feedback |
|---|---|
| Discount saved | Confirm success and show the saved rule. |
| Invalid percentage | Explain the accepted range after it is confirmed; do not silently clamp user input. |
| Invalid fixed amount | Explain that the value must be a valid positive amount. |
| End date before start date | Show a field-level date-range error. |
| Selected-product scope has no products | Require at least one product. |
| Discount expired | Show an expired/ineligible state; do not apply it. |
| Customer usage limit reached | Skip the discount and show a safe reason in internal billing detail if supported. |
| Minimum amount/quantity not met | Skip the discount; do not block invoice generation. |
| Discount calculation fails | Record a safe failure; do not silently produce a potentially incorrect invoice. |
| Concurrent usage-limit conflict | Re-evaluate or report a clear business conflict; never overrun the limit silently. |
| Unauthorized Staff/Customer request | Reject server-side and do not reveal protected management data. |

---

## 9. Business logic and service boundaries

### 9.1 Suggested services

Names are illustrative; follow existing app conventions.

- `create_discount(data, actor)`
- `update_discount(discount, data, actor)`
- `get_eligible_discounts(customer, subscription, invoice_context, as_of)`
- `evaluate_discount_eligibility(discount, customer, invoice_context, as_of)`
- `apply_stacked_discounts(eligible_amounts, eligible_discounts)`
- `record_confirmed_redemptions(invoice, actor_or_system)`
- `get_customer_discount_usage(discount, customer)`

Avoid thin wrappers that add no policy. Keep business writes in services and complex reads in selectors.

### 9.2 Suggested app organization

The coding standards explicitly include `apps/discounts/` for discount rules, redemptions, and the stacking engine.

```text
apps/
  discounts/
    models.py          # Discount, DiscountProduct, DiscountRedemption
    services.py        # create/update, eligibility, stacking, redemption writes
    selectors.py       # list/detail and eligibility/usage reads
    forms.py           # Admin discount forms
    views.py           # thin Admin request handlers
    permissions.py     # Admin-only rule management
    exceptions.py      # invalid rule / eligibility / redemption conflicts
    admin.py
    urls.py
    tests/
      test_models.py
      test_rule_validation.py
      test_permissions.py
      test_eligibility.py
      test_scope.py
      test_stacking.py
      test_redemptions.py
      test_concurrency.py
```

Adapt this tree to the repository's actual app structure. Do not create duplicate modules if equivalent boundaries already exist.

### 9.3 Dependency direction

- Views call services.
- Services own write-side business logic.
- Selectors own complex read/query logic.
- Models hold fields, constraints, and simple properties.
- M6 may depend on Accounts, Catalog, Subscriptions, and the invoice integration contract.
- M5 calls M6's discount service at invoice-calculation/confirmation boundaries.
- Avoid circular imports. In particular, do not make Catalog import from Discounts or Billing.

### 9.4 M5 integration contract

M5 owns invoice generation. M6 must provide a stable calculation and redemption interface.

At invoice-generation time:

1. M5 supplies the customer, subscription, billing-period context, candidate invoice lines, qualifying quantities/amounts, and calculation date.
2. M6 evaluates eligible rules.
3. M6 returns ordered discount results and skipped-rule reasons.
4. M5 persists the invoice financial snapshot and renders the discount breakdown.
5. Invoice generation remains idempotent under M5's `(subscription, billing_period)` uniqueness rule.

At invoice-confirmation time:

1. M5 invokes M6 redemption confirmation as part of the invoice confirmation service.
2. M6 increments usage exactly once for each applied discount.
3. M5 and M6 use a shared transaction boundary where possible.
4. If the discount usage limit is no longer valid at confirmation, apply the product-approved conflict policy; do not invent a silent fallback.

M6 must not create invoices, change invoice status independently, or duplicate M5's billing-run orchestration.

### 9.5 M4 integration

M4 provides subscription and subscription-line context, including products and quantities. M6 uses that context for scope and minimum-condition evaluation. M4 must not duplicate discount rule CRUD or stacking calculations.

### 9.6 M2 integration

M2 owns products and variants. M6 references Products for selected-product scope and must validate that selected products exist and are eligible for use under the catalog's rules. M6 does not create or edit products.

### 9.7 Transaction and database integrity

Use PostgreSQL constraints and transactions for:

- Unique `(discount, customer)` redemption aggregate.
- Unique `(discount, product)` scope links.
- Unique invoice/discount redemption identity if a redemption-use table is implemented.
- Positive discount value and usage limit constraints where expressible.
- Atomic rule updates where multiple related rows are changed.
- Atomic redemption updates and invoice confirmation.

A pre-check in application code is not a replacement for a database constraint.

---

## 10. Security, auditability, and operational behavior

### 10.1 Authorization

- Admin-only discount create/edit operations.
- Server-side permission checks on every management endpoint.
- Default-deny for Staff and Customer discount-management requests.
- Customer identity is derived from the authenticated account, not submitted form data.
- Customer-facing invoice and quotation discount detail is ownership-scoped.

### 10.2 Input validation

Validate all fields server-side:

- Type enum.
- Positive Decimal value.
- Percentage range according to the confirmed policy.
- Date ordering and boundary semantics.
- Positive per-customer usage limit.
- Minimum purchase amount.
- Minimum quantity.
- Scope enum.
- Product existence and selection.
- Consistency between scope and product links.

Client-side validation is a usability aid only.

### 10.3 Audit events

The system's general requirements include an AuditLog entity and coding standards require audit entries for important state changes. Record at least:

- Discount created.
- Discount edited.
- Discount activation/archive/deactivation, if implemented.
- Discount redemption confirmed.
- Any approved redemption reversal or correction.

Audit records should identify the actor, affected rule/customer/invoice IDs, timestamp, and relevant before/after values. Do not log secrets or unnecessary personal data.

Whether every automated redemption event is represented in the general AuditLog or only in the dedicated redemption record is an implementation detail; the operation must remain traceable.

### 10.4 Logging

Use Python's `logging` module.

Useful context includes:

- Discount ID.
- Customer ID.
- Subscription ID.
- Invoice ID.
- Reason code for a skipped or failed rule.

Do not log full payment details, secrets, or unnecessary customer personal data. Do not use `print()`.

### 10.5 Error handling

Use narrow exception handling and domain-specific errors such as:

- `InvalidDiscountRule`
- `DiscountNotApplicable`
- `DiscountUsageLimitReached`
- `DiscountScopeMismatch`
- `DiscountRedemptionConflict`

Expected ineligibility is not an exceptional invoice-generation failure. Expired, exhausted, or ineligible discounts should be skipped and logged as required by the coding standards. Unexpected calculation or persistence failures must be surfaced safely and must not create incorrect financial records.

---

## 11. Data integrity and performance

- PostgreSQL is the source of truth.
- Use Decimal fields for monetary values and percentages.
- Add indexes based on real query patterns, such as active/validity dates and redemption lookup by `(discount, customer)`.
- Use `select_related` and `prefetch_related` to avoid N+1 queries.
- Paginate the discount list and redemption history.
- Evaluate a bounded set of candidate discounts rather than loading every rule and every redemption into memory.
- Use database aggregation or focused selectors for usage counts.
- Do not use process-local caches as the authority for usage limits.
- Lock the relevant redemption record during the final usage-limit check and increment.
- Keep calculations deterministic so the same inputs produce the same discount result.
- Do not recompute confirmed invoice amounts from current discount rules.

The system-wide performance target is that every page responds in under two seconds at thousands of subscriptions. Validate discount queries as part of the broader billing performance tests; do not claim this target is met without measurement.

---

## 12. Acceptance criteria

M6 is acceptable when all applicable criteria below pass.

### Rule management

- [ ] Only Admin can create discount rules.
- [ ] Staff and Customers cannot create or edit discount rules through UI or direct requests.
- [ ] Admin can configure fixed-amount and percentage discounts.
- [ ] Invalid values, dates, usage limits, and scope selections are rejected server-side.
- [ ] Selected-product scope requires valid selected products.
- [ ] Whole-subscription scope does not accidentally retain or apply selected-product restrictions.

### Eligibility

- [ ] Start and end dates are evaluated using the approved boundary and timezone policy.
- [ ] Minimum purchase amount is evaluated against the approved calculation base.
- [ ] Minimum quantity is evaluated against the correct scope.
- [ ] Usage is counted per customer per discount.
- [ ] A discount is not applied after expiry.
- [ ] A discount is not applied after the customer's usage limit is reached.
- [ ] Selected-product discounts affect only matching products.
- [ ] Whole-subscription discounts use the approved subscription-level base.

### Stacking and calculation

- [ ] Multiple eligible discounts can stack.
- [ ] Fixed-amount discounts are applied before percentage discounts.
- [ ] Each percentage discount is calculated on the remaining amount.
- [ ] The combined discount never exceeds the eligible amount under the 100% working assumption.
- [ ] The discounted amount never becomes negative.
- [ ] Decimal arithmetic and the shared rounding helper are used.
- [ ] Applied discount detail reconciles with invoice totals.

### Invoice and redemption integration

- [ ] M5 automatically receives eligible discount results during invoice generation.
- [ ] Invoice discount details are visible in the invoice breakdown.
- [ ] Draft invoice generation does not increment confirmed usage.
- [ ] Invoice confirmation increments each applied discount redemption exactly once.
- [ ] Repeated confirmation attempts do not double-increment usage.
- [ ] Concurrent confirmations cannot exceed a customer's usage limit.
- [ ] Confirmed invoice snapshots remain unchanged after a discount rule is edited.
- [ ] Expired, exhausted, and ineligible discounts are skipped without blocking unrelated invoice generation.

### Quality and operations

- [ ] All migrations are present and no applied migration was edited.
- [ ] Unit, integration, permission, and concurrency tests cover the acceptance criteria.
- [ ] No secrets or unnecessary personal data are written to logs.
- [ ] No unused imports, debug prints, placeholder functions, or dead code remain.
- [ ] No unapproved dependencies or out-of-scope discount features are introduced.
- [ ] Open decisions are documented and resolved or explicitly accepted before release.

---

## 13. Test plan

Use `pytest` and `pytest-django` in line with `CODING_STANDARDS.md`. Use factories for users, customers, products, subscriptions, discounts, invoices, and redemption records. Tests must not call real external services. Money assertions must use `Decimal`, never float.

### 13.1 Model and validation tests

- Create a fixed-amount discount with a valid value.
- Create a percentage discount with a valid value.
- Reject unsupported discount types.
- Reject zero and negative values.
- Reject invalid percentage values according to the approved range.
- Reject an end date before the start date.
- Reject a zero or negative per-customer usage limit.
- Reject selected-product scope with no products.
- Reject references to nonexistent products.
- Enforce unique `(discount, product)`.
- Enforce unique `(discount, customer)` redemption aggregate.

### 13.2 Permission tests

- Admin can access the discount list and detail.
- Admin can create a discount.
- Admin can edit a discount, subject to the approved edit policy.
- Staff receives a forbidden response for create/edit endpoints.
- Customer receives a forbidden response for create/edit endpoints.
- Anonymous users cannot access management endpoints.
- Hiding a button does not replace server-side authorization.

### 13.3 Eligibility tests

- Discount is eligible on a valid date under the selected date-boundary policy.
- Discount is rejected before its start date.
- Discount is rejected after its end date.
- Minimum purchase amount passes at the threshold.
- Minimum purchase amount fails below the threshold.
- Minimum quantity passes at the threshold.
- Minimum quantity fails below the threshold.
- Both configured minimum conditions follow the approved AND/OR policy.
- Customer A's usage does not affect Customer B.
- Usage of Discount A does not affect Discount B.
- Discount is skipped when the customer's limit is reached.
- Selected-product scope matches only selected products.
- Whole-subscription scope uses the approved subscription base.
- Ineligible discounts do not block invoice generation.

### 13.4 Calculation and stacking tests

- Fixed amount is applied before percentage.
- Percentage is calculated on the remaining amount.
- Multiple fixed discounts follow the approved deterministic tie-break order.
- Multiple percentage discounts follow the approved deterministic tie-break order.
- Fixed discount larger than eligible amount is capped.
- Stacked discounts cannot make the eligible amount negative.
- Combined discount reaches but does not exceed the 100% cap.
- Decimal rounding follows the shared helper.
- Per-line and aggregate totals reconcile.
- Product-scoped allocation does not affect unrelated lines.
- Tax interaction matches the approved M5 calculation contract.
- Zero eligible amount produces no negative discount.

### 13.5 Redemption tests

- Draft invoice generation does not increment usage.
- Confirming an invoice increments usage once.
- Confirming an invoice with two discounts increments each relevant discount once.
- Repeating the confirmation request does not increment twice.
- A failed invoice confirmation does not commit a redemption increment.
- Concurrent confirmations cannot exceed the per-customer limit.
- A duplicate redemption-use record is rejected by the database constraint.
- Cancellation follows the explicitly approved usage-restoration policy.
- Editing a discount does not alter confirmed invoice snapshots.

### 13.6 Integration tests

- M5 passes the correct customer, subscription, line, quantity, amount, and date context to M6.
- M6 returns a deterministic ordered calculation result.
- M5 persists the discount snapshot and presents the applied amount.
- M5 confirmation calls the redemption service within the correct transaction boundary.
- A skipped discount is recorded with a safe reason and does not stop the billing run.
- An unexpected discount calculation failure is handled safely and does not produce a silently incorrect invoice.
- Existing M5 invoice idempotency remains intact.

### 13.7 Performance tests

- Discount list is paginated.
- Eligibility lookup avoids N+1 queries.
- Redemption usage lookup uses indexed fields.
- Candidate rule evaluation remains bounded under realistic rule counts.
- Billing performance is measured with thousands of subscriptions and representative discount data.

### 13.8 Required project checks

Run using the repository's actual environment and scripts:

```bash
ruff check .
ruff format .
python manage.py makemigrations --check --dry-run
pytest
```

Also run the project's dependency audit before release, as required by the coding standards. Record any check that could not be run and the reason; do not claim it passed without execution.

---

## 14. Open decisions and assumptions

The following points are not fully specified by the source documents. They must remain visible rather than being silently treated as settled requirements.

| # | Topic | Source position / working assumption | Decision needed |
|---|---|---|---|
| 1 | Meaning of cap “100” | Open Item A working assumption: 100% of eligible amount. | Confirm percentage cap versus 100 currency units. |
| 2 | Date boundaries | Start/end dates exist; inclusivity is not explicit. | Confirm inclusive/exclusive boundaries and timezone. |
| 3 | Date used for eligibility | Not specified. | Invoice date, billing-period date, confirmation date, or another date? |
| 4 | Minimum purchase base | Not specified. | Before/after tax, before/after other discounts, and scoped amount. |
| 5 | Minimum quantity | Not specified for mixed product lines or fractional quantities. | Define quantity aggregation and unit compatibility. |
| 6 | Both minimum conditions | Requirements list minimum purchase amount or minimum quantity. | Can both be configured, and if so are they AND or OR? |
| 7 | Required minimum condition | Not stated whether at least one minimum must be configured. | Are date and usage limit alone sufficient? |
| 8 | Fixed discount allocation | Product-scope behavior is specified, allocation across multiple lines is not. | First matching line, proportional allocation, or another policy? |
| 9 | Multiple discounts within same type | Type order is fixed; tie-break order is not. | Choose stable order (priority, creation order, or ID). |
| 10 | Usage limit zero/unlimited | Per-customer limit is required. | Is unlimited usage supported, and how is it represented? |
| 11 | Draft-to-confirmation race | Counter increments on confirmation. | If the limit is reached after draft generation, reject, recalculate, or honor draft snapshot? |
| 12 | Cancelled invoice | Increment occurs on confirmation; reversal is not defined. | Does cancellation restore a customer's usage? |
| 13 | Editing used rules | Edit UI is specified, but historical/draft behavior is not. | Restrict edits, version rules, or apply changes to future calculations only? |
| 14 | Delete/archive/deactivate | Not specified. | Define lifecycle and behavior for rules already used. |
| 15 | Stacking across scopes | Both product and whole-subscription scopes exist. | Define interaction where multiple scopes overlap. |
| 16 | Tax interaction | M5 owns tax calculation; M6 discount-tax base is not fully specified. | Confirm tax calculation order and line allocation. |
| 17 | Discount visibility in quotations | UI/UX mentions discounts in quotation detail, while FR-6.5 says next invoice. | Confirm whether quotations preview discounts and whether they consume no usage. |
| 18 | Currency precision | Single currency is the working assumption; currency is not specified here. | Confirm currency and fixed discount precision. |
| 19 | Redemption history UI | Usage tracking is required; exact Admin screen is not prescribed. | Decide whether to show per-customer redemption history and invoice links. |
| 20 | Rule name uniqueness | UI suggests a name/identifier; uniqueness is not stated. | Decide whether duplicate names are allowed. |

### 14.1 Explicit assumptions to avoid

Do not silently assume:

- That 100 means a fixed amount of 100 currency units.
- That date boundaries are inclusive without confirmation.
- That eligibility is based on the current server date rather than invoice/billing date.
- That minimum purchase amount is tax-inclusive or tax-exclusive without the M5 calculation contract.
- That quantity can be summed across products with different units.
- That fixed discounts are allocated to the first line or proportionally without approval.
- That a draft invoice reserves a discount redemption.
- That cancelling an invoice restores a redemption.
- That editing a discount rewrites confirmed invoice history.
- That Staff can manage discounts because they can run billing.
- That customers can enter arbitrary coupon codes.
- That a discount is applicable merely because its dates are valid; scope, conditions, and usage limit must also pass.

---

## 15. Dependencies and implementation sequence

### 15.1 Upstream dependencies

- **M1 Authentication and User Management:** authenticated actor, Admin role, Customer identity, and server-side RBAC.
- **M2 Product Catalog:** Product records for selected-product scope and product line references.
- **M4 Quotation Templates and Subscriptions:** customer, subscription, subscription lines, products, quantities, and billing context.
- **M5 Invoicing:** invoice generation, invoice-line/tax/proration calculations, invoice discount snapshots, confirmation transaction, and billing-run integration.
- **M9 Taxes and Payment Terms:** tax configuration consumed by M5; M6 must not duplicate tax administration.

### 15.2 Downstream consumers

- **M5 Invoicing:** consumes eligibility and stacking results and calls redemption confirmation.
- **M8 Reporting and Dashboard:** may consume discount totals/redemption information if reporting requirements define those measures.
- **Audit/notification infrastructure:** records operational events where required; M6 does not own the general notification system.

### 15.3 Suggested implementation order

1. Confirm Open Items affecting the calculation base, date semantics, allocation, tie-break order, and confirmation-time usage race.
2. Inspect the existing repository and align the `apps/discounts/` structure with current conventions.
3. Implement Discount and selected-product scope models.
4. Implement DiscountRedemption and any invoice/discount use idempotency record.
5. Add database constraints and indexes.
6. Implement model/form validation and Admin-only permissions.
7. Implement discount list, create, edit, and preview screens.
8. Implement eligibility selectors and service logic.
9. Implement deterministic fixed-first, percentage-second stacking with Decimal arithmetic.
10. Define and implement the M5 calculation result contract.
11. Integrate M6 results into M5 draft invoice generation and invoice snapshots.
12. Integrate confirmation-time redemption increments into the M5 confirmation transaction.
13. Add concurrency and idempotency protections.
14. Add invoice breakdown visibility and safe skip/failure feedback.
15. Complete unit, permission, calculation, integration, concurrency, and performance tests.
16. Run lint, formatting, migration checks, tests, and dependency audit.
17. Document all remaining product decisions before release.

---

## 16. Definition of Done

M6 is ready for acceptance when:

- [ ] FR-6.1 through FR-6.9 are implemented and verified.
- [ ] Only Admin can create and edit discount rules.
- [ ] Fixed-amount and percentage types are supported.
- [ ] Minimum purchase amount, minimum quantity, date window, and per-customer usage limit are evaluated according to confirmed policy.
- [ ] Selected-product and whole-subscription scopes are supported.
- [ ] Eligible discounts are applied automatically during the M5 invoice workflow.
- [ ] Expired, exhausted, and ineligible discounts are skipped without blocking unrelated billing.
- [ ] Multiple discounts stack in fixed-first, percentage-second order.
- [ ] Percentage discounts apply to the remaining amount.
- [ ] Combined discounts are capped according to the confirmed interpretation of Open Item A.
- [ ] Monetary calculations use Decimal and the shared rounding helper.
- [ ] Applied discounts are represented in the invoice breakdown and financial snapshot.
- [ ] Redemption usage is tracked per customer per discount.
- [ ] Usage increments only when an invoice using the discount is confirmed.
- [ ] Confirmation retries and concurrent requests cannot double-increment or exceed the usage limit.
- [ ] Confirmed invoice snapshots are not recalculated from edited rules.
- [ ] Required permissions, auditability, and safe logging are in place.
- [ ] Tests cover rule validation, eligibility, scope, stacking, cap, redemption, permissions, and concurrency.
- [ ] Migrations are present and consistent.
- [ ] `ruff check .`, `ruff format .`, `python manage.py makemigrations --check --dry-run`, and `pytest` pass, or any unavailable check is explicitly recorded with its reason.
- [ ] No unapproved dependencies or out-of-scope features are introduced.
- [ ] All unresolved product decisions are recorded and approved or explicitly deferred.

---

## 17. Developer self-review checklist

Complete this checklist when implementing M6, in line with `CODING_STANDARDS.md`.

| Area | Review question | Status |
|---|---|---|
| File/component structure | Are models, services, selectors, forms, views, permissions, and tests placed according to the existing project structure? Are views thin? | To verify during implementation |
| State management | Is PostgreSQL the source of truth for rules and redemption usage? | To verify during implementation |
| Calculation integrity | Are calculations Decimal-based, deterministic, fixed-first, and capped? | To verify during implementation |
| Redemption integrity | Are usage increments atomic, idempotent, and protected against concurrent over-redemption? | To verify during implementation |
| Historical data | Are confirmed invoice discount snapshots immutable? | To verify during implementation |
| Unused imports / dead code | Are unused imports, variables, stubs, debug prints, and dead code removed? | To verify during implementation |
| Dependencies | Were new packages avoided unless justified, approved, pinned, and compatible with Vercel? | To verify during implementation |
| Over-engineering | Were coupon portals, campaign engines, configurable rule DSLs, and speculative features avoided? | To verify during implementation |
| Security | Are discount management actions Admin-only on the server? Are customer records ownership-scoped? | To verify during implementation |
| Error handling | Are expected ineligibility outcomes skipped cleanly, while unexpected failures are logged and surfaced safely? | To verify during implementation |
| Performance | Are eligibility and redemption queries indexed, paginated where needed, and free of N+1 behavior? | To verify during implementation |

---

## 18. Source of truth and conflict handling

This document is derived from the Brightloop Subscription Management System source documents:

1. `REQUIREMENTS.md` — M6 Discounts (FR-6.1 through FR-6.9), role–permission matrix, BR-9 and BR-10, invoice discount integration in FR-5.8, and Open Items A, F, and J.
2. `CODING_STANDARDS.md` — Django modular-monolith structure, `apps/discounts/` ownership, services/selectors boundaries, PostgreSQL constraints and transactions, Decimal money handling, concurrency, domain exceptions, logging, and pytest standards.
3. `UI_UX.md` — Section 5.12 Discounts, Admin-only audience, list columns, create/edit fields, example preview, stacking explanation, and invoice discount presentation.

`REQUIREMENTS.md` defines what the product must do. `CODING_STANDARDS.md` defines how implementation must be structured and validated. `UI_UX.md` defines the expected interface and interaction behavior.

Where the sources define behavior, this document preserves it. Where the sources leave a decision open, the uncertainty is recorded in Section 14 instead of being silently replaced with an invented business rule. This document is an implementation baseline; it does not claim that M6 is already implemented.