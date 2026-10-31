# M2. Product Catalog

**Project:** Brightloop Subscription Management System  
**Module:** M2 — Product Catalog  
**Document type:** Current feature specification / implementation baseline  
**Status:** Draft — pending confirmation of the open decisions listed below  
**Primary source:** `REQUIREMENTS.md` v2.0  
**Supporting sources:** `UI_UX.md` and `CODING_STANDARDS.md`

> This document defines the expected behavior and acceptance baseline for M2. It does not claim that the feature has already been implemented. The requirements document remains the source of truth. Where the source documents are silent or explicitly leave a decision open, this specification records the gap instead of silently turning an assumption into a requirement.

---

## 1. Purpose and scope

M2 provides the administrative catalog used to define the products that can later be placed on subscription lines. A product stores its commercial identity, type, sales price, cost price, notes, associated tax, and optional variants. Products may be used as recurring subscription items or as add-ons.

The catalog is intended to give Admins one place to maintain product information and pricing while ensuring Staff and Customers cannot change catalog configuration.

### 1.1 Goals

1. Allow an Admin to create, view, edit, and archive products.
2. Store the required product attributes: name, type, sales price, cost price, and notes.
3. Associate every product with one tax record.
4. Support optional product variants and a price adjustment for each variant value.
5. Make product pricing and tax information available to later subscription and billing modules.
6. Preserve the meaning of existing subscription and invoice history when a product is edited or archived.
7. Enforce catalog permissions on the server, not only in the interface.

### 1.2 In scope

- Admin-only product catalog list and detail views.
- Product creation and editing.
- Product archiving and active/archived status display.
- Product fields and validation.
- Product-to-tax association, using the Tax entity managed under M9.
- Variant dimensions/values and per-value price adjustments.
- Base-price and adjusted-price preview in the variant editor.
- Product availability for later subscription-line selection.
- Automated tests for catalog behavior, pricing adjustments, validation, and permissions.

### 1.3 Out of scope

The following are not defined as M2 deliverables by the source requirements and must not be added without a separate decision or requirement:

- Tax creation, editing, or tax-rate administration (M9 owns this).
- Payment-term management (M9).
- Plan creation or plan pricing (M3).
- Quotation templates and subscriptions (M4), except for making catalog products available to those workflows.
- Invoice generation, invoice-line snapshots, billing, or payment collection (M5/M7).
- Discount rules or discount calculation (M6).
- Region-based, customer-specific, or multi-jurisdiction tax calculation.
- Multi-currency or multi-company catalog support.
- Inventory, stock levels, warehouses, procurement, or fulfillment.
- Product images, file attachments, SKUs, barcodes, categories, tags, or product search facets unless separately approved.
- Complex configurable variant combinations until the combination and adjustment rules are confirmed.
- Customer-facing product browsing or direct product purchasing.

---

## 2. Requirement traceability

All listed requirements are **Must (M)** in `REQUIREMENTS.md`.

| Requirement | Source requirement | M2 behavior |
|---|---|---|
| FR-2.1 | Admin can create, edit, and archive products with name, type, sales price, cost price, and notes. | Provide Admin-only create, edit, archive, list, and detail behavior for those fields. |
| FR-2.2 | A product can have variants (for example, by brand) with a price adjustment per variant value. | Allow variant values to carry a monetary adjustment and show the adjusted-price preview. |
| FR-2.3 | Each product has an associated tax (see M9). | Require a valid associated Tax record for each product. M2 consumes tax records; M9 manages them. |
| FR-2.4 | Products can be used as recurring items or add-ons on subscription lines. | Expose active products to subscription-line selection; represent add-ons as subscription lines in M4. |

### 2.1 Related requirements and rules

- **Role matrix, Section 4:** only Admin can manage products and variants. Staff and Customer are denied catalog-management access. Unlisted permissions are denied by default.
- **BR-8:** tax comes only from the product's tax.
- **BR-13:** prices are tax-exclusive; tax is added on top. This is a working assumption recorded in the requirements and Open Item B.
- **BR-14:** the system assumes one currency and one company; this remains subject to confirmation under Open Item D.
- **NFR-5:** relevant Admin changes are auditable with user and timestamp.
- **NFR-10:** monetary values use fixed-precision decimals, never floating point.
- **Domain entities:** `Product` contains name, type, sales price, cost price, notes, and tax; `ProductVariant` stores a variant value and its price adjustment; `Tax` stores a name and rate.

