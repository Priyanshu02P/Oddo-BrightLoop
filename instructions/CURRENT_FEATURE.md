# M1. Authentication and User Management

**Project:** Brightloop Subscription Management System\
**Feature ID:** M1\
**Feature name:** Authentication and User Management\
**Priority:** Must-have\
**Source specification:** `REQUIREMENTS.md` v2.0, Section 5.1\
**Supporting documents:** `CODING_STANDARDS.md`, `UI_UX.md` v1.0\
**Feature status:** Specification baseline --- implementation status has
not been verified\
**Last updated:** 2026-10-31

------------------------------------------------------------------------

## 1. Feature overview

M1 provides the identity, authentication, account-management,
authorization, and customer-data-isolation foundation for Brightloop.

The system supports three account roles:

-   **Admin** --- controls the system and is the only role permitted to
    create Staff accounts.
-   **Internal Staff** --- performs permitted day-to-day subscription
    and billing operations, but cannot manage users or restricted
    commercial configuration.
-   **Customer** --- uses the self-service portal and can access only
    their own subscriptions, invoices, and payments.

Customers must be able to create an account using an email address and
password, sign in, and recover access through a password-reset link. The
system must enforce role permissions on the server, not merely hide
unavailable controls in the interface.

M1 is a security-critical foundation for the rest of the application.
All protected features must rely on the authenticated user and the
authorization rules defined here.

### 1.1 Goals

1.  Allow customers to register and authenticate securely.
2.  Ensure that one email address maps to at most one account,
    regardless of letter casing.
3.  Enforce the specified password policy.
4.  Provide secure, single-use, time-limited password reset.
5.  Support Admin, Staff, and Customer roles with server-side role-based
    access control (RBAC).
6.  Restrict Staff account creation to Admins.
7.  Prevent customers from reading or modifying another customer's
    records.
8.  Store passwords only as secure salted hashes.

### 1.2 Out of scope

The source requirements do not define the following as part of M1. They
must not be treated as committed functionality without a separate
requirement or product decision:

-   Social login or third-party identity providers.
-   Multi-factor authentication (MFA/2FA).
-   Email verification before account activation.
-   CAPTCHA or bot-detection integration.
-   Self-service role changes.
-   Customer profile editing beyond the account/security entry points
    described in the UI/UX specification.
-   Account deletion, account suspension workflows, or account recovery
    by support.
-   A public Staff or Admin registration flow.
-   A public online-payment flow.
-   A full audit-log user interface.
-   A specific session lifetime, idle timeout, or concurrent-session
    policy.

------------------------------------------------------------------------

## 2. Requirement traceability

All requirements below are **Must (M)** unless stated otherwise.

  -----------------------------------------------------------------------
  Requirement             Description             Feature behavior
  ----------------------- ----------------------- -----------------------
  FR-1.1                  A customer can sign up  Public registration
                          with an email and a     creates a Customer
                          password.               account.

  FR-1.2                  Each email can belong   Normalize/compare email
                          to only one account     identities consistently
                          (unique,                and enforce uniqueness
                          case-insensitive).      in PostgreSQL.

  FR-1.3                  Password policy: more   Validate the policy on
                          than 8 characters, at   the server and explain
                          least one uppercase     unmet rules in the
                          letter, one lowercase   form.
                          letter, and one special 
                          character.              

  FR-1.4                  Forgot password sends a Use Django's
                          reset link to the       password-reset token
                          registered email; the   mechanism and a neutral
                          link is single-use and  response.
                          time-limited.           

  FR-1.5                  RBAC with Admin, Staff, Centralize permission
                          and Customer, enforced  checks and deny access
                          server-side according   by default.
                          to Requirements Section 
                          4.                      

  FR-1.6                  Only an Admin can       Ignore any submitted
                          create Staff accounts.  role value during
                          Public signup always    public signup.
                          creates a Customer.     

  FR-1.7                  Customers can only      Scope customer-facing
                          access their own        data access to the
                          subscriptions,          authenticated user's
                          invoices, and payments. linked Customer record.

  FR-1.8                  Passwords are stored as Use Django password
                          salted hashes, never in hashers; never store or
                          plain text.             log raw passwords.
  -----------------------------------------------------------------------

Related source rules:

-   **BR-1:** One account per email address.
-   **BR-2:** Only Admin creates Staff; public signup creates Customers
    only.
