# Brightloop · Subscription & Revenue Operations Platform

A clear, unified workspace for recurring subscriptions, billing runs, invoicing, and revenue operations.

---

## 🌟 Overview

Brightloop is a production-grade subscription management and automated billing engine built with **Django 5.2** and **Python 3.11+**. It manages the complete contract-to-cash lifecycle for recurring software businesses, from product and plan configuration to subscription management, automated billing, payment collection, and revenue analytics.

### 🔄 Contract-to-Cash Lifecycle

**Product & Plan Setup** → **Quotations** → **Subscriptions** → **Automated Billing** → **Payment Collection** → **Revenue Analytics**

### Core Problems Solved
- **No Missed Renewals**: Scheduled automation tracks next billing dates, automatically triggering recurring cycles or retries for failed payments.
- **Accurate Invoicing**: Automated batch billing runs generate locked, tax-calculated, discount-adjusted invoices without manual entry.
- **Zero Double-Billing**: Every period and subscription contract is idempotency-guaranteed; processed cycles are never billed twice.
- **Unified Finance Visibility**: Real-time receivables aging, payment success rates, MRR growth, and portfolio health at a glance.

---

## 🚀 Key Features & Modules

### 1. Workspace
- **Executive Dashboard**: Real-time KPIs (Active Subscriptions, Revenue Collected, Outstanding Receivables, Overdue Invoices, Failed Renewals) with dynamic trend sparklines, revenue bar charts, and subscription health donut breakdowns.
- **Subscription Lifecycle Engine**: Full contract state machine:
  $$\text{Draft} \longrightarrow \text{Quotation} \longrightarrow \text{Confirmed} \longrightarrow \text{Active} \longleftrightarrow \text{Paused} \longrightarrow \text{Closed}$$
- **Quotation Templates**: Reusable commercial templates with validity windows and conversion tracking.
- **Mid-Cycle Proration**: Automatic proration calculations for upgrades, downgrades, and quantity changes.

### 2. Finance & Billing
- **Automated Billing Runs**: Daily batch execution that generates draft invoices for all due contracts, tracking processed, created, skipped, and failed counts.
- **Invoicing System**: Multi-line item invoices with frozen tax rates, discount snapshots, and printable PDF layouts.
- **Receivables & Aging**: Automatic bucket categorization (`Current`, `1–30d`, `31–60d`, `61–90d`, `90+d`) and automated dunning reminders.
- **Payment Processing**: Record manual payments (Bank Transfer, Cash, Card, Cheque) or run transactions through the built-in test payment gateway.

### 3. Configuration & Catalog
- **Products & Variants**: Service and physical goods catalog with dimension adjustments.
- **Pricing Plans**: Daily, weekly, monthly, and yearly recurring periods with minimum quantity rules and availability windows.
- **Discounts Engine**: Fixed-value and percentage-based discounts with customer usage caps and subscription-wide or item-level scopes.
- **Taxes & Payment Terms**: Custom tax rates and standard terms (`Net 15`, `Net 30`, `Net 60`, `Immediate`).

### 4. Customer Self-Service Portal
- Dedicated customer workspace allowing clients to view their active contracts, inspect line items, download invoice records, and manage security credentials.

---

## 🎨 UI & Design System

Brightloop features an **Atlas-inspired design system** ported from modern React/Next.js design tokens:
- **Palette**: Deep navy-green navigation chrome (`#001e2b`), forest-green brand accents (`#00684a`), and neon-green highlights (`#00ed64`).
- **Data Visualizations**: 100% lightweight, dependency-free inline SVG and CSS charts:
  - **Revenue Overview Bar Chart**: Responsive weekly/monthly billing volume bars.
  - **Portfolio Health Donut**: CSS `conic-gradient` distribution of subscription statuses.
  - **Receivables Aging Spectrum**: Multi-color proportional debt aging indicator.
  - **Payment Success Semicircle Gauge**: Real-time payment collection success rate indicator.
  - **MRR Growth Area Chart**: Actual monthly recurring revenue plotted against plan trajectory.
  - **Billing Run Stacked Bars**: Historical run outcome tracker (invoiced vs skipped vs failed).

---

## 💻 Tech Stack

- **Backend**: Python 3.11+, Django 5.2
- **Database**: PostgreSQL (production via Neon/Supabase) / SQLite (local development)
- **Styling**: Modern Semantic CSS with CSS Variables & Responsive Flex/Grid
- **Testing**: Pytest, Pytest-Django, Factory Boy, Faker
- **Linting & Formatting**: Ruff (`ruff.toml`)
- **Deployment**: Vercel Serverless (`vercel.json`), Docker Compose

---

## 🛠️ Quickstart Guide

### 1. Prerequisites
- Python 3.11 or higher
- Git

### 2. Clone and Setup Environment
```bash
git clone https://github.com/your-org/brightloop.git
cd brightloop

# Create and activate virtual environment
python -m venv .venv

# Windows:
.\.venv\Scripts\activate

# macOS / Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
For local development using SQLite, leave `DATABASE_URL` commented out in `.env`.

### 4. Run Migrations & Seed Demo Data
```bash
# Run database schema migrations
python manage.py migrate

# Seed rich mock demo data (Customers, Plans, Invoices, Subscriptions, Payments)
python manage.py seed_ui_data
```

### 5. Start the Development Server
```bash
python manage.py runserver
```
Visit `http://localhost:8000` in your browser.

---

## 🔑 Demo Credentials

The database is pre-seeded with test accounts for each role:

| Role | Email | Password | Access Area |
|---|---|---|---|
| **Admin** | `admin@brightloop.com` | `Admin#12345` | Full system, catalog, plans, users, billing |
| **Staff** | `staff@brightloop.com` | `Staff#12345` | Customer operations, subscriptions, payments |
| **Customer** | `acme.corp@example.com` | `Customer#12345` | Customer self-service portal (`/portal/`) |

---

## 🧪 Testing & Code Quality

Brightloop comes with an exhaustive test suite covering state transitions, role permissions, tax math, proration, and dunning cadences.

```bash
# Run test suite
pytest

# Run tests with coverage
pytest --cov=apps

# Run linter and formatting checks
ruff check .
ruff format --check .
```

---

## ⏰ Automated Scheduled Jobs

Brightloop includes automated commands designed to run as periodic cron jobs:
- **Daily Billing Run**: `python manage.py run_daily_billing`
- **Auto-Renewals & Dunning**: `python manage.py process_renewals_and_dunning`

---

## 📂 Project Structure

```
26-10-31-Brightloop/
├── apps/
│   ├── accounts/         # Auth, RBAC permissions, Customer profiles, Portal
│   ├── billing/          # Invoices, Billing runs, Tax calculations
│   ├── catalog/          # Products, Variants, Taxes, Payment Terms
│   ├── discounts/        # Discount rules, coupons, validation
│   ├── payments/         # Payment recording, Gateways, Dunning
│   ├── plans/            # Commercial plans, Pricing tiers, Lifecycles
│   └── subscriptions/    # Contracts, Quotations, Lines, Renewals
├── config/               # Django project settings, WSGI/ASGI, URLs
├── instructions/         # Requirements, UI/UX specs, Coding standards
├── templates/            # Django HTML templates with embedded SVG charts
├── manage.py
├── pytest.ini
├── requirements.txt
├── ruff.toml
└── vercel.json           # Serverless deployment configuration
```

---

## 📄 License

This project is proprietary and confidential. Copyright © 2026 Brightloop Software.