---

## 3. Roles and permissions

### 3.1 Admin

Admin has full system control and is the only role permitted to:

- Open the product catalog management area.
- List and view products, including archived products.
- Create products.
- Edit product details, tax association, and variants.
- Archive products.
- Review variant price adjustments and adjusted-price previews.

### 3.2 Internal Staff

Staff can handle day-to-day customer, quotation, subscription, invoice, and payment operations. Staff must not manage products or variants.

For M2, Staff:

- Must not see product create, edit, or archive controls.
- Must not access catalog-management URLs or endpoints.
- May encounter product choices in later workflows only as permitted by the relevant module. M2 does not grant Staff catalog write access.

### 3.3 Customer

Customers use the self-service portal for their own subscriptions and invoices. They do not manage the product catalog.

For M2, Customers:

- Must not access the catalog-management area.
- Must not create, edit, archive, or configure products or variants.
- Must not use catalog endpoints to inspect or modify internal catalog configuration unless a later customer-facing requirement explicitly permits a limited read view.

### 3.4 Authorization rules

- Enforce Admin-only authorization server-side on every catalog view and write operation.
- Hiding a button or menu item is not sufficient authorization.
- Default to deny when a role/capability is not explicitly granted.
- A Staff or Customer request to a protected catalog endpoint must not modify data.
- Use the project's central permission conventions where available; do not create a second, inconsistent role system inside `catalog`.

---

## 4. Product data model

The following describes the logical fields required by the source documents. Exact Django field names can follow existing project conventions, provided the persisted behavior remains equivalent.

### 4.1 Product

| Attribute | Required | Description / rule |
|---|---:|---|
| `id` | Yes | Database identifier. |
| `name` | Yes | Product's display name. Reject a blank value. |
| `type` | Yes | Product type. The exact allowed values are not enumerated in the source requirements and must be confirmed or taken from an existing project decision. |
| `sales_price` | Yes | Base selling price before tax and before variant adjustments. Use fixed-precision decimal storage. |
| `cost_price` | Yes | Product cost price. Use fixed-precision decimal storage. |
| `notes` | No | Optional descriptive/internal notes. |
| `tax` | Yes | Foreign-key/reference to one valid Tax record managed by M9. |
| `is_archived` / status | Yes | Distinguishes active from archived products. The exact field representation may follow project conventions. |
| `created_at` | Recommended | Creation timestamp, if consistent with the shared model conventions. |
| `updated_at` | Recommended | Last-update timestamp, if consistent with the shared model conventions. |

**Important:** timestamps and the precise status-field implementation are implementation conventions, not additional functional requirements explicitly stated in FR-2.1. The UI does require an active/archived status.

### 4.2 Product type

The requirements require a `type` field but do not provide its allowed values or define type-specific behavior.

Implementation must therefore:

- Reuse an already documented project-level set of product types if one exists.
- Otherwise record the allowed values as an open decision before enforcing a final enumeration.
- Avoid inventing behavior such as physical/digital inventory handling or service fulfillment based only on the existence of a type field.

### 4.3 ProductVariant

A product may have variants. Each variant value has a price adjustment.

| Attribute | Required | Description / rule |
|---|---:|---|
| `id` | Yes | Database identifier. |
| `product` | Yes | Parent Product. A variant value belongs to a product. |
| `dimension` / attribute name | Required for a dimension-based editor | Example: `Brand`. The source UI describes variant dimensions and values. |
| `value` | Yes | Example: `Odoo`. |
| `price_adjustment` | Yes | Fixed-precision decimal adjustment applied to the base sales price when the value is selected. |

The requirements explicitly provide the example that choosing brand `Odoo` adds `560` to the product price. Therefore, for a base price of `2,000`, the illustrative adjusted price is `2,560` before tax, assuming the example's adjustment is additive.

The source does not define whether a variant adjustment can be negative, whether values must be unique within a dimension, or how multiple dimensions combine. These are open decisions, not silently assumed rules.

### 4.4 Tax relationship

