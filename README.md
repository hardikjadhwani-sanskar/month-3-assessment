# Vendor Portal

A Frappe/ERPNext application for end-to-end vendor lifecycle management — from self-service onboarding through purchase automation, delivery scoring, and performance analytics.

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [DocType Reference](#doctype-reference)
- [API Documentation](#api-documentation)
- [Override Documentation](#override-documentation)
- [Scheduled Jobs](#scheduled-jobs)
- [Client Scripts](#client-scripts)
- [Web Portal Pages](#web-portal-pages)
- [Script Reports](#script-reports)
- [Print Format](#print-format)
- [Data Patches](#data-patches)
- [Permissions & Roles](#permissions--roles)
- [Running Tests](#running-tests)
- [Assumptions](#assumptions)
- [Limitations](#limitations)
- [Known Issues](#known-issues)

---

## Overview

Vendor Portal extends ERPNext's procurement module with:

- **Vendor Onboarding** — structured application workflow with GST/PAN validation, document collection, and Purchase Manager approval
- **Vendor Ratings** — automated scoring on Purchase Order submit (Pricing) and Purchase Receipt submit (Delivery), plus manual ratings from desk forms
- **Blacklist Enforcement** — blocks PO creation for blacklisted suppliers at the controller level
- **Rating Threshold Enforcement** — blocks POs when supplier rating falls below category minimums
- **Self-Service Web Portal** — public-facing registration and status-check pages requiring no Frappe login
- **Vendor Dashboard** — Frappe page with live charts (rating distribution, delivery trend, PO value by category)
- **Performance Reports** — two Script Reports for procurement analytics
- **Scheduled Automation** — daily rating recalculation, weekly email digests, stale onboarding expiry
- **Bulk Import** — CSV-based vendor onboarding via background queue


---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.14+ |
| Node.js | 24+ |
| Frappe Framework | v16.x |
| ERPNext | v16.x |
| MariaDB | 10.6+ |
| Redis | 6+ |

---

## Installation

### 1. Initialize bench and create site

```bash
bench init vendor-bench --frappe-branch version-16
cd vendor-bench
bench new-site vendor.localhost
```

### 2. Install ERPNext

```bash
bench get-app erpnext --branch version-16
bench --site vendor.localhost install-app erpnext
```

### 3. Install Vendor Portal

```bash
# From PyPI / git
bench get-app vendor_portal https://github.com/hardikjadhwani-sanskar/month-3-assessment

bench --site vendor.localhost install-app vendor_portal
```

### 4. Run migrations and build assets

```bash
bench --site vendor.localhost export-fixtures
bench --site vendor.localhost migrate
bench build --app vendor_portal
bench --site vendor.localhost clear-cache
```

### 5. Start bench

```bash
bench start
```

Open `http://vendor.localhost:8000` and complete the ERPNext setup wizard.

---

## Configuration

### Vendor Portal Settings

Navigate to: **Awesome Bar → Vendor Portal Settings**

| Field | Default | Description |
|---|---|---|
| `auto_create_supplier` | ✅ | Auto-create Supplier record on onboarding approval |
| `default_supplier_group` | — | Supplier Group assigned to auto-created suppliers |
| `require_gst_verification` | ✅ | Enforce GST format validation on onboarding |
| `min_documents_required` | 2 | Minimum documents vendor must attach |
| `rating_weight_delivery` | 0.3 | Weight for Delivery in weighted avg rating |
| `rating_weight_quality` | 0.3 | Weight for Quality in weighted avg rating |
| `rating_weight_pricing` | 0.2 | Weight for Pricing in weighted avg rating |
| `rating_weight_communication` | 0.2 | Weight for Communication in weighted avg rating |
| `auto_rating_enabled` | ✅ | Enable automatic rating on PO/PR submit |
| `low_rating_threshold` | 2.5 | Rating below this triggers alerts |


### Custom Fields on Supplier

These are installed automatically via fixtures on `bench migrate`:

| Field Name | Type | Purpose |
|---|---|---|
| `custom_vendor_category` | Link → Vendor Category | Assigns vendor to a category |
| `custom_vendor_rating` | Rating | Weighted average score (auto-calculated) |
| `custom_total_rating_count` | Int | Total number of rating log entries |
| `custom_onboarding_reference` | Link → Vendor Onboarding | Back-reference to originating onboarding |
| `custom_is_blacklisted` | Check | Blocks all PO creation when enabled |
| `custom_blacklist_reason` | Small Text | Reason stored for audit trail |

---

## DocType Reference

### A. Vendor Category

**Module:** Vendor Portal  
**Naming:** `field:category_name`  
**Purpose:** Groups suppliers into categories with rating thresholds.

| Field | Type | Rules |
|---|---|---|
| `category_name` | Data | Mandatory, Unique |
| `description` | Small Text | — |
| `default_payment_terms` | Link → Payment Terms Template | — |
| `minimum_rating_threshold` | Float | Default 3.0. POs blocked if supplier rating < this |
| `is_active` | Check | Default 1. Inactive categories excluded from dropdowns |

---

### B. Vendor Onboarding

**Module:** Vendor Portal  
**Naming:** `VOB-.YYYY.-.#####`  
**Submittable:** Yes  
**Workflow:** Vendor Onboarding Approval

The primary document for vendor applications. Submitting triggers the workflow. Approval auto-creates a Supplier record.

| Field | Type | Rules |
|---|---|---|
| `supplier_name` | Data | Mandatory |
| `company_name` | Data | Mandatory |
| `email` | Data | Mandatory, validated format |
| `phone` | Data | Mandatory |
| `gst_number` | Data | Validated: 15-char alphanumeric (2-digit state + PAN + entity + Z + check) |
| `pan_number` | Data | Validated: AAAAA9999A format |
| `vendor_category` | Link → Vendor Category | Mandatory |
| `bank_name` | Data | — |
| `bank_account_number` | Data | — |
| `ifsc_code` | Data | — |
| `address_line_1` | Data | Mandatory |
| `city` | Data | Mandatory |
| `state` | Data | Mandatory |
| `pincode` | Data | — |
| `contact_person` | Data | — |
| `documents` | Table → Vendor Document | Min count enforced by settings |
| `onboarding_status` | Select | Draft / Under Review / Approved / Rejected — read_only, workflow-controlled |
| `reviewed_by` | Link → User | read_only, set on approve/reject |
| `review_date` | Datetime | read_only, set on approve/reject |
| `rejection_reason` | Small Text | Populated by `reject_onboarding()` |
| `linked_supplier` | Link → Supplier | read_only, set after Supplier creation |

**Workflow transitions:**

```
Draft ──[Submit for Review / Purchase User]──► Under Review
                                                    │
                          [Approve / Purchase Manager]├──► Approved
                                                    │
                          [Reject / Purchase Manager] └──► Rejected
                                                              │
                        [Resubmit / Purchase User] ◄──────────┘
```

**docstatus mapping:**

| State | doc_status | Editable |
|---|---|---|
| Draft | 0 | ✅ Yes |
| Under Review | 1 | ❌ No |
| Approved | 1 | ❌ No |
| Rejected | 1 | ❌ No |


---

### C. Vendor Document _(Child Table)_

**Parent:** Vendor Onboarding  
**Purpose:** Stores uploaded compliance documents.

| Field | Type | Rules |
|---|---|---|
| `document_type` | Select | GST Certificate / PAN Card / Bank Statement / Trade License / MSME Certificate / Other — Mandatory |
| `document_file` | Attach | Mandatory |
| `is_verified` | Check | Default 0 |
| `verified_by` | Data | read_only |
| `remarks` | Small Text | — |

---

### D. Vendor Rating Log

**Module:** Vendor Portal  
**Naming:** `VRL-.YYYY.-.#####`  
**Purpose:** Immutable audit log of all supplier ratings — auto-generated and manual.

| Field | Type | Rules |
|---|---|---|
| `supplier` | Link → Supplier | Mandatory |
| `purchase_order` | Link → Purchase Order | Optional — set for Pricing ratings |
| `purchase_receipt` | Link → Purchase Receipt | Optional — set for Delivery ratings |
| `rating_type` | Select | Delivery / Quality / Pricing / Communication — Mandatory |
| `score` | Float | Mandatory, 1–5 |
| `remarks` | Small Text | — |
| `rated_by` | Link → User | read_only, defaults to `frappe.session.user` |
| `rating_date` | Date | read_only, defaults to today |

Score is always stored as a raw float (1.0–5.0). The Frappe Rating field widget in forms returns 0.0–1.0 — multiply by 5 before passing to API.

---

### E. Vendor Portal Settings _(Single DocType)_

**Module:** Vendor Portal  
**Is Single:** Yes  
**Purpose:** Central configuration for the entire app. See [Configuration](#configuration) for field details.

---

## API Documentation

All endpoints are in `vendor_portal/api.py` and decorated with `@frappe.whitelist()`.  
Call from JS: `frappe.call({ method: "vendor_portal.api.<function>", args: {...} })`

---

### `get_vendor_dashboard(supplier)`

Returns comprehensive stats for a supplier's dashboard section.

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `supplier` | str | ✅ | Supplier document name |

**Response:**

```json
{
  "total_pos": 12,
  "total_po_value": 450000.00,
  "total_receipts": 10,
  "pending_receipts": 2,
  "total_invoiced": 380000.00,
  "outstanding_amount": 70000.00,
  "avg_rating": 4.2,
  "total_ratings": 24,
  "rating_breakdown": [
    { "rating_type": "Delivery", "avg_score": 4.5, "count": 10 },
    { "rating_type": "Pricing",  "avg_score": 3.8, "count": 10 }
  ],
  "recent_ratings": [...]
}
```

---

### `submit_vendor_rating(supplier, rating_type, score, remarks, purchase_order?, purchase_receipt?)`

Creates a Vendor Rating Log and recalculates the supplier's weighted average rating.

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `supplier` | str | ✅ | Supplier name |
| `rating_type` | str | ✅ | Delivery / Quality / Pricing / Communication |
| `score` | float | ✅ | 1.0 – 5.0 (validated server-side) |
| `remarks` | str | — | Free text notes |
| `purchase_order` | str | — | Link to PO (used for Pricing type) |
| `purchase_receipt` | str | — | Link to PR (used for Delivery type) |

**Response:**

```json
{ "name": "VRL-2026-00042", "score": 4.0 }
```

**Error:** Throws `ValidationError` if score is outside 1–5.

---

### `get_vendor_rating_history(supplier)`

Fetches the 50 most recent Vendor Rating Log entries for a supplier.

**Parameters:**

| Name | Type | Required |
|---|---|---|
| `supplier` | str | ✅ |

**Response:**

```json
[
  {
    "name": "VRL-2026-00042",
    "rating_date": "2026-06-01",
    "rating_type": "Delivery",
    "score": 5.0,
    "remarks": "On time, full quantity",
    "rated_by": "admin@company.com"
  }
]
```

---

### `create_vendor_rating_log(supplier, rating_type, score, remarks, purchase_order?, purchase_receipt?)`

Alias for `submit_vendor_rating`. Used directly from JavaScript form dialogs.

---

### `get_supplier_comparison(item_code, qty?)`

Returns all suppliers who have previously supplied an item, with ratings and pricing stats. Useful for vendor selection on a new PO.

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `item_code` | str | ✅ | Item to compare suppliers for |
| `qty` | float | — | Planned quantity (currently informational) |

**Response:**

```json
[
  {
    "supplier": "SUP-001",
    "supplier_name": "ABC Supplies",
    "vendor_rating": 4.3,
    "vendor_category": "Raw Materials",
    "last_rate": 250.00,
    "avg_rate": 245.00,
    "total_supplied_qty": 500,
    "delivery_score": 4.5
  }
]
```

---

### `get_onboarding_status_summary()`

Returns pipeline counts for the Vendor Dashboard widget.

**Response:**

```json
{
  "total_pending": 5,
  "total_approved": 23,
  "total_rejected": 4,
  "total_draft": 2,
  "recent_submissions": [...]
}
```

---

### `vendor_portal.vendor_portal.doctype.vendor_onboarding.vendor_onboarding.approve_onboarding(onboarding_name)`

Approves a Vendor Onboarding, auto-creates a Supplier record, and sends approval email.

**Roles required:** Purchase Manager

**Parameters:**

| Name | Type | Required |
|---|---|---|
| `onboarding_name` | str | ✅ |

**Response:** Supplier document name (string)

**Side effects:**
- Sets `onboarding_status = Approved`
- Sets `reviewed_by`, `review_date`
- Creates Supplier with mapped fields
- Sets `linked_supplier` on onboarding
- Sends email to vendor's registered address

---

### `vendor_portal.vendor_portal.doctype.vendor_onboarding.vendor_onboarding.reject_onboarding(onboarding_name, reason)`

Rejects a Vendor Onboarding with a mandatory reason.

**Roles required:** Purchase Manager

**Parameters:**

| Name | Type | Required |
|---|---|---|
| `onboarding_name` | str | ✅ |
| `reason` | str | ✅ |

**Side effects:**
- Sets `onboarding_status = Rejected`
- Sets `rejection_reason`, `reviewed_by`, `review_date`
- Sends rejection email to vendor

---

### `vendor_portal.www.vendor_register.submit_vendor_registration(**kwargs)` _(allow\_guest=True)_

Public API — no Frappe login required. Creates a Draft Vendor Onboarding from the web registration form.

**Response:**

```json
{ "name": "VOB-2026-00012", "status": "Draft" }
```

---

### `vendor_portal.www.vendor_status.get_status(query)` _(allow\_guest=True)_

Looks up onboarding status by reference number or email address.

**Response:** Vendor Onboarding dict or `null`.

---

### `vendor_portal.api_bulk.bulk_import_vendors(csv_data)`

Accepts a CSV string and enqueues bulk Vendor Onboarding creation as a background job.

**CSV columns (header row required):**

```
supplier_name, company_name, email, phone, gst_number, pan_number,
vendor_category, address_line_1, city, state, pincode
```

**Limits:** Maximum 500 rows per call.

**Response:**

```json
{ "queued": 42, "message": "42 vendors queued for import." }
```

Results are emailed to the submitting user when the background job completes.

---

## Override Documentation

Two distinct override patterns are used in this app. The choice between them is deliberate and documented here.

---

### Pattern 1: `override_doctype_class` — Purchase Order

**File:** `vendor_portal/overrides/purchase_order.py`  
**Class:** `CustomPurchaseOrder(PurchaseOrder)`  
**Registered in hooks.py:**
```python
override_doctype_class = {
    "Purchase Order": "vendor_portal.overrides.purchase_order.CustomPurchaseOrder"
}
```

**Why this pattern for Purchase Order:**

Purchase Order validation needs to intercept and **abort** ERPNext's own submit flow — specifically to throw a hard `frappe.throw()` that prevents the document from saving. This requires inheriting from ERPNext's `PurchaseOrder` class and calling `super()` explicitly so the original logic still runs, then layering custom checks on top.

`doc_events` cannot cancel or modify the result of ERPNext's own `validate()` — hooks always run *after* the original method. With `override_doctype_class`, we control the method call order.

**Methods overridden:**

| Method | `super()` called | Custom behavior |
|---|---|---|
| `validate()` | ✅ First | Block blacklisted suppliers; enforce rating threshold |
| `on_submit()` | ✅ First | Auto-create Pricing rating log |
| `on_cancel()` | ✅ First | Delete linked rating logs |

**Rule: always call `super()` first.** ERPNext's `on_submit()` handles stock reservation and GL entries. Calling it after custom code risks those entries seeing partially-modified state.

---

### Pattern 2: `doc_events` — Purchase Receipt, Supplier, Vendor Onboarding

**File:** `vendor_portal/overrides/purchase_receipt.py`  
**Registered in hooks.py:**
```python
doc_events = {
    "Purchase Receipt": {
        "validate":     "vendor_portal.overrides.purchase_receipt.validate",
        "after_insert": "vendor_portal.overrides.purchase_receipt.insert_comment",
        "on_update":    "vendor_portal.overrides.purchase_receipt.insert_comment",
        "on_submit":    "vendor_portal.overrides.purchase_receipt.on_submit",
    }
}
```

**Why this pattern for Purchase Receipt:**

Purchase Receipt only needs **side effects** — creating rating logs, adding comments, showing warnings. It does not need to modify or intercept ERPNext's own receipt processing (stock ledger entries, valuation, etc.). `doc_events` is the correct tool: lighter, simpler, and allows multiple apps to hook the same event simultaneously.

Function signatures take `(doc, method)` instead of `self`. No `super()` needed — ERPNext's original code runs independently.

**Functions registered:**

| Hook | Function | Purpose |
|---|---|---|
| `validate` | `validate(doc, method)` | Detect short delivery; set `doc.flags.has_short_delivery`; queue comment via `doc._pending_comment` |
| `after_insert` | `insert_comment(doc, method)` | Write the short delivery comment to DB (doc now exists in DB) |
| `on_update` | `insert_comment(doc, method)` | Same — covers re-saves |
| `on_submit` | `on_submit(doc, method)` | Auto-create Delivery rating log with score 2–5 |

**Key design decisions in Purchase Receipt:**

1. **Why not `add_comment()` in `validate`?**  
   On a first save, the document has not been committed to the DB yet. `add_comment()` creates a `Comment` record with `reference_name = doc.name` — if that name doesn't exist in the DB, Frappe's link validation throws `Could not find Reference Name`. Solution: set `doc._pending_comment` in `validate`, then write the comment in `after_insert`/`on_update` when the doc is guaranteed to be in the DB.

2. **Why raw SQL for comment insert instead of `frappe.get_doc().insert()`?**  
   `frappe.get_doc({...}).insert()` runs Frappe's full link validation pipeline. Even in `after_insert`, there are edge cases (new doc within same transaction) where the reference check fails. Raw `INSERT INTO tabComment` bypasses this entirely while still writing to the same table.

3. **Why `doc.flags` and `doc._pending_comment` instead of a DB field?**  
   `flags` is an in-memory object that lives only for the current HTTP request. Since `validate`, `after_insert`, and `on_update` all run within the same request when a user saves a document, the flag set in `validate` is readable in `insert_comment` without any DB round-trip or schema changes.

---

### Pattern Comparison Table

| Criterion | `override_doctype_class` | `doc_events` |
|---|---|---|
| Function signature | `self` (class method) | `fn(doc, method)` |
| `super()` required | ✅ Yes | ❌ No |
| Can intercept/cancel ERPNext's own logic | ✅ Yes | ❌ No |
| Multiple apps can hook same event | ❌ Only one class wins | ✅ All hooks fire |
| Complexity | Higher | Lower |
| Best for | Changing or gating core doctype behaviour | Side effects, logging, notifications |
| Used for | Purchase Order | Purchase Receipt, Supplier, Vendor Onboarding |

---

## Scheduled Jobs

Registered in `hooks.py` under `scheduler_events`. File: `vendor_portal/tasks.py`.

| Job | Schedule | Function | Description |
|---|---|---|---|
| Auto Calculate Ratings | Daily | `auto_calculate_vendor_ratings` | Recalculates weighted avg rating for all suppliers with a vendor category. Sends low-rating alert if below threshold |
| Auto Rate Deliveries | Hourly | `auto_rate_deliveries` | Finds PRs submitted in the last 2 hours with no Delivery rating. Creates rating automatically |
| Vendor Performance Digest | Weekly | `vendor_performance_digest` | Emails HTML digest to all Vendor Manager users: top/bottom 5 suppliers, weekly PO stats, new onboardings |
| Auto Expire Stale Onboardings | Daily + Cron 9am | `auto_expire_stale_onboardings` | Sends reminder to Vendor Managers for onboardings stuck in Under Review > 7 days. Auto-rejects after 14 days |

**To trigger a job manually:**
```bash
bench --site vendor.localhost execute vendor_portal.tasks.auto_calculate_vendor_ratings
```

---

## Client Scripts

All JS files are loaded via `app_include_js` in `hooks.py` — globally on the desk, but form events only activate on the relevant form.

### `public/js/purchase_order.js`

Hooks: `setup`, `refresh`, `supplier`

| Feature | Implementation |
|---|---|
| Supplier info banner (rating, category, count) | `frm.dashboard.set_headline_alert()` with 300ms `setTimeout` to fire after ERPNext's own refresh wipes the banner |
| Blacklist banner | Red `set_headline_alert` + `frm.disable_save()` |
| "View Vendor Rating History" button | `frappe.ui.Dialog` with `fieldtype: HTML` — renders table manually. **Not** `fieldtype: Table` (requires child DocType) |
| "Rate This Supplier" button | Dialog with `fieldtype: Rating` (returns 0–1, multiplied by 5 before API call). Visible only after submit (`docstatus === 1`) |

### `public/js/purchase_order_list.js`

Hooks: `frappe.listview_settings["Purchase Order"]`

| Feature | Implementation |
|---|---|
| Extra list columns | `add_fields: ["supplier_name", "grand_total", "per_received", "status"]` |
| Overdue indicator | Custom `get_indicator()` — red "Overdue" badge if `schedule_date < today` and `per_received < 100` |
| `per_received` formatter | Color-coded: green ≥ 100%, orange > 0%, grey = 0 |
| Quick Rate action | `listview.page.add_action_item()` — bulk rate from list selection |

### `public/js/supplier.js`

Hooks: `refresh`

| Feature | Implementation |
|---|---|
| Vendor stats dashboard | `frappe.call` to `get_vendor_dashboard` → rendered as stat cards via `frm.dashboard.add_section()` |
| Blacklist / Remove Blacklist buttons | `frappe.prompt` for reason → `frm.set_value` + `frm.save()` |
| Low rating warning | `frm.set_intro()` in orange if rating < `low_rating_threshold` |
| View Onboarding button | `frappe.set_route` to linked Vendor Onboarding |

### `public/js/vendor_onboarding.js`

Hooks: `refresh`, `vendor_category`, `gst_number`

| Feature | Implementation |
|---|---|
| Approve / Reject buttons | Visible to Purchase Manager only when `onboarding_status === "Under Review"`. Calls whitelisted server methods |
| Document progress bar | `frm.dashboard.add_progress()` showing verified/total documents |
| GST client-side validation | Regex check on field change (UX only — server also validates) |
| Category threshold info | `frappe.show_alert` showing minimum threshold when category is selected |

### `public/js/purchase_invoice.js`

Hooks: `refresh`

| Feature | Implementation |
|---|---|
| Low rating notice | Orange `set_headline_alert` if supplier rating < 3. Informational only — does not block |

---

## Web Portal Pages

Public-facing pages with no Frappe desk login required.

### `/vendor-register`

**Files:** `www/vendor-register.html`, `www/vendor_register.py`

Renders a multi-section form (Basic Info, Address, Bank Details). On submit, calls `submit_vendor_registration` and shows the reference number. Loads active Vendor Categories dynamically via public REST API.

**Note:** CSRF token is passed as `X-Frappe-CSRF-Token` header.

### `/vendor-status`

**Files:** `www/vendor-status.html`, `www/vendor_status.py`

Accepts reference number (e.g. `VOB-2026-00001`) or registered email. Returns current status, rejection reason if applicable, and Supplier ID if approved.

---

## Script Reports

### Vendor Performance Report

**Ref DocType:** Supplier  
**Filters:** Supplier, Vendor Category, From Date, To Date, Minimum Rating

Shows per-supplier stats: total POs and value, average scores by rating type, overall rating, receipt count, on-time delivery %, and short delivery count. Includes a bar chart of top 10 suppliers by overall rating.

**Access:** Awesome Bar → Vendor Performance Report

### Purchase Analysis by Vendor Category

**Ref DocType:** Vendor Category  
**Filters:** Vendor Category, From Date, To Date

Shows per-category aggregates: supplier count, PO value and average, items purchased, average rating, and lowest-rated supplier. Includes a pie chart of PO value distribution by category.

**Access:** Awesome Bar → Purchase Analysis by Vendor Category

---

## Print Format

**Name:** Vendor Portal Purchase Order  
**DocType:** Purchase Order

A custom HTML print format that renders:
- Company header and PO metadata
- **Vendor Information box** — category, star rating (rendered via `rating_to_stars` Jinja filter), total ratings count
- **Low rating caution note** — shown if supplier rating < 3
- Standard items table with amounts
- Totals section
- Terms and conditions

**Jinja filter used:** `{{ supplier.custom_vendor_rating | rating_to_stars }}`  
**Registered in hooks.py:**
```python
jinja = {
    "filters": ["vendor_portal.utils.jinja_filters.rating_to_stars"]
}
```

---

## Data Patches

Registered in `patches.txt`. Run automatically on `bench migrate`.

### `v1_0/populate_vendor_category_on_suppliers`

Maps existing Suppliers to Vendor Categories based on their `supplier_group`. Unmapped suppliers are logged to the Error Log for manual review. Customize the `group_to_category` dict in the patch file to match your data.

### `v1_0/recalculate_vendor_ratings`

Recalculates `custom_vendor_rating` and `custom_total_rating_count` for all suppliers that have Vendor Rating Log entries, using the weighted formula from Vendor Portal Settings. Run this after changing rating weights.

### `v1_0/migrate_supplier_notes_to_rating_logs`

Scans existing `Comment` records on Supplier documents. If a comment contains rating keywords (e.g. "excellent", "late delivery", "poor"), it creates a Communication-type Vendor Rating Log entry with an estimated score. Useful for seeding historical ratings from freeform notes.

**To run a specific patch manually:**
```bash
bench --site vendor.localhost execute vendor_portal.patches.v1_0.recalculate_vendor_ratings
```

---

## Permissions & Roles

### Roles

| Role | Purpose |
|---|---|
| `Vendor Manager` | Full access to all Vendor Portal DocTypes. Can approve/reject onboardings, blacklist suppliers, view all ratings. Receives alert emails |
| `Purchase Team` | Can create and submit Vendor Onboardings. Can read ratings. Cannot approve, reject, or blacklist |

### DocType Permissions

| DocType | Vendor Manager | Purchase Team | Purchase User | Purchase Manager |
|---|---|---|---|---|
| Vendor Category | RWCDA | R | R | R |
| Vendor Onboarding | RWCDSCA | RWCS | S | — |
| Vendor Rating Log | RWCDA | RWC | — | — |
| Vendor Portal Settings | RW | R | — | R |

R=Read, W=Write, C=Create, D=Delete, S=Submit, A=Amend, CA=Cancel+Amend

### Custom Permission Hooks

**`has_permission` (Vendor Rating Log):**  
Non-Vendor-Manager users can only write/delete their own rating entries (`rated_by == current_user`). Read access is open to all users with DocType permission.

**`permission_query_conditions` (Vendor Onboarding):**  
Vendor Managers see all onboarding records. Purchase Team users see only records they submitted (`owner == current_user`).

---

## Running Tests

Tests are in `vendor_portal/tests/test_vendor_portal.py`.

### Run all tests

```bash
bench --site vendor.localhost run-tests --app vendor_portal
```

### Run a specific test class

```bash
bench --site vendor.localhost run-tests \
  --app vendor_portal \
  --module vendor_portal.tests.test_vendor_portal \
  --test TestVendorOnboardingValidation
```

### Test classes

| Class | Tests |
|---|---|
| `TestVendorOnboardingValidation` | GST format validation, PAN format validation, duplicate GST blocking, minimum documents enforcement |
| `TestPurchaseOrderOverride` | Blacklisted supplier blocks PO, low rating blocks PO, submit creates Pricing rating, cancel deletes ratings |
| `TestVendorRatingAPI` | Rating recalculation, supplier comparison API, dashboard API, onboarding summary API |
| `TestPermissions` | Own-rating-only write enforcement for non-manager users |

### Prerequisites for tests

Tests create real documents in the database (using the test site). Ensure:
- A default company exists
- At least one Warehouse is configured
- `Vendor Portal Settings` is saved with default values

Clean up after testing:
```bash
bench --site vendor.localhost run-tests --app vendor_portal --force
```

---

## Assumptions

1. **One active PO per Purchase Receipt** — the delivery scoring logic reads `schedule_date` from the first linked PO found in `items`. Multi-PO receipts will score based on the first PO's date only.

2. **Rating weights sum to 1.0** — the weighted average formula assumes the four weights in Vendor Portal Settings add up to exactly 1.0. There is no runtime validation of this.

3. **`schedule_date` as delivery date** — the system uses the PO-level `schedule_date` field for delivery date comparison, not per-item schedule dates. If your workflow uses item-level dates, modify `_is_late()` in `purchase_receipt.py`.

4. **Email delivery** — scheduled jobs send email alerts. These silently no-op if the site's email settings are not configured.

5. **Single company** — the app is designed for a single-company ERPNext setup. Multi-company scenarios (cross-company POs, inter-company transactions) are not tested.

6. **ERPNext v16 field names** — `accepted_qty` in Purchase Receipt Item is stored as `qty` in ERPNext v16. If you upgrade to a version that renames this field, `purchase_receipt.py` will need updating.

7. **GST validation is India-specific** — the GST format regex (`^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$`) only validates Indian GST numbers. Set `require_gst_verification = 0` in settings for non-India deployments.

---

## Limitations

1. **No real-time rating sync** — `custom_vendor_rating` on Supplier is recalculated in the background (daily job or on each API call). There is a window where the displayed rating is stale if many logs are created in quick succession.

2. **Bulk import has no progress indicator** — `bulk_import_vendors` enqueues a background job and returns immediately. The only feedback is an email on completion. There is no in-desk progress bar.

3. **Print format star display** — stars are rendered as Unicode characters (★ ½ ☆). PDF rendering quality depends on the font available in the PDF engine (wkhtmltopdf). In some environments, ½ may render as a replacement character.

4. **Vendor Dashboard charts require Frappe Charts** — the `vendor-dashboard` page uses `frappe.Chart`. This library is bundled with Frappe but requires desk access — it is not available on public web pages.

5. **`doc_events` comment deduplication** — the short delivery comment is deduplicated by exact content match. If the same item ships short twice with the same quantities, the second comment will not be added.

6. **No two-factor approval** — the workflow has a single Purchase Manager approver. There is no dual-approval or committee-approval mechanism.

7. **Patch `migrate_supplier_notes_to_rating_logs` is lossy** — keyword matching is approximate. Comments with no recognized keywords are silently skipped. The patch should be reviewed and customized before running on a production site.

8. **Web portal CSRF** — the vendor registration page reads `frappe.csrf_token` from the global JS context. If Frappe changes how CSRF tokens are exposed on guest pages, the form submission will break.

---