-   **NFR-4:** Server-side RBAC, hashed passwords, expiring single-use
    reset tokens, customer data isolation, and protection against common
    web attacks.
-   **NFR-5:** Relevant changes must be auditable with user and
    timestamp where the underlying operation is covered by the system's
    audit requirements.

------------------------------------------------------------------------

## 3. Roles and account model

### 3.1 Admin

Admin has full system control.

For M1, Admin can:

-   Sign in and use the internal application.
-   Create Staff accounts.
-   Access the User Management area.
-   Perform the administrative actions permitted by the broader
    role-permission matrix.

Admin-only user creation must be checked on the server. A Staff or
Customer must not be able to create a Staff account by calling a URL or
submitting a crafted request directly.

The requirements identify Admin as a role but do not define the initial
Admin bootstrap procedure. That setup mechanism must be decided
separately and must not be replaced with public Admin registration.

### 3.2 Internal Staff

Staff can:

-   Sign in and use the internal application.
-   Perform the operations allowed by the role-permission matrix.

Staff cannot:

-   Create Staff accounts.
-   Manage users.
-   Manage products, variants, plans, taxes, payment terms, or
    discounts.
-   Create or manage quotation templates (Staff may use existing
    templates).

The requirements describe Staff as a limited internal role. Any
permission not explicitly granted by the role-permission matrix is
denied by default.

### 3.3 Customer

Customer can:

-   Sign up publicly.
-   Sign in and reset their password.
-   Access the customer portal.
-   View their own subscriptions, quotations, invoices, and payment
    information.
-   Perform subscription actions only where the subscription's plan
    permits them.

Customer cannot:

-   Create Staff accounts.
-   Access the internal dashboard or reports.
-   Run billing or generate invoices.
-   Confirm, cancel, or send invoices.
-   Record payments.
-   Read or modify another customer's data.

### 3.4 Role comparison

  ------------------------------------------------------------------------------------------
  Capability                            Admin               Staff             Customer
  ------------------------------ ------------------- ------------------- -------------------
  Public customer signup           Not applicable      Not applicable            Yes

  Sign in                                Yes                 Yes                 Yes

  Request password reset                 Yes                 Yes                 Yes

  Create Staff accounts                  Yes                 No                  No

  Manage users                   Yes, within defined         No                  No
                                        scope                            

  View internal dashboard and            Yes                 Yes                 No
  reports                                                                

  Manage subscriptions                   Yes                 Yes          Own records only,
                                                                          permitted portal
                                                                               actions

  View own                          As authorized       As authorized            Yes
  subscription/invoice/payment                                           
  data                                                                   

  Access another customer's        Internal access     Internal access           No
  records                           according to        according to     
                                     permissions         permissions     
  ------------------------------------------------------------------------------------------

The matrix above summarizes the M1 boundary and selected downstream
permissions. The complete permission matrix in `REQUIREMENTS.md` Section
4 remains authoritative for non-authentication capabilities.

------------------------------------------------------------------------

## 4. Functional behavior

### 4.1 Customer registration

**Entry point:** Customer sign-up link on the sign-in screen.

**Fields:**

  ------------------------------------------------------------------------
  Field                                     Required Rules
  --------------------- ---------------------------- ---------------------
  Email                                          Yes Valid email address;
                                                     unique without regard
                                                     to letter casing.

  Password                                       Yes Must satisfy the M1
                                                     password policy.

  Confirm password                       Recommended Must match the
                                                     password. This field
                                                     is a UI/UX
                                                     recommendation, not a
                                                     separate functional
                                                     requirement.
  ------------------------------------------------------------------------

**Registration behavior:**

1.  The customer opens the sign-up page.
2.  The customer enters an email address and password.
3.  The server validates required fields and email format.
4.  The server validates the password policy.
5.  The server checks email uniqueness, while the database constraint
    remains the final authority.
6.  The server creates the account with the **Customer** role.
7.  The password is stored using Django's password-hashing mechanism.
8.  The user receives a clear success or validation result.

**Mandatory security rules:**

-   Public signup must always create a Customer account.
-   Do not render a role selector.
-   Ignore or reject any client-supplied `role`, `is_staff`,
    `is_superuser`, permission, or equivalent privilege-escalation
    field. Never use these values to set account privileges.
-   Do not permit public signup to create Admin or Staff users.
-   Enforce email uniqueness in PostgreSQL, not only in the form.
-   Keep CSRF protection enabled for browser form submissions.