- Each Product must reference exactly one Tax record.
- The Tax entity is managed by M9, not by M2.
- The product form must allow the Admin to select an existing tax.
- A product cannot be saved without a valid tax association, unless the product requirements are formally changed.
- Tax calculation is not performed by catalog CRUD itself. Later subscription and invoice workflows use the product's tax.
- The source rule says tax comes only from the product's tax; M2 must not introduce region-based or customer-specific tax selection.

### 4.5 Money representation

- Store `sales_price`, `cost_price`, and `price_adjustment` using Django `DecimalField` or the project's equivalent fixed-precision decimal type.
- Follow the coding standard's example precision (`max_digits=12`, `decimal_places=2`) unless the project already defines a shared money convention.
- Never use Python `float` or JavaScript floating-point values as the authoritative persisted amount.
- Parse and validate submitted values on the server.
- Use the project's single money-rounding helper where calculations require rounding. The global rounding rule is an open item in the requirements (Open Item J); do not invent a separate catalog-only rule.
- Display amounts consistently with the system's configured single currency. The currency itself is not named in the source requirements.

---

## 5. Product lifecycle and behavior

### 5.1 Create product

An Admin can create a product by providing:

1. Name.
2. Type.
3. Sales price.
4. Cost price.
5. Optional notes.
6. Associated tax.
7. Optional variant dimensions/values and their price adjustments.

On successful creation:

- Persist the product and its variant data.
- Mark the product active by default, unless the existing project has an explicitly documented alternative.
- Make the active product available to later subscription-line selection.
- Show a visible success result and navigate to the product detail page or back to the product list.

If validation fails:

- Do not create a partial product.
- Keep the submitted form values where practical.
- Display field-level validation messages.
- Do not expose database errors or stack traces.

### 5.2 View products

Admin can view a paginated product list and open a product detail page.

The list must distinguish active and archived records and show the catalog fields specified by the UI/UX source (Section 6 below).

### 5.3 Edit product

Admin can update product information, tax association, and variants.

- Validate all submitted values on the server.
- Do not trust client-submitted prices, tax rates, totals, or calculated adjusted prices.
- Recalculate the adjusted-price preview from persisted base price and variant adjustment values.
- Changes to the current product must not silently rewrite historical subscription or invoice line values. The UI/UX source explicitly requires existing history to remain understandable and not be silently rewritten when products are archived; the same historical-snapshot principle should be applied when downstream records are created.
- The precise policy for editing a product already used by subscriptions is not fully specified and is listed as an open decision.

### 5.4 Archive product

Admin can archive a product instead of permanently deleting it.

- Archived products remain visible to Admin in the catalog with an Archived status.
- Archived products must not be offered for new subscription lines.
- Existing subscription and invoice history must remain understandable.
- Archiving must not delete historical subscription lines or invoices.
- The source documents do not define unarchive/restore behavior or whether products referenced by drafts can be archived; these are open decisions.

### 5.5 Delete behavior

The M2 requirements specify archive, not permanent deletion. Do not add a permanent-delete workflow as a substitute for archive. Database deletion policy for referenced products should protect referential integrity and historical records; the exact `on_delete` strategy should be chosen consistently with the project data-retention design.

---

## 6. User interface specification

**Audience:** Admin only for catalog management.

### 6.1 Navigation

- Provide a Product Catalog entry in the internal Admin navigation.
- Do not expose catalog-management navigation to Staff or Customers.
- Direct URL access must still be protected server-side.

### 6.2 Product list

The UI/UX source specifies these columns:

| Column | Description |
|---|---|
| Product name | Product's display name. |
| Type | Product type. |
| Sales price | Base sales price. |
| Cost price | Cost price. |
| Tax | Associated tax name/rate, as available from M9. |
| Variant count | Number of configured variant values or the project's agreed count convention. |
| Status | Active or Archived. |

Available actions:

- Create product.
- Edit product.
- Archive product.
- Open product details.

List behavior:

- Clearly distinguish active and archived products; do not rely on color alone.
- Archived products should remain discoverable to Admin.
- Provide a useful empty state when no products exist.
- Provide loading and error feedback where applicable.
- Paginate the list; avoid loading an unbounded catalog.
- Avoid N+1 queries by selecting the tax relation efficiently and prefetching variants where needed.

### 6.3 Product create/edit form

Fields required by the UI/UX specification:

| Field | UI behavior |
|---|---|
| Name | Required text input. |
| Type | Required selector/input using the confirmed type values. |
| Sales price | Required decimal amount input. Clearly label it as the base sales price. |
| Cost price | Required decimal amount input. |
| Notes | Optional text area. |
| Associated tax | Required selector populated from available Tax records. |
| Variants | Variant editor described below. |

Form behavior:

- Show validation messages beside the relevant fields.
- Do not accept a client-calculated amount as authoritative.
- Show a clear save/cancel action.
- Warn before leaving if unsaved-change protection is part of the shared application UX pattern; this is a UX enhancement rather than a separately stated M2 functional requirement.
- On a recoverable error, preserve entered values where practical.

### 6.4 Variant editor

The UI/UX source requires the Admin to add variant dimensions/values and their price adjustments.

At minimum, the editor must support:

- Adding a variant dimension (example: `Brand`).
- Adding a value under that dimension (example: `Odoo`).
- Entering a price adjustment for the value (example: `+560`).
- Reviewing the base price and adjusted-price preview.

Example preview:

| Item | Amount |
|---|---:|
| Base sales price | 2,000.00 |
| Selected variant adjustment (Odoo) | +560.00 |
| Adjusted price before tax | 2,560.00 |

The example amounts illustrate the source requirement; they are not fixed product prices.

Do not implement a sophisticated multi-dimension configurator until the rules for selecting one value per dimension, combining adjustments, and handling conflicting selections have been confirmed.

### 6.5 Product detail view

The source UI requires an action to open product details but does not prescribe a full detail-page layout. A minimal detail view should therefore show the stored product information without introducing new business behavior:

- Name and type.
- Base sales price and cost price.
- Notes, when present.
- Associated tax.
- Active/archived status.
- Configured variant dimensions/values and their adjustments.
- Available Admin actions (edit and archive where applicable).

This is a presentation of existing M2 data, not a separate functional expansion.

### 6.6 Empty, success, and error states

| State | Expected behavior |
|---|---|
| No products | Explain that no products exist and offer Create product to Admin. |
| No variants | Show that no variants are configured; do not treat this as an error. |
| No tax records | Explain that a tax must be configured under M9 before a product can be saved. Do not silently create a tax. |
| Invalid form | Show field-level errors and preserve valid entered values. |
| Save success | Show confirmation and the resulting product. |
| Archive confirmation | Explain that the product will no longer be available for new subscription lines; require confirmation. |
| Archived product | Display Archived status and prevent selection for new subscription lines. |
| Permission denied | Return the project's standard forbidden/not-found behavior without exposing internal data. |
| Unexpected error | Show a generic error and log diagnostic context server-side; do not expose stack traces. |

---

## 7. Pricing and variant rules

### 7.1 Base price

`Product.sales_price` is the base selling price. The requirements do not state that variant adjustments modify the cost price. Therefore, M2 must not automatically apply a variant adjustment to `cost_price`.

### 7.2 Variant adjustment

For a selected variant value, the example indicates an additive adjustment:

`adjusted_price = base_sales_price + selected_variant_adjustment`

Example:

- Base sales price: 2,000.00
- Brand: Odoo
- Adjustment: +560.00
- Adjusted price before tax: 2,560.00

This formula is directly supported for the single-value example. Multiple dimensions, multiple selected values, negative adjustments, and compounding behavior are not defined.

### 7.3 Tax treatment

The current working assumption is tax-exclusive pricing: tax is added on top of the product price (BR-13 / Open Item B).

M2 should:

- Store the product's tax association.
- Display tax context in the product list and detail/form views.
- Avoid adding tax into `sales_price` itself.
- Leave final tax calculation and invoice-line snapshots to the subscription/billing modules that consume the catalog.

The tax-inclusive/exclusive decision is still identified as an open item in the requirements and should be confirmed before treating it as immutable policy.

### 7.4 Server authority

- The server calculates adjusted prices from the stored base price and selected variant adjustment.
- The browser may display a preview, but the preview is not authoritative.
- Never accept a client-submitted total or tax amount without recomputing it from trusted database records.
- Use `Decimal` for all monetary calculations and tests.