**Duplicate email behavior:**

-   The registration must be rejected if an account already exists for
    the same email under a different casing.
-   The UI should explain that the email cannot be used for another
    account without disclosing another user's private information.
-   The database uniqueness constraint must handle concurrent
    registration attempts safely.

### 4.2 Sign in

**Fields:**

-   Email
-   Password

**Actions:**

-   Sign in
-   Forgot password
-   Customer sign-up

**Behavior:**

1.  The user submits email and password.
2.  The server authenticates using the case-insensitive email identity.
3.  On success, the application establishes the configured authenticated
    session.
4.  The application routes the user to the correct experience based on
    the account role.
5.  On failure, the UI displays a generic authentication error.

The error must not reveal whether the email is registered. Avoid
separate public messages such as "email not found" and "password
incorrect".

**Role-based destination:**

-   Admin → internal application.
-   Staff → internal application.
-   Customer → customer portal.

The exact post-login URL and behavior for inactive or otherwise
unavailable accounts are implementation details that are not specified
in the source requirements.

### 4.3 Password policy

The password must satisfy every rule below:

  Rule                Required condition
  ------------------- ------------------------------------------------
  Length              More than 8 characters (minimum 9 characters).
  Uppercase           At least one uppercase letter.
  Lowercase           At least one lowercase letter.
  Special character   At least one special character.

The policy must be enforced on the server using a custom Django password
validator, as required by `CODING_STANDARDS.md`.

The sign-up and reset-password interfaces must display the actual
policy. When validation fails, show which rule or rules were not met.

Do not silently substitute a different policy. In particular, the source
requirement says **more than 8**, not "8 or more".

### 4.4 Forgot password

**Entry point:** "Forgot password" on the sign-in page.

**Flow:**

1.  The user opens the forgot-password page.
2.  The user submits an email address.
3.  The server processes the request without revealing whether the
    account exists.
4.  The UI displays a neutral confirmation, such as: "If an account
    exists for that email, password-reset instructions will be sent."
5.  If the account exists and is eligible for reset, the system sends a
    reset email containing a reset link.
6.  The link uses Django's password-reset token generator.
7.  The token is single-use and time-limited.
8.  The user follows the link and enters a new password and
    confirmation.
9.  The server validates the token and new password.
10. On success, the password hash is updated and the token can no longer
    be used.

**Reset-link requirements:**

-   A valid token can be used only once.
-   A token expires after the configured validity period.
-   An expired or already-used token must not permit a password change.
-   The UI must explain that the link is no longer valid and provide a
    route to request another reset link.
-   Reset responses must not reveal whether an email exists.
-   Never log the reset token or full reset URL.

**Unspecified detail:** The exact token validity duration is not
provided in the requirements. Use the configured Django/application
setting and record the chosen duration as an implementation decision; do
not present an invented duration as a product requirement.

### 4.5 Password reset page

**Fields:**

-   New password
-   Confirm new password

**Behavior:**

-   Validate that both fields are present.
-   Validate that both values match.
-   Enforce the complete M1 password policy on the server.
-   Validate that the reset token is valid, unused, and unexpired.
-   Preserve safe form feedback and explain validation errors.
-   Do not reveal internal exceptions, token contents, or account
    details.

The UI should offer a new reset request when the link is expired or
already used.

### 4.6 Admin creates Staff accounts

**Access:** Admin only.

The Admin is the only role allowed to create Staff accounts.

**Expected behavior:**

1.  Admin opens User Management.
2.  Admin chooses the create-Staff action.
3.  Admin supplies the account information required by the implemented
    account form.
4.  The server verifies that the requester is an authenticated Admin.
5.  The server validates the submitted data and email uniqueness.
6.  The server creates the account with the Staff role.
7.  The UI displays the result.

The requirements establish the authorization rule but do not specify:

-   The exact Staff creation fields.
-   Whether Staff receive an invitation or an administrator-set
    temporary password.
-   Whether Staff must change a password on first sign-in.
-   Whether Staff activation requires email verification.
-   Whether Admin can edit, deactivate, reactivate, or delete existing
    Staff accounts.

These are open implementation/product decisions. Do not silently add
them to the feature.

### 4.7 Sign out

The UI/UX specification includes a sign-out action in the global
application elements and customer portal.