---

## 8. Integration with other modules

### 8.1 M3 — Plans

M2 provides the product catalog. M3 manages plans and their pricing/billing-period rules. Do not merge plan fields into Product or treat a Product as a Plan.

### 8.2 M4 — Quotation templates and subscriptions

- Subscription lines reference products.
- Products can be recurring items or add-ons.
- Add-ons are modeled as subscription lines, not as a separate product lifecycle entity.
- M2's responsibility is to make active products and their catalog data available to the subscription workflow.
- M2 must not implement subscription lifecycle, quotation acceptance, proration, or subscription billing.

### 8.3 M5 — Invoicing

- Invoice lines are generated from subscription data.
- Tax is taken from the tax attached to each product.
- Confirmed invoice totals are stored at confirmation time and historical invoices must not be recomputed from current catalog prices.
- M2 must not implement invoice generation or invoice status transitions.

### 8.4 M6 — Discounts

M2 does not manage discount rules or apply discounts. Discounts are handled by M6 and applied to invoices according to the requirements.

### 8.5 M9 — Taxes and payment terms

M9 manages Tax records (name and rate). M2 references one Tax per product and allows Admin to select it. M2 must not duplicate tax CRUD or invent tax rules.

---

## 9. Architecture and implementation guidance

The project coding standards define a Django modular monolith backed by PostgreSQL. Follow the existing project layout rather than introducing a new architecture.

### 9.1 Suggested catalog app responsibilities

The coding standards identify `apps/catalog/` as the location for products, variants, taxes, and payment terms. For M2, keep the implementation focused on Product and ProductVariant; Tax administration remains M9.

Expected app structure, adapted to the existing repository:

```text
apps/catalog/
├── models.py          # Product and ProductVariant data/invariants
├── services.py        # create, update, archive, variant operations
├── selectors.py       # product list/detail query logic
├── views.py           # thin request handlers
├── forms.py           # server-side form validation
├── permissions.py     # only if shared permission layer does not cover it
├── urls.py
├── admin.py
├── tests/
└── migrations/
```

Do not create duplicate files if the repository already has equivalent modules. Keep views thin; write operations belong in services; complex reads belong in selectors.

### 9.2 Model constraints and validation

Use Django model/form validation and PostgreSQL constraints where appropriate.

Expected protections include:

- Required product name, type, sales price, cost price, and tax association.
- Decimal fields for all monetary values.
- Valid reference from Product to Tax.
- Variant values associated with a valid parent Product.
- Any uniqueness constraints for variant dimensions/values only after their intended scope is confirmed.
- No direct client ability to set archived/active state through an untrusted field unless the endpoint is an authorized Admin action.

Do not rely on form validation alone for invariants that must hold under concurrent requests; use database constraints where a clear invariant exists.

### 9.3 Services

Write operations should be exposed through focused service functions, for example:

- `create_product(...)`
- `update_product(...)`
- `archive_product(...)`
- `replace_product_variants(...)` or smaller variant operations, depending on the actual UI workflow.

These are suggested names, not mandatory public APIs. Match existing naming conventions and avoid creating abstractions with no second concrete use.

Wrap multi-record writes (such as saving a product and its variants together) in `transaction.atomic()` so the operation cannot leave a partially updated catalog record.

### 9.4 Selectors and query performance

- Keep catalog list/detail query logic in selectors when it becomes non-trivial.
- Use `select_related` for the Tax foreign key.
- Use `prefetch_related` for variants when listing variant counts or displaying variant details.
- Paginate product lists.
- Add indexes only where supported by actual query patterns or measured performance needs; do not add speculative indexes.

### 9.5 Auditability

NFR-5 requires relevant Admin changes to be auditable with actor and timestamp. Product creation, edits, and archive actions should integrate with the project's existing audit mechanism if present.

The source documents do not specify the exact audit event schema or whether every individual variant edit needs a separate event. Reuse the project's shared audit approach and record enough context to identify the actor, product, operation, and time.

### 9.6 Dependencies and deployment

- Prefer Django and the standard library.
- Do not add a package solely to implement basic catalog CRUD or decimal arithmetic.
- PostgreSQL is the source of truth.
- Every model change requires a migration.
- Do not use local files or in-memory globals as persistent catalog storage.
- Keep the application compatible with the project's Vercel/serverless constraints.

---

## 10. Validation rules

The following rules are required or directly implied by the defined fields and security requirements. Any additional business constraints must be confirmed rather than invented.

| Field / operation | Validation |
|---|---|
| Name | Required; reject blank/whitespace-only input. |
| Type | Required; validate against the confirmed set of types. |
| Sales price | Required decimal; reject malformed values and values outside the agreed field precision. |
| Cost price | Required decimal; reject malformed values and values outside the agreed field precision. |
| Notes | Optional text; apply normal input handling and output escaping. |
| Tax | Required reference to an existing valid Tax record. |
| Variant dimension | Required when a dimension is created; allowed naming/uniqueness rules need confirmation. |
| Variant value | Required for each configured value. |
| Price adjustment | Decimal; validate precision and range according to the decision on negative adjustments. |
| Archive | Admin-only action; require confirmation in the UI. |
| New subscription-line selection | Exclude archived products. |

**Not specified by the source:** whether sales price or cost price may be zero or negative; whether cost price must be less than/equal to sales price; maximum name/notes lengths beyond the chosen database limits; whether duplicate product names are allowed; whether tax can be changed after a product is used. These are listed as open decisions below.

---

## 11. Security and data integrity

- Admin-only catalog operations must be protected server-side.
- Staff and Customer must not be able to call catalog write endpoints directly.
- Validate all input using Django forms/serializers and service-level rules as appropriate.
- Use ORM queries or parameterized SQL; never interpolate raw user input into SQL.
- Keep Django template auto-escaping enabled. Do not mark user notes as safe HTML.
- Keep CSRF protection enabled for browser-based write actions.
- Do not trust client-supplied price, tax rate, adjusted price, or status.
- Use atomic transactions for multi-row product/variant updates.
- Preserve referenced products and historical downstream records; archive instead of deleting.
- Record relevant Admin changes through the shared audit mechanism.
- Do not expose stack traces, SQL errors, or internal identifiers unnecessarily in user-facing error messages.

---

## 12. Acceptance criteria

M2 is acceptable when all applicable criteria below pass.

### 12.1 Product CRUD

- [ ] Admin can open the product catalog.
- [ ] Admin can create a product with name, type, sales price, cost price, notes, and tax.
- [ ] Required fields are validated on the server.
- [ ] Admin can view product details.
- [ ] Admin can edit product fields.
- [ ] Admin can archive a product.
- [ ] The list displays active and archived status.
- [ ] Archived products remain visible to Admin.
- [ ] No permanent-delete workflow is substituted for archive.

### 12.2 Variants

- [ ] Admin can configure a variant dimension and its values.
- [ ] Each variant value can store a price adjustment.
- [ ] The example variant `Odoo` can be represented with a `+560` adjustment.
- [ ] The UI displays the base price and adjusted-price preview.
- [ ] The server calculates the adjusted price from trusted product and variant data.
- [ ] Invalid variant data is rejected without leaving partial records.
- [ ] The implementation does not silently invent multi-dimension combination rules.

### 12.3 Tax association

- [ ] Every saved product references one existing Tax record.
- [ ] The product form lets Admin select a tax.
- [ ] M2 does not duplicate M9 tax administration.
- [ ] Tax is not silently baked into the product's base sales price under the current tax-exclusive working assumption.

### 12.4 Subscription-line compatibility

- [ ] Active products can be selected by the later subscription-line workflow.
- [ ] Products can represent recurring items or add-ons on subscription lines.
- [ ] Archived products are excluded from new subscription-line selection.
- [ ] Existing subscription/invoice history remains understandable after product edits or archive.

### 12.5 Permissions and security

- [ ] Admin can perform all catalog operations.
- [ ] Staff cannot create, edit, archive, or manage variants.
- [ ] Customer cannot create, edit, archive, or manage variants.
- [ ] Direct requests to protected endpoints are denied for unauthorized roles.
- [ ] Prices and tax data are validated/recalculated server-side.
- [ ] CSRF and output escaping remain enabled.