The sign-out action must end the user's authenticated session using the
application's configured Django authentication/session mechanism. The
exact session-expiry and revocation policy is not defined by the
requirements.

------------------------------------------------------------------------

## 5. Role-based access control (RBAC)

### 5.1 Enforcement principles

-   Authorization is enforced on the server for every protected view and
    service operation.
-   Hiding a button or navigation item is a usability measure only; it
    is not an authorization control.
-   Use a central permission layer in `apps/accounts/permissions.py` (or
    the project's equivalent structure).
-   Map permissions to the role-permission matrix in `REQUIREMENTS.md`
    Section 4.
-   **Default deny:** if an action is not explicitly allowed, reject it.
-   Validate permissions on every request, including direct URL access
    and crafted POST requests.
-   Do not trust a role or permission value supplied by the browser.

### 5.2 Permission checks

A protected operation should follow this sequence:

1.  Confirm that the request has an authenticated user.
2.  Determine the user's persisted role.
3.  Check whether that role is permitted to perform the requested
    action.
4.  For customer-owned data, resolve the authenticated user's associated
    Customer record.
5.  Scope the object lookup to that Customer.
6.  Perform the operation only after authorization and ownership checks
    succeed.

Views should remain thin and delegate business operations to services.
Services that can be called from multiple entry points must also enforce
the relevant authorization boundary; a view-only check is insufficient
where the service is independently callable.

### 5.3 Customer data isolation

Customer isolation is mandatory for:

-   Subscriptions.
-   Invoices.
-   Payments.

Customer-facing queries must filter by the Customer associated with the
authenticated user.

**Safe lookup pattern (illustrative Django ORM):**

``` python
get_object_or_404(
    Invoice,
    pk=invoice_id,
    customer=request.user.customer,
)
```

Do not retrieve an invoice by its primary key alone and then assume that
the user is allowed to see it.

Apply the same ownership-scoping principle to subscription and payment
detail pages, list pages, downloads/prints, and any action endpoints.

**IDOR protection:**

-   Changing an identifier in a URL must not expose another customer's
    record.
-   A customer must not be able to submit another customer's object ID
    to a form or service and operate on that record.
-   Do not disclose whether a foreign customer's record exists.
-   Return a safe not-found or access-denied response consistent with
    the application's established behavior.
-   Validate ownership again on write operations; a previously rendered
    page is not proof of current authorization.

The exact data model relationship between `User` and `Customer` must be
confirmed in implementation. The requirements define both entities and
state that Customer is linked to User, but do not prescribe the field
name or cardinality beyond the account/customer relationship.

------------------------------------------------------------------------

## 6. User interface and navigation

### 6.1 Authentication screens

The UI/UX specification defines the following screens and elements.

#### Sign-in screen

-   Email field.
-   Password field.
-   Sign-in action.
-   Forgot-password link.
-   Customer sign-up link.
-   Required-field validation.
-   Generic authentication error.
-   Role-based routing after successful authentication.

#### Customer sign-up screen

-   Email field.
-   Password field.
-   Confirm-password field (recommended).
-   Visible password-policy guidance.
-   No role selector.
-   Field-level validation feedback.

#### Forgot-password screen

-   Email field.
-   Submit action.
-   Neutral confirmation message regardless of whether the account
    exists.

#### Reset-password screen

-   New-password field.
-   Confirm-password field.
-   Visible password policy.
-   Clear expired/used-link explanation.
-   Link or action to request another reset.

### 6.2 Internal navigation

The internal application includes a User Management navigation item
visible to Admin only.

Staff must not see User Management controls. Customers use a separate
portal and must not see internal navigation.

### 6.3 Customer portal navigation

The customer portal navigation includes:

-   Overview
-   My subscriptions
-   My quotations
-   My invoices
-   Account / security

The Account / security area provides the account email, a password
reset/change entry point subject to the authentication implementation,
and sign out.

Editing other customer profile details is not specified.

### 6.4 Permission-aware interface

-   Hide or disable actions that the current role cannot perform.
-   Explain why an action is unavailable where appropriate.
-   Do not rely on interface visibility for security.
-   If a user directly requests an unauthorized URL/action, enforce the
    server-side permission check and show an access-denied result.
-   Preserve entered form data where possible after validation or
    recoverable network errors.

------------------------------------------------------------------------

## 7. Data and persistence requirements

### 7.1 Core entities

The requirements identify:

-   `User` --- login identity with a role (Admin, Staff, Customer).
-   `Customer` --- customer profile linked to a user.

The exact model fields and relationship implementation are not fully
specified.

### 7.2 User identity

-   Email is the login identity.
-   Email uniqueness is case-insensitive.
-   Enforce uniqueness at the database level using a case-insensitive
    unique index/constraint appropriate to the chosen PostgreSQL/Django
    model design.
-   Form validation should provide a useful error, but database
    enforcement is authoritative.
-   Ensure the chosen email normalization strategy is consistent across
    registration, login, Admin-created Staff accounts, and password
    reset.

### 7.3 Password storage

-   Use Django's built-in password hashing APIs and configured password
    hashers (PBKDF2/Argon2).
-   Store only the encoded password hash.
-   Never store a raw password in a model field, log, audit entry,
    email, or analytics event.
-   Never return a password or password hash to the client.
-   Never write passwords into fixtures or seed data as plaintext.

### 7.4 Database integrity

At minimum, persistence must enforce:

-   One account per case-insensitive email.
-   A valid role representation for the three supported roles.
-   A valid relationship between a Customer account and its Customer
    profile, according to the chosen model.

Use migrations for model and constraint changes. Do not edit migrations
that have already been applied.

------------------------------------------------------------------------

## 8. Security requirements

### 8.1 Authentication and password security

-   Use Django's authentication and password-hashing facilities.
-   Enforce the custom M1 password validator server-side.
-   Do not reveal whether an email exists through login or reset
    responses.
-   Use single-use, expiring Django reset tokens.
-   Never log credentials, password hashes, reset tokens, or reset
    links.

### 8.2 Authorization

-   Server-side RBAC on every protected view and service.
-   Central permission layer.
-   Default deny.
-   Only Admin can create Staff.
-   Ignore public signup role input.
-   Enforce customer ownership for every customer-facing record lookup
    and operation.

### 8.3 Web protections

-   Keep CSRF protection enabled.
-   Validate request data with Django forms or serializers.
-   Use ORM/parameterized queries; do not build SQL through string
    formatting.
-   Keep Django template auto-escaping enabled.
-   Do not use `safe` or `mark_safe` on user-provided values.
-   Do not expose stack traces, SQL errors, or internal exception
    details to users.

### 8.4 Abuse protection

Apply throttling or lockout protection to:

-   Login.
-   Customer signup.
-   Password-reset requests.

The requirements do not specify thresholds, cooldown durations, or
whether throttling is per IP, account, or both. Those values must be
selected and documented as implementation configuration rather than
represented as fixed product requirements.

### 8.5 Production configuration

Follow the project's security settings requirements:

-   Keep secrets out of source control.
-   Use environment variables for secrets and deployment configuration.
-   `DEBUG = False` in production.
-   Set `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` explicitly.
-   Configure `SECURE_SSL_REDIRECT`.
-   Configure `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE`.
-   Configure `SECURE_HSTS_SECONDS` and `SECURE_CONTENT_TYPE_NOSNIFF`.

------------------------------------------------------------------------

## 9. Application architecture and coding conventions

The project stack is Django, PostgreSQL, and Vercel. M1 belongs in
`apps/accounts/`.

Recommended responsibility boundaries, following `CODING_STANDARDS.md`:

  -----------------------------------------------------------------------
  Location                            Responsibility
  ----------------------------------- -----------------------------------
  `apps/accounts/models.py`           User/Customer data, role
                                      representation, constraints, and
                                      simple model properties.

  `apps/accounts/services.py`         Account creation and other
                                      write/business operations.

  `apps/accounts/selectors.py`        Complex read/query logic, if
                                      needed.

  `apps/accounts/views.py`            Parse request, invoke form/service,
                                      return response; keep views thin.

  `apps/accounts/forms.py`            Registration, login, password
                                      reset, and Staff creation input
                                      validation.

  `apps/accounts/permissions.py`      Central role and ownership
                                      authorization rules.

  `apps/accounts/urls.py`             Authentication and
                                      account-management routes.

  `apps/accounts/admin.py`            Django admin integration, subject
                                      to the project's Admin model
                                      design.

  `apps/accounts/tests/`              Authentication, password, RBAC, and
                                      isolation tests.

  `apps/accounts/migrations/`         Schema and constraint migrations.
  -----------------------------------------------------------------------

This is a responsibility map, not a requirement to create every file
regardless of need. Follow the existing project structure and avoid
unnecessary files.

### 9.1 Layering rules

-   Views are thin.
-   Business logic belongs in services.
-   Complex reads belong in selectors.
-   Models hold fields, constraints, and simple properties.
-   No external email calls from model `save()` methods.
-   Avoid circular imports.
-   Use Django built-ins before introducing dependencies.
-   Do not introduce a SPA framework, message queue, microservice, or
    event bus for M1.

### 9.2 Email boundary

Password-reset email delivery is required. Keep email sending behind the
project's email boundary so failures can be handled and the provider can
be changed without embedding provider logic in models or views.

Email delivery failure behavior must not expose secrets. The coding
standards state that email failures should be logged and retried without
rolling back unrelated business transactions. The precise retry
implementation and delivery provider are not specified in M1.

### 9.3 Deployment constraints

-   PostgreSQL is the single source of truth.
-   Do not use in-memory globals or local files for persistent
    account/session state.
-   Use database-backed sessions or signed cookies; do not rely on
    local-memory or file-backed sessions.
-   Vercel functions are stateless and may run in parallel or be
    recycled.
-   Do not write persistent data to the local filesystem.
-   Run migrations as an explicit deployment step, not during a request.

------------------------------------------------------------------------

## 10. Error and feedback behavior

  -----------------------------------------------------------------------
  Situation                           Expected behavior
  ----------------------------------- -----------------------------------
  Required field missing              Show field-level validation.

  Invalid email format                Show an email validation message.

  Email already registered            Reject signup and explain that the
                                      email cannot be used again.

  Email differs only by casing from   Treat it as a duplicate.
  an existing account                 

  Password too short                  Explain that it must contain more
                                      than 8 characters.

  Missing uppercase character         Identify the uppercase requirement.

  Missing lowercase character         Identify the lowercase requirement.

  Missing special character           Identify the special-character
                                      requirement.

  Password confirmation mismatch      Show a confirmation error.

  Invalid login credentials           Show a generic authentication
                                      error; do not identify which
                                      credential was wrong.

  Password-reset email submitted      Show neutral confirmation whether
                                      or not the account exists.

  Reset token expired                 Explain that the link expired and
                                      offer a new reset request.

  Reset token already used            Explain that the link is no longer
                                      valid and offer a new reset
                                      request.

  User lacks role permission          Deny the operation; do not expose
                                      the protected action as available.

  Customer requests another           Deny access without disclosing
  customer's record                   whether the record exists.

  Login/signup/reset throttled        Show a safe retry-later message
                                      without exposing internal
                                      rate-limit details.

  Network/server failure              Show a generic safe error and
                                      preserve form input where possible.
  -----------------------------------------------------------------------

All system errors must be logged with useful operational context but
without passwords, reset tokens, reset links, or unnecessary personal
data.

------------------------------------------------------------------------

## 11. Acceptance criteria

M1 is functionally acceptable only when all applicable criteria below
are demonstrated.

### 11.1 Registration

-   [ ] A visitor can register with a valid email and a compliant
    password.
-   [ ] The created account receives the Customer role.
-   [ ] The public form does not offer a role selector.
-   [ ] A crafted public signup request containing `role=Admin` or
    `role=Staff` cannot create a privileged account.
-   [ ] An email already used by an account is rejected.
-   [ ] An email differing only by case is also rejected.
-   [ ] Database-level uniqueness protects against concurrent duplicate
    registration.
-   [ ] Password confirmation, if present, must match.

### 11.2 Password policy and storage

-   [ ] Passwords of 8 characters or fewer are rejected.
-   [ ] Passwords without an uppercase character are rejected.
-   [ ] Passwords without a lowercase character are rejected.
-   [ ] Passwords without a special character are rejected.
-   [ ] A password meeting all four rules is accepted.
-   [ ] The policy is enforced server-side, not only in browser
    JavaScript.
-   [ ] Stored credentials are salted password hashes, not plaintext.
-   [ ] Passwords and password hashes do not appear in logs or
    responses.

### 11.3 Sign in and sign out

-   [ ] A valid Admin can sign in and reach the internal application.
-   [ ] A valid Staff user can sign in and reach the internal
    application.
-   [ ] A valid Customer can sign in and reach the customer portal.
-   [ ] Email identity is case-insensitive.
-   [ ] Invalid credentials produce a generic error.
-   [ ] Sign out ends the authenticated session.

### 11.4 Password reset

-   [ ] A user can submit an email address to request a reset.
-   [ ] The response does not disclose whether the account exists.
-   [ ] A registered account receives a reset link through the
    configured email path.
-   [ ] A valid reset link allows the user to set a compliant password.
-   [ ] A reset token cannot be reused.
-   [ ] An expired token cannot be used.
-   [ ] Invalid/expired/used links show a safe explanation and a
    new-request path.
-   [ ] Reset tokens and links are not logged.

### 11.5 Staff account management

-   [ ] An Admin can create a Staff account.
-   [ ] A Staff user cannot create a Staff account through the UI or a
    direct request.
-   [ ] A Customer cannot create a Staff account through the UI or a
    direct request.
-   [ ] Public signup cannot create Staff or Admin accounts.
-   [ ] Duplicate email rules apply to Admin-created accounts as well.

### 11.6 RBAC and customer isolation

-   [ ] Each role is allowed only the capabilities granted by
    `REQUIREMENTS.md` Section 4.
-   [ ] Every unlisted capability is denied by default.
-   [ ] Authorization is checked server-side on every protected
    endpoint.
-   [ ] Hiding a control is not the only permission enforcement.
-   [ ] A Customer can list and view only their own subscriptions.
-   [ ] A Customer can list and view only their own invoices.
-   [ ] A Customer can view only their own payment information.
-   [ ] Changing a URL/object identifier cannot expose another
    customer's data.
-   [ ] Write/action endpoints also enforce customer ownership.
-   [ ] Unauthorized requests do not reveal whether another customer's
    record exists.

------------------------------------------------------------------------

## 12. Test plan

Use `pytest` and `pytest-django`, with `factory-boy` where useful, as
specified by the coding standards. Tests must not call real external
services.

### 12.1 Registration and email uniqueness

Test cases:

1.  Successful customer registration.
2.  Missing email.
3.  Invalid email format.
4.  Missing password.
5.  Duplicate email with identical casing.
6.  Duplicate email with different casing.
7.  Concurrent duplicate registration attempts; the database constraint
    must prevent two accounts.
8.  Signup request includes a forged Admin role.
9.  Signup request includes a forged Staff role.
10. Signup request includes privilege-related fields.

### 12.2 Password validation and hashing

Test each policy rule independently, including boundary length:

-   8 characters → rejected.
-   9 characters with all required character classes → accepted.
-   No uppercase → rejected.
-   No lowercase → rejected.
-   No special character → rejected.

Also verify:

-   Stored password is not equal to the raw password.
-   Django password verification accepts the correct password.
-   Django password verification rejects an incorrect password.
-   No password value is written to logs.

### 12.3 Authentication

Test:

-   Successful Admin login.
-   Successful Staff login.
-   Successful Customer login.
-   Case-insensitive email login.
-   Incorrect password.
-   Unknown email.
-   Generic response equivalence for unknown email and incorrect
    password.
-   Session termination on logout.
-   Role-based destination behavior.

### 12.4 Password reset

Test:

-   Reset request for an existing account.
-   Reset request for an unknown email.
-   Same public response for both cases.
-   Reset email generated through a test email backend.
-   Valid token accepted.
-   Token rejected after use.
-   Expired token rejected.
-   Password-policy failure on reset.
-   Password confirmation mismatch.
-   Reset link/token absent from application logs.

### 12.5 Staff management and RBAC

Test each role against both allowed and denied operations:

-   Admin creates Staff.
-   Staff cannot create Staff.
-   Customer cannot create Staff.
-   Customer cannot access User Management.
-   Staff cannot access User Management.
-   Admin-only catalog/configuration permissions remain protected.
-   Staff permissions match the matrix.
-   Customer cannot access internal dashboard/report routes.
-   Unlisted capabilities are denied.

### 12.6 Customer data isolation

Create at least two customers, each with separate subscriptions,
invoices, and payments. Verify:

-   Customer A sees only Customer A's records.
-   Customer B sees only Customer B's records.
-   Customer A cannot open Customer B's record by changing a URL ID.
-   Customer A cannot submit Customer B's ID to a write/action endpoint.
-   List, detail, print/download, and action queries all enforce
    ownership.
-   Unauthorized responses do not disclose whether the foreign record
    exists.

### 12.7 Required checks

Before accepting an implementation:

-   `ruff check .`
-   `ruff format .` (or the project's selected formatter)
-   `python manage.py makemigrations --check --dry-run`
-   Relevant pytest suite.
-   `pip-audit` (or equivalent) before release.

Report a check as **not run** if it was not actually executed.

------------------------------------------------------------------------

## 13. Open decisions and assumptions

The source documents are drafts and explicitly leave some implementation
details open. These points must be confirmed or recorded as assumptions
before they are treated as final behavior.

  -------------------------------------------------------------------------
  Topic                   What the source says    Decision still needed
  ----------------------- ----------------------- -------------------------
  Initial Admin           Admin is a role and can How the first Admin
  provisioning            create Staff.           account is securely
                                                  provisioned.

  Staff onboarding        Only Admin can create   Required fields,
                          Staff.                  invitation vs. temporary
                                                  password, activation, and
                                                  first-login behavior.

  Reset expiry            Reset links are         Exact validity
                          time-limited.           duration/configuration.

  Abuse protection        Login, signup, and      Thresholds, window,
                          reset need throttling   cooldown, and keying
                          or lockout.             strategy.

  Email verification      Not specified.          Whether customer signup
                                                  requires verification
                                                  before portal access.

  Session policy          Database-backed         Session expiry, idle
                          sessions or signed      timeout, and
                          cookies; no             concurrent-session
                          local-memory/file       behavior.
                          dependency.             

  User lifecycle          Admin creates Staff.    Whether Admin can edit,
                                                  deactivate, reactivate,
                                                  or delete Staff accounts.

  Customer profile        A Customer profile is   Exact profile fields and
                          linked to a User.       relationship
                                                  implementation.

  Account email changes   Not specified.          Whether users can change
                                                  their email and how the
                                                  change is verified.

  MFA/social login        Not specified.          Excluded from M1 unless
                                                  separately approved.
  -------------------------------------------------------------------------

### 13.1 Explicit implementation assumptions to avoid

Do not silently assume:

-   That the first registered user becomes Admin.
-   That the first Admin is created through public signup.
-   That Staff can invite or create other Staff.
-   That password reset links last a particular number of minutes or
    hours.
-   That email verification is mandatory.
-   That a Customer can edit their email or profile.
-   That a Customer can access another Customer's records because an
    identifier is guessable.
-   That a hidden UI button is sufficient authorization.

If a decision is required to proceed, record the chosen assumption in
implementation/PR notes and seek confirmation for product-level
behavior.

------------------------------------------------------------------------

## 14. Definition of done

M1 is complete when:

-   [ ] FR-1.1 through FR-1.8 are implemented.
-   [ ] Registration always creates a Customer account.
-   [ ] Email uniqueness is case-insensitive and database-enforced.
-   [ ] The exact password policy is enforced server-side.
-   [ ] Passwords are stored using Django's salted password hashers.
-   [ ] Login and role-based routing work for all three roles.
-   [ ] Password reset is single-use, expiring, and
    enumeration-resistant.
-   [ ] Only Admin can create Staff.
-   [ ] RBAC is centralized, server-side, and default-deny.
-   [ ] Customer subscriptions, invoices, and payments are isolated by
    ownership.
-   [ ] CSRF and the required production security settings are enabled.
-   [ ] Login, signup, and password reset have abuse protection.
-   [ ] Success and failure paths have automated tests.
-   [ ] Migrations are included and consistent.
-   [ ] No secrets, plaintext credentials, debug statements, or dead
    code remain.
-   [ ] The feature respects PostgreSQL and Vercel stateless/serverless
    constraints.
-   [ ] The implementation self-review is completed.

------------------------------------------------------------------------

## 15. Source of truth and conflict handling

Use the documents in this order for M1:

1.  `REQUIREMENTS.md` --- authoritative definition of what the product
    must do, especially FR-1.1--FR-1.8 and Section 4.
2.  `CODING_STANDARDS.md` --- mandatory implementation, architecture,
    security, testing, and deployment rules.
3.  `UI_UX.md` --- screen content, navigation, user flows, and expected
    feedback.

This file consolidates the M1 requirements from those documents. It does
not claim that the feature is already implemented. Where the documents
do not define a behavior, the gap is called out in Section 13 rather
than silently filled with an invented requirement.