### 12.6 Quality

- [ ] Product list is paginated.
- [ ] Catalog queries avoid obvious N+1 access patterns.
- [ ] Multi-record writes are atomic.
- [ ] Model changes have migrations.
- [ ] Tests cover success, validation failure, permission denial, and archive behavior.
- [ ] No unused imports, dead code, debug statements, or unnecessary dependencies remain.

---

## 13. Test plan

Use `pytest` and `pytest-django`, with `factory-boy` where useful, as specified by `CODING_STANDARDS.md`. Tests must not call real external services. Monetary assertions must use `Decimal`, never float.

### 13.1 Product creation

1. Admin creates a valid product.
2. Missing name is rejected.
3. Blank name is rejected.
4. Missing type is rejected.
5. Missing sales price is rejected.
6. Malformed sales price is rejected.
7. Missing cost price is rejected.
8. Malformed cost price is rejected.
9. Missing tax is rejected.
10. Non-existent tax reference is rejected.
11. Optional notes may be empty.
12. A submitted forged role or actor value does not grant catalog access.
13. Product and variants are not partially saved if a multi-record creation fails.

### 13.2 Product editing

Test:

- Admin can edit each editable field.
- Invalid values are rejected.
- Tax association can be changed to another valid tax, subject to the unresolved policy for products already in use.
- Product updates do not rewrite historical invoice totals or existing immutable invoice-line snapshots.
- Concurrent updates do not leave inconsistent variant relations.

### 13.3 Product archive

Test:

- Admin can archive an active product.
- Archived status appears in the Admin list/detail view.
- Archived product is excluded from new subscription-line selection.
- Existing subscription lines and invoice history remain accessible and understandable.
- Staff and Customer cannot archive products.
- Repeated archive requests behave safely and do not corrupt data.

### 13.4 Variants and price adjustments

Test:

- Product can have no variants.
- Admin can add a dimension and value.
- A value stores a decimal adjustment.
- Base price `2000.00` plus adjustment `560.00` previews as `2560.00` before tax.
- The server-side calculation matches the preview.
- Malformed adjustment is rejected.
- Precision is enforced consistently.
- Negative adjustments follow the confirmed policy; do not encode an unapproved assumption.
- Multiple dimensions are tested only after their combination rules are decided.

### 13.5 Permissions

For each operation (list, detail, create, update, archive, variant management), test:

- Admin allowed.
- Staff denied.
- Customer denied.
- Anonymous user handled by the project's standard authentication behavior.
- Direct URL/API access is denied even if UI controls are hidden.

### 13.6 Query and integrity tests

- Product list includes associated tax information without an N+1 query pattern.
- Variant count is correct.
- Archived and active filters/statuses are correct.
- Database constraints protect confirmed invariants.
- Money values are `Decimal` and never converted to float for persistence or assertions.

### 13.7 Required project checks

Before accepting an implementation, run the project checks specified by the coding standards:

```bash
ruff check .
ruff format .
python manage.py makemigrations --check --dry-run
pytest
```

Run the relevant focused test suite during development as well. Report any check that was not actually executed as **not run**. Run `pip-audit` (or the project's approved equivalent) before release.

---

## 14. Open decisions and assumptions

The source documents are drafts and leave several catalog details unspecified. These must be confirmed or explicitly recorded as implementation assumptions.

| Topic | What the source defines | Decision still needed |
|---|---|---|
| Product type values | Product has a `type` field. | Exact allowed choices and any type-specific behavior. |
| Price range | Sales price and cost price are required. | Whether zero/negative prices are permitted; whether cost must be below sales price. |
| Product-name uniqueness | No uniqueness rule stated. | Whether duplicate product names are allowed and whether matching is case-insensitive. |
| Variant dimensions | UI supports dimensions and values. | Whether multiple dimensions are required in the first release. |
| Variant combinations | Price adjustment per variant value is required. | How multiple selected dimensions/values combine; whether exactly one value per dimension is selected. |
| Negative adjustment | Not specified. | Whether negative variant adjustments are allowed and any lower bound. |
| Variant uniqueness | Not specified. | Uniqueness scope for dimension names and values. |
| Variant changes | Variants can be edited as part of product maintenance. | What happens to existing subscription lines if a variant value is renamed, changed, or removed. |
| Tax-inclusive/exclusive | Working assumption is tax-exclusive (BR-13 / Open Item B). | Confirm that prices are tax-exclusive. |
| Tax changes after use | Product has one tax; tax comes from product. | Whether tax can be changed after subscriptions or invoices reference the product, and how future lines are affected. |
| Currency | Working assumption is one currency (Open Item D). | Confirm the currency and display format. |
| Archive and restore | Archive is required; archived products are not offered for new subscription lines. | Whether unarchive/restore is supported and whether archiving is blocked when drafts reference the product. |
| Historical pricing | UI says history must remain understandable and not be silently rewritten. | Exact snapshot fields stored on subscription lines and invoice lines; coordinate with M4/M5. |
| Audit details | Admin changes must be auditable (NFR-5). | Exact event schema and variant-level audit granularity. |
| Field limits | Not specified. | Maximum lengths and decimal precision if not already standardized project-wide. |

### 14.1 Explicit working assumptions used in this document

1. A newly created product is active by default.
2. `sales_price` is the base price before variant adjustment and tax.
3. The `Odoo +560` example is additive for the selected value.
4. Variant adjustments do not change `cost_price`, because no such behavior is specified.
5. Archived products remain visible to Admin but are unavailable for new subscription lines.
6. Product history is preserved; archive is used instead of permanent deletion.
7. The system's shared money precision/rounding convention is reused rather than introducing a catalog-specific one.

These are implementation assumptions, not all separately approved business decisions. Confirm them where they affect the final data model or user-facing behavior.

---

## 15. Definition of Done

M2 is complete when:

- [ ] FR-2.1 through FR-2.4 are implemented and accepted.
- [ ] Product and variant models follow the existing Django/PostgreSQL architecture.
- [ ] Admin-only catalog access is enforced server-side.
- [ ] Product CRUD and archive behavior work as specified.
- [ ] Product tax association uses the M9 Tax entity.
- [ ] Variant values store decimal price adjustments and the UI previews adjusted price.
- [ ] Active products are available to subscription lines; archived products are excluded from new lines.
- [ ] Existing subscription/invoice history is not silently rewritten.
- [ ] Migrations are included and consistent.
- [ ] Success and failure-path tests pass.
- [ ] `ruff` and migration checks pass, or are explicitly reported as not run.
- [ ] No unnecessary dependencies, debug code, or dead code are introduced.
- [ ] The open decisions and assumptions are documented for review.

---

## 16. Self-review

**Requirements covered:** FR-2.1, FR-2.2, FR-2.3, FR-2.4; related role matrix, BR-8, BR-13, BR-14, NFR-5, and NFR-10.  
**Assumptions made:** New products are active by default; variant adjustment is additive in the provided single-value example; adjustments do not alter cost price; archived products remain visible to Admin but are excluded from new subscription lines; history is preserved. See Section 14.  
**Got right:** The specification separates catalog ownership from tax administration, plans, subscriptions, and invoicing; uses decimal money; enforces Admin-only catalog management; and preserves the explicitly stated archive/history behavior.  
**Uncertain / possibly wrong:** Product type choices, negative price/adjustment policy, multiple variant-combination rules, tax-change behavior for products already in use, restore behavior, and exact historical snapshot implementation require confirmation.  
**Not done / out of scope:** No application code, migrations, templates, or tests were created by this document. No tax CRUD, plan management, subscription lifecycle, or invoice generation is specified as M2 implementation work.  
**New dependencies:** None.  
**Tests added:** None — this is a feature specification, not an implementation change.  
**Checks run:** File content created and path verified; `ruff`, Django migration checks, and pytest were not run because no application code was changed.

---

## 17. Source documents and precedence

1. `REQUIREMENTS.md` v2.0 — authoritative source for functional and non-functional requirements.
2. `UI_UX.md` — interface translation of the requirements, including the Product Catalog section.
3. `CODING_STANDARDS.md` — implementation architecture, money handling, security, testing, and quality rules.

If this document conflicts with `REQUIREMENTS.md`, the requirements document takes precedence. If the source documents do not define a behavior, treat it as an open decision rather than assuming it is approved.